"""
Diagnostic complet de la base SQL, de l’ingestion et des features.
Permet d’identifier pourquoi les colonnes sont à 0 dans features_base.csv et features_final.csv.
"""

import pandas as pd
from sqlalchemy import text
from config import get_engine
from pathlib import Path

DATA_DIR = Path("data/processed/run")


def check_sql_tables():
    print("\n=== 1. Vérification des tables SQL ===")

    with get_engine().connect() as conn:
        # Vérifier si la table fires contient des données
        df = pd.read_sql(text("SELECT COUNT(*) AS n FROM fires"), conn)
        print(f"Table fires : {df['n'].iloc[0]} lignes")

        df = pd.read_sql(text("SELECT COUNT(*) AS n FROM ref_communes"), conn)
        print(f"Table ref_communes : {df['n'].iloc[0]} lignes")

        # Vérifier les années disponibles
        df = pd.read_sql(
            text(
                "SELECT annee, COUNT(*) AS n FROM fires GROUP BY annee ORDER BY annee"
            ),
            conn,
        )
        print("\nAnnées disponibles dans fires :")
        print(df)

        # Vérifier les colonnes disponibles dans fires
        df_cols = pd.read_sql(text("SELECT * FROM fires LIMIT 1"), conn)
        print("\nColonnes dans fires :")
        print(list(df_cols.columns))


def check_ingestion():
    print("\n=== 2. Vérification de l’ingestion ===")

    from models.pipeline.ingestion import load_incendies, load_communes

    incendies = load_incendies()
    communes = load_communes()

    print(f"Incendies chargés : {len(incendies)} lignes")
    print(f"Communes chargées : {len(communes)} lignes")

    print("\nColonnes incendies :")
    print(list(incendies.columns))

    print("\nColonnes communes :")
    print(list(communes.columns))

    # Vérifier si les surfaces sont toutes à 0
    surface_cols = [c for c in incendies.columns if "surface" in c]
    print("\nSurfaces dans incendies (moyennes) :")
    print(incendies[surface_cols].mean())


def check_features_base(run_dir):
    print("\n=== 3. Vérification de features_base.csv ===")

    base_path = run_dir / "features_base.csv"
    if not base_path.exists():
        print("features_base.csv introuvable")
        return

    df = pd.read_csv(base_path)
    print(f"features_base.csv : {len(df)} lignes")

    # Vérifier les colonnes critiques
    cols = [
        "nb_feux",
        "surface_ha",
        "surface_foret_ha",
        "surface_maquis_ha",
        "surface_autres_nat_ha",
        "surface_agricole_ha",
        "surface_autres_ha",
        "nb_deces",
        "nb_bat_detruits",
        "nb_bat_partiels",
    ]

    print("\nMoyennes des colonnes critiques :")
    print(df[cols].mean())

    # Vérifier si toutes les valeurs sont à 0
    print("\nPourcentage de zéros par colonne :")
    print((df[cols] == 0).mean())


def check_features_final(run_dir):
    print("\n=== 4. Vérification de features_final.csv ===")

    final_path = run_dir / "features_final.csv"
    if not final_path.exists():
        print("features_final.csv introuvable")
        return

    df = pd.read_csv(final_path)
    print(f"features_final.csv : {len(df)} lignes")

    # Vérifier les colonnes temporelles
    temporal_cols = [
        "nb_feux_5a",
        "surface_5a_ha",
        "surface_foret_5a_ha",
        "nb_feux_10a",
        "surface_10a_ha",
        "surface_moyenne_5a_ha",
        "part_feux_ete_5a",
    ]

    print("\nMoyennes des colonnes temporelles :")
    print(df[temporal_cols].mean())

    print("\nPourcentage de zéros dans les colonnes temporelles :")
    print((df[temporal_cols] == 0).mean())

    # Vérifier la cible
    print("\nDistribution de la cible :")
    print(df["cible_incendie_suivant"].value_counts())


def main():
    print("=== DIAGNOSTIC PIPELINE ML ===")

    # Charger latest_run.json
    latest_path = Path("data/processed/latest_run.json")
    if not latest_path.exists():
        print("latest_run.json introuvable")
        return

    import json

    with open(latest_path) as f:
        latest = json.load(f)

    run_dir = Path(latest["run_dir"])

    check_sql_tables()
    check_ingestion()
    check_features_base(run_dir)
    check_features_final(run_dir)

    print("\n=== FIN DU DIAGNOSTIC ===")


if __name__ == "__main__":
    main()
