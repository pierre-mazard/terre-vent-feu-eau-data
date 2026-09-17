import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from api.streamlit.bootstrap import ROOT
from config import DATA_PROCESSED, MODELS

import streamlit as st
import json
import pandas as pd

st.set_page_config(page_title="Cross-validation", layout="wide")

st.title("Validation croisée")

latest_path = DATA_PROCESSED / "latest_run.json"
if not latest_path.exists():
    st.error("latest_run.json introuvable.")
    st.stop()

with open(latest_path) as f:
    latest = json.load(f)

run_dir = Path(latest["run_dir"])
model_run_dir = MODELS / "run" / run_dir.name

cv_path = model_run_dir / "cross_validation_report.json"
if not cv_path.exists():
    st.error(
        "cross_validation_report.json introuvable. Relance `make run-pipeline-ml`."
    )
    st.stop()

with open(cv_path) as f:
    cv = json.load(f)

st.subheader("Validation croisée temporelle")
temporal = cv["temporal_cv"]
df_temporal = pd.DataFrame(temporal["folds"])
st.dataframe(df_temporal)

col1, col2 = st.columns(2)
with col1:
    st.line_chart(df_temporal.set_index("annee")[["roc_auc", "pr_auc"]])
with col2:
    st.line_chart(df_temporal.set_index("annee")[["brier_score", "rappel_top_5pct"]])

st.subheader("Résumé temporel")
st.json(temporal["mean"])
st.json(temporal["std"])

st.subheader("Validation croisée géographique")
geo = cv["geographic_cv"]
st.json(geo)
