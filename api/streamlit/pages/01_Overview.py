# --- BOOTSTRAP (obligatoire dans chaque page) ---
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

# --- Imports projet ---
from api.streamlit.bootstrap import ROOT
from config import DATA_PROCESSED, MODELS

# --- Imports Streamlit ---
import streamlit as st
import json
import pandas as pd
from pathlib import Path

st.set_page_config(page_title="Overview", layout="wide")
st.title("Overview - TVFE")

# Charger latest_run
latest_path = DATA_PROCESSED / "latest_run.json"
if not latest_path.exists():
    st.error("latest_run.json introuvable. Lance le pipeline ML.")
    st.stop()

with open(latest_path) as f:
    latest = json.load(f)

run_dir = Path(latest["run_dir"])
model_run_dir = MODELS / "run" / run_dir.name

st.subheader("Run courant")
st.json({"run_dir": str(run_dir), "model_run_dir": str(model_run_dir)})

# Manifest
manifest_path = run_dir / "run_manifest.json"
if manifest_path.exists():
    st.subheader("Run manifest")
    with open(manifest_path) as f:
        manifest = json.load(f)
    st.json(manifest)
else:
    st.warning("run_manifest.json manquant.")

# Dataset report
dataset_report_path = run_dir / "dataset_report.json"
if dataset_report_path.exists():
    st.subheader("Dataset report")
    with open(dataset_report_path) as f:
        dataset_report = json.load(f)
    st.json(dataset_report)
else:
    st.warning("dataset_report.json manquant.")
