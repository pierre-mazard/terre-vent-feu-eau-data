# models/pipeline/build_dataset.py
import pandas as pd
from config import DATA_PROCESSED
from models.pipeline.ingestion import load_incendies, load_communes
from models.pipeline.cleaning import clean_incendies, clean_communes
from models.pipeline.features import build_features
from models.pipeline.clustering import add_clusters
from models.pipeline.run_utils import create_run_folder, save_json


def main():
    print("=== BUILD DATASET ===")

    run_dir = create_run_folder()

    # 1. Ingestion
    incendies = load_incendies()
    communes = load_communes()

    # 2. Nettoyage
    incendies_clean, rep_inc = clean_incendies(incendies)
    communes_clean, rep_com = clean_communes(communes)

    # Sauvegarde des CSV nettoyés
    incendies_clean.to_csv(run_dir / "incendies_clean.csv", index=False)
    communes_clean.to_csv(run_dir / "communes_clean.csv", index=False)

    # 3. Construction des features de base
    features_base = build_features(incendies_clean, communes_clean)

    rep_feat = {
        "nb_lignes": len(features_base),
        "colonnes": list(features_base.columns),
        "nb_colonnes": len(features_base.columns),
    }

    # Sauvegarde features_base
    features_base.to_csv(run_dir / "features_base.csv", index=False)

    # 4. Clustering (risque + spatial)
    features_final, rep_clusters = add_clusters(features_base, incendies_clean)

    # Correction des NA pour le pipeline ML
    features_final = features_final.fillna(0)

    # Sauvegarde features_final
    features_final.to_csv(run_dir / "features_final.csv", index=False)

    # 5. Sauvegarde des rapports JSON
    save_json(run_dir, "cleaning_report_incendies", rep_inc)
    save_json(run_dir, "cleaning_report_communes", rep_com)
    save_json(run_dir, "features_report", rep_feat)
    save_json(run_dir, "clustering_report", rep_clusters)
    save_json(
        run_dir,
        "dataset_report",
        {
            "run_dir": str(run_dir),
            "nb_incendies": len(incendies_clean),
            "nb_communes": len(communes_clean),
            "nb_features_base": len(features_base),
            "nb_features_final": len(features_final),
        },
    )

    # Manifest du run
    run_manifest = {
        "run_dir": str(run_dir),
        "timestamp": run_dir.name,
        "nb_incendies": len(incendies_clean),
        "nb_communes": len(communes_clean),
        "nb_features_base": len(features_base),
        "nb_features_final": len(features_final),
        "features_columns": list(features_final.columns),
    }
    save_json(run_dir, "run_manifest", run_manifest)

    # Enregistrer le run courant pour le pipeline ML
    save_json(DATA_PROCESSED, "latest_run", {"run_dir": str(run_dir)})

    print("=== DATASET SAUVEGARDÉ ===")
    print(f"Run folder: {run_dir}")


if __name__ == "__main__":
    main()
