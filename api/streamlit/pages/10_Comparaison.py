# api/streamlit/pages/10_Comparaison.py
"""Comparaison chiffree des trois familles de modeles."""

import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[3]
if str(RACINE) not in sys.path:
    sys.path.insert(0, str(RACINE))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from api.streamlit import donnees  # noqa: E402

st.set_page_config(page_title="Comparaison des modeles", page_icon="⚖️", layout="wide")
st.title("⚖️ Quel modele choisir ?")

_, model_run_dir = donnees.dossiers_run()
rapport = donnees.charger_json(
    model_run_dir / "comparaison_modeles.json",
    "Le rapport de comparaison `comparaison_modeles.json`",
    "python -m models.train_test.comparaison_modeles",
)

protocole = rapport["protocole"]
st.caption(
    f"Meme decoupage pour les trois : entrainement {protocole['annees_entrainement']}, "
    f"test {protocole['annee_test']} · {protocole['lignes_entrainement']:,} lignes "
    f"d'entrainement · {len(protocole['variables'])} variables · "
    f"{protocole['calibration']}".replace(",", " ")
)

modeles = rapport["modeles"]
tableau = pd.DataFrame(modeles).T

meilleur = max(modeles, key=lambda k: modeles[k]["pr_auc"])
reference = modeles.get("Regression logistique", {}).get("pr_auc")

st.subheader("Le verdict")
colonnes = st.columns(len(modeles))
for col, (nom, m) in zip(colonnes, modeles.items()):
    ecart = ""
    if reference and nom != "Regression logistique":
        ecart = f"{(m['pr_auc'] / reference - 1) * 100:+.0f} % vs logistique"
    col.metric(
        nom,
        f"{m['pr_auc']:.3f}",
        ecart or None,
        help="PR-AUC sur le test temporel : plus c'est haut, mieux c'est.",
    )
    col.caption(
        f"soit **{m['gain_sur_le_hasard']:.1f}×** le hasard · "
        f"entraine en {m['duree_entrainement_s']:.0f} s"
    )

st.success(
    f"**{meilleur}** obtient la meilleure PR-AUC. "
    "La regression logistique sert de plancher : elle montre ce qu'on obtient "
    "sans interaction entre variables, et donc ce que les modeles a arbres "
    "apportent reellement."
)

st.subheader("Toutes les metriques")
affichage = pd.DataFrame(
    {
        "PR-AUC": tableau["pr_auc"].astype(float).round(4),
        "Gain sur le hasard": tableau["gain_sur_le_hasard"].astype(float).round(1),
        "ROC-AUC": tableau["roc_auc"].astype(float).round(4),
        "Brier": tableau["brier_score"].astype(float).round(4),
        "Precision top 5 % (%)": (
            tableau["precision_top_5pct"].astype(float) * 100
        ).round(1),
        "Rappel top 5 % (%)": (tableau["rappel_top_5pct"].astype(float) * 100).round(1),
        "Entrainement (s)": tableau["duree_entrainement_s"].astype(float).round(0),
    }
)
st.dataframe(affichage)

g1, g2 = st.columns(2)
with g1:
    st.markdown("**PR-AUC** — la mesure principale")
    st.bar_chart(affichage["PR-AUC"], height=280)
with g2:
    st.markdown("**Rappel au top 5 %** — la traduction operationnelle")
    st.bar_chart(affichage["Rappel top 5 % (%)"], height=280)

st.subheader("Comment lire ces chiffres")
st.markdown(f"""
- **PR-AUC** : le plancher n'est pas 0,5 mais le taux de communes qui brulent,
  ici **{protocole['taux_positifs_test']:.4f}**. Un modele a 0,33 est donc a
  environ **13 fois** le hasard, pas a « un tiers de la note maximale ».
- **Precision au top 5 %** : parmi les communes designees, la part qui a
  reellement brule.
- **Rappel au top 5 %** : parmi les communes qui ont brule, la part qui avait
  ete designee. Meme numerateur que la precision, denominateur different :
  confondre les deux divise le chiffre annonce par deux.
- **Brier** : qualite de la calibration. Une probabilite annoncee a 30 % doit
  correspondre a 30 % de cas reels, sinon elle ne sert a rien pour decider.
- **Duree d'entrainement** : a performance comparable, un modele cinq fois plus
  rapide se reentraine cinq fois plus souvent.
""")

st.subheader("Ce que chaque famille apporte")
st.markdown("""
| Modele | Principe | Ce qu'il capte | Limite |
|---|---|---|---|
| Regression logistique | somme ponderee des variables | les effets simples et monotones | aucune interaction, aucun seuil |
| Random Forest | des centaines d'arbres tires au hasard, moyennes | seuils et interactions, robuste au bruit | lourde, lente a entrainer |
| XGBoost | des arbres construits l'un apres l'autre, chacun corrigeant le precedent | idem, avec une regularisation plus fine | plus sensible au reglage |
""")
