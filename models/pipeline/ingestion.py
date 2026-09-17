import pandas as pd
from sqlalchemy import text
from config import get_engine

ANNEE_DEBUT = 2006


def load_incendies() -> pd.DataFrame:
    """
    Charge les incendies depuis la base SQL, avec toutes les surfaces utiles
    et les indicateurs de gravité.
    """
    sql = text("""
        SELECT
            f.code_insee,
            f.annee,
            f.mois,
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
    """)
    with get_engine().connect() as conn:
        df = pd.read_sql(sql, conn, params={"annee_debut": ANNEE_DEBUT})

    df["code_insee"] = df["code_insee"].astype(str).str.zfill(5)
    return df


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
    """)
    with get_engine().connect() as conn:
        df = pd.read_sql(sql, conn)

    df["code_insee"] = df["code_insee"].astype(str).str.zfill(5)
    return df
