# models/pipeline/training.py

import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import roc_auc_score, average_precision_score
from models.config_pipeline import FEATURE_COLUMNS, ANNEE_TEST


def train_model(features):
    # Séparation train/test
    train = features[features["annee"] < ANNEE_TEST]
    test = features[features["annee"] == ANNEE_TEST]

    X_train = train[FEATURE_COLUMNS]
    y_train = train["cible_incendie_suivant"]

    X_test = test[FEATURE_COLUMNS]
    y_test = test["cible_incendie_suivant"]

    # --- 1) Modèle brut (RandomForest) ---
    model_raw = RandomForestClassifier(
        n_estimators=300,
        min_samples_leaf=2,
        n_jobs=-1,
        random_state=42,
    )
    model_raw.fit(X_train, y_train)

    # --- 2) Modèle calibré ---
    model_calibrated = CalibratedClassifierCV(model_raw, method="sigmoid")
    model_calibrated.fit(X_train, y_train)

    # --- 3) Métriques sur le modèle calibré ---
    proba_test = model_calibrated.predict_proba(X_test)[:, 1]

    metrics = {
        "roc_auc": float(roc_auc_score(y_test, proba_test)),
        "pr_auc": float(average_precision_score(y_test, proba_test)),
    }

    # On retourne les deux modèles
    return model_raw, model_calibrated, metrics
