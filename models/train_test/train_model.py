import json
import joblib
import pandas as pd
from pathlib import Path
from hashlib import sha256

from config import DATA_PROCESSED, MODELS
from models.config_pipeline import ANNEE_FIN, ANNEE_TEST
from models.pipeline.training import train_model
from models.pipeline.score_future import score_future

# Chargement du dernier run
with open(DATA_PROCESSED / "latest_run.json") as f:
    latest = json.load(f)

run_dir = Path(latest["run_dir"])
MODEL_RUN_DIR = MODELS / "run" / run_dir.name
MODEL_RUN_DIR.mkdir(parents=True, exist_ok=True)


def compute_split_report(features: pd.DataFrame) -> dict:
    train = features[features["annee"] < ANNEE_TEST]
    test = features[features["annee"] == ANNEE_TEST]

    report = {
        "annee_test": int(ANNEE_TEST),
        "train_rows": len(train),
        "test_rows": len(test),
        "train_years": sorted(train["annee"].unique().tolist()),
        "test_years": sorted(test["annee"].unique().tolist()),
        "train_communes": int(train["code_insee"].nunique()),
        "test_communes": int(test["code_insee"].nunique()),
    }

    h = sha256()

    concat_train = (
        train["code_insee"]
        .astype(str)
        .str.cat(train["annee"].astype(str))
        .str.cat(sep=",")
    )
    h.update(concat_train.encode())

    concat_test = (
        test["code_insee"]
        .astype(str)
        .str.cat(test["annee"].astype(str))
        .str.cat(sep=",")
    )
    h.update(concat_test.encode())

    report["split_hash"] = h.hexdigest()

    return report


def main():
    print("=== TRAIN MODEL : START ===")

    print(">> Chargement des features finales...")
    features = pd.read_csv(run_dir / "features_final.csv")
    print(f"   - features: {len(features)} lignes")

    split_report = compute_split_report(features)
    (MODEL_RUN_DIR / "split_report.json").write_text(json.dumps(split_report, indent=2))

    print(">> Entraînement du modèle...")
    model_raw, model_calibrated, metrics = train_model(features)
    print("   - modèles entraînés")

    print(">> Scoring futur...")
    scores = score_future(model_calibrated, features)
    print("   - scoring OK")

    print(">> Sauvegarde des artefacts...")
    features.to_csv(MODEL_RUN_DIR / "features_risque.csv", index=False)
    scores.to_csv(MODEL_RUN_DIR / "scores_risque.csv", index=False)

    # Sauvegarde des deux modèles
    joblib.dump(model_raw, MODEL_RUN_DIR / "model_risque_raw.joblib")
    joblib.dump(model_calibrated, MODEL_RUN_DIR / "model_risque.joblib")

    metadata = {
        **metrics,
        "annee_score": int(ANNEE_FIN + 1),
    }
    (MODEL_RUN_DIR / "metadata.json").write_text(json.dumps(metadata, indent=2))

    print("=== TRAIN MODEL : END ===")


if __name__ == "__main__":
    main()
