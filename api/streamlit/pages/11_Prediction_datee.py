# api/streamlit/pages/11_Prediction_datee.py
"""Risque d'incendie pour une commune a une date precise."""

import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[3]
if str(RACINE) not in sys.path:
    sys.path.insert(0, str(RACINE))

import datetime as dt  # noqa: E402

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from api.streamlit import donnees  # noqa: E402

st.set_page_config(page_title="Prediction datee", page_icon="📅", layout="wide")
st.title("📅 Risque a une date precise")

_, model_run_dir = donnees.dossiers_run()

for fichier in (
    "horizons_metriques.json",
    "feux_historique.csv",
    "panel_horizon.parquet",
    "modele_horizon_30j.json",
):
    donnees.exige(
        model_run_dir / fichier,
        f"Le fichier `{fichier}`",
        "python -m models.train_test.train_horizons",
    )

meta = donnees.charger_json(
    model_run_dir / "horizons_metriques.json",
    "Les metriques des modeles a horizon",
    "python -m models.train_test.train_horizons",
)
HORIZONS = sorted(int(h.rstrip("j")) for h in meta["horizons"])


@st.cache_data(show_spinner="Chargement de la chronologie des feux…", persist="disk")
def charger_feux(chemin: str, _cle: float) -> pd.DataFrame:
    df = pd.read_csv(chemin, parse_dates=["date"], dtype={"code_insee": str})
    df["code_insee"] = df["code_insee"].str.zfill(5)
    return df


@st.cache_data(show_spinner=False, persist="disk")
def charger_panel(chemin: str, _cle: float) -> pd.DataFrame:
    return pd.read_parquet(chemin)


@st.cache_resource(show_spinner="Preparation du voisinage…")
def preparer(_panel_signature: str):
    from models.pipeline.features_horizon import Voisinage

    panel = charger_panel(
        str(model_run_dir / "panel_horizon.parquet"),
        (model_run_dir / "panel_horizon.parquet").stat().st_mtime,
    )
    communes = sorted(panel["code_insee"].unique().tolist())
    geo = (
        panel.drop_duplicates("code_insee")
        .set_index("code_insee")
        .loc[communes, ["latitude", "longitude"]]
        .to_numpy("float64")
    )
    return communes, Voisinage(communes, geo)


# `st.stop()` ne fonctionne pas a l'interieur d'une fonction mise en cache :
# on verifie donc la dependance AVANT, au niveau de la page.
xgboost = donnees.module_optionnel("xgboost")


@st.cache_resource(show_spinner="Chargement des modeles a horizon…")
def charger_modeles(_cle: float) -> dict:
    modeles = {}
    for h in HORIZONS:
        m = xgboost.XGBClassifier()
        m.load_model(str(model_run_dir / f"modele_horizon_{h}j.json"))
        modeles[h] = m
    return modeles


feux = charger_feux(
    str(model_run_dir / "feux_historique.csv"),
    (model_run_dir / "feux_historique.csv").stat().st_mtime,
)
panel = charger_panel(
    str(model_run_dir / "panel_horizon.parquet"),
    (model_run_dir / "panel_horizon.parquet").stat().st_mtime,
)
communes, voisinage = preparer(str(model_run_dir))
modeles = charger_modeles((model_run_dir / "modele_horizon_30j.json").stat().st_mtime)

scores = donnees.charger_scores()
noms = scores.set_index("code_insee")["nom"].to_dict()

st.markdown(
    "Le modele annuel repond a « cette commune brulera-t-elle dans l'annee ? ». "
    "Cette page repond a une question plus fine : **« y aura-t-il un feu dans "
    "les 10, 30 ou 60 jours qui suivent cette date ? »**"
)

# ---------------------------------------------------------------------------
# Choix de la commune et de la date
# ---------------------------------------------------------------------------
c1, c2, c3 = st.columns([2, 2, 2])

with c1:
    recherche = st.text_input(
        "Rechercher une commune", placeholder="ex. Aix", key="rech_datee"
    ).strip()

candidats = scores
if recherche:
    candidats = scores[
        scores["nom"].str.contains(recherche, case=False, na=False)
        | scores["code_insee"].str.startswith(recherche)
    ]
    if candidats.empty:
        st.warning(f"Aucune commune ne correspond a « {recherche} ».")
        st.stop()
else:
    with c2:
        dep = st.selectbox(
            "Departement", sorted(scores["departement"].unique()), key="dep_datee"
        )
    candidats = scores[scores["departement"] == dep]

candidats = candidats.sort_values("nom")
etiquettes = dict(
    zip(
        candidats["code_insee"], candidats["nom"] + " (" + candidats["code_insee"] + ")"
    )
)

with c2 if recherche else c3:
    code = st.selectbox(
        "Commune",
        options=list(etiquettes.keys()),
        format_func=lambda c: etiquettes[c],
        key="com_datee",
    )

with c3 if recherche else c1:
    date = st.date_input(
        "Date evaluee",
        value=dt.date(2025, 6, 15),
        min_value=dt.date(2010, 1, 1),
        max_value=dt.date(2030, 12, 31),
        key="date_datee",
        format="DD/MM/YYYY",
    )

# ---------------------------------------------------------------------------
# Prediction
# ---------------------------------------------------------------------------
from models.pipeline.features_horizon import (  # noqa: E402
    COLONNES_HORIZON,
    corriger_prior,
    variables_ponctuelles,
)

codes_voisins = [communes[i] for i in voisinage.voisins(code)]
X = variables_ponctuelles(code, pd.Timestamp(date), feux, panel, codes_voisins)

probabilites = {}
for h, modele in modeles.items():
    brute = modele.predict_proba(X[COLONNES_HORIZON])[:, 1]
    probabilites[h] = float(corriger_prior(brute, meta["fraction_negatifs"])[0])

st.header(f"{noms.get(code, code)} — {date.strftime('%d/%m/%Y')}")

colonnes = st.columns(len(HORIZONS))
for col, h in zip(colonnes, HORIZONS):
    p = probabilites[h]
    fin = pd.Timestamp(date) + pd.Timedelta(days=h)
    col.metric(
        f"Dans les {h} jours",
        f"{p * 100:.1f} %",
        help=f"Au moins un depart de feu entre le "
        f"{(pd.Timestamp(date) + pd.Timedelta(days=1)).strftime('%d/%m/%Y')} "
        f"et le {fin.strftime('%d/%m/%Y')}.",
    )
    col.caption(f"jusqu'au {fin.strftime('%d/%m/%Y')}")

st.progress(
    min(1.0, probabilites[max(HORIZONS)]),
    text=f"Risque a {max(HORIZONS)} jours",
)

# ---------------------------------------------------------------------------
# Ce qui produit ce chiffre
# ---------------------------------------------------------------------------
st.subheader("Ce que le modele a regarde a cette date")

v = X.iloc[0]
e1, e2, e3 = st.columns(3)

with e1:
    st.markdown("**Activite recente de la commune**")
    st.dataframe(
        pd.DataFrame(
            {
                "valeur": [
                    f"{v['feux_7j']:.0f}",
                    f"{v['feux_30j']:.0f}",
                    f"{v['feux_365j']:.0f}",
                    f"{v['surface_365j_ha']:.1f} ha",
                    (
                        "jamais"
                        if v["jours_depuis_dernier_feu"] >= 3650
                        else f"il y a {v['jours_depuis_dernier_feu']:.0f} jours"
                    ),
                ]
            },
            index=[
                "Feux dans les 7 derniers jours",
                "Feux dans les 30 derniers jours",
                "Feux dans les 365 derniers jours",
                "Surface brulee sur 1 an",
                "Dernier feu",
            ],
        ),
        height=220,
    )

with e2:
    st.markdown("**Voisinage (rayon 20 km)**")
    st.dataframe(
        pd.DataFrame(
            {
                "valeur": [
                    f"{len(codes_voisins)}",
                    f"{v['feux_voisinage_30j']:.0f}",
                    f"{v['feux_voisinage_5a']:.0f}",
                ]
            },
            index=[
                "Communes voisines",
                "Feux chez les voisins sur 30 jours",
                "Feux chez les voisins sur 5 ans",
            ],
        ),
        height=220,
    )
    st.caption("Un feu ne s'arrete pas a la limite communale.")

with e3:
    st.markdown("**Saison et historique long**")
    st.dataframe(
        pd.DataFrame(
            {
                "valeur": [
                    f"{int(v['mois'])}",
                    f"{v['feux_meme_mois_5a']:.0f}",
                    f"{v['nb_feux_5a']:.0f}",
                    f"{v['nb_feux_10a']:.0f}",
                ]
            },
            index=[
                "Mois",
                "Feux ce mois-ci sur 5 ans",
                "Feux sur 5 ans",
                "Feux sur 10 ans",
            ],
        ),
        height=220,
    )

# ---------------------------------------------------------------------------
# Profil sur l'annee
# ---------------------------------------------------------------------------
st.subheader("Profil du risque sur l'annee")
st.caption(
    "La meme commune, evaluee tous les quinze jours sur douze mois : c'est la "
    "saisonnalite apprise par le modele."
)

if st.button("Calculer la courbe annuelle"):
    debut = pd.Timestamp(date.year, 1, 1)
    dates = pd.date_range(debut, periods=24, freq="15D")
    lignes = []
    barre = st.progress(0.0)
    for k, d in enumerate(dates):
        Xd = variables_ponctuelles(code, d, feux, panel, codes_voisins)
        ligne = {"date": d}
        for h, modele in modeles.items():
            brute = modele.predict_proba(Xd[COLONNES_HORIZON])[:, 1]
            ligne[f"{h} jours"] = (
                float(corriger_prior(brute, meta["fraction_negatifs"])[0]) * 100
            )
        lignes.append(ligne)
        barre.progress((k + 1) / len(dates))
    barre.empty()
    courbe = pd.DataFrame(lignes).set_index("date")
    st.line_chart(courbe, height=340)
    st.caption("Probabilite en %, par horizon.")

# ---------------------------------------------------------------------------
# Performance et limites
# ---------------------------------------------------------------------------
st.subheader("Ce que valent ces chiffres")

perf = pd.DataFrame(
    {
        "PR-AUC": [meta["horizons"][f"{h}j"]["pr_auc"] for h in HORIZONS],
        "Gain sur le hasard": [
            meta["horizons"][f"{h}j"]["gain_sur_le_hasard"] for h in HORIZONS
        ],
        "Precision top 5 % (%)": [
            meta["horizons"][f"{h}j"]["precision_top_5pct"] * 100 for h in HORIZONS
        ],
        "Rappel top 5 % (%)": [
            meta["horizons"][f"{h}j"]["rappel_top_5pct"] * 100 for h in HORIZONS
        ],
    },
    index=[f"{h} jours" for h in HORIZONS],
).round(2)
st.dataframe(perf)

st.markdown("**Les variables qui pesent le plus, a 30 jours**")
importance = pd.Series(meta["horizons"]["30j"]["importance"]).sort_values(
    ascending=False
)
importance_pct = (importance.head(10) * 100).rename("part_information_pct")
st.bar_chart(importance_pct, height=300)

espace = meta["espace_complet"]
st.info(f"""
**Comment on evite les 242 millions de lignes.** Une ligne par commune et par
jour sur vingt ans, c'est 242 millions d'enregistrements : impossible a traiter
sur une machine de bureau. On garde donc **tous** les cas ou un feu suit, et
seulement une fraction tiree au hasard des autres — ici
**{meta['fraction_negatifs'] * 100:.2f} %** des negatifs, sur un espace de
{espace:,} couples. La probabilite affichee est ensuite **corrigee** pour
revenir au taux reel ; sans cette correction elle serait environ vingt fois
trop elevee.
""".replace(",", " "))

st.warning("""
**Limites du modele.**

- Toujours aucune donnee meteo : le modele apprend *quand* et *ou* ca brule
  habituellement, pas si la semaine a venir sera seche et ventee. C'est ce qui
  distinguerait une alerte operationnelle de ce qu'on a ici.
- Les trois horizons sont trois modeles distincts. Sur les communes a tres
  faible risque, leurs probabilites peuvent ne pas etre parfaitement
  croissantes avec l'horizon.
- Au-dela de la derniere annee connue, l'historique long est fige a son dernier
  etat : c'est exactement l'information dont on dispose pour predire le futur.
""")
