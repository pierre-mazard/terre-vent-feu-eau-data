-- =============================================================================
--  Projet "Terre, Vent, Feu, Eau, Data"
--  Schema de la base consolidee  (PostgreSQL 16 + PostGIS 3.4)
--
--  Ce fichier est joue AUTOMATIQUEMENT par Docker a la premiere creation de la
--  base (voir docker-compose.yml, volume vers /docker-entrypoint-initdb.d/).
--  Pour le rejouer a la main :
--     docker exec -i tvfed_db psql -U tvfed -d tvfed < sql/01_schema.sql
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS postgis;

-- -----------------------------------------------------------------------------
-- 1. REFERENTIEL DES COMMUNES  (source : data.gouv.fr, licence ouverte)
--    C'est ce qui apporte la latitude/longitude que la BDIFF ne donne pas.
-- -----------------------------------------------------------------------------
DROP TABLE IF EXISTS ref_communes CASCADE;
CREATE TABLE ref_communes (
    code_insee      VARCHAR(5)  PRIMARY KEY,
    nom             TEXT        NOT NULL,
    code_postal     TEXT,
    dep_code        VARCHAR(3),
    reg_code        VARCHAR(2),
    population      INTEGER,
    superficie_km2  NUMERIC(10,3),
    densite         NUMERIC(12,2),
    altitude_moy    INTEGER,
    latitude        DOUBLE PRECISION,
    longitude       DOUBLE PRECISION,
    -- GEOGRAPHY(POINT,4326) = un point sur le globe en degres lat/lon.
    -- Avec ce type, ST_DWithin(a, b, 20000) veut dire "a moins de 20 000 METRES",
    -- PostGIS gere la courbure de la Terre tout seul.
    geom            GEOGRAPHY(POINT, 4326)
);

-- -----------------------------------------------------------------------------
-- 2. STAGING : copie BRUTE des CSV BDIFF, tout en texte.
--    Regle d'or de l'ingestion : on charge d'abord SANS rien transformer,
--    on nettoie ensuite EN SQL. Comme ca, si le nettoyage est faux, on le
--    rejoue sans retelecharger 52 fichiers.
--    Colonnes = exactement l'en-tete du CSV BDIFF (24 colonnes).
-- -----------------------------------------------------------------------------
DROP TABLE IF EXISTS stg_bdiff CASCADE;
CREATE TABLE stg_bdiff (
    annee                        TEXT,
    numero                       TEXT,
    departement                  TEXT,
    code_insee                   TEXT,
    nom_commune                  TEXT,
    date_alerte                  TEXT,
    surface_parcourue_m2         TEXT,
    surface_foret_m2             TEXT,
    surface_maquis_m2            TEXT,
    surface_autres_nat_m2        TEXT,   -- fiches >= 2023
    surface_agricole_m2          TEXT,   -- fiches >= 2023
    surface_autres_m2            TEXT,   -- fiches >= 2023
    surface_autres_boisees_m2    TEXT,   -- fiches <  2023
    surface_non_boisees_nat_m2   TEXT,   -- fiches <  2023
    surface_non_boisees_art_m2   TEXT,   -- fiches <  2023
    surface_non_boisees_m2       TEXT,   -- fiches <  2023
    precision_surfaces           TEXT,
    type_peuplement              TEXT,
    nature                       TEXT,
    deces_ou_batiments           TEXT,
    nb_deces                     TEXT,
    nb_bat_detruits              TEXT,
    nb_bat_partiels              TEXT,
    precision_donnee             TEXT,
    fichier_source               TEXT     -- tracabilite : d'ou vient la ligne
);

-- -----------------------------------------------------------------------------
-- 3. TABLE DE FAITS : les incendies, propres et types.
--    Cle metier = (annee, numero) : verifie unique sur l'export 2024.
-- -----------------------------------------------------------------------------
DROP TABLE IF EXISTS fires CASCADE;
CREATE TABLE fires (
    fire_id                     TEXT PRIMARY KEY,          -- 'annee-numero'
    annee                       SMALLINT      NOT NULL,
    numero                      INTEGER       NOT NULL,
    departement                 VARCHAR(3),
    code_insee                  VARCHAR(5) REFERENCES ref_communes(code_insee),
    nom_commune                 TEXT,
    date_alerte                 TIMESTAMP,
    mois                        SMALLINT,
    jour_julien                 SMALLINT,
    -- ATTENTION : la BDIFF exporte les surfaces en METRES CARRES, pas en ha.
    surface_parcourue_ha        NUMERIC(12,4),
    surface_foret_ha            NUMERIC(12,4),
    surface_maquis_ha           NUMERIC(12,4),
    surface_autres_nat_ha       NUMERIC(12,4),
    surface_agricole_ha         NUMERIC(12,4),
    surface_autres_ha           NUMERIC(12,4),
    surface_autres_boisees_ha   NUMERIC(12,4),
    surface_non_boisees_nat_ha  NUMERIC(12,4),
    surface_non_boisees_art_ha  NUMERIC(12,4),
    precision_surfaces          TEXT,          -- 'Estimees' | 'Mesurees'
    type_peuplement             SMALLINT,      -- code 1..6, voir docs/SCHEMA.md
    nature                      TEXT,          -- Naturelle / Accidentelle / ...
    nb_deces                    SMALLINT,
    nb_bat_detruits             SMALLINT,
    nb_bat_partiels             SMALLINT,
    precision_donnee            TEXT,
    is_geocoded                 BOOLEAN DEFAULT FALSE,
    fichier_source              TEXT,
    CONSTRAINT uq_fires_annee_numero UNIQUE (annee, numero)
);

-- -----------------------------------------------------------------------------
-- 4. INDEX
--    Un index, c'est l'equivalent de l'index d'un livre : sans lui, Postgres
--    relit toute la table a chaque requete.
-- -----------------------------------------------------------------------------
CREATE INDEX idx_fires_insee    ON fires(code_insee);
CREATE INDEX idx_fires_annee    ON fires(annee);
CREATE INDEX idx_fires_dep      ON fires(departement);
CREATE INDEX idx_fires_date     ON fires(date_alerte);
-- GIST = index specialise pour les donnees geographiques (recherche par zone)
CREATE INDEX idx_communes_geom  ON ref_communes USING GIST(geom);

-- -----------------------------------------------------------------------------
-- 5. VUE DE TRAVAIL : incendies + coordonnees, prete pour la carto.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_fires_geo AS
SELECT  f.*,
        c.nom            AS commune_ref,
        c.latitude,
        c.longitude,
        c.population,
        c.superficie_km2,
        c.densite,
        c.altitude_moy,
        c.reg_code,
        c.geom
FROM    fires f
JOIN    ref_communes c ON c.code_insee = f.code_insee;
