#!/usr/bin/env python
"""Verifie, sauvegarde et restaure les artefacts du projet.

Pourquoi ce script existe
-------------------------
Git versionne le **code**, pas les **donnees**. Le `.gitignore` exclut
`models/run/`, `data/processed/run/`, les fichiers `.joblib` et les gros CSV
bruts : ils ne suivent donc pas les branches. Un aller-retour entre deux
branches peut les laisser intacts... ou les emporter, selon ce que l'outil
Git utilise fait des fichiers non suivis.

Trois commandes :

    python verifier_etat.py                  dit ce qui est present ou manquant
    python verifier_etat.py --sauvegarder    archive les artefacts avant de bouger
    python verifier_etat.py --restaurer <zip>  les remet en place

Lance TOUJOURS `--sauvegarder` avant de changer de branche.
"""

from __future__ import annotations

import argparse
import json
import sys
import zipfile
from datetime import datetime
from pathlib import Path

RACINE = Path(__file__).resolve().parent
DOSSIER_SAUVEGARDES = RACINE / "sauvegardes"

# Ce que Git ne suit pas et qu'il faut donc proteger a la main.
CHEMINS_A_SAUVEGARDER = [
    "data/processed/run",
    "data/processed/latest_run.json",
    "models/run",
    "data/raw",
]


def _couleurs_disponibles() -> bool:
    """Les sequences ANSI ne s'affichent pas partout sous Windows.

    On les active si la console le permet, et on les desactive proprement
    sinon : mieux vaut un affichage sans couleur qu'un affichage parasite par
    des codes d'echappement.
    """
    import os

    if not sys.stdout.isatty():
        return False
    if os.name == "nt":
        try:
            import ctypes

            noyau = ctypes.windll.kernel32
            noyau.SetConsoleMode(noyau.GetStdHandle(-11), 7)
            return True
        except Exception:
            return False
    return True


if _couleurs_disponibles():
    VERT, ROUGE, ORANGE, GRIS, FIN = (
        "\033[92m",
        "\033[91m",
        "\033[93m",
        "\033[90m",
        "\033[0m",
    )
else:
    VERT = ROUGE = ORANGE = GRIS = FIN = ""


def coche(ok: bool) -> str:
    return f"{VERT}OK{FIN}" if ok else f"{ROUGE}MANQUANT{FIN}"


def poids(chemin: Path) -> str:
    if not chemin.exists():
        return "-"
    if chemin.is_dir():
        total = sum(f.stat().st_size for f in chemin.rglob("*") if f.is_file())
    else:
        total = chemin.stat().st_size
    if total > 1024**3:
        return f"{total / 1024**3:.1f} Go"
    if total > 1024**2:
        return f"{total / 1024**2:.0f} Mo"
    return f"{total / 1024:.0f} ko"


def nom_de_run(chemin: str) -> str:
    """Dernier segment d'un chemin, que les separateurs soient / ou \\."""
    return chemin.replace("\\", "/").rstrip("/").split("/")[-1]


def localiser_run() -> tuple[Path | None, Path | None, str]:
    """Retrouve le run courant, meme si latest_run.json est vide ou perime."""
    fichier = RACINE / "data/processed/latest_run.json"
    if not fichier.exists():
        return None, None, "latest_run.json absent"

    texte = fichier.read_text(encoding="utf-8").strip() or "{}"
    try:
        latest = json.loads(texte)
    except json.JSONDecodeError:
        return None, None, "latest_run.json illisible"

    if "run_dir" not in latest:
        return None, None, "latest_run.json sans cle run_dir"

    nom = nom_de_run(str(latest["run_dir"]))
    run_dir = RACINE / "data/processed/run" / nom
    model_dir = RACINE / "models/run" / nom

    if not run_dir.exists() and not model_dir.exists():
        return run_dir, model_dir, f"le run {nom} n'existe plus sur le disque"
    return run_dir, model_dir, nom


# Artefact -> (emplacement, commande qui le regenere, page concernee)
ARTEFACTS = [
    ("features_final.csv", "run", "python -m models.pipeline.build_dataset", "-"),
    ("run_manifest.json", "run", "python -m models.pipeline.build_dataset", "01"),
    ("dataset_report.json", "run", "python -m models.pipeline.build_dataset", "01"),
    ("clustering_report.json", "run", "python -m models.pipeline.build_dataset", "01"),
    ("features_risque.csv", "modeles", "python -m models.train_test.train_model", "08"),
    (
        "scores_risque.csv",
        "modeles",
        "python -m models.train_test.train_model",
        "05 08 09",
    ),
    ("metadata.json", "modeles", "python -m models.train_test.train_model", "03"),
    ("split_report.json", "modeles", "python -m models.train_test.train_model", "01"),
    ("model_risque.joblib", "modeles", "python -m models.train_test.train_model", "-"),
    (
        "model_risque_raw.joblib",
        "modeles",
        "python -m models.train_test.train_model",
        "07 08",
    ),
    (
        "cross_validation_report.json",
        "modeles",
        "python -m models.train_test.cross_validation",
        "02",
    ),
    (
        "comparaison_modeles.json",
        "modeles",
        "python -m models.train_test.comparaison_modeles",
        "10",
    ),
    (
        "horizons_metriques.json",
        "modeles",
        "python -m models.train_test.train_horizons",
        "11",
    ),
    (
        "modele_horizon_10j.json",
        "modeles",
        "python -m models.train_test.train_horizons",
        "11",
    ),
    (
        "modele_horizon_30j.json",
        "modeles",
        "python -m models.train_test.train_horizons",
        "11",
    ),
    (
        "modele_horizon_60j.json",
        "modeles",
        "python -m models.train_test.train_horizons",
        "11",
    ),
    (
        "feux_historique.csv",
        "modeles",
        "python -m models.train_test.train_horizons",
        "11",
    ),
    (
        "panel_horizon.parquet",
        "modeles",
        "python -m models.train_test.train_horizons",
        "11",
    ),
    ("shap_values.npy", "modeles", "python explainability/compute_shap.py", "07"),
    (
        "shap_expected_value.npy",
        "modeles",
        "python explainability/compute_shap.py",
        "07",
    ),
    (
        "shap_feature_names.json",
        "modeles",
        "python explainability/compute_shap.py",
        "07 08",
    ),
    ("shap_X_sample.csv", "modeles", "python explainability/compute_shap.py", "07"),
]


def verifier() -> int:
    print(f"\n{'=' * 78}\n  ETAT DU PROJET\n{'=' * 78}\n")

    run_dir, model_dir, nom = localiser_run()
    if run_dir is None or not (run_dir.exists() or model_dir.exists()):
        print(f"  {ROUGE}Aucun run exploitable{FIN} : {nom}\n")
        print("  Lance d'abord :  python -m models.pipeline.build_dataset\n")
        return 1

    print(f"  Run courant : {nom}")
    print(f"  Donnees     : {run_dir}  ({poids(run_dir)})")
    print(f"  Modeles     : {model_dir}  ({poids(model_dir)})\n")

    print(f"  {'artefact':<32} {'etat':<20} {'taille':>8}   pages")
    print(f"  {'-' * 72}")

    manquantes = {}
    for nom_fichier, emplacement, commande, pages in ARTEFACTS:
        base = run_dir if emplacement == "run" else model_dir
        chemin = base / nom_fichier
        present = chemin.exists()
        if not present:
            manquantes.setdefault(commande, []).append(nom_fichier)
        print(f"  {nom_fichier:<32} {coche(present):<29} {poids(chemin):>8}   {pages}")

    print()
    if not manquantes:
        lancement = "streamlit run api/streamlit/app.py"
        print(f"  {VERT}Tout est en place.{FIN} Lance :  {lancement}\n")
        return 0

    suite = "Commandes a lancer, dans cet ordre :"
    print(f"  {ORANGE}Il manque des artefacts.{FIN} {suite}\n")
    ordre = [
        "python -m models.pipeline.build_dataset",
        "python -m models.train_test.train_model",
        "python -m models.train_test.cross_validation",
        "python -m models.train_test.comparaison_modeles",
        "python -m models.train_test.train_horizons",
        "python explainability/compute_shap.py",
    ]
    for commande in ordre:
        if commande in manquantes:
            fichiers = ", ".join(manquantes[commande][:3])
            suite = " ..." if len(manquantes[commande]) > 3 else ""
            print(f"    {commande}")
            print(f"      {GRIS}-> {fichiers}{suite}{FIN}")
    print()
    return 1


def sauvegarder() -> int:
    DOSSIER_SAUVEGARDES.mkdir(exist_ok=True)
    horodatage = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    archive = DOSSIER_SAUVEGARDES / f"artefacts_{horodatage}.zip"

    fichiers: list[Path] = []
    for relatif in CHEMINS_A_SAUVEGARDER:
        cible = RACINE / relatif
        if not cible.exists():
            continue
        if cible.is_file():
            fichiers.append(cible)
        else:
            fichiers.extend(f for f in cible.rglob("*") if f.is_file())

    if not fichiers:
        print(f"\n  {ORANGE}Rien a sauvegarder : aucun artefact trouve.{FIN}\n")
        return 1

    total = sum(f.stat().st_size for f in fichiers)
    print(f"\n  Archivage de {len(fichiers)} fichiers ({total / 1024**2:.0f} Mo)…")
    print(f"  {GRIS}La compression peut prendre une minute sur les gros CSV.{FIN}\n")

    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=1) as zf:
        for i, fichier in enumerate(fichiers, 1):
            zf.write(fichier, fichier.relative_to(RACINE))
            if i % 20 == 0 or i == len(fichiers):
                print(f"\r  {i}/{len(fichiers)}", end="", flush=True)

    print(f"\n\n  {VERT}Sauvegarde ecrite :{FIN} {archive}")
    print(f"  ({archive.stat().st_size / 1024**2:.0f} Mo)\n")
    print("  Tu peux changer de branche. Au retour :")
    print(f"    python verifier_etat.py --restaurer {archive.name}\n")
    return 0


def restaurer(nom_archive: str) -> int:
    archive = Path(nom_archive)
    if not archive.exists():
        archive = DOSSIER_SAUVEGARDES / nom_archive
    if not archive.exists():
        print(f"\n  {ROUGE}Archive introuvable :{FIN} {nom_archive}\n")
        if DOSSIER_SAUVEGARDES.exists():
            print("  Archives disponibles :")
            for f in sorted(DOSSIER_SAUVEGARDES.glob("*.zip")):
                print(f"    {f.name}  ({f.stat().st_size / 1024**2:.0f} Mo)")
            print()
        return 1

    print(f"\n  Restauration depuis {archive.name}…")
    with zipfile.ZipFile(archive) as zf:
        noms = zf.namelist()
        for i, nom in enumerate(noms, 1):
            zf.extract(nom, RACINE)
            if i % 20 == 0 or i == len(noms):
                print(f"\r  {i}/{len(noms)}", end="", flush=True)

    print(f"\n\n  {VERT}Restauration terminee.{FIN}\n")
    return verifier()


def main() -> int:
    parseur = argparse.ArgumentParser(
        description="Verifie, sauvegarde et restaure les artefacts non versionnes."
    )
    parseur.add_argument(
        "--sauvegarder",
        action="store_true",
        help="archive les artefacts avant de changer de branche",
    )
    parseur.add_argument(
        "--restaurer",
        metavar="ARCHIVE",
        help="remet en place les artefacts d'une archive",
    )
    args = parseur.parse_args()

    if args.sauvegarder:
        return sauvegarder()
    if args.restaurer:
        return restaurer(args.restaurer)
    return verifier()


if __name__ == "__main__":
    sys.exit(main())
