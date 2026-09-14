import importlib


def test_streamlit_app_import():
    """
    Vérifie que l'application Streamlit s'importe sans erreur.
    """
    try:
        importlib.import_module("api.streamlit.app")
        imported = True
    except Exception as e:
        imported = False
        raise AssertionError(f"Erreur lors de l'import de Streamlit : {e}")

    assert imported is True
