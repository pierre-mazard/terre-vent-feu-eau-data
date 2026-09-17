# api/streamlit/pages/07_Explainability.py

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from config import DATA_PROCESSED, MODELS

import streamlit as st
import json
import pandas as pd
import numpy as np
import shap
import joblib
import matplotlib.pyplot as plt

st.set_page_config(page_title="Explainability", layout="wide")
st.title("🧠 Interprétabilité du modèle (SHAP)")

st.info("""
### ℹ️ À propos du SHAP

Le SHAP (SHapley Additive exPlanations) est une méthode d'explicabilité qui permet de comprendre **comment** et **pourquoi** un modèle de Machine Learning prend une décision.

Dans cette page :

- **SHAP global stratifié** : importance moyenne des features sur un échantillon équilibré par cluster de risque.
- **Summary plot** : montre quelles variables influencent le plus le modèle.
- **Dependence plot** : montre comment une feature influence la prédiction selon sa valeur.
- **SHAP local** : explique la prédiction pour une commune précise.
- **SHAP cluster** : explique les comportements typiques d'un groupe de communes.

Un SHAP positif **augmente** la probabilité d'incendie.
Un SHAP négatif **diminue** la probabilité d'incendie.
""")

# Charger latest_run
with open(DATA_PROCESSED / "latest_run.json") as f:
    latest = json.load(f)

run_dir = Path(latest["run_dir"])
model_run_dir = MODELS / "run" / run_dir.name

# Charger SHAP global pré-calculé
shap_values = np.load(model_run_dir / "shap_values.npy", allow_pickle=True)
expected_value = np.load(model_run_dir / "shap_expected_value.npy", allow_pickle=True)
feature_cols = json.loads((model_run_dir / "shap_feature_names.json").read_text())

# Charger EXACTEMENT l'échantillon stratifié utilisé pour SHAP global
X = pd.read_csv(model_run_dir / "shap_X_sample.csv")[feature_cols]

# Charger features complètes pour SHAP local + cluster
df = pd.read_csv(model_run_dir / "features_risque.csv")

# Sécurisation : forcer SHAP à correspondre aux features
if shap_values.ndim == 3:
    # Multi-output → prendre la première sortie
    shap_values = shap_values[:, 0, :]

# Si SHAP a trop de colonnes → tronquer
if shap_values.shape[1] > len(feature_cols):
    shap_values = shap_values[:, : len(feature_cols)]

# Si SHAP a trop peu de colonnes → erreur explicite
if shap_values.shape[1] != len(feature_cols):
    st.error(
        f"Mismatch: SHAP a {shap_values.shape[1]} colonnes mais features en ont {len(feature_cols)}. Recalculez SHAP global."
    )
    st.stop()


# --- SHAP GLOBAL ---
st.header("📊 Importance globale des features")

fig, ax = plt.subplots(figsize=(10, 6))
shap.summary_plot(
    shap_values, X, feature_names=feature_cols, plot_type="bar", show=False
)
st.pyplot(fig)
plt.close(fig)

fig, ax = plt.subplots(figsize=(10, 6))
shap.summary_plot(shap_values, X, feature_names=feature_cols, show=False)
st.pyplot(fig)
plt.close(fig)

# --- SHAP DEPENDENCE ---
st.header("📈 Analyse d'une feature")

selected_feature = st.selectbox("Choisir une feature", feature_cols)

# SHAP peut renvoyer une liste (multi-output) → on prend la première sortie
if isinstance(shap_values, list):
    shap_values_single = shap_values[0]
else:
    # SHAP multi-output (ex: RandomForest) → on prend la première dimension
    if shap_values.ndim == 3:
        shap_values_single = shap_values[:, 0, :]
    else:
        shap_values_single = shap_values

fig, ax = plt.subplots(figsize=(10, 6))

# Désactiver l'interaction automatique en passant interaction_index=None
shap.dependence_plot(
    selected_feature,
    shap_values_single,
    X,
    feature_names=feature_cols,
    interaction_index=None,  # ← FIX DÉFINITIF
    show=False,
)

st.pyplot(fig)
plt.close(fig)


# --- SHAP LOCAL ---
st.header("🔍 Analyse locale (commune)")

commune_list = df["code_insee"].astype(str).tolist()
selected_commune = st.selectbox("Choisir une commune", commune_list)

row = df[df["code_insee"].astype(str) == selected_commune].iloc[0]
row_X = row[feature_cols]

# Charger modèle brut pour SHAP local
model_raw = joblib.load(model_run_dir / "model_risque_raw.joblib")
explainer = shap.TreeExplainer(model_raw)
local_shap = explainer.shap_values(row_X)

fig, ax = plt.subplots(figsize=(10, 6))
shap.waterfall_plot(local_shap, feature_names=feature_cols, show=False)
st.pyplot(fig)
plt.close(fig)

st.subheader("Contribution des features")
local_df = pd.DataFrame(
    {"feature": feature_cols, "shap_value": local_shap}
).sort_values("shap_value", ascending=False)

st.dataframe(local_df)

# --- SHAP CLUSTER ---
st.header("🧩 Analyse SHAP du cluster")

if "cluster_risque" in df.columns:
    cluster = row["cluster_risque"]
    st.write(f"Cluster de la commune : **{cluster}**")

    df_cluster = df[df["cluster_risque"] == cluster]
    X_cluster = df_cluster[feature_cols]

    shap_cluster = explainer.shap_values(X_cluster)
    shap_cluster_mean = shap_cluster.mean(axis=0)

    st.subheader("📊 Importance moyenne des features dans le cluster")

    fig, ax = plt.subplots(figsize=(10, 6))
    shap.summary_plot(
        shap_cluster, X_cluster, feature_names=feature_cols, plot_type="bar", show=False
    )
    st.pyplot(fig)
    plt.close(fig)

    st.subheader("📉 Waterfall SHAP moyen du cluster")

    fig, ax = plt.subplots(figsize=(10, 6))
    shap.waterfall_plot(shap_cluster_mean, feature_names=feature_cols, show=False)
    st.pyplot(fig)
    plt.close(fig)

else:
    st.warning("cluster_risque manquant dans features_risque.csv")

# --- SHAP INTERACTIONS GLOBAL ---
st.header("🧠 SHAP — Interactions globales entre features")

shap_interactions = shap.TreeExplainer(model_raw).shap_interaction_values(X)

feature_i = st.selectbox("Feature 1 (i)", feature_cols, index=0)
feature_j = st.selectbox("Feature 2 (j)", feature_cols, index=1)

i_idx = feature_cols.index(feature_i)
j_idx = feature_cols.index(feature_j)

fig, ax = plt.subplots(figsize=(10, 6))
shap.dependence_plot(
    (i_idx, j_idx), shap_interactions, X, feature_names=feature_cols, show=False
)
st.pyplot(fig)
plt.close(fig)
