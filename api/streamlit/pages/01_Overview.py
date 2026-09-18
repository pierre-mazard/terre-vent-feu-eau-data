# api/streamlit/pages/01_Overview.py
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[3]
if str(RACINE) not in sys.path:
    sys.path.insert(0, str(RACINE))

import streamlit as st  # noqa: E402

from api.streamlit import donnees  # noqa: E402

st.set_page_config(page_title="Overview", page_icon="🗂️", layout="wide")
st.title("🗂️ Vue d'ensemble du run")

run_dir, model_run_dir = donnees.dossiers_run()

st.subheader("Emplacements")
st.json({"donnees": str(run_dir), "modeles": str(model_run_dir)})

for titre, chemin in [
    ("Manifeste du run", run_dir / "run_manifest.json"),
    ("Rapport du jeu de donnees", run_dir / "dataset_report.json"),
    ("Nettoyage — incendies", run_dir / "cleaning_report_incendies.json"),
    ("Nettoyage — communes", run_dir / "cleaning_report_communes.json"),
    ("Clustering", run_dir / "clustering_report.json"),
    ("Decoupage train / test", model_run_dir / "split_report.json"),
    ("Metriques du modele", model_run_dir / "metadata.json"),
]:
    contenu = donnees.lire_json_optionnel(chemin)
    st.subheader(titre)
    if contenu is None:
        st.warning(f"`{chemin.name}` absent de ce run.")
    else:
        st.json(contenu)
