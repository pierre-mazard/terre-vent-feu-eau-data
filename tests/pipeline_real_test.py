import pytest
import sys
from data.ingestion_pipeline import pipeline


@pytest.mark.integration
def test_pipeline_real():
    # On simule les arguments de la ligne de commande
    sys.argv = ["pipeline.py", "--skip-download"]

    # On monkey-patch l'étape SQL pour éviter psycopg2
    pipeline.load.main = lambda: None

    pipeline.main()
