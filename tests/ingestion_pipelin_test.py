from data.ingestion_pipeline import pipeline


def test_pipeline_importable():
    """Le pipeline doit pouvoir être importé sans erreur."""
    assert callable(pipeline.main)
