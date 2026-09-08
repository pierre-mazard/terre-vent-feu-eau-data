"""Configuration centrale : chemins du projet + connexion a la base.

Tout le reste du code importe d'ici. Comme ca, si on change le port de la base
ou le nom d'un dossier, on ne le change qu'a UN seul endroit.
"""

from pathlib import Path
import os

from dotenv import load_dotenv
from sqlalchemy import create_engine

# --- chemins -----------------------------------------------------------------
# data/ingestion_pipeline/config.py -> la racine du depot est 2 niveaux au-dessus
ROOT = Path(__file__).resolve().parents[2]
DATA_RAW = ROOT / "data" / "raw"
DATA_PROCESSED = ROOT / "data" / "processed"
MODELS = ROOT / "models"
for _d in (DATA_RAW, DATA_PROCESSED, MODELS):
    _d.mkdir(parents=True, exist_ok=True)

# --- variables d'environnement (.env) ----------------------------------------
load_dotenv(ROOT / ".env")

TRUST_SOURCE = "certifi (magasin interne de Python)"
CA_BUNDLE = None
# on garde la trace des echecs au lieu de les avaler silencieusement :
# un "except: pass" cache les vraies causes et est signale par bandit (B110).
AVERTISSEMENTS_TLS = []


def _bundle_depuis_magasin_windows():
    """Ecrit un fichier .pem contenant certifi + les autorites de confiance de Windows.

    ssl.enum_certificates n'existe que sous Windows. Chaque certificat vient avec
    un indicateur de confiance : True (tous usages) ou un ensemble d'OID ; celui
    qui nous interesse est 1.3.6.1.5.5.7.3.1 = authentification de serveur TLS.
    """
    import ssl
    import tempfile

    pems = []
    try:
        import certifi

        pems.append(pathlib_read(certifi.where()))
    except Exception as err:
        AVERTISSEMENTS_TLS.append(f"certifi illisible : {err}")

    trouve = 0
    for magasin in ("ROOT", "CA"):
        try:
            for cert, encodage, confiance in ssl.enum_certificates(magasin):
                if encodage != "x509_asn":
                    continue
             
                if confiance is True or (
                    confiance and "1.3.6.1.5.5.7.3.1" in confiance
                ):
                    pems.append(ssl.DER_cert_to_PEM_cert(cert))
                    trouve += 1
        except Exception as err:
            AVERTISSEMENTS_TLS.append(f"magasin {magasin} illisible : {err}")
            continue

    if not trouve:
        return None, 0

    fichier = Path(tempfile.gettempdir()) / "tvfed_ca_bundle.pem"
    fichier.write_text("\n".join(pems), encoding="ascii", errors="ignore")
    return str(fichier), trouve


def pathlib_read(chemin):
    return Path(chemin).read_text(encoding="ascii", errors="ignore")


try:
    import truststore

    truststore.inject_into_ssl()
    TRUST_SOURCE = "magasin du systeme (truststore)"
except Exception:
    try:
        import ssl as _ssl

        if hasattr(_ssl, "enum_certificates"):  # -> Windows uniquement
            CA_BUNDLE, _n = _bundle_depuis_magasin_windows()
            if CA_BUNDLE:
                os.environ.setdefault("REQUESTS_CA_BUNDLE", CA_BUNDLE)
                os.environ.setdefault("SSL_CERT_FILE", CA_BUNDLE)
                TRUST_SOURCE = f"magasin de certificats Windows ({_n} autorites)"
    except Exception as err:
        AVERTISSEMENTS_TLS.append(f"magasin systeme indisponible : {err}")

# Filet de DERNIER RECOURS, uniquement pour diagnostiquer : SSL_VERIFY=false dans
# le .env desactive la verification. A ne jamais laisser actif, et a documenter.
SSL_VERIFY = os.getenv("SSL_VERIFY", "true").strip().lower() not in ("false", "0", "no")
if SSL_VERIFY and CA_BUNDLE:
    SSL_VERIFY = CA_BUNDLE  # requests accepte un chemin de bundle ici
if SSL_VERIFY is False:
    import urllib3

    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    print(
        "!!! ATTENTION : verification des certificats HTTPS DESACTIVEE"
        " (SSL_VERIFY=false)"
    )

DB_USER = os.getenv("DB_USER", "tvfed")
DB_PASSWORD = os.getenv("DB_PASSWORD", "tvfed")
DB_NAME = os.getenv("DB_NAME", "tvfed")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")

DB_URL = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"


def get_engine():
    """Retourne le moteur SQLAlchemy (l'objet qui parle a PostgreSQL)."""
    return create_engine(DB_URL, future=True)


if __name__ == "__main__":
    # Test rapide : python src/config.py
    from sqlalchemy import text

    with get_engine().connect() as conn:
        v = conn.execute(text("SELECT version(), postgis_version()")).one()
    print("Connexion OK")
    print(" Confiance TLS :", TRUST_SOURCE)
    print(" PostgreSQL :", v[0].split(",")[0])
    print(" PostGIS    :", v[1])
