# api/streamlit/pages/06_RunExplorer.py
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[3]
if str(RACINE) not in sys.path:
    sys.path.insert(0, str(RACINE))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from config import DATA_PROCESSED, MODELS  # noqa: E402
from api.streamlit import donnees  # noqa: E402

st.set_page_config(page_title="Explorateur de runs", page_icon="📦", layout="wide")
st.title("📦 Explorateur de runs")

run_courant, _ = donnees.dossiers_run()
dossier = DATA_PROCESSED / "run"
runs = (
    sorted((d.name for d in dossier.iterdir() if d.is_dir()), reverse=True)
    if dossier.exists()
    else []
)

if not runs:
    st.warning("Aucun run sur le disque.")
    st.stop()

st.caption(f"Run courant : `{run_courant.name}`")
choisi = st.selectbox(
    "Run a inspecter",
    runs,
    index=runs.index(run_courant.name) if run_courant.name in runs else 0,
)

rd = dossier / choisi
md = MODELS / "run" / choisi

lignes = []
for base, etiquette in ((rd, "donnees"), (md, "modeles")):
    if base.exists():
        for f in sorted(base.iterdir()):
            if f.is_file():
                lignes.append(
                    {
                        "emplacement": etiquette,
                        "fichier": f.name,
                        "taille (Mo)": round(f.stat().st_size / (1024 * 1024), 2),
                    }
                )

st.subheader("Artefacts produits")
if lignes:
    tableau = pd.DataFrame(lignes)
    st.dataframe(tableau, hide_index=True)
    lourds = tableau[tableau["taille (Mo)"] > donnees.TAILLE_MODELE_MAX_MO]
    if not lourds.empty:
        st.error(
            "Artefacts anormalement lourds : "
            + ", ".join(
                f"{r.fichier} ({r['taille (Mo)'] / 1024:.1f} Go)"
                for _, r in lourds.iterrows()
            )
            + ".\n\nUn modele de plusieurs Go vient d'une foret sans `max_depth` "
            "calibree sans `cv`. Corrige `models/pipeline/training.py` et relance "
            "l'entrainement : il doit retomber autour de 100 Mo."
        )
else:
    st.warning("Ce run ne contient aucun fichier.")

for titre, chemin in [
    ("Manifeste", rd / "run_manifest.json"),
    ("Decoupage train / test", md / "split_report.json"),
    ("Metriques", md / "metadata.json"),
]:
    contenu = donnees.lire_json_optionnel(chemin)
    if contenu is not None:
        st.subheader(titre)
        st.json(contenu)
