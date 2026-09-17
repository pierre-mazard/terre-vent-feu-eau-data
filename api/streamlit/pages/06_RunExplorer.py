import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from api.streamlit.bootstrap import ROOT
from config import DATA_PROCESSED, MODELS
import streamlit as st
import json

st.set_page_config(page_title="Run explorer", layout="wide")

st.title("Explorateur de runs")

runs_dir = DATA_PROCESSED / "run"
if not runs_dir.exists():
    st.error("Aucun dossier de runs trouvé.")
    st.stop()

run_dirs = sorted([p for p in runs_dir.iterdir() if p.is_dir()])

st.subheader("Liste des runs")
selected_run = st.selectbox(
    "Choisir un run",
    options=[p.name for p in run_dirs],
)

run_dir = runs_dir / selected_run
model_run_dir = MODELS / "run" / selected_run

st.write(f"Dossier data : {run_dir}")
st.write(f"Dossier modèles : {model_run_dir}")

manifest_path = run_dir / "run_manifest.json"
if manifest_path.exists():
    st.subheader("Manifest du run")
    with open(manifest_path) as f:
        manifest = json.load(f)
    st.json(manifest)
else:
    st.warning("run_manifest.json manquant pour ce run.")

dataset_report_path = run_dir / "dataset_report.json"
if dataset_report_path.exists():
    st.subheader("Dataset report")
    with open(dataset_report_path) as f:
        dataset_report = json.load(f)
    st.json(dataset_report)
else:
    st.warning("dataset_report.json manquant pour ce run.")
