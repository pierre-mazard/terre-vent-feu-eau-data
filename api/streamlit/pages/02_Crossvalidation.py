# api/streamlit/pages/02_Crossvalidation.py
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[3]
if str(RACINE) not in sys.path:
    sys.path.insert(0, str(RACINE))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from api.streamlit import donnees  # noqa: E402

st.set_page_config(page_title="Validation croisee", page_icon="🔁", layout="wide")
st.title("🔁 Validation croisee")

_, model_run_dir = donnees.dossiers_run()
rapport = donnees.charger_json(
    model_run_dir / "cross_validation_report.json",
    "Le rapport de validation croisee",
    "python -m models.train_test.cross_validation",
)

temporel = rapport.get("temporal_cv", {})
plis = pd.DataFrame(temporel.get("folds", []))

st.subheader("Validation temporelle")
st.caption(
    "Le protocole est rejoue annee apres annee : on entraine sur tout ce qui "
    "precede et on evalue sur l'annee suivante. Cela verifie que la performance "
    "n'est pas un coup de chance sur une seule annee."
)

if plis.empty:
    st.warning("Aucun pli temporel dans le rapport.")
else:
    moyennes = temporel.get("mean", {})
    c1, c2, c3 = st.columns(3)
    c1.metric("PR-AUC moyenne", f"{moyennes.get('pr_auc', float('nan')):.3f}")
    c2.metric("ROC-AUC moyenne", f"{moyennes.get('roc_auc', float('nan')):.3f}")
    c3.metric("Brier moyen", f"{moyennes.get('brier_score', float('nan')):.4f}")

    st.line_chart(plis.set_index("annee")[["pr_auc", "roc_auc"]], height=280)
    st.line_chart(plis.set_index("annee")[["brier_score"]], height=220)
    st.dataframe(plis, hide_index=True)

st.subheader("Validation geographique")
geo = rapport.get("geographic_cv", {})
if not geo:
    st.warning("Aucun resultat geographique dans le rapport.")
else:
    g1, g2, g3 = st.columns(3)
    g1.metric("Communes tenues a l'ecart", geo.get("communes_test_geo", "—"))
    g2.metric("PR-AUC", f"{geo.get('pr_auc', float('nan')):.3f}")
    g3.metric("ROC-AUC", f"{geo.get('roc_auc', float('nan')):.3f}")
    st.caption(
        "Limite connue : les communes tenues a l'ecart sont tirees au hasard sur "
        "toute la France, donc leurs voisines restent dans l'entrainement. Un "
        "decoupage par departement entier serait plus severe — et plus honnete."
    )
