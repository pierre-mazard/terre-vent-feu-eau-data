import pandas as pd


def clean_incendies(df: pd.DataFrame):
    report = {}

    df0 = len(df)
    df = df.copy()

    # coordonnées
    before = len(df)
    df = df.dropna(subset=["latitude", "longitude"])
    df = df[df["latitude"].between(-90, 90)]
    df = df[df["longitude"].between(-180, 180)]
    after = len(df)

    report["coordonnees_supprimees"] = before - after

    # surface
    surface_cols = [c for c in df.columns if "surface" in c or "surf" in c]
    report["surface_cols_detectees"] = surface_cols

    if surface_cols:
        col = surface_cols[0]
        df[col] = df[col].fillna(0).clip(lower=0)
    else:
        df["surface_ha"] = 0
        col = "surface_ha"

    df["surface_ha"] = df[col]

    # année
    before = len(df)
    df = df.dropna(subset=["annee"])
    df["annee"] = df["annee"].astype(int)
    after = len(df)

    report["annee_supprimees"] = before - after
    report["total_avant"] = df0
    report["total_apres"] = len(df)

    return df, report


def clean_communes(df: pd.DataFrame):
    report = {}

    df = df.copy()
    for col in ["population", "densite", "altitude_moy", "superficie_km2"]:
        na_count = df[col].isna().sum()
        df[col] = df[col].fillna(0)
        report[f"{col}_na_corriges"] = int(na_count)

    return df, report
