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
	python -m models.pipeline.main
run-streamlit:
	streamlit run api/streamlit/app.py
