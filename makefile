.PHONY: lint security test run-pipeline run streamlit
lint:
	black .
	flake8 .
security:
	bandit -r . -x .venv
	pip-audit
test:
	pytest -q
run-pipeline:
	python -m data.ingestion_pipeline.pipeline
run-streamlit:
	streamlit run api/streamlit/app.py
