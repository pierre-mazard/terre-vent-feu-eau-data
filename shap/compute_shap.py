import sys
import time
import json
import joblib
import numpy as np
import pandas as pd
import shap
from pathlib import Path

from config import DATA_PROCESSED, MODELS
from models.config_pipeline import FEATURE_COLUMNS


def log(msg):
    print(f"[SHAP] {msg}", flush=True)


def load_run_dirs():
    with open(DATA_PROCESSED / "latest_run.json") as f:
        latest = json.load(f)
    run_dir = Path(latest["run_dir"])
    model_run_dir = MODELS / "run" / run_dir.name
    return run_dir, model_run_dir


def load_model(model_run_dir):
    model_path = model_run_dir / "model_risque_raw.joblib"
    return joblib.load(model_path)


def load_features(model_run_dir):
    return pd.read_csv(model_run_dir / "features_risque.csv")


def build_stratified_sample(df):
    clusters = sorted(df["cluster_risque"].unique())
    n_per_cluster = 150
    sample_list = []

    for c in clusters:
        df_c = df[df["cluster_risque"] == c]
        n = min(n_per_cluster, len(df_c))
        log(f" - Cluster {c}: {n} lignes")
        sample_list.append(df_c.sample(n=n, random_state=42))

    sample = pd.concat(sample_list, ignore_index=True)
    X = sample[FEATURE_COLUMNS]
    return sample, X


def compute_shap_values(model, X):
    explainer = shap.TreeExplainer(model)
    raw_shap = explainer.shap_values(X)

    # Multi-output → prendre la classe positive (1)
    if isinstance(raw_shap, list):
        shap_values = raw_shap[1]
    elif raw_shap.ndim == 3:
        shap_values = raw_shap[:, 1, :]
    else:
        shap_values = raw_shap

    return explainer, shap_values


def check_shap_consistency(shap_values):
    if shap_values.shape[1] != len(FEATURE_COLUMNS):
        msg = (
            f"SHAP invalide: {shap_values.shape[1]} colonnes "
            f"mais {len(FEATURE_COLUMNS)} features."
        )
        raise ValueError(msg)


def save_shap(model_run_dir, shap_values, expected_value):
    np.save(model_run_dir / "shap_values.npy", shap_values)
    np.save(model_run_dir / "shap_expected_value.npy", expected_value)

    feature_file = model_run_dir / "shap_feature_names.json"
    feature_file.write_text(json.dumps(FEATURE_COLUMNS, indent=2))


def main():
    log("=== SHAP GLOBAL STRATIFIÉ : START ===")

    run_dir, model_run_dir = load_run_dirs()

    log("Chargement du modèle brut...")
    model = load_model(model_run_dir)

    log("Chargement des features...")
    df = load_features(model_run_dir)

    log("Construction de l'échantillon stratifié...")
    sample, X = build_stratified_sample(df)
    sample.to_csv(model_run_dir / "shap_X_sample.csv", index=False)

    log("Initialisation du TreeExplainer...")
    start_time = time.time()

    explainer, shap_values = compute_shap_values(model, X)
    log(f"SHAP mono-output (classe positive) → shape: {shap_values.shape}")

    check_shap_consistency(shap_values)

    expected_value = explainer.expected_value
    if isinstance(expected_value, (list, np.ndarray)):
        expected_value = expected_value[1]

    log("Sauvegarde des fichiers SHAP...")
    save_shap(model_run_dir, shap_values, expected_value)

    total_time = time.time() - start_time
    log(f"=== SHAP GLOBAL : DONE en {total_time:.1f} secondes ===")


if __name__ == "__main__":
    main()
