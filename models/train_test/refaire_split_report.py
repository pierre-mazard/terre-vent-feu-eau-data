"""Regenere uniquement `split_report.json`, sans reentrainer le modele.

A lancer une seule fois, apres le correctif de `compute_split_report()` :

    python -m models.train_test.refaire_split_report

Le rapport ecrit avant ce correctif annoncait un entrainement 2006-2022 alors
que `training.py` demarre en 2011. Le modele lui-meme est correct : seul le
rapport mentait. Relire `features_final.csv` et recalculer le rapport prend
une trentaine de secondes, contre une dizaine de minutes pour un
reentrainement complet — inutile ici.
"""

import json

import pandas as pd

from models.train_test.train_model import (
    MODEL_RUN_DIR,
    compute_split_report,
    run_dir,
)


def main() -> None:
    chemin_rapport = MODEL_RUN_DIR / "split_report.json"

    ancien = None
    if chemin_rapport.exists():
        ancien = json.loads(chemin_rapport.read_text())

    print(f">> Lecture de {run_dir / 'features_final.csv'} ...")
    features = pd.read_csv(
        run_dir / "features_final.csv",
        usecols=["code_insee", "annee"],
        low_memory=False,
    )
    print(f"   - {len(features)} lignes lues")

    rapport = compute_split_report(features)
    chemin_rapport.write_text(json.dumps(rapport, indent=2))

    print()
    if ancien:
        annees = ancien.get("train_years") or []
        if annees:
            lignes = ancien.get("train_rows")
            print(f"  AVANT : {annees[0]}-{annees[-1]}  ({lignes} lignes)")

    annees = rapport["train_years"]
    print(f"  APRES : {annees[0]}-{annees[-1]}  ({rapport['train_rows']} lignes)")
    print()
    print(f"  Ecrit : {chemin_rapport}")


if __name__ == "__main__":
    main()
