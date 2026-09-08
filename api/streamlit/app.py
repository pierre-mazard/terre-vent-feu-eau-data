"""Application Streamlit -- squelette.

Lancement :
    streamlit run api/streamlit/app.py      (ou : make run-streamlit)

Ce fichier pose la structure a deux onglets demandee par le sujet. Le contenu
sera rempli aux jours 3 et 4 du projet. Il existe des maintenant pour deux
raisons : la CI verifie que api/streamlit/*.py compile, et le makefile pointe
vers ce chemin.
"""

import sys
from pathlib import Path

import streamlit as st
from sqlalchemy import text

# le pipeline expose la connexion a la base ; on ajoute son dossier au chemin
RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "data" / "ingestion_pipeline"))

from config import get_engine  # noqa: E402


@st.cache_resource
def moteur():
    """Cree la connexion UNE fois pour toute la session Streamlit."""
    return get_engine()


@st.cache_data(ttl=3600)
def compter_incendies() -> int:
    with moteur().connect() as conn:
        return conn.execute(text("SELECT count(*) FROM fires")).scalar_one()


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
            st.metric("Incendies en base", f"{compter_incendies():,}".replace(",", " "))
        except Exception as e:  # base non demarree : on le dit sans planter
            st.warning(f"Base de donnees injoignable : {e}")
        st.info("Carte, filtres et statistiques : a construire (jour 3).")

    with onglet_prediction:
        st.subheader("Prediction du risque par commune")
        st.info("Modele et interface predictive : a construire (jour 4).")

    with onglet_methodo:
        st.subheader("Methodologie")
        st.markdown("Voir `docs/METHODOLOGIE.md` et `docs/DOSSIER_PROJET.md`.")


if __name__ == "__main__":
    main()
