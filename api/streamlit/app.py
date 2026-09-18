# api/streamlit/app.py
"""Page d'accueil de l'application TVFE.

Le bootstrap doit etre AVANT tout import projet : quand Streamlit lance ce
fichier, `sys.path[0]` vaut `api/streamlit/`, pas la racine du depot. Ecrire
`from api.streamlit.bootstrap import ROOT` ici echouait donc forcement, puisque
c'est justement `bootstrap` qui ajoute la racine au chemin de recherche.
"""

import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
if str(RACINE) not in sys.path:
    sys.path.insert(0, str(RACINE))

import streamlit as st  # noqa: E402

st.set_page_config(
    page_title="TVFE — Risque incendie",
    page_icon="🔥",
    layout="wide",
)

st.title("🔥 TVFE — Risque d'incendie de foret en France")
st.caption("Terre, Vent, Feu, Eau, Data · MSc IA & Data · La Plateforme_")

st.markdown("""
Cette application explore un modele qui repond a une seule question :

> **cette commune connaitra-t-elle au moins un incendie l'annee prochaine ?**

Le modele ne dit ni quand, ni quelle surface : il **classe** les communes par
exposition, pour aider a decider ou regarder en priorite.
""")

from api.streamlit import donnees  # noqa: E402

run_dir, model_run_dir = donnees.dossiers_run()
meta = donnees.lire_json_optionnel(model_run_dir / "metadata.json") or {}
split = donnees.lire_json_optionnel(model_run_dir / "split_report.json") or {}
dataset = donnees.lire_json_optionnel(run_dir / "dataset_report.json") or {}

st.subheader("Run actuellement charge")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Run", run_dir.name)
c2.metric("Communes", f"{dataset.get('nb_communes', '—'):,}".replace(",", " "))
c3.metric("PR-AUC (test)", f"{meta['pr_auc']:.3f}" if "pr_auc" in meta else "—")
c4.metric("Annee predite", meta.get("annee_score", "—"))

if split:
    annees = split.get("train_years", [])
    if annees:
        empreinte = split.get("split_hash", "")[:16]
        st.caption(
            f"Entrainement {min(annees)}-{max(annees)} · "
            f"test {split.get('annee_test')} · "
            f"empreinte du decoupage `{empreinte}…`"
        )

st.subheader("Par ou commencer")
st.markdown("""
| Page | Ce qu'on y trouve |
|---|---|
| **08 · Fiche commune** | Une commune, sa prediction pour l'annee |
| **11 · Prediction datee** | Une commune **et une date** : le risque a 10, 30 et 60 jours |
| **10 · Comparaison** | XGBoost, Random Forest, regression logistique : les chiffres |
| 05 · Scores | La carte nationale et le classement des communes |
| 09 · Dashboard | Synthese par departement |
| 03 · Metriques | Performance mesuree du modele |
| 02 · Validation croisee | Robustesse dans le temps et dans l'espace |
| 07 · Explicabilite | SHAP : quelle variable pese sur quoi |
| 01 · Overview · 04 · Variables · 06 · Runs | Details techniques du pipeline |
""")

st.info(
    "Les scores sont **pre-calcules** par le pipeline et charges en cache : "
    "l'application ne reentraine jamais le modele. Si un artefact manque, la "
    "page concernee indique la commande a lancer."
)

st.subheader("Deux echelles de temps")
st.markdown("""
| | Question posee | Granularite | Page |
|---|---|---|---|
| **Modele annuel** | cette commune brulera-t-elle dans l'annee ? | commune x annee | 08 |
| **Modeles a horizon** | y aura-t-il un feu dans les 10, 30 ou 60 jours ? | commune x date | 11 |

Le second n'a pas remplace le premier : il repond a une autre question, avec
d'autres variables (activite recente, voisinage a 20 km, saison) et une autre
facon de gerer le volume de donnees.
""")
