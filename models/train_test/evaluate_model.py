"""
Évaluation du modèle : métriques globales, géographiques, top-k.
"""

import numpy as np
import pandas as pd
from sklearn.metrics import (
    roc_auc_score,
    average_precision_score,
    brier_score_loss,
    balanced_accuracy_score,
    precision_score,
    recall_score,
    f1_score,
)
from models.config_pipeline import FEATURE_COLUMNS, ANNEE_TEST
from models.pipeline.utils import log_event


def evaluate_model(model, features):
    log_event("evaluate_model_start")

    test = features[features["annee"] == ANNEE_TEST].copy()
    X_test = test[FEATURE_COLUMNS].fillna(0)
    y_test = test["cible_incendie_suivant"]

    proba = model.predict_proba(X_test)[:, 1]
    preds = (proba >= 0.5).astype(int)

    seuil_top5 = np.quantile(proba, 0.95)
    vrais_top5 = y_test[proba >= seuil_top5]

    metrics = {
        "roc_auc": float(roc_auc_score(y_test, proba)),
        "pr_auc": float(average_precision_score(y_test, proba)),
        "brier_score": float(brier_score_loss(y_test, proba)),
        "balanced_accuracy": float(balanced_accuracy_score(y_test, preds)),
        "precision": float(precision_score(y_test, preds, zero_division=0)),
        "recall": float(recall_score(y_test, preds, zero_division=0)),
        "f1": float(f1_score(y_test, preds, zero_division=0)),
        "pr_auc_baseline": float(y_test.mean()),
        "rappel_top_5pct": float(vrais_top5.mean()) if len(vrais_top5) else 0.0,
        "taux_incendie_test": float(y_test.mean()),
    }

    log_event("evaluate_model_end", metrics=metrics)
    return metrics
