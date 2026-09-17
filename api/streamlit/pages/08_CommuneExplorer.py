# api/streamlit/pages/08_CommuneExplorer.py

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import streamlit as st
import pandas as pd
import numpy as np
import json
import joblib
import shap
import pydeck as pdk
import matplotlib.pyplot as plt

from sklearn.preprocessing import StandardScaler
from sklearn.neighbors import NearestNeighbors

from config import DATA_PROCESSED, MODELS

st.set_page_config(page_title="Commune Explorer", layout="wide")
st.title("🏘️ Commune Explorer")

# Charger latest_run
with open(DATA_PROCESSED / "latest_run.json") as f:
    latest = json.load(f)

run_dir = Path(latest["run_dir"])
model_run_dir = MODELS / "run" / run_dir.name

# Charger features + scores
df_features = pd.read_csv(model_run_dir / "features_risque.csv")
df_scores = pd.read_csv(model_run_dir / "scores_risque.csv")

df = df_features.merge(df_scores, on="code_insee", how="left")

# Charger modèle brut pour SHAP local
model_raw = joblib.load(model_run_dir / "model_risque_raw.joblib")
explainer = shap.TreeExplainer(model_raw)

# Charger les features du modèle
feature_cols = json.loads((model_run_dir / "shap_feature_names.json").read_text())


# Charger les données historiques des feux
def load_bdiff():
    raw_dir = Path("data/raw")
    files = sorted(raw_dir.glob("bdiff_*.csv"))
    dfs = []
    for f in files:
        df = pd.read_csv(f, sep=";", low_memory=False)
        df.columns = [c.strip().replace('"', "") for c in df.columns]
        dfs.append(df)
    return pd.concat(dfs, ignore_index=True)


df_bdiff = load_bdiff()

# Nettoyage minimal
df_bdiff["Code INSEE"] = df_bdiff["Code INSEE"].astype(str)
df_bdiff["Année"] = df_bdiff["Année"].astype(int)

# Sélecteur de commune
communes = df["code_insee"].astype(str).tolist()
selected_commune = st.selectbox("Choisir une commune", communes)

row = df[df["code_insee"].astype(str) == selected_commune].iloc[0]

st.header(f"🏘️ Commune : {selected_commune}")

# --- SCORE DE RISQUE ---
st.subheader("🔥 Score de risque")
col1, col2 = st.columns(2)

with col1:
    st.metric(
        "Probabilité d'incendie l'année suivante",
        f"{row['proba_incendie_suivant']:.3f}",
    )

with col2:
    dep = row["code_insee"][:2]
    df_dep = df[df["code_insee"].astype(str).str.startswith(dep)]
    rank_dep = (
        df_dep["proba_incendie_suivant"] > row["proba_incendie_suivant"]
    ).sum() + 1
    st.metric("Rang départemental", f"{rank_dep} / {len(df_dep)}")

# --- HISTORIQUE DES FEUX ---
st.header("🔥 Historique des feux")

df_hist = df_bdiff[df_bdiff["Code INSEE"] == selected_commune]

if len(df_hist) == 0:
    st.info("Aucun feu historique pour cette commune.")
else:
    df_hist_year = (
        df_hist.groupby("Année")["Surface parcourue (m2)"].sum().reset_index()
    )

    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(df_hist_year["Année"], df_hist_year["Surface parcourue (m2)"], marker="o")
    ax.set_title("Surface brûlée par année")
    ax.set_ylabel("Surface (m2)")
    st.pyplot(fig)
    plt.close(fig)

    # Timeline interactive
    st.subheader("📅 Timeline des feux")
    min_year = int(df_hist["Année"].min())
    max_year = int(df_hist["Année"].max())

    year_range = st.slider("Plage d'années", min_year, max_year, (min_year, max_year))

    df_hist_range = df_hist[
        (df_hist["Année"] >= year_range[0]) & (df_hist["Année"] <= year_range[1])
    ]

    df_hist_year_range = (
        df_hist_range.groupby("Année")["Surface parcourue (m2)"].sum().reset_index()
    )

    fig, ax = plt.subplots(figsize=(10, 4))
    ax.bar(df_hist_year_range["Année"], df_hist_year_range["Surface parcourue (m2)"])
    ax.set_title("Surface brûlée par année (plage sélectionnée)")
    ax.set_ylabel("Surface (m2)")
    st.pyplot(fig)
    plt.close(fig)

# --- CARTE PYDECK ---
st.header("🗺️ Carte des feux")

if (
    len(df_hist) > 0
    and "Latitude" in df_hist.columns
    and "Longitude" in df_hist.columns
):
    df_hist_map = df_hist.copy()
    df_hist_map["lat"] = df_hist_map["Latitude"].astype(float)
    df_hist_map["lon"] = df_hist_map["Longitude"].astype(float)

    midpoint = (df_hist_map["lat"].mean(), df_hist_map["lon"].mean())

    layer = pdk.Layer(
        "ScatterplotLayer",
        df_hist_map,
        get_position=["lon", "lat"],
        get_radius=50,
        get_fill_color=[255, 0, 0, 140],
        pickable=True,
    )

    view_state = pdk.ViewState(
        latitude=midpoint[0],
        longitude=midpoint[1],
        zoom=11,
        pitch=45,
    )

    st.pydeck_chart(pdk.Deck(layers=[layer], initial_view_state=view_state))

st.info(f"""
### ℹ️ Explication SHAP pour la commune {selected_commune}

Le SHAP local explique **pourquoi** le modèle prédit un risque particulier pour cette commune.

- Les valeurs **positives** poussent la prédiction vers un risque plus élevé.
- Les valeurs **négatives** poussent la prédiction vers un risque plus faible.
- Le graphique *waterfall* montre l'effet de chaque feature sur la prédiction finale.

Le SHAP cluster permet de comprendre les **caractéristiques communes** aux communes du même cluster de risque.
""")


# --- SHAP LOCAL ---
st.header("🧠 SHAP — Explication locale")

row_X = row[feature_cols]
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
# --- INTERPRÉTATION AUTOMATIQUE SHAP LOCAL ---
st.header("🧾 Interprétation automatique du risque")

# Trier les contributions
local_sorted = local_df.sort_values("shap_value", ascending=False)

# Top facteurs augmentant le risque
top_pos = local_sorted[local_sorted["shap_value"] > 0].head(3)

# Top facteurs diminuant le risque
top_neg = local_sorted[local_sorted["shap_value"] < 0].tail(3)

# Génération du texte
interpretation = ""

interpretation += f"La commune **{selected_commune}** présente un risque "
interpretation += (
    "élevé"
    if row["proba_incendie_suivant"] > 0.5
    else "modéré" if row["proba_incendie_suivant"] > 0.2 else "faible"
)
interpretation += " d'incendie selon le modèle.\n\n"

if len(top_pos) > 0:
    interpretation += "### 🔺 Facteurs qui augmentent le risque :\n"
    for _, r in top_pos.iterrows():
        interpretation += (
            f"- **{r['feature']}** : contribution de +{r['shap_value']:.3f}\n"
        )
else:
    interpretation += "Aucun facteur majeur n'augmente le risque.\n"

interpretation += "\n"

if len(top_neg) > 0:
    interpretation += "### 🔻 Facteurs qui diminuent le risque :\n"
    for _, r in top_neg.iterrows():
        interpretation += (
            f"- **{r['feature']}** : contribution de {r['shap_value']:.3f}\n"
        )
else:
    interpretation += "Aucun facteur majeur ne diminue le risque.\n"

st.markdown(interpretation)
# --- RISQUE EXPLIQUÉ (phrase synthétique) ---
st.header("🗣️ Risque expliqué (résumé synthétique)")


def synthese_risque(row, top_pos, top_neg):
    phrase = ""

    # Niveau de risque
    p = row["proba_incendie_suivant"]
    if p > 0.7:
        phrase += "La commune présente un **risque très élevé** d'incendie. "
    elif p > 0.4:
        phrase += "La commune présente un **risque élevé** d'incendie. "
    elif p > 0.2:
        phrase += "La commune présente un **risque modéré** d'incendie. "
    else:
        phrase += "La commune présente un **risque faible** d'incendie. "

    # Facteurs principaux
    if len(top_pos) > 0:
        phrase += "Ce risque est principalement dû à "
        phrase += ", ".join([f"**{r['feature']}**" for _, r in top_pos.iterrows()])
        phrase += ". "

    if len(top_neg) > 0:
        phrase += "Certains facteurs réduisent toutefois ce risque, notamment "
        phrase += ", ".join([f"**{r['feature']}**" for _, r in top_neg.iterrows()])
        phrase += ". "

    return phrase


st.markdown(synthese_risque(row, top_pos, top_neg))

# --- SHAP CLUSTER ---
st.header("🧩 SHAP — Explication du cluster")

if "cluster_risque" in df.columns:
    cluster = row["cluster_risque"]
    st.write(f"Cluster sélectionné : **{cluster}**")

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

# --- SHAP INTERACTIONS CLUSTER ---
st.header("🧠 SHAP — Interactions dans le cluster")

if "cluster_risque" in df.columns:
    cluster = row["cluster_risque"]
    df_cluster = df[df["cluster_risque"] == cluster]
    X_cluster = df_cluster[feature_cols]

    shap_inter_cluster = shap.TreeExplainer(model_raw).shap_interaction_values(
        X_cluster
    )

    feature_i = st.selectbox("Feature 1 (cluster)", feature_cols, index=0)
    feature_j = st.selectbox("Feature 2 (cluster)", feature_cols, index=1)

    i_idx = feature_cols.index(feature_i)
    j_idx = feature_cols.index(feature_j)

    fig, ax = plt.subplots(figsize=(10, 6))
    shap.dependence_plot(
        (i_idx, j_idx),
        shap_inter_cluster,
        X_cluster,
        feature_names=feature_cols,
        show=False,
    )
    st.pyplot(fig)
    plt.close(fig)


# --- SURFACES BRÛLÉES PAR TYPE ---
st.header("🌲 Détails des surfaces brûlées")

if len(df_hist) > 0:
    cols_surfaces = [
        "Surface forêt (m2)",
        "Surface maquis garrigues (m2)",
        "Autres surfaces naturelles hors forêt (m2)",
        "Surfaces agricoles (m2)",
        "Autres surfaces (m2)",
        "Surface autres terres boisées (m2)",
        "Surfaces non boisées naturelles (m2)",
        "Surfaces non boisées artificialisées (m2)",
    ]

    df_surf = df_hist[cols_surfaces].sum().reset_index()
    df_surf.columns = ["Type", "Surface (m2)"]

    st.dataframe(df_surf)

# --- DÉGÂTS ---
st.header("🏚️ Dégâts humains et matériels")

if len(df_hist) > 0:
    nb_deces = df_hist["Nombre de décès"].sum()
    nb_detruits = df_hist["Nombre de bâtiments totalement détruits"].sum()
    nb_partiels = df_hist["Nombre de bâtiments partiellement détruits"].sum()

    st.metric("Décès", nb_deces)
    st.metric("Bâtiments détruits", nb_detruits)
    st.metric("Bâtiments partiellement détruits", nb_partiels)

# --- COMMUNES SIMILAIRES (KNN) ---
st.header("🧭 Communes similaires")

X_all = df[feature_cols].copy()
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X_all)

idx = df.index[df["code_insee"].astype(str) == selected_commune][0]
x_selected = X_scaled[idx].reshape(1, -1)

knn = NearestNeighbors(n_neighbors=6, metric="euclidean")
knn.fit(X_scaled)
distances, indices = knn.kneighbors(x_selected)

similar_indices = indices[0][1:]
df_similar = df.iloc[similar_indices][
    ["code_insee", "nom", "proba_incendie_suivant", "cluster_risque"]
]

st.dataframe(df_similar)

# --- COMPARAISON ENTRE COMMUNES ---
st.header("⚖️ Comparaison avec une autre commune")

other_commune = st.selectbox(
    "Choisir une commune à comparer",
    [c for c in communes if c != selected_commune],
)

row_other = df[df["code_insee"].astype(str) == other_commune].iloc[0]

col1, col2 = st.columns(2)

with col1:
    st.subheader(f"Commune {selected_commune}")
    st.metric("Proba incendie", f"{row['proba_incendie_suivant']:.3f}")
    st.metric("Nb feux", int(row["nb_feux"]))
    st.metric("Surface brûlée (ha)", float(row["surface_ha"]))

with col2:
    st.subheader(f"Commune {other_commune}")
    st.metric("Proba incendie", f"{row_other['proba_incendie_suivant']:.3f}")
    st.metric("Nb feux", int(row_other["nb_feux"]))
    st.metric("Surface brûlée (ha)", float(row_other["surface_ha"]))
