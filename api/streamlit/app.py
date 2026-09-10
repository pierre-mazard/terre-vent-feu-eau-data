"""Application Streamlit de cartographie et d'analyse historique."""

import sys
from pathlib import Path

import pandas as pd
import streamlit as st
from sqlalchemy import text

# Le module est lance depuis Streamlit ou le debogueur, avec des repertoires
# courants differents. On ajoute explicitement le dossier qui contient config.py.
RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "data" / "ingestion_pipeline"))

from config import get_engine  # noqa: E402


@st.cache_resource
def moteur():
    """Cree la connexion UNE fois pour toute la session Streamlit."""
    return get_engine()


@st.cache_data(ttl=3600)
def charger_incendies() -> pd.DataFrame:
    requete = text(
        """
        SELECT f.fire_id, f.annee, f.numero, f.departement, f.code_insee,
               f.nom_commune, f.date_alerte, f.mois, f.surface_parcourue_ha,
               f.surface_foret_ha, f.surface_maquis_ha,
               f.surface_agricole_ha, f.nature, f.is_geocoded,
               c.nom AS commune_ref, c.latitude, c.longitude, c.reg_code
        FROM fires f
        LEFT JOIN ref_communes c ON c.code_insee = f.code_insee
        ORDER BY f.annee, f.numero
        """
    )
    with moteur().connect() as conn:
        donnees = pd.read_sql(requete, conn)
    donnees["date_alerte"] = pd.to_datetime(
        donnees["date_alerte"], errors="coerce"
    )
    donnees["nature_affichage"] = donnees["nature"].fillna("Non renseignee")
    donnees["saison"] = donnees["mois"].map(
        {
            12: "Hiver", 1: "Hiver", 2: "Hiver",
            3: "Printemps", 4: "Printemps", 5: "Printemps",
            6: "Ete", 7: "Ete", 8: "Ete",
            9: "Automne", 10: "Automne", 11: "Automne",
        }
    )
    donnees["vegetation"] = _categorie_vegetation(donnees)
    return donnees


def _categorie_vegetation(donnees: pd.DataFrame) -> pd.Series:
    categories = pd.Series("Autres / non renseignee", index=donnees.index)
    foret = donnees["surface_foret_ha"].fillna(0) > 0
    maquis = donnees["surface_maquis_ha"].fillna(0) > 0
    agricole = donnees["surface_agricole_ha"].fillna(0) > 0
    categories.loc[foret] = "Foret"
    categories.loc[maquis & ~foret] = "Maquis / garrigues"
    categories.loc[agricole & ~foret & ~maquis] = "Agricole"
    return categories


def main() -> None:
    st.set_page_config(
        page_title="Terre, Vent, Feu, Eau, Data",
        page_icon="🔥",
        layout="wide",
    )
    st.title("Terre, Vent, Feu, Eau, Data")
    st.caption("Surveillance des risques de feux de foret en France")

    onglet_carte, onglet_prediction, onglet_methodo = st.tabs(
        ["Cartographie & historique", "Prediction du risque", "Methodologie"]
    )

    with onglet_carte:
        st.subheader("Cartographie et analyse historique")
        try:
            donnees = charger_incendies()
        except Exception as erreur:
            st.error(f"Base de donnees injoignable : {erreur}")
            st.stop()

        annees = sorted(donnees["annee"].dropna().astype(int).unique())
        saisons = ["Hiver", "Printemps", "Ete", "Automne"]
        departements = sorted(donnees["departement"].dropna().unique())
        natures = sorted(donnees["nature_affichage"].unique())
        surfaces = donnees["surface_parcourue_ha"].dropna()
        surface_max = max(float(surfaces.max()), 1.0) if not surfaces.empty else 1.0

        with st.sidebar:
            st.header("Filtres historiques")
            periode = st.slider(
                "Periode", min(annees), max(annees), (min(annees), max(annees))
            )
            mois = st.multiselect("Mois", list(range(1, 13)), default=list(range(1, 13)))
            saison = st.multiselect("Saison", saisons, default=saisons)
            departement = st.multiselect("Departement", departements)
            nature = st.multiselect("Nature", natures)
            vegetation = st.multiselect(
                "Vegetation dominante", sorted(donnees["vegetation"].unique())
            )
            surface_min = st.slider(
                "Surface minimale (ha)", 0.0, surface_max, 0.0, step=0.1
            )

        filtre = donnees["annee"].between(*periode)
        filtre &= donnees["mois"].isin(mois)
        filtre &= donnees["saison"].isin(saison)
        if departement:
            filtre &= donnees["departement"].isin(departement)
        if nature:
            filtre &= donnees["nature_affichage"].isin(nature)
        if vegetation:
            filtre &= donnees["vegetation"].isin(vegetation)
        filtre &= donnees["surface_parcourue_ha"].fillna(0).ge(surface_min)
        selection = donnees.loc[filtre].copy()

        metriques = st.columns(4)
        metriques[0].metric("Incendies", f"{len(selection):,}".replace(",", " "))
        metriques[1].metric(
            "Surface parcourue",
            f"{selection['surface_parcourue_ha'].sum():,.0f} ha".replace(",", " "),
        )
        metriques[2].metric(
            "Surface moyenne",
            f"{selection['surface_parcourue_ha'].mean():,.2f} ha".replace(",", " "),
        )
        metriques[3].metric(
            "Communes geocodees",
            f"{selection['is_geocoded'].mean():.1%}" if not selection.empty else "0.0%",
        )

        if selection.empty:
            st.info("Aucun incendie ne correspond aux filtres selectionnes.")
            return

        annuel = selection.groupby("annee", as_index=True).agg(
            incendies=("fire_id", "count"),
            surface_ha=("surface_parcourue_ha", "sum"),
        )
        gauche, droite = st.columns(2)
        with gauche:
            st.subheader("Evolution du nombre de feux")
            st.line_chart(annuel["incendies"])
        with droite:
            st.subheader("Evolution des surfaces")
            st.line_chart(annuel["surface_ha"])

        carte = selection.dropna(subset=["latitude", "longitude"])[
            ["latitude", "longitude", "surface_parcourue_ha"]
        ].copy()
        if not carte.empty:
            carte["surface_visuelle"] = (
                carte["surface_parcourue_ha"].fillna(0).clip(lower=1).pow(0.5) * 3
            )
            st.subheader("Localisation des incendies")
            st.caption(
                "La taille des points represente la surface parcourue, selon une echelle racine carree."
            )
            st.map(carte, latitude="latitude", longitude="longitude", size="surface_visuelle")

        st.subheader("Departements les plus representes")
        classement = (
            selection.groupby("departement", dropna=False)
            .agg(incendies=("fire_id", "count"), surface_ha=("surface_parcourue_ha", "sum"))
            .sort_values("incendies", ascending=False)
        )
        st.dataframe(classement.head(15), use_container_width=True)

    with onglet_prediction:
        st.subheader("Prediction du risque par commune")
        st.info("Le modele de risque et les features seront construits au jour 4.")

    with onglet_methodo:
        st.subheader("Methodologie")
        st.markdown(
            "L'onglet historique exploite la table `fires` enrichie par le "
            "referentiel communal. Les feux non geocodes restent dans les "
            "statistiques, mais ne sont pas affiches sur la carte."
        )


if __name__ == "__main__":
    main()
