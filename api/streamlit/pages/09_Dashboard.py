# api/streamlit/pages/09_Dashboard.py
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[3]
if str(RACINE) not in sys.path:
    sys.path.insert(0, str(RACINE))

import streamlit as st  # noqa: E402

from api.streamlit import donnees  # noqa: E402

st.set_page_config(page_title="Dashboard", page_icon="📈", layout="wide")
st.title("📈 Synthese nationale et departementale")

scores = donnees.charger_scores()
_, model_run_dir = donnees.dossiers_run()
meta = donnees.lire_json_optionnel(model_run_dir / "metadata.json") or {}
annee = meta.get("annee_score", int(scores["annee"].max()) + 1)

proba = scores["proba_incendie_suivant"]

st.subheader(f"France entiere — prediction {annee}")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Communes", f"{len(scores):,}".replace(",", " "))
c2.metric("Probabilite moyenne", f"{proba.mean() * 100:.1f} %")
c3.metric("Probabilite maximale", f"{proba.max() * 100:.1f} %")
c4.metric(
    "Top 5 % (surveillance ciblee)",
    f"{int(len(scores) * 0.05):,}".replace(",", " "),
)

st.subheader("Classement des departements")
par_dep = (
    scores.groupby("departement")
    .agg(
        communes=("code_insee", "size"),
        proba_moyenne=("proba_incendie_suivant", "mean"),
        proba_max=("proba_incendie_suivant", "max"),
        feux_5a=("nb_feux_5a", "sum"),
    )
    .sort_values("proba_moyenne", ascending=False)
)
par_dep["proba_moyenne"] = (par_dep["proba_moyenne"] * 100).round(2)
par_dep["proba_max"] = (par_dep["proba_max"] * 100).round(1)

g1, g2 = st.columns([2, 3])
with g1:
    st.bar_chart(par_dep["proba_moyenne"].head(20), height=420)
with g2:
    st.dataframe(
        par_dep.reset_index().rename(
            columns={
                "departement": "Departement",
                "communes": "Communes",
                "proba_moyenne": "Proba moyenne (%)",
                "proba_max": "Proba max (%)",
                "feux_5a": "Feux sur 5 ans",
            }
        ),
        hide_index=True,
        height=420,
    )

st.subheader("Detail d'un departement")
dep = st.selectbox("Departement", sorted(scores["departement"].unique()))
df_dep = scores[scores["departement"] == dep]

d1, d2, d3 = st.columns(3)
d1.metric("Communes", len(df_dep))
d2.metric(
    "Probabilite moyenne", f"{df_dep['proba_incendie_suivant'].mean() * 100:.1f} %"
)
d3.metric("Feux sur 5 ans", f"{df_dep['nb_feux_5a'].sum():.0f}")

colonnes = [
    c
    for c in [
        "code_insee",
        "nom",
        "proba_incendie_suivant",
        "nb_feux_5a",
        "nb_feux_10a",
        "cluster_risque",
    ]
    if c in df_dep.columns
]
top = df_dep.nlargest(20, "proba_incendie_suivant")[colonnes].copy()
top["proba_incendie_suivant"] = (top["proba_incendie_suivant"] * 100).round(1)

t1, t2 = st.columns([3, 2])
with t1:
    st.dataframe(
        top.rename(columns={"proba_incendie_suivant": "probabilite (%)"}),
        hide_index=True,
    )
with t2:
    carte = df_dep[["latitude", "longitude"]].dropna()
    if not carte.empty:
        st.map(carte, size=400, zoom=8)

st.subheader("Repartition des niveaux de risque")
if "decile_proba" in scores.columns:

    def niveau(d):
        d = int(d)
        return (
            "Tres eleve"
            if d >= 9
            else "Eleve" if d == 8 else "Modere" if d >= 6 else "Faible"
        )

    repartition = (
        scores["decile_proba"]
        .dropna()
        .map(niveau)
        .value_counts()
        .reindex(["Faible", "Modere", "Eleve", "Tres eleve"])
    )
    st.bar_chart(repartition, height=260)
    st.caption(
        "Niveaux definis par deciles. Avec des seuils fixes sur 100, le niveau "
        "le plus haut serait vide : aucune commune ne depasse "
        f"{proba.max() * 100:.0f} / 100."
    )

st.info(
    "Pour l'explication d'une commune precise, va sur la page "
    "**08 · Fiche commune**."
)
