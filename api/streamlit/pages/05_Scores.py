# api/streamlit/pages/05_Scores.py

# --- BOOTSTRAP ---
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

# --- Imports projet ---
from config import DATA_PROCESSED, MODELS

# --- Imports Streamlit ---
import streamlit as st
import json
import pandas as pd
import numpy as np

# --- Carte ---
import pydeck as pdk

st.set_page_config(page_title="Scores", layout="wide")
st.title("🔥 Carte des scores de risque par commune")

# Charger latest_run
latest_path = DATA_PROCESSED / "latest_run.json"
with open(latest_path) as f:
    latest = json.load(f)

run_dir = Path(latest["run_dir"])
model_run_dir = MODELS / "run" / run_dir.name

# Charger scores
scores_path = model_run_dir / "scores_risque.csv"
features_risque_path = model_run_dir / "features_risque.csv"

if not scores_path.exists():
    st.error("scores_risque.csv introuvable.")
    st.stop()

scores = pd.read_csv(scores_path)

# Vérification des colonnes nécessaires
required_cols = [
    "code_insee",
    "latitude",
    "longitude",
    "proba_incendie_suivant",
    "cluster_risque",
    "cluster_spatial",
]

missing = [c for c in required_cols if c not in scores.columns]
if missing:
    st.error(f"Colonnes manquantes dans scores_risque.csv : {missing}")
    st.stop()

# Filtre département
st.sidebar.subheader("Filtres")
departements = sorted(scores["code_insee"].astype(str).str[:2].unique())
selected_dep = st.sidebar.selectbox("Département", ["Tous"] + departements)

df = scores.copy()

if selected_dep != "Tous":
    df = df[df["code_insee"].astype(str).str.startswith(selected_dep)]

# Filtre cluster_risque
clusters_risque = sorted(df["cluster_risque"].unique())
selected_cluster_risque = st.sidebar.selectbox(
    "Cluster risque", ["Tous"] + clusters_risque
)

if selected_cluster_risque != "Tous":
    df = df[df["cluster_risque"] == selected_cluster_risque]

# Filtre cluster_spatial
clusters_spatial = sorted(df["cluster_spatial"].unique())
selected_cluster_spatial = st.sidebar.selectbox(
    "Cluster spatial", ["Tous"] + clusters_spatial
)

if selected_cluster_spatial != "Tous":
    df = df[df["cluster_spatial"] == selected_cluster_spatial]

# Déciles de risque
df["decile_risque"] = pd.qcut(
    df["proba_incendie_suivant"], 10, labels=False, duplicates="drop"
)
selected_decile = st.sidebar.selectbox(
    "Décile de risque", ["Tous"] + list(range(df["decile_risque"].max() + 1))
)

if selected_decile != "Tous":
    df = df[df["decile_risque"] == selected_decile]

st.subheader(f"Communes affichées : {len(df)}")

# Carte PyDeck
if len(df) == 0:
    st.warning("Aucune commune à afficher avec ces filtres.")
    st.stop()

# Couleur = probabilité (rouge = fort risque)
df["color"] = df["proba_incendie_suivant"].apply(lambda p: [int(255 * p), 50, 50])

# Taille = nombre de feux historiques si dispo
if "nb_feux_5a" in df.columns:
    df["radius"] = df["nb_feux_5a"].fillna(0) * 200 + 300
else:
    df["radius"] = 300

# Centre de la carte
center_lat = df["latitude"].mean()
center_lon = df["longitude"].mean()

layer = pdk.Layer(
    "ScatterplotLayer",
    data=df,
    get_position=["longitude", "latitude"],
    get_fill_color="color",
    get_radius="radius",
    pickable=True,
    opacity=0.6,
)

tooltip = {
    "html": """
    <b>Commune :</b> {code_insee}<br/>
    <b>Probabilité :</b> {proba_incendie_suivant}<br/>
    <b>Cluster risque :</b> {cluster_risque}<br/>
    <b>Cluster spatial :</b> {cluster_spatial}<br/>
    <b>Décile :</b> {decile_risque}<br/>
    """,
    "style": {"color": "white"},
}

view_state = pdk.ViewState(
    latitude=center_lat,
    longitude=center_lon,
    zoom=7,
    pitch=45,
)

st.pydeck_chart(
    pdk.Deck(
        layers=[layer],
        initial_view_state=view_state,
        tooltip=tooltip,
    )
)

# Tableau des top communes
st.subheader("Top communes à risque")
top = df.sort_values("proba_incendie_suivant", ascending=False).head(50)
st.dataframe(top)
