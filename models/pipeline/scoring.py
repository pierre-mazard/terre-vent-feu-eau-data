# models/pipeline/scoring.py
import numpy as np
import pandas as pd
from models.config_pipeline import FEATURE_COLUMNS, ANNEE_FIN


def score_future(model, features: pd.DataFrame) -> pd.DataFrame:
    # Colonnes réellement présentes et pertinentes pour le modèle
    feature_cols = [
        col
        for col in FEATURE_COLUMNS
        if col in features.columns and col not in ("latitude", "longitude")
    ]

    # On part de l'année ANNEE_FIN comme état connu
    base = features[features["annee"] == ANNEE_FIN].copy()

    if base.empty:
        raise ValueError(
            f"Aucune ligne pour l'année ANNEE_FIN={ANNEE_FIN} dans features. "
            "Impossible de construire le scoring futur."
        )

    # On construit artificiellement l'année N+1 à partir de l'état N
    future = base.copy()
    future["annee"] = ANNEE_FIN + 1

    # On neutralise la cible si elle est présente (on ne l'utilise pas pour le scoring)
    if "cible_incendie_suivant" in future.columns:
        future["cible_incendie_suivant"] = np.nan

    X_future = future[feature_cols].replace([np.inf, -np.inf], np.nan).fillna(0)

    future["proba"] = model.predict_proba(X_future)[:, 1]

    return future
