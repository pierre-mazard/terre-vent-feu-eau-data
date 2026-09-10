from pathlib import Path
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine

# ---------------------------------------------------------------------------
# Chargement du .env
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

# ---------------------------------------------------------------------------
# Chemins du projet
# ---------------------------------------------------------------------------
DATA_RAW = ROOT / "data" / "raw"
DATA_PROCESSED = ROOT / "data" / "processed"
MODELS = ROOT / "models"

for d in (DATA_RAW, DATA_PROCESSED, MODELS):
    d.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# SSL / HTTPS
# ---------------------------------------------------------------------------
SSL_VERIFY = os.getenv("SSL_VERIFY", "true").strip().lower() not in ("false", "0", "no")

# ---------------------------------------------------------------------------
# Base de données
# ---------------------------------------------------------------------------
DB_USER = os.getenv("DB_USER", "tvfed")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "tvfed")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")

DB_URL = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"


def get_engine():
    return create_engine(DB_URL, future=True)
