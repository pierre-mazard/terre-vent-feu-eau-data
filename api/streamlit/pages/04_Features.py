import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from api.streamlit.bootstrap import ROOT
from config import DATA_PROCESSED, MODELS

import streamlit as st
import json
import pandas as pd

st.set_page_config(page_title="Features", layout="wide")

st.title("Exploration des features")

latest_path = DATA_PROCESSED / "latest_run.json"
if not latest_path.exists():
    st.error("latest_run.json introuvable.")
    st.stop()

with open(latest_path) as f:
    latest = json.load(f)

run_dir = Path(latest["run_dir"])

features_path = run_dir / "features_final.csv"
if not features_path.exists():
    st.error("features_final.csv introuvable.")
    st.stop()

df = pd.read_csv(features_path)

st.subheader("Aperçu des données")
st.dataframe(df.head())

st.subheader("Colonnes disponibles")
st.write(list(df.columns))

st.subheader("Statistiques descriptives")
st.write(df.describe())

st.subheader("Distribution de la cible")
if "cible_incendie_suivant" in df.columns:
    st.bar_chart(df["cible_incendie_suivant"].value_counts())
else:
    st.warning("Colonne cible_incendie_suivant absente.")
