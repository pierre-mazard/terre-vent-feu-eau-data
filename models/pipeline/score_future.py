import pandas as pd
from models.config_pipeline import FEATURE_COLUMNS, ANNEE_FIN


def score_future(model, features: pd.DataFrame) -> pd.DataFrame:
    """
    Applique le modèle entraîné sur l'année ANNEE_FIN
    et retourne un DataFrame de scores.
    """

    future = features[features["annee"] == ANNEE_FIN].copy()

    X_future = future[FEATURE_COLUMNS].fillna(0)
    proba = model.predict_proba(X_future)[:, 1]

    future["proba_incendie_suivant"] = proba

    # Déciles de risque
    future["decile_proba"] = pd.qcut(
        future["proba_incendie_suivant"],
        q=10,
        labels=False,
        duplicates="drop",
    )

    # Rang par département si disponible
    if "departement" in future.columns:
        future["rang_dep"] = future.groupby("departement")[
            "proba_incendie_suivant"
        ].rank(method="dense", ascending=False)

    return future
