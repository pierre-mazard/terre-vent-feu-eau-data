# api/streamlit/pages/08_CommuneExplorer.py
"""Fiche de risque d'une commune.

Cette page lit uniquement `scores_risque.csv` (34 863 lignes, 9 Mo) : la
probabilite y est deja calculee par le pipeline, il n'y a donc **aucun modele a
charger** pour afficher une prediction. Le SHAP local, qui lui a besoin du
modele, est optionnel et derriere un bouton.
"""

# --- BOOTSTRAP : la racine du depot doit etre sur sys.path avant tout import projet
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[3]
if str(RACINE) not in sys.path:
    sys.path.insert(0, str(RACINE))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from api.streamlit import donnees  # noqa: E402

st.set_page_config(page_title="Fiche commune", page_icon="🏘️", layout="wide")
st.title("🏘️ Fiche de risque d'une commune")

scores = donnees.charger_scores()
run_dir, model_run_dir = donnees.dossiers_run()
meta = donnees.lire_json_optionnel(model_run_dir / "metadata.json") or {}
annee_score = int(meta.get("annee_score", int(scores["annee"].max()) + 1))

st.caption(
    f"Run `{run_dir.name}` · {len(scores):,} communes · "
    f"prediction pour l'annee {annee_score}".replace(",", " ")
)

# ---------------------------------------------------------------------------
# 1. Selection de la commune
# ---------------------------------------------------------------------------
# On ne met jamais 34 863 entrees dans un selecteur : le navigateur rame. On
# filtre d'abord par departement (ou par recherche de nom), ce qui ramene la
# liste a quelques centaines d'elements.
st.subheader("Choisir une commune")

col_rech, col_dep, col_com = st.columns([2, 1, 3])

with col_rech:
    recherche = st.text_input(
        "Rechercher par nom",
        placeholder="ex. Lançon",
        key="recherche_nom",
    ).strip()

if recherche:
    masque = scores["nom"].str.contains(recherche, case=False, na=False) | scores[
        "code_insee"
    ].str.startswith(recherche)
    candidats = scores[masque]
    with col_dep:
        st.metric("Resultats", len(candidats))
    if candidats.empty:
        st.warning(f"Aucune commune ne correspond a « {recherche} ».")
        st.stop()
else:
    departements = sorted(scores["departement"].unique())
    with col_dep:
        dep = st.selectbox("Departement", departements, key="dep_choisi")
    candidats = scores[scores["departement"] == dep]

candidats = candidats.sort_values("nom")
etiquettes = {
    code: f"{nom} ({code})"
    for code, nom in zip(candidats["code_insee"], candidats["nom"])
}

with col_com:
    code_choisi = st.selectbox(
        "Commune",
        options=list(etiquettes.keys()),
        format_func=lambda c: etiquettes[c],
        key="commune_choisie",
    )

ligne = scores.loc[scores["code_insee"] == code_choisi].iloc[0]


# ---------------------------------------------------------------------------
# 2. Le score
# ---------------------------------------------------------------------------
def niveau_par_decile(decile: float) -> tuple[str, str]:
    """Niveau de risque fonde sur les deciles, pas sur des seuils fixes.

    Avec des seuils fixes (> 50/100 = « tres eleve »), aucune commune de France
    n'atteint le niveau le plus haut : la probabilite maximale est de 0,31. Les
    deciles decrivent la position **relative** de la commune, ce qui est ce que
    l'on veut pour cibler la prevention.
    """
    if pd.isna(decile):
        return "Indetermine", "gray"
    d = int(decile)
    if d >= 9:
        return "Tres eleve", "red"
    if d == 8:
        return "Eleve", "orange"
    if d >= 6:
        return "Modere", "blue"
    return "Faible", "green"


proba = float(ligne["proba_incendie_suivant"])
niveau, couleur = niveau_par_decile(ligne.get("decile_proba", np.nan))

rang_national = int((scores["proba_incendie_suivant"] > proba).sum()) + 1
meme_dep = scores[scores["departement"] == ligne["departement"]]
rang_dep = int((meme_dep["proba_incendie_suivant"] > proba).sum()) + 1

st.header(f"{ligne['nom']}  ·  {code_choisi}")

c1, c2, c3, c4 = st.columns(4)
c1.metric(f"Probabilite d'au moins un feu en {annee_score}", f"{proba * 100:.1f} %")
c2.metric("Niveau de risque", niveau)
c3.metric("Rang national", f"{rang_national} / {len(scores)}")
c4.metric(
    f"Rang dans le departement {ligne['departement']}",
    f"{rang_dep} / {len(meme_dep)}",
)

taux_base = float(scores["proba_incendie_suivant"].mean())
st.caption(
    f"Moyenne nationale : {taux_base * 100:.1f} % — cette commune est a "
    f"**{proba / taux_base:.1f}×** la moyenne. "
    "La probabilite repond a la question « au moins un feu dans l'annee ? », "
    "pas « quand » ni « quelle surface »."
)

st.progress(
    min(1.0, proba / max(1e-9, float(scores["proba_incendie_suivant"].max()))),
    text=f"Position sur l'echelle nationale (max observe : "
    f"{scores['proba_incendie_suivant'].max() * 100:.1f} %)",
)

# ---------------------------------------------------------------------------
# 3. Ce qui explique ce score
# ---------------------------------------------------------------------------
st.subheader("Ce que le modele a vu sur cette commune")

g1, g2, g3 = st.columns(3)


def encart(titre: str, valeurs: dict) -> None:
    """Petit tableau cle / valeur, toutes les valeurs en texte.

    Melanger des entiers et des chaines dans une meme colonne fait echouer la
    serialisation Arrow utilisee par Streamlit : on formate donc tout en amont.
    """
    st.markdown(f"**{titre}**")
    st.dataframe(
        pd.DataFrame(
            {"valeur": [str(v) for v in valeurs.values()]},
            index=list(valeurs.keys()),
        ),
        height=180,
    )


with g1:
    encart(
        "Historique des feux",
        {
            "Feux sur 5 ans": f"{ligne.get('nb_feux_5a', 0):.0f}",
            "Feux sur 10 ans": f"{ligne.get('nb_feux_10a', 0):.0f}",
            "Surface brulee 10 ans (ha)": f"{ligne.get('surface_10a_ha', 0):.1f}",
            "Part des feux d'ete": f"{ligne.get('part_feux_ete_5a', 0) * 100:.0f} %",
        },
    )

with g2:
    zone = int(ligne.get("cluster_spatial", -1))
    encart(
        "Groupes",
        {
            "Profil KMeans": int(ligne.get("cluster_risque", -1)),
            "Zone DBSCAN": "hors zone dense" if zone < 0 else f"zone {zone}",
            "Decile de risque": (
                "n/a"
                if pd.isna(ligne.get("decile_proba", np.nan))
                else f"{int(ligne['decile_proba']) + 1} / 10"
            ),
        },
    )

with g3:
    encart(
        "Contexte",
        {
            "Population": f"{ligne.get('population', 0):,.0f}".replace(",", " "),
            "Superficie (km2)": f"{ligne.get('superficie_km2', 0):.1f}",
            "Altitude moyenne (m)": f"{ligne.get('altitude_moy', 0):.0f}",
            "Latitude / longitude": (
                f"{ligne.get('latitude', 0):.3f} / {ligne.get('longitude', 0):.3f}"
            ),
        },
    )

# ---------------------------------------------------------------------------
# 4. Historique annuel
# ---------------------------------------------------------------------------
st.subheader("Historique annuel des feux")

historique = donnees.charger_historique()
hist_commune = historique[historique["code_insee"] == code_choisi].sort_values("annee")

if hist_commune.empty or hist_commune["nb_feux"].sum() == 0:
    st.info(
        "Aucun incendie enregistre pour cette commune sur la periode couverte "
        "par la base. Son score provient alors surtout de sa position "
        "geographique et de son groupe."
    )
else:
    h1, h2 = st.columns(2)
    with h1:
        st.markdown("**Nombre de feux par annee**")
        st.bar_chart(hist_commune.set_index("annee")["nb_feux"], height=240)
    with h2:
        st.markdown("**Surface brulee par annee (ha)**")
        st.bar_chart(hist_commune.set_index("annee")["surface_ha"], height=240)

# ---------------------------------------------------------------------------
# 5. Situation dans le departement
# ---------------------------------------------------------------------------
st.subheader(f"Situation dans le departement {ligne['departement']}")

top_dep = meme_dep.nlargest(15, "proba_incendie_suivant")[
    ["code_insee", "nom", "proba_incendie_suivant", "nb_feux_5a", "cluster_risque"]
].copy()
top_dep["proba_incendie_suivant"] = (top_dep["proba_incendie_suivant"] * 100).round(1)
top_dep = top_dep.rename(
    columns={
        "code_insee": "Code INSEE",
        "nom": "Commune",
        "proba_incendie_suivant": "Probabilite (%)",
        "nb_feux_5a": "Feux 5 ans",
        "cluster_risque": "Profil",
    }
)

d1, d2 = st.columns([3, 2])
with d1:
    st.dataframe(top_dep, hide_index=True)
with d2:
    if {"latitude", "longitude"}.issubset(meme_dep.columns):
        carte = meme_dep[["latitude", "longitude"]].dropna()
        if not carte.empty:
            st.map(carte, size=300, zoom=7)

# ---------------------------------------------------------------------------
# 6. Comparaison
# ---------------------------------------------------------------------------
st.subheader("Comparer avec une autre commune")

autres = {c: e for c, e in etiquettes.items() if c != code_choisi}
if autres:
    code_autre = st.selectbox(
        "Commune de comparaison",
        options=list(autres.keys()),
        format_func=lambda c: autres[c],
        key="commune_comparee",
    )
    autre = scores.loc[scores["code_insee"] == code_autre].iloc[0]

    champs = [
        ("Probabilite (%)", "proba_incendie_suivant", 100, 1),
        ("Feux sur 5 ans", "nb_feux_5a", 1, 0),
        ("Feux sur 10 ans", "nb_feux_10a", 1, 0),
        ("Surface brulee 10 ans (ha)", "surface_10a_ha", 1, 1),
        ("Population", "population", 1, 0),
        ("Superficie (km²)", "superficie_km2", 1, 1),
    ]
    comparaison = pd.DataFrame(
        {
            ligne["nom"]: [
                round(float(ligne.get(col, 0)) * fac, dec)
                for _, col, fac, dec in champs
            ],
            autre["nom"]: [
                round(float(autre.get(col, 0)) * fac, dec)
                for _, col, fac, dec in champs
            ],
        },
        index=[libelle for libelle, _, _, _ in champs],
    )
    st.dataframe(comparaison)

# ---------------------------------------------------------------------------
# 7. SHAP local — optionnel, car il faut charger le modele
# ---------------------------------------------------------------------------
st.subheader("Explication detaillee (SHAP)")

poids_modele = donnees.taille_mo(model_run_dir / "model_risque_raw.joblib")
st.caption(
    "Le SHAP local dit quelle variable a pousse le score vers le haut ou vers "
    f"le bas pour cette commune. Il necessite de charger le modele "
    f"({poids_modele:.0f} Mo), ce qui prend quelques secondes la premiere fois."
)

if st.button("Calculer l'explication SHAP de cette commune"):
    donnees.module_optionnel("shap")
    modele = donnees.charger_modele_brut()
    if modele is not None:
        noms = donnees.lire_json_optionnel(model_run_dir / "shap_feature_names.json")
        if noms is None:
            from models.config_pipeline import FEATURE_COLUMNS as noms
        manquantes = [c for c in noms if c not in scores.columns]
        if manquantes:
            st.error(f"Variables absentes de scores_risque.csv : {manquantes}")
        else:
            explainer = donnees.charger_explainer(modele)
            x = ligne[noms].astype(float).to_frame().T
            valeurs = donnees.contribution_classe_positive(explainer.shap_values(x))
            valeurs = np.asarray(valeurs).reshape(-1)[: len(noms)]

            contributions = (
                pd.DataFrame({"variable": noms, "contribution": valeurs})
                .assign(effet=lambda d: np.where(d["contribution"] >= 0, "↑", "↓"))
                .sort_values("contribution", ascending=False)
            )

            s1, s2 = st.columns(2)
            with s1:
                st.markdown("**Ce qui augmente le risque**")
                st.dataframe(
                    contributions[contributions["contribution"] > 0].head(6),
                    hide_index=True,
                )
            with s2:
                st.markdown("**Ce qui le diminue**")
                st.dataframe(
                    contributions[contributions["contribution"] < 0].tail(6),
                    hide_index=True,
                )

            st.bar_chart(
                contributions.set_index("variable")["contribution"],
                height=340,
            )
            st.caption(
                f"Valeur de base du modele : "
                f"{donnees.valeur_attendue(explainer):.4f}. Les contributions "
                "s'ajoutent a cette base pour donner la prediction."
            )
