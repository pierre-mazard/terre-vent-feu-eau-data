# api/streamlit/pages/09_Dashboard.py

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import streamlit as st
import pandas as pd
import json
import numpy as np
import pydeck as pdk
import shap
import joblib
import matplotlib.pyplot as plt

from config import DATA_PROCESSED, MODELS

st.set_page_config(page_title="Dashboard global", layout="wide")
st.title("📊 Dashboard global du risque incendie")

# Charger latest_run
with open(DATA_PROCESSED / "latest_run.json") as f:
    latest = json.load(f)

run_dir = Path(latest["run_dir"])
model_run_dir = MODELS / "run" / run_dir.name

# Charger données
df_scores = pd.read_csv(model_run_dir / "scores_risque.csv")
df_features = pd.read_csv(model_run_dir / "features_risque.csv")
df_all = df_features.merge(df_scores, on="code_insee", how="left")

# Charger SHAP global
shap_values = np.load(model_run_dir / "shap_values.npy", allow_pickle=True)
feature_cols = json.loads((model_run_dir / "shap_feature_names.json").read_text())

# Charger modèle brut pour SHAP local/département
model_raw = joblib.load(model_run_dir / "model_risque_raw.joblib")
explainer = shap.TreeExplainer(model_raw)

# -----------------------------
# 🗺️ CARTE DÉPARTEMENTALE
# -----------------------------
st.header("🗺️ Carte départementale des risques")

dep = st.text_input("Code département (2 chiffres)", "13")

df_dep = df_all[df_all["code_insee"].astype(str).str.startswith(dep)]

if len(df_dep) == 0:
    st.warning("Aucune commune trouvée dans ce département.")
else:
    layer = pdk.Layer(
        "ScatterplotLayer",
        df_dep,
        get_position=["longitude", "latitude"],
        get_radius=2000,
        get_fill_color="[proba_incendie_suivant * 255, 50, 150, 160]",
        pickable=True,
    )

    view_state = pdk.ViewState(
        latitude=df_dep["latitude"].mean(),
        longitude=df_dep["longitude"].mean(),
        zoom=8,
        pitch=45,
    )

    st.pydeck_chart(pdk.Deck(layers=[layer], initial_view_state=view_state))

# -----------------------------
# 📈 STATISTIQUES GLOBALES
# -----------------------------
st.header("📈 Statistiques globales")

col1, col2, col3 = st.columns(3)

with col1:
    st.metric("Nb communes", len(df_all))

with col2:
    st.metric("Proba moyenne", f"{df_all['proba_incendie_suivant'].mean():.3f}")

with col3:
    st.metric("Nb feux total", int(df_all["nb_feux"].sum()))

# -----------------------------
# 🔥 TOP 20 COMMUNES À RISQUE
# -----------------------------
st.subheader("🔥 Top 20 communes à risque")

df_top = df_all.sort_values("proba_incendie_suivant", ascending=False).head(20)
st.dataframe(
    df_top[
        [
            "code_insee",
            "nom",
            "proba_incendie_suivant",
            "nb_feux",
            "surface_ha",
            "cluster_risque",
        ]
    ]
)

# -----------------------------
# 🧠 SHAP — RANKING DÉPARTEMENTAL
# -----------------------------
st.header("🧠 SHAP — Importance des features dans le département")

if len(df_dep) > 0:

    X_dep = df_dep[feature_cols]
    shap_dep = explainer.shap_values(X_dep)

    # Importance moyenne absolue
    shap_mean = np.abs(shap_dep).mean(axis=0)

    df_rank = pd.DataFrame(
        {"feature": feature_cols, "importance": shap_mean}
    ).sort_values("importance", ascending=False)

    st.subheader("Top features du département")
    st.dataframe(df_rank.head(15))

    # Bar plot SHAP départemental
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.barh(df_rank["feature"].head(15), df_rank["importance"].head(15))
    ax.invert_yaxis()
    ax.set_title(f"Importance SHAP — Département {dep}")
    st.pyplot(fig)
    plt.close(fig)

else:
    st.info("Sélectionnez un département pour afficher l'analyse SHAP.")

st.info("""
### ℹ️ SHAP départemental

Cette section montre l'importance des features **uniquement pour les communes du département sélectionné**.

Cela permet de comprendre :

- quelles variables influencent le plus le risque dans ce territoire,
- si les facteurs de risque sont différents d'un département à l'autre,
- quelles interactions entre variables sont spécifiques au département.

Les valeurs SHAP sont **moyennées** sur toutes les communes du département.
""")


# --- SHAP INTERACTIONS DÉPARTEMENT ---
st.header("🧠 SHAP — Interactions des features dans le département")

if len(df_dep) > 0:
    X_dep = df_dep[feature_cols]
    shap_inter_dep = shap.TreeExplainer(model_raw).shap_interaction_values(X_dep)

    feature_i = st.selectbox("Feature 1 (département)", feature_cols, index=0)
    feature_j = st.selectbox("Feature 2 (département)", feature_cols, index=1)

    i_idx = feature_cols.index(feature_i)
    j_idx = feature_cols.index(feature_j)

    fig, ax = plt.subplots(figsize=(10, 6))
    shap.dependence_plot(
        (i_idx, j_idx), shap_inter_dep, X_dep, feature_names=feature_cols, show=False
    )
    st.pyplot(fig)
    plt.close(fig)
