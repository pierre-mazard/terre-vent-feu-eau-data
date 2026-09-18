"""
Validation croisée temporelle et géographique.
"""

import numpy as np
import pandas as pd
import json
from pathlib import Path
from sklearn.ensemble import RandomForestClassifier
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import (
    roc_auc_score,
    average_precision_score,
    balanced_accuracy_score,
    brier_score_loss,
)

from models.config_pipeline import FEATURE_COLUMNS, ANNEE_TEST
from models.pipeline.utils import log_event
from config import MODELS, DATA_PROCESSED


def compute_metrics(y_true, proba, preds):
    return {
        "roc_auc": float(roc_auc_score(y_true, proba)),
        "pr_auc": float(average_precision_score(y_true, proba)),
        "balanced_accuracy": float(balanced_accuracy_score(y_true, preds)),
        "brier_score": float(brier_score_loss(y_true, proba)),
    }


def temporal_cv(features):
    log_event("temporal_cv_start")

    fold_results = []

    for year in range(2011, ANNEE_TEST):
        train = features[features["annee"] < year]
        test = features[features["annee"] == year]

        X_train = train[FEATURE_COLUMNS].fillna(0)
        y_train = train["cible_incendie_suivant"]

        X_test = test[FEATURE_COLUMNS].fillna(0)
        y_test = test["cible_incendie_suivant"]

        base = RandomForestClassifier(
            n_estimators=150,
            max_depth=12,
            min_samples_leaf=3,
            class_weight="balanced",
            random_state=42,
            n_jobs=-1,
        )

        model = CalibratedClassifierCV(base, method="sigmoid", cv=3)
        model.fit(X_train, y_train)

        proba = model.predict_proba(X_test)[:, 1]
        preds = (proba >= 0.5).astype(int)

        seuil_top5 = np.quantile(proba, 0.95)
        vrais_top5 = y_test[proba >= seuil_top5]

        metrics = compute_metrics(y_test, proba, preds)
        metrics["rappel_top_5pct"] = (
            float(vrais_top5.mean()) if len(vrais_top5) else 0.0
        )

        fold_results.append(
            {
                "annee": year,
                **metrics,
            }
        )

    df = pd.DataFrame(fold_results)

    summary = {
        "folds": fold_results,
        "mean": df.mean(numeric_only=True).to_dict(),
        "std": df.std(numeric_only=True).to_dict(),
    }

    log_event("temporal_cv_end", results=summary)
    return summary


def geographic_cv(features):
    log_event("geographic_cv_start")

    train = features[features["annee"] < ANNEE_TEST]
    test = features[features["annee"] == ANNEE_TEST]

    communes = train["code_insee"].drop_duplicates().tolist()
    rng = np.random.default_rng(42)
    rng.shuffle(communes)

    split = int(len(communes) * 0.8)
    train_codes = set(communes[:split])
    test_codes = set(communes[split:])

    train_geo = train[train["code_insee"].isin(train_codes)]
    test_geo = test[test["code_insee"].isin(test_codes)]

    X_train = train_geo[FEATURE_COLUMNS].fillna(0)
    y_train = train_geo["cible_incendie_suivant"]

    X_test = test_geo[FEATURE_COLUMNS].fillna(0)
    y_test = test_geo["cible_incendie_suivant"]

    base = RandomForestClassifier(
        n_estimators=150,
        max_depth=12,
        min_samples_leaf=3,
        class_weight="balanced",
        random_state=42,
        n_jobs=-1,
    )

    model = CalibratedClassifierCV(base, method="sigmoid", cv=3)
    model.fit(X_train, y_train)

    proba = model.predict_proba(X_test)[:, 1]
    preds = (proba >= 0.5).astype(int)

    result = {
        "communes_test_geo": len(test_codes),
        **compute_metrics(y_test, proba, preds),
    }

    log_event("geographic_cv_end", result=result)
    return result


def main():
    """Point d'entrée appelé par le Makefile."""
    with open(DATA_PROCESSED / "latest_run.json") as f:
        latest = json.load(f)

    run_dir = Path(latest["run_dir"])
    model_run_dir = MODELS / "run" / run_dir.name

    # Charger les features finales (déjà clusterisées)
    features = pd.read_csv(run_dir / "features_final.csv")

    # IMPORTANT : ne pas recalculer les clusters ici
    # Ils sont déjà présents dans features_final.csv

    temporal = temporal_cv(features)
    geographic = geographic_cv(features)

    report = {
        "temporal_cv": temporal,
        "geographic_cv": geographic,
    }

    (model_run_dir / "cross_validation_report.json").write_text(
        json.dumps(report, indent=2)
    )

    print("Validation croisée sauvegardée dans cross_validation_report.json")


if __name__ == "__main__":
    main()
