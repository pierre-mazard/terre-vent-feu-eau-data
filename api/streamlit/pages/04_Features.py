# api/streamlit/pages/04_Features.py
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[3]
if str(RACINE) not in sys.path:
    sys.path.insert(0, str(RACINE))

import streamlit as st  # noqa: E402

from api.streamlit import donnees  # noqa: E402

st.set_page_config(page_title="Variables", page_icon="🧮", layout="wide")
st.title("🧮 Les variables du modele")

scores = donnees.charger_scores()
_, model_run_dir = donnees.dossiers_run()

noms = donnees.lire_json_optionnel(model_run_dir / "shap_feature_names.json")
if noms is None:
    from models.config_pipeline import FEATURE_COLUMNS as noms

st.caption(
    f"{len(noms)} variables d'entree, decrites ici sur les {len(scores):,} communes "
    "de l'annee de scoring. Le fichier complet des variables fait 157 Mo et "
    "couvre toutes les annees : on ne le charge pas ici.".replace(",", " ")
)

presentes = [c for c in noms if c in scores.columns]

st.subheader("Statistiques descriptives")
st.dataframe(scores[presentes].describe().T)

st.subheader("Distribution d'une variable")
variable = st.selectbox("Variable", presentes)
st.bar_chart(scores[variable], height=280)

st.subheader("Correlation avec la probabilite predite")
correlations = (
    scores[presentes + ["proba_incendie_suivant"]]
    .corr(numeric_only=True)["proba_incendie_suivant"]
    .drop("proba_incendie_suivant")
    .sort_values(ascending=False)
)
st.bar_chart(correlations, height=360)
st.caption(
    "Une correlation elevee ne signifie pas que la variable est importante pour "
    "le modele : l'importance reelle se mesure par permutation ou par SHAP "
    "(page 07)."
)
