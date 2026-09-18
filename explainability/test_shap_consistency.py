import numpy as np
import pandas as pd
import json
from pathlib import Path
from config import MODELS, DATA_PROCESSED


def test_shap_consistency():
    with open(DATA_PROCESSED / "latest_run.json") as f:
        latest = json.load(f)

    run_dir = Path(latest["run_dir"])
    model_run_dir = MODELS / "run" / run_dir.name

    shap_values = np.load(model_run_dir / "shap_values.npy", allow_pickle=True)
    feature_cols = json.loads((model_run_dir / "shap_feature_names.json").read_text())
    X = pd.read_csv(model_run_dir / "shap_X_sample.csv")[feature_cols]

    print("SHAP shape:", shap_values.shape)
    print("X shape:", X.shape)

    assert shap_values.shape[0] == X.shape[0], "Mismatch: SHAP rows != X rows"
    assert shap_values.shape[1] == X.shape[1], "Mismatch: SHAP columns != X columns"

    print("✔ SHAP cohérent avec le modèle.")


if __name__ == "__main__":
    test_shap_consistency()
