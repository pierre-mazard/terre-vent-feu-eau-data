# api/streamlit/pages/05_Scores.py
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[3]
if str(RACINE) not in sys.path:
    sys.path.insert(0, str(RACINE))

import pydeck as pdk  # noqa: E402
import streamlit as st  # noqa: E402

from api.streamlit import donnees  # noqa: E402

st.set_page_config(page_title="Carte des scores", page_icon="🗺️", layout="wide")
st.title("🗺️ Carte nationale du risque")

scores = donnees.charger_scores()

st.sidebar.subheader("Filtres")
dep = st.sidebar.selectbox(
    "Departement", ["Tous"] + sorted(scores["departement"].unique())
)
df = scores if dep == "Tous" else scores[scores["departement"] == dep]

if "cluster_risque" in df.columns:
    profils = sorted(df["cluster_risque"].dropna().unique().tolist())
    profil = st.sidebar.selectbox("Profil KMeans", ["Tous"] + profils)
    if profil != "Tous":
        df = df[df["cluster_risque"] == profil]

if "decile_proba" in df.columns:
    deciles = sorted(int(d) + 1 for d in df["decile_proba"].dropna().unique())
    decile = st.sidebar.selectbox("Decile de risque", ["Tous"] + deciles)
    if decile != "Tous":
        df = df[df["decile_proba"] == decile - 1]

seuil = st.sidebar.slider(
    "Probabilite minimale (%)",
    0.0,
    float(scores["proba_incendie_suivant"].max() * 100),
    0.0,
    step=0.5,
)
df = df[df["proba_incendie_suivant"] * 100 >= seuil]

st.subheader(f"{len(df):,} communes affichees".replace(",", " "))

if df.empty:
    st.warning("Aucune commune ne correspond a ces filtres.")
    st.stop()

# Echelle de couleur relative au maximum national, pas a 1 : sans cela, avec un
# maximum de 0,31 toutes les communes ressortent presque noires.
maximum = float(scores["proba_incendie_suivant"].max()) or 1.0
carte = df.dropna(subset=["latitude", "longitude"]).copy()
carte["intensite"] = (carte["proba_incendie_suivant"] / maximum).clip(0, 1)
carte["couleur"] = carte["intensite"].apply(
    lambda t: [int(60 + 195 * t), int(120 * (1 - t)), int(60 * (1 - t)), 170]
)
carte["rayon"] = 900 + carte["intensite"] * 4500
carte["proba_pct"] = (carte["proba_incendie_suivant"] * 100).round(1)

couche = pdk.Layer(
    "ScatterplotLayer",
    data=carte,
    get_position=["longitude", "latitude"],
    get_fill_color="couleur",
    get_radius="rayon",
    pickable=True,
    opacity=0.65,
)

st.pydeck_chart(
    pdk.Deck(
        layers=[couche],
        initial_view_state=pdk.ViewState(
            latitude=float(carte["latitude"].mean()),
            longitude=float(carte["longitude"].mean()),
            zoom=7 if dep != "Tous" else 5,
        ),
        tooltip={
            "html": "<b>{nom}</b> ({code_insee})<br/>"
            "Probabilite : {proba_pct} %<br/>"
            "Feux sur 5 ans : {nb_feux_5a}",
            "style": {"color": "white"},
        },
    )
)

st.subheader("Communes les plus exposees")
colonnes = [
    c
    for c in [
        "code_insee",
        "nom",
        "proba_incendie_suivant",
        "nb_feux_5a",
        "nb_feux_10a",
        "cluster_risque",
        "cluster_spatial",
    ]
    if c in df.columns
]
top = df.nlargest(50, "proba_incendie_suivant")[colonnes].copy()
top["proba_incendie_suivant"] = (top["proba_incendie_suivant"] * 100).round(1)
st.dataframe(
    top.rename(columns={"proba_incendie_suivant": "probabilite (%)"}),
    hide_index=True,
)
