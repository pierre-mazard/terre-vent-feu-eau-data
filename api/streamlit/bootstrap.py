# api/streamlit/bootstrap.py
"""Ajoute la racine du depot a sys.path.

Conserve pour compatibilite : les pages font desormais ce bootstrap
elles-memes, avant tout import projet. Importer ce module ne peut pas servir a
mettre la racine sur le chemin, puisqu'il faut deja que la racine y soit pour
pouvoir l'importer.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
