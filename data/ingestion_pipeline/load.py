"""ETAPE 2 ET 3 DE L'INGESTION : lire les CSV, nettoyer, charger dans PostgreSQL.

Rappel du tuyau complet :
    site BDIFF  --(ingest_bdiff.py)-->  data/raw/*.csv  --(ce fichier)-->  base SQL

Ordre des operations ici :
    1. ref_communes : le referentiel geographique (il doit exister AVANT fires,
       a cause de la cle etrangere).
    2. stg_bdiff    : copie brute des CSV, tout en texte.
    3. fires        : version propre et typee, construite EN SQL depuis stg_bdiff.
"""

from __future__ import annotations

import glob

import pandas as pd
from sqlalchemy import text

from config import DATA_RAW, get_engine

COLONNES_BDIFF = [
    "annee",
    "numero",
    "departement",
    "code_insee",
    "nom_commune",
    "date_alerte",
    "surface_parcourue_m2",
    "surface_foret_m2",
    "surface_maquis_m2",
    "surface_autres_nat_m2",
    "surface_agricole_m2",
    "surface_autres_m2",
    "surface_autres_boisees_m2",
    "surface_non_boisees_nat_m2",
    "surface_non_boisees_art_m2",
    "surface_non_boisees_m2",
    "precision_surfaces",
    "type_peuplement",
    "nature",
    "deces_ou_batiments",
    "nb_deces",
    "nb_bat_detruits",
    "nb_bat_partiels",
    "precision_donnee",
]


# --------------------------------------------------------------------------- #
def ligne_entete(chemin: str) -> int:
    """Retourne le numero de la ligne d'en-tete reelle du CSV BDIFF.

    POURQUOI CE N'EST PAS TOUJOURS 2 :
    la BDIFF ajoute un nombre VARIABLE de lignes de texte libre avant l'en-tete.
        - export 2024 : 2 lignes  (compteur, criteres)
        - export 2020 : 3 lignes  (avertissement "ancienne version du formulaire",
                                   compteur, criteres)
    Coder skiprows=2 en dur decalerait donc toutes les colonnes des annees
    anciennes, SANS provoquer d'erreur : le pire type de bug.
    On cherche donc la vraie ligne d'en-tete, celle qui commence par "Année;".
    """
    with open(chemin, encoding="utf-8") as fh:
        for i, ligne in enumerate(fh):
            if ligne.startswith("Année;"):
                return i
            if i > 10:
                break
    raise RuntimeError(f"En-tete introuvable dans {chemin}")


def charger_communes(engine) -> None:
    fichier = DATA_RAW / "communes_france.csv"
    # dtype=str sur le code INSEE : sinon "01004" devient 1004 et "2B033"
    # devient NaN. C'est LE piege classique des codes INSEE.
    df = pd.read_csv(fichier, dtype=str, low_memory=False)

    colonnes = {
        "code_insee": "code_insee",
        "nom_standard": "nom",
        "code_postal": "code_postal",
        "dep_code": "dep_code",
        "reg_code": "reg_code",
        "population": "population",
        "superficie_km2": "superficie_km2",
        "densite": "densite",
        "altitude_moyenne": "altitude_moy",
        "latitude_centre": "latitude",
        "longitude_centre": "longitude",
    }
    manquantes = [c for c in colonnes if c not in df.columns]
    if manquantes:
        raise RuntimeError(f"Colonnes absentes du referentiel : {manquantes}")

    out = df[list(colonnes)].rename(columns=colonnes)
    out["code_insee"] = out["code_insee"].str.strip().str.zfill(5)
    for c in ("population", "altitude_moy"):
        out[c] = pd.to_numeric(out[c], errors="coerce").astype("Int64")
    for c in ("superficie_km2", "densite", "latitude", "longitude"):
        out[c] = pd.to_numeric(out[c], errors="coerce")
    out = out.dropna(subset=["latitude", "longitude"]).drop_duplicates("code_insee")

    with engine.begin() as conn:
        conn.execute(text("TRUNCATE ref_communes CASCADE"))
    out.to_sql("ref_communes", engine, if_exists="append", index=False)

    # on fabrique le point geographique a partir de lat/lon, cote base
    with engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE ref_communes "
                "SET geom = ST_SetSRID("
                "ST_MakePoint(longitude, latitude), 4326)::geography"
            )
        )
    print(f"ref_communes : {len(out)} communes chargees")


# --------------------------------------------------------------------------- #
def charger_staging(engine) -> None:
    fichiers = sorted(glob.glob(str(DATA_RAW / "bdiff_*.csv")))
    if not fichiers:
        raise RuntimeError(
            "Aucun CSV BDIFF dans data/raw. Lancer ingest_bdiff.py d'abord."
        )

    with engine.begin() as conn:
        conn.execute(text("TRUNCATE stg_bdiff"))

    total = 0
    for f in fichiers:
        # le nombre de lignes de texte libre avant l'en-tete VARIE selon l'annee
        saut = ligne_entete(f)
        df = pd.read_csv(f, sep=";", skiprows=saut, dtype=str, encoding="utf-8")
        if len(df.columns) != len(COLONNES_BDIFF):
            print(
                f"  ATTENTION {f} : {len(df.columns)} colonnes au lieu de "
                f"{len(COLONNES_BDIFF)} -> fichier ignore"
            )
            continue
        df.columns = COLONNES_BDIFF
        df["fichier_source"] = f.split("/")[-1].split("\\")[-1]
        df.to_sql("stg_bdiff", engine, if_exists="append", index=False)
        total += len(df)
        print(
            f"  {df['fichier_source'].iloc[0]} : {len(df)} lignes"
            f" (en-tete ligne {saut})"
        )
    print(f"stg_bdiff : {total} lignes brutes chargees")


# --------------------------------------------------------------------------- #
SQL_FIRES = """
TRUNCATE fires;

INSERT INTO fires (
    fire_id, annee, numero, departement, code_insee, nom_commune, date_alerte,
    mois, jour_julien,
    surface_parcourue_ha, surface_foret_ha, surface_maquis_ha,
    surface_autres_nat_ha, surface_agricole_ha, surface_autres_ha,
    surface_autres_boisees_ha, surface_non_boisees_nat_ha, surface_non_boisees_art_ha,
    precision_surfaces, type_peuplement, nature,
    nb_deces, nb_bat_detruits, nb_bat_partiels, precision_donnee,
    is_geocoded, fichier_source
)
SELECT DISTINCT ON (s.annee, s.numero)
    s.annee || '-' || s.numero,
    s.annee::SMALLINT,
    s.numero::INTEGER,
    NULLIF(s.departement, ''),
    LPAD(NULLIF(s.code_insee, ''), 5, '0'),
    s.nom_commune,
    NULLIF(s.date_alerte, '')::TIMESTAMP,
    EXTRACT(MONTH FROM NULLIF(s.date_alerte, '')::TIMESTAMP)::SMALLINT,
    EXTRACT(DOY   FROM NULLIF(s.date_alerte, '')::TIMESTAMP)::SMALLINT,
    -- m2 -> hectares
    NULLIF(s.surface_parcourue_m2,       '')::NUMERIC / 10000,
    NULLIF(s.surface_foret_m2,           '')::NUMERIC / 10000,
    NULLIF(s.surface_maquis_m2,          '')::NUMERIC / 10000,
    NULLIF(s.surface_autres_nat_m2,      '')::NUMERIC / 10000,
    NULLIF(s.surface_agricole_m2,        '')::NUMERIC / 10000,
    NULLIF(s.surface_autres_m2,          '')::NUMERIC / 10000,
    NULLIF(s.surface_autres_boisees_m2,  '')::NUMERIC / 10000,
    NULLIF(s.surface_non_boisees_nat_m2, '')::NUMERIC / 10000,
    NULLIF(s.surface_non_boisees_art_m2, '')::NUMERIC / 10000,
    NULLIF(s.precision_surfaces, ''),
    NULLIF(s.type_peuplement, '')::SMALLINT,
    NULLIF(s.nature, ''),
    NULLIF(s.nb_deces, '')::SMALLINT,
    NULLIF(s.nb_bat_detruits, '')::SMALLINT,
    NULLIF(s.nb_bat_partiels, '')::SMALLINT,
    NULLIF(s.precision_donnee, ''),
    EXISTS (SELECT 1 FROM ref_communes c
            WHERE c.code_insee = LPAD(NULLIF(s.code_insee, ''), 5, '0')),
    s.fichier_source
FROM stg_bdiff s
WHERE s.annee ~ '^[0-9]{4}$' AND s.numero ~ '^[0-9]+$'
ORDER BY s.annee, s.numero, s.fichier_source;
"""


def construire_fires(engine) -> None:
    with engine.begin() as conn:
        # la cle etrangere refuse les communes inconnues : on la desactive le
        # temps du chargement, puis on marque is_geocoded pour tracer la perte
        conn.execute(
            text("ALTER TABLE fires DROP CONSTRAINT IF EXISTS fires_code_insee_fkey")
        )
        conn.execute(text(SQL_FIRES))
        stats = conn.execute(
            text(
                "SELECT count(*), count(*) FILTER (WHERE is_geocoded), "
                "min(annee), max(annee) FROM fires"
            )
        ).one()
    total, geo, amin, amax = stats
    print(
        f"fires : {total} incendies ({amin}-{amax}), "
        f"{geo} geocodes ({geo/max(total,1):.1%})"
    )


def main() -> None:
    engine = get_engine()
    charger_communes(engine)
    charger_staging(engine)
    construire_fires(engine)


if __name__ == "__main__":
    main()
