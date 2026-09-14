from pathlib import Path
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine

# ---------------------------------------------------------------------------
# Chargement intelligent du .env (compatible Streamlit, Docker, scripts)
# ---------------------------------------------------------------------------

# Dossier où se trouve config.py
PROJECT_ROOT = Path(__file__).resolve().parent

# Chemin principal du .env
ENV_FILE = PROJECT_ROOT / ".env"

# Si Streamlit est lancé depuis api/streamlit/, le .env est un cran au-dessus
if not ENV_FILE.exists():
    ENV_FILE = PROJECT_ROOT.parent / ".env"

# Si Docker lance depuis un autre contexte, on remonte encore
if not ENV_FILE.exists():
    ENV_FILE = PROJECT_ROOT.parent.parent / ".env"

# Chargement final
load_dotenv(ENV_FILE)

# ---------------------------------------------------------------------------
# Chemins du projet
# ---------------------------------------------------------------------------
DATA_RAW = PROJECT_ROOT / "data" / "raw"
DATA_PROCESSED = PROJECT_ROOT / "data" / "processed"
MODELS = PROJECT_ROOT / "models"

for d in (DATA_RAW, DATA_PROCESSED, MODELS):
    d.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# SSL / HTTPS
# ---------------------------------------------------------------------------
SSL_VERIFY = os.getenv("SSL_VERIFY", "true").strip().lower() not in ("false", "0", "no")

# ---------------------------------------------------------------------------
# Base de données
# ---------------------------------------------------------------------------
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")

DB_URL = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
print("DB_USER =", DB_USER)
print("DB_PASSWORD =", DB_PASSWORD)
print("DB_HOST =", DB_HOST)
print("DB_PORT =", DB_PORT)
print("DB_NAME =", DB_NAME)
print("DB_URL =", DB_URL)


def get_engine():
    return create_engine(DB_URL, future=True)
