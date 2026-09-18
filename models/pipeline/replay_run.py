import json
from pathlib import Path
import pandas as pd
import joblib


def replay(run_dir: str):
    run_dir = Path(run_dir)

    print(f"=== REPLAY RUN : {run_dir.name} ===")

    # Recharger les features
    features = pd.read_csv(run_dir / "features_final.csv")
    print(f" - features: {len(features)} lignes")

    # Recharger les artefacts ML
    model_dir = Path("models/run") / run_dir.name
    model = joblib.load(model_dir / "model_risque.joblib")
    print(" - modèle chargé")

    # Recharger le split
    split = json.loads((model_dir / "split_report.json").read_text())
    print(f" - split hash: {split['split_hash']}")

    print("=== REPLAY OK ===")
