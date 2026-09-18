import os
import importlib
import pytest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def list_python_files(root):
    """Liste tous les fichiers .py du projet, sauf .venv et __pycache__."""
    py_files = []
    for dirpath, dirnames, filenames in os.walk(root):
        # Exclusions
        if ".venv" in dirpath or "__pycache__" in dirpath:
            continue
        for filename in filenames:
            if filename.endswith(".py"):
                full_path = os.path.join(dirpath, filename)
                py_files.append(full_path)
    return py_files


def module_name_from_path(path, root):
    """
    Convertit un chemin de fichier Python en nom de module importable.
    Exemple :
        /project/data/ingestion_pipeline/load.py
        → data.ingestion_pipeline.load
    """
    rel = os.path.relpath(path, root)
    rel = rel.replace(os.sep, ".")
    if rel.endswith(".py"):
        rel = rel[:-3]
    return rel


@pytest.mark.parametrize("pyfile", list_python_files(PROJECT_ROOT))
def test_import_all_python_files(pyfile):
    """Test : chaque fichier Python doit être importable sans erreur."""
    module_name = module_name_from_path(pyfile, PROJECT_ROOT)

    try:
        importlib.import_module(module_name)
    except Exception as e:
        pytest.fail(f"Import failed for {module_name}: {e}")
