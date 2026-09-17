"""
Fonctions utilitaires pour le pipeline ML.
"""

import numpy as np
import pandas as pd
import logging
import json

# Logger structuré
logger = logging.getLogger("pipeline")
logger.setLevel(logging.INFO)

handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(message)s"))
logger.addHandler(handler)


def log_event(event: str, **kwargs):
    """Log structuré JSON."""
    payload = {"event": event, **kwargs}
    logger.info(json.dumps(payload))


def safe_numeric(df, columns):
    log_event("safe_numeric_start", columns=columns)
    for col in columns:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    log_event("safe_numeric_end")
    return df


def replace_inf(df):
    log_event("replace_inf")
    return df.replace([np.inf, -np.inf], np.nan).fillna(0)


def rolling_sum(group, column, window):
    log_event("rolling_sum", column=column, window=window)
    return group[column].transform(
        lambda s: s.shift(1).rolling(window, min_periods=1).sum()
    )


def rolling_mean(group, column, window):
    log_event("rolling_mean", column=column, window=window)
    return group[column].transform(
        lambda s: s.shift(1).rolling(window, min_periods=1).mean()
    )
