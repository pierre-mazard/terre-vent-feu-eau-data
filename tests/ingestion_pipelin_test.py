import pytest
from data.ingestion_pipeline import pipeline


def test_pipeline_runs_without_error():
    """
    Vérifie que le pipeline d’ingestion s’exécute sans lever d’exception.
    """
    try:
        pipeline.main()
        executed = True
    except Exception as e:
        executed = False
        pytest.fail(f"Le pipeline a levé une exception : {e}")

    assert executed is True
