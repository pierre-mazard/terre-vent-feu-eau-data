# api/streamlit/app.py

import sys
from pathlib import Path

# Maintenant on peut importer api, config, models
from api.streamlit.bootstrap import ROOT
import streamlit as st

st.set_page_config(
    page_title="TVFE - Risque incendie",
    page_icon="🔥",
    layout="wide",
)

st.sidebar.title("Navigation")
st.sidebar.markdown("TVFE - Terre Vent Feu Eau")

st.title("TVFE - Risque incendie")
st.markdown("""
Application Streamlit pour explorer :
- le dataset,
- les performances du modèle,
- la validation croisée,
- les scores de risque par commune.
""")

st.markdown("Utilise le dernier run du pipeline ML (latest_run.json).")
