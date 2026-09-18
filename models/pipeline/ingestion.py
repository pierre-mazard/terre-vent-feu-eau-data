import pandas as pd
from sqlalchemy import text

from config import get_engine

ANNEE_DEBUT = 2006


def load_incendies() -> pd.DataFrame:
    """
    Charge les incendies depuis la base SQL, avec toutes les surfaces utiles
    et les indicateurs de gravité.

    `ORDER BY` n'est pas cosmétique : sans tri explicite, PostgreSQL renvoie
    les lignes dans l'ordre physique de la table, qui change après un VACUUM ou
    un rechargement. Plusieurs étapes en aval supposent un ordre stable.
    """
    sql = text("""
        SELECT
            f.code_insee,
            f.annee,
            f.mois,
            f.date_alerte,
            f.surface_parcourue_ha,
            f.surface_foret_ha,
            f.surface_maquis_ha,
            f.surface_autres_nat_ha,
            f.surface_agricole_ha,
            f.surface_autres_ha,
            f.surface_autres_boisees_ha,
            f.surface_non_boisees_nat_ha,
            f.surface_non_boisees_art_ha,
            f.nb_deces,
            f.nb_bat_detruits,
            f.nb_bat_partiels,
            c.latitude,
            c.longitude
        FROM fires f
        LEFT JOIN ref_communes c ON c.code_insee = f.code_insee
        WHERE f.annee >= :annee_debut
        ORDER BY f.code_insee, f.annee, f.mois
    """)
    with get_engine().connect() as conn:
        df = pd.read_sql(sql, conn, params={"annee_debut": ANNEE_DEBUT})

    df["code_insee"] = df["code_insee"].astype(str).str.zfill(5)
    return df


def load_feux_dates(annee_debut: int = 2000) -> pd.DataFrame:
    """Chronologie des feux à la journée : (commune, date, surface).

    Le modèle annuel n'a besoin que de l'année et du mois. Les modèles à
    horizon court, eux, raisonnent en jours : il leur faut la date d'alerte.
    On remonte plus loin que 2006 pour que les fenêtres glissantes de cinq ans
    soient complètes dès la première année d'entraînement.
    """
    sql = text("""
        SELECT
            code_insee,
            date_alerte,
            surface_parcourue_ha
        FROM fires
        WHERE date_alerte IS NOT NULL
          AND annee >= :annee_debut
        ORDER BY code_insee, date_alerte
    """)
    with get_engine().connect() as conn:
        df = pd.read_sql(sql, conn, params={"annee_debut": annee_debut})

    df = df.rename(
        columns={"date_alerte": "date", "surface_parcourue_ha": "surface_ha"}
    )
    df["code_insee"] = df["code_insee"].astype(str).str.zfill(5)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["surface_ha"] = pd.to_numeric(df["surface_ha"], errors="coerce").fillna(0.0)
    return df.dropna(subset=["date"]).reset_index(drop=True)


def load_communes() -> pd.DataFrame:
    """
    Charge les communes géocodées.
    """
    sql = text("""
        SELECT
            code_insee,
            latitude,
            longitude,
            population,
            densite,
            altitude_moy,
            superficie_km2,
            nom
        FROM ref_communes
        WHERE latitude IS NOT NULL AND longitude IS NOT NULL
        ORDER BY code_insee
    """)
    with get_engine().connect() as conn:
        df = pd.read_sql(sql, conn)

    df["code_insee"] = df["code_insee"].astype(str).str.zfill(5)
    return df
