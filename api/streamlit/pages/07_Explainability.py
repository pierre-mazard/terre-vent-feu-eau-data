# api/streamlit/pages/07_Explainability.py
"""SHAP global, a partir des valeurs pre-calculees par `shap/compute_shap.py`.

Ce qui a ete retire : `shap_interaction_values()`. Sur une foret de 300 arbres
non bornes, le calcul des interactions est de l'ordre du carre du nombre de
variables multiplie par la taille des arbres — il bloquait l'application a
chaque reexecution. Le dependence plot classique repond a la meme question pour
une fraction du cout.
"""

import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[3]
if str(RACINE) not in sys.path:
    sys.path.insert(0, str(RACINE))

import json  # noqa: E402

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from api.streamlit import donnees  # noqa: E402

st.set_page_config(page_title="Explicabilite", page_icon="🧠", layout="wide")
st.title("🧠 Explicabilite du modele (SHAP)")

_, model_run_dir = donnees.dossiers_run()


@st.cache_data(show_spinner="Chargement des valeurs SHAP…")
def charger_shap(dossier: str, _cle: float):
    d = Path(dossier)
    valeurs = np.load(d / "shap_values.npy", allow_pickle=True)
    attendue = np.load(d / "shap_expected_value.npy", allow_pickle=True)
    noms = json.loads((d / "shap_feature_names.json").read_text(encoding="utf-8"))
    echantillon = pd.read_csv(d / "shap_X_sample.csv")
    return valeurs, attendue, noms, echantillon


for fichier in ("shap_values.npy", "shap_feature_names.json", "shap_X_sample.csv"):
    donnees.exige(
        model_run_dir / fichier,
        f"Le fichier SHAP `{fichier}`",
        "python shap/compute_shap.py",
    )

cle = max(
    (model_run_dir / f).stat().st_mtime
    for f in ("shap_values.npy", "shap_X_sample.csv")
)
valeurs, attendue, noms, echantillon = charger_shap(str(model_run_dir), cle)

valeurs = donnees.contribution_classe_positive(valeurs)
valeurs = np.asarray(valeurs)
if valeurs.ndim == 3:
    valeurs = valeurs[:, :, -1]
valeurs = valeurs[:, : len(noms)]

X = echantillon[noms]
n = min(len(X), valeurs.shape[0])
X, valeurs = X.iloc[:n], valeurs[:n]

st.caption(
    f"Echantillon stratifie par profil de risque : {n} communes, "
    f"{len(noms)} variables. "
    "Un SHAP positif pousse la probabilite vers le haut, un SHAP negatif vers le bas."
)

st.subheader("Importance globale")
importance = (
    pd.DataFrame({"variable": noms, "importance": np.abs(valeurs).mean(axis=0)})
    .sort_values("importance", ascending=False)
    .set_index("variable")
)
st.bar_chart(importance, height=420)
st.dataframe(importance.reset_index(), hide_index=True)

st.subheader("Effet d'une variable selon sa valeur")
variable = st.selectbox("Variable", noms)
i = noms.index(variable)

nuage = pd.DataFrame(
    {variable: X[variable].to_numpy(), "contribution SHAP": valeurs[:, i]}
)
st.scatter_chart(nuage, x=variable, y="contribution SHAP", height=380)

st.subheader("Resume detaille")
st.caption("Graphique SHAP classique : chaque point est une commune de l'echantillon.")
if st.button("Afficher le summary plot"):
    shap = donnees.module_optionnel("shap")

    fig = plt.figure(figsize=(9, 6))
    shap.summary_plot(valeurs, X, feature_names=noms, show=False)
    st.pyplot(fig)
    plt.close(fig)

st.info(
    "L'explication commune par commune se trouve sur la page "
    "**08 · Fiche commune**, en bas, derriere un bouton : elle demande de "
    "charger le modele, ce qui n'est pas necessaire pour le reste."
)
