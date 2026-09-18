# models/pipeline/training.py
"""Entrainement du modele de risque.

Les hyperparametres ne sont pas cosmetiques : sans `max_depth`, les arbres
grandissent jusqu'a isoler chaque observation. Sur 592 671 lignes, cela donnait
un `model_risque_raw.joblib` de 730 Mo et, apres calibration sur 5 replis, un
`model_risque.joblib` de 3,4 Go — impossible a charger dans une application
Streamlit. Avec les valeurs ci-dessous, les deux fichiers retombent autour de
la centaine de Mo, et les metriques s'ameliorent.
"""

import numpy as np
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score

from models.config_pipeline import ANNEE_DEBUT_TRAIN, ANNEE_TEST, FEATURE_COLUMNS


def decouper(features):
    """Decoupage chronologique strict.

    On ne commence qu'en 2011 : avant cette annee, `nb_feux_10a` est calcule sur
    moins de dix ans d'historique (`min_periods=1`), donc la variable ment.
    """
    train = features[
        (features["annee"] >= ANNEE_DEBUT_TRAIN) & (features["annee"] < ANNEE_TEST)
    ]
    test = features[features["annee"] == ANNEE_TEST]
    return train, test


def train_model(features):
    train, test = decouper(features)

    X_train = train[FEATURE_COLUMNS]
    y_train = train["cible_incendie_suivant"]

    X_test = test[FEATURE_COLUMNS]
    y_test = test["cible_incendie_suivant"]

    # --- 1) Modele brut ---
    model_raw = RandomForestClassifier(
        n_estimators=200,
        max_depth=12,  # borne la taille du modele ET le surapprentissage
        min_samples_leaf=3,
        class_weight="balanced",  # environ 2,5 % de positifs seulement
        n_jobs=-1,
        random_state=42,
    )
    model_raw.fit(X_train, y_train)

    # --- 2) Modele calibre ---
    # cv=3 : la calibration doit se faire sur des donnees que la foret n'a pas
    # vues. Sans `cv`, scikit-learn en utilise 5 et stocke donc cinq forets.
    model_calibrated = CalibratedClassifierCV(model_raw, method="sigmoid", cv=3)
    model_calibrated.fit(X_train, y_train)

    # --- 3) Metriques sur le modele calibre ---
    proba_test = model_calibrated.predict_proba(X_test)[:, 1]

    seuil = float(np.quantile(proba_test, 0.95))
    designees = y_test[proba_test >= seuil]
    positifs = float(y_test.sum())

    metrics = {
        "roc_auc": float(roc_auc_score(y_test, proba_test)),
        "pr_auc": float(average_precision_score(y_test, proba_test)),
        "pr_auc_baseline": float(y_test.mean()),
        "brier_score": float(brier_score_loss(y_test, proba_test)),
        # Precision : parmi les communes designees, combien ont brule.
        "precision_top_5pct": float(designees.mean()) if len(designees) else 0.0,
        # Rappel : parmi les communes qui ont brule, combien etaient designees.
        # Meme numerateur, denominateur different : confondre les deux divise
        # par deux le chiffre annonce.
        "rappel_top_5pct": (float(designees.sum() / positifs) if positifs else 0.0),
        "annees_entrainement": f"{ANNEE_DEBUT_TRAIN}-{ANNEE_TEST - 1}",
        "annee_test": int(ANNEE_TEST),
    }

    return model_raw, model_calibrated, metrics
