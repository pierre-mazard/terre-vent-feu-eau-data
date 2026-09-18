"""Chargement mutualise et mis en cache des artefacts du dernier run.

Pourquoi ce module existe
-------------------------
Streamlit **reexecute le script entier a chaque interaction** : chaque fois que
l'utilisateur change une commune dans un selecteur, tout le fichier de la page
est rejoue du debut. Sans cache, cela signifiait relire `features_risque.csv`
(157 Mo) et `model_risque_raw.joblib` (730 Mo) a chaque clic : la memoire
saturait et l'application plantait.

Les regles appliquees ici :

* `@st.cache_data`     pour les DataFrames et les JSON (objets serialisables) ;
* `@st.cache_resource` pour le modele et l'explainer SHAP (objets lourds qu'on
  ne veut ni copier ni serialiser) ;
* la cle de cache inclut la date de modification du fichier, donc relancer le
  pipeline invalide automatiquement le cache ;
* `persist="disk"` sur les deux gros CSV : la lecture n'est payee qu'une seule
  fois, meme apres un redemarrage de l'application ;
* aucune fonction ne remonte une exception brute : on affiche un message clair
  et on arrete la page proprement.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st

from config import DATA_PROCESSED, MODELS

# Seuil au-dela duquel on refuse de charger un modele sans confirmation : un
# joblib de plusieurs Go fait tomber l'application sur une machine de bureau.
TAILLE_MODELE_MAX_MO = 600


# ---------------------------------------------------------------------------
# Localisation du run courant
# ---------------------------------------------------------------------------
def _resoudre(chemin: str) -> Path:
    """Retrouve un dossier de run meme si le chemin enregistre ne vaut plus.

    `latest_run.json` contient le chemin **absolu** de la machine qui a lance le
    pipeline. Si le depot est clone ailleurs, ce chemin ne pointe nulle part :
    on retombe alors sur le dossier de meme nom sous `data/processed/run/`.
    """
    p = Path(chemin)
    if p.exists():
        return p
    # Sous Linux, Path() ne reconnait pas l'antislash comme separateur : le
    # chemin Windows entier se retrouverait dans `.name`. On normalise a la main.
    nom = chemin.replace("\\", "/").rstrip("/").split("/")[-1]
    candidat = DATA_PROCESSED / "run" / nom
    if candidat.exists():
        return candidat
    return p


def _dernier_run_sur_disque() -> Path | None:
    dossier = DATA_PROCESSED / "run"
    if not dossier.exists():
        return None
    runs = sorted(d for d in dossier.iterdir() if d.is_dir())
    return runs[-1] if runs else None


def _arret(titre: str, remede: str) -> None:
    st.error(titre)
    st.info(remede)
    st.stop()


def dossiers_run() -> tuple[Path, Path]:
    """Renvoie (dossier du run de donnees, dossier du run de modeles)."""
    fichier = DATA_PROCESSED / "latest_run.json"

    run_dir: Path | None = None
    if fichier.exists():
        texte = fichier.read_text(encoding="utf-8").strip()
        if texte:
            try:
                latest = json.loads(texte)
            except json.JSONDecodeError:
                latest = {}
            if isinstance(latest, dict) and latest.get("run_dir"):
                run_dir = _resoudre(str(latest["run_dir"]))

    # Filet de securite : latest_run.json absent, vide ou sans cle "run_dir".
    if run_dir is None or not run_dir.exists():
        run_dir = _dernier_run_sur_disque()

    if run_dir is None:
        _arret(
            "Aucun run du pipeline n'a ete trouve.",
            "Lance d'abord la construction du jeu de donnees :\n\n"
            "`python -m models.pipeline.build_dataset`\n\n"
            "puis l'entrainement :\n\n"
            "`python -m models.train_test.train_model`",
        )

    return run_dir, MODELS / "run" / run_dir.name


def exige(chemin: Path, quoi: str, commande: str) -> Path:
    """Verifie qu'un artefact existe, sinon arrete la page avec un message utile."""
    if not chemin.exists():
        _arret(
            f"{quoi} est introuvable.\n\nAttendu ici : `{chemin}`",
            f"Regenere-le avec :\n\n`{commande}`",
        )
    return chemin


def _mtime(chemin: Path) -> float:
    """Date de modification, utilisee comme cle de cache."""
    try:
        return chemin.stat().st_mtime
    except OSError:
        return 0.0


def taille_mo(chemin: Path) -> float:
    try:
        return chemin.stat().st_size / (1024 * 1024)
    except OSError:
        return 0.0


# ---------------------------------------------------------------------------
# Chargeurs mis en cache
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner="Chargement des scores…", persist="disk")
def _lire_scores(chemin: str, _cle: float) -> pd.DataFrame:
    df = pd.read_csv(chemin, low_memory=False)
    # Le code INSEE est numerique dans le CSV : "01001" devient 1001, et le
    # departement lu sur les deux premiers caracteres devient faux.
    df["code_insee"] = df["code_insee"].astype(str).str.replace(r"\.0$", "", regex=True)
    df["code_insee"] = df["code_insee"].str.zfill(5)
    df["departement"] = df["code_insee"].str[:2]
    if "nom" in df.columns:
        df["nom"] = df["nom"].fillna("(sans nom)").astype(str)
    else:
        df["nom"] = df["code_insee"]
    return df


def charger_scores() -> pd.DataFrame:
    """Un enregistrement par commune pour l'annee de scoring (~9 Mo)."""
    _, model_run_dir = dossiers_run()
    chemin = exige(
        model_run_dir / "scores_risque.csv",
        "Le fichier des scores `scores_risque.csv`",
        "python -m models.train_test.train_model",
    )
    return _lire_scores(str(chemin), _mtime(chemin))


@st.cache_data(show_spinner="Chargement de l'historique…", persist="disk")
def _lire_historique(chemin: str, _cle: float) -> pd.DataFrame:
    # On ne lit que 5 colonnes sur 30 : le fichier fait 157 Mo, on en garde
    # environ 25 Mo en memoire au lieu de plus de 600 Mo.
    colonnes = ["code_insee", "annee", "nb_feux", "surface_ha", "surface_foret_ha"]
    df = pd.read_csv(chemin, usecols=colonnes, low_memory=False)
    df["code_insee"] = df["code_insee"].astype(str).str.replace(r"\.0$", "", regex=True)
    df["code_insee"] = df["code_insee"].str.zfill(5)
    df["annee"] = df["annee"].astype("int16")
    for col in ("nb_feux", "surface_ha", "surface_foret_ha"):
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype("float32")
    return df


def charger_historique() -> pd.DataFrame:
    """Serie annuelle par commune, en 5 colonnes seulement."""
    run_dir, model_run_dir = dossiers_run()
    chemin = model_run_dir / "features_risque.csv"
    if not chemin.exists():
        chemin = run_dir / "features_final.csv"
    chemin = exige(
        chemin,
        "Le fichier des variables (`features_risque.csv` ou `features_final.csv`)",
        "python -m models.pipeline.build_dataset",
    )
    return _lire_historique(str(chemin), _mtime(chemin))


@st.cache_data(show_spinner=False)
def _lire_json(chemin: str, _cle: float) -> dict:
    return json.loads(Path(chemin).read_text(encoding="utf-8"))


def charger_json(chemin: Path, quoi: str, commande: str) -> dict:
    chemin = exige(chemin, quoi, commande)
    return _lire_json(str(chemin), _mtime(chemin))


def lire_json_optionnel(chemin: Path) -> dict | None:
    if not chemin.exists():
        return None
    return _lire_json(str(chemin), _mtime(chemin))


# ---------------------------------------------------------------------------
# Modele et SHAP : @st.cache_resource, jamais @st.cache_data
# ---------------------------------------------------------------------------
@st.cache_resource(show_spinner="Chargement du modele…")
def _charger_modele(chemin: str, _cle: float):
    import joblib

    return joblib.load(chemin)


def charger_modele_brut(forcer: bool = False):
    """Charge `model_risque_raw.joblib`, avec un garde-fou sur la taille.

    `@st.cache_resource` garde l'objet en memoire et le partage entre les
    reexecutions : le modele n'est lu qu'une seule fois par session.
    `@st.cache_data` serait ici une erreur, car il serialiserait le modele a
    chaque appel.
    """
    _, model_run_dir = dossiers_run()
    chemin = exige(
        model_run_dir / "model_risque_raw.joblib",
        "Le modele brut `model_risque_raw.joblib`",
        "python -m models.train_test.train_model",
    )
    poids = taille_mo(chemin)
    if poids > TAILLE_MODELE_MAX_MO and not forcer:
        st.warning(
            f"Le modele pese **{poids / 1024:.1f} Go**. Le charger va saturer la "
            "memoire et faire tomber l'application.\n\n"
            "Cause : l'entrainement ne borne plus la profondeur des arbres "
            "(`max_depth`) et calibre sans `cv`. Corrige "
            "`models/pipeline/training.py`, relance l'entrainement, et le "
            "modele retombera autour de 100 Mo."
        )
        return None
    return _charger_modele(str(chemin), _mtime(chemin))


@st.cache_resource(show_spinner="Preparation de l'explainer SHAP…")
def charger_explainer(_modele):
    import shap

    return shap.TreeExplainer(_modele)


def contribution_classe_positive(valeurs_shap):
    """Isole la contribution de la classe 1, quelle que soit la version de shap."""
    if isinstance(valeurs_shap, list):
        return valeurs_shap[1]
    if getattr(valeurs_shap, "ndim", 0) == 3:
        return valeurs_shap[..., 1]
    return valeurs_shap


def valeur_attendue(explainer):
    import numpy as np

    v = explainer.expected_value
    if isinstance(v, (list, np.ndarray)):
        return float(np.ravel(v)[-1])
    return float(v)


def module_optionnel(nom: str, paquet: str | None = None):
    """Importe une dependance facultative, ou arrete la page avec un message clair.

    `xgboost` et `shap` ne sont pas installes par defaut avec Streamlit. Sans ce
    garde-fou, l'utilisateur recoit une traceback Python de quinze lignes au
    lieu de la seule information utile : la commande a taper.
    """
    import importlib

    try:
        return importlib.import_module(nom)
    except ImportError:
        _arret(
            f"La bibliotheque **{nom}** n'est pas installee dans cet environnement.",
            "Installe-la puis relance l'application :\n\n"
            f"`pip install {paquet or nom}`\n\n"
            "Toutes les dependances du projet sont dans `requirements.txt` :\n\n"
            "`pip install -r requirements.txt`",
        )
