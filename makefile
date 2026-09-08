install:
    pip install -r requirements.txt

lint:
    flake8 .
    black --check .

security:
    bandit -r .
    pip-audit

test:
    pytest -q

run-streamlit:
    streamlit run api/streamlit/app.py

run-pipeline:
    python data/ingestion_pipeline/pipeline.py
