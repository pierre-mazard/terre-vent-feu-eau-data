# api/streamlit/pages/03_ModelMetrics.py
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[3]
if str(RACINE) not in sys.path:
    sys.path.insert(0, str(RACINE))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from api.streamlit import donnees  # noqa: E402

st.set_page_config(page_title="Metriques", page_icon="📊", layout="wide")
st.title("📊 Performance du modele")

_, model_run_dir = donnees.dossiers_run()
meta = donnees.charger_json(
    model_run_dir / "metadata.json",
    "Les metriques du modele `metadata.json`",
    "python -m models.train_test.train_model",
)
scores = donnees.charger_scores()

taux_base = 1 / 40  # ordre de grandeur du taux de communes qui brulent
pr = meta.get("pr_auc")
roc = meta.get("roc_auc")

c1, c2, c3 = st.columns(3)
c1.metric("PR-AUC (test temporel)", f"{pr:.3f}" if pr else "—")
c2.metric("ROC-AUC", f"{roc:.3f}" if roc else "—")
c3.metric("Annee predite", meta.get("annee_score", "—"))

st.info(
    "**Pourquoi la PR-AUC et pas l'exactitude.** Environ 2,5 % des communes "
    "brulent d'une annee sur l'autre. Un modele qui repond « non » partout "
    "obtient donc 97,5 % d'exactitude sans servir a rien. Le plancher de la "
    "PR-AUC n'est pas 0,5 mais ce taux de base : c'est a lui qu'il faut la "
    "comparer."
)

st.subheader("Distribution des probabilites predites")
st.caption(
    "Ces probabilites portent sur l'annee de scoring, pour laquelle la verite "
    "n'est pas encore connue : on ne peut donc pas y recalculer une courbe ROC. "
    "Les metriques ci-dessus viennent du test temporel, sur une annee dont la "
    "cible est observee."
)

proba = scores["proba_incendie_suivant"]
histogramme = (
    pd.cut(proba, bins=20).value_counts().sort_index().rename("communes").to_frame()
)
histogramme.index = [f"{i.left:.2f}–{i.right:.2f}" for i in histogramme.index]
st.bar_chart(histogramme, height=300)

st.subheader("Niveaux de risque, par deciles")
st.caption(
    "Les niveaux sont definis par deciles et non par des seuils fixes : avec un "
    f"maximum national de {proba.max() * 100:.1f} %, un seuil « > 50 / 100 » "
    "laisserait le niveau le plus haut vide."
)

if "decile_proba" in scores.columns:
    par_decile = (
        scores.groupby("decile_proba")
        .agg(
            communes=("code_insee", "size"),
            proba_min=("proba_incendie_suivant", "min"),
            proba_max=("proba_incendie_suivant", "max"),
        )
        .reset_index()
    )
    par_decile["decile_proba"] = par_decile["decile_proba"].astype(int) + 1
    st.dataframe(par_decile, hide_index=True)

st.subheader("Statistiques")
st.write(
    {
        "Communes scorees": int(len(scores)),
        "Probabilite moyenne": round(float(proba.mean()), 4),
        "Probabilite mediane": round(float(proba.median()), 4),
        "Probabilite maximale": round(float(proba.max()), 4),
        "Communes au-dessus de 2x la moyenne": int((proba > 2 * proba.mean()).sum()),
    }
)
