import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

import json
import joblib
import numpy as np
import pandas as pd
import shap

from config import DATA_PROCESSED, MODELS
from models.config_pipeline import FEATURE_COLUMNS


def log(msg):
    print(f"[SHAP] {msg}", flush=True)


# -----------------------------
# CHARGEMENT DES ARTEFACTS
# -----------------------------
with open(DATA_PROCESSED / "latest_run.json") as f:
    latest = json.load(f)

run_dir = Path(latest["run_dir"])
model_run_dir = MODELS / "run" / run_dir.name

log("=== SHAP GLOBAL STRATIFIÉ : START ===")

# Charger modèle brut
log("Chargement du modèle brut...")
model_raw_path = model_run_dir / "model_risque_raw.joblib"
model = joblib.load(model_raw_path)

# Charger features
log("Chargement des features...")
df = pd.read_csv(model_run_dir / "features_risque.csv")

# -----------------------------
# ÉCHANTILLON STRATIFIÉ
# -----------------------------
log("Construction de l'échantillon stratifié...")

clusters = sorted(df["cluster_risque"].unique())
N_PER_CLUSTER = 150

X_list = []
for c in clusters:
    df_c = df[df["cluster_risque"] == c]
    n = min(N_PER_CLUSTER, len(df_c))
    log(f" - Cluster {c}: {n} lignes")
    X_list.append(df_c.sample(n=n, random_state=42))

X_sample = pd.concat(X_list, ignore_index=True)
X = X_sample[FEATURE_COLUMNS]

log(f"Total échantillon stratifié : {len(X)} lignes")
log(f"Features utilisées : {len(FEATURE_COLUMNS)}")

# Sauvegarde de l'échantillon stratifié
X_sample.to_csv(model_run_dir / "shap_X_sample.csv", index=False)
log("Échantillon stratifié sauvegardé → shap_X_sample.csv")

# -----------------------------
# CALCUL SHAP
# -----------------------------
log("Initialisation du TreeExplainer...")
explainer = shap.TreeExplainer(model)
log("TreeExplainer initialisé.")

log("Début du calcul SHAP...")

start_time = time.time()

raw_shap = explainer.shap_values(X)

# -----------------------------
# FORCE MONO-OUTPUT (classe positive)
# -----------------------------
# Cas 1 : SHAP renvoie une liste → modèle binaire → prendre la classe 1
if isinstance(raw_shap, list):
    shap_values = raw_shap[1]

# Cas 2 : SHAP renvoie un tenseur (N, F, 2) → prendre la classe 1
# (versions recentes de shap : dernier axe = classes, pas le second)
elif raw_shap.ndim == 3:
    shap_values = raw_shap[:, :, 1]

# Cas 3 : SHAP mono-output → rien à faire
else:
    shap_values = raw_shap

log(f"SHAP mono-output (classe positive) → shape final: {shap_values.shape}")

# -----------------------------
# TEST DE COHÉRENCE
# -----------------------------
if shap_values.shape[1] != len(FEATURE_COLUMNS):
    raise ValueError(
        f"SHAP invalide: {shap_values.shape[1]} colonnes mais {len(FEATURE_COLUMNS)} features. "
        f"Le modèle utilisé pour SHAP n'est pas le modèle actuel."
    )

expected_value = explainer.expected_value
if isinstance(expected_value, (list, np.ndarray)):
    expected_value = expected_value[1]  # classe positive

# -----------------------------
# SAUVEGARDE
# -----------------------------
log("Sauvegarde des fichiers SHAP...")

np.save(model_run_dir / "shap_values.npy", shap_values)
np.save(model_run_dir / "shap_expected_value.npy", expected_value)

(model_run_dir / "shap_feature_names.json").write_text(
    json.dumps(FEATURE_COLUMNS, indent=2)
)

total_time = time.time() - start_time
log(f"=== SHAP GLOBAL : DONE en {total_time:.1f} secondes ===")
