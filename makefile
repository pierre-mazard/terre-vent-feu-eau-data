.PHONY: lint security test run-pipeline-ingestion clean-data build-dataset run-pipeline-ml run-streamlit replay-run shap

# -----------------------------
# QUALITÉ CODE
# -----------------------------
lint:
	black .
	flake8 .

security:
	bandit -r . -x .venv
	pip-audit

test:
	pytest -q

# -----------------------------
# PIPELINE INGESTION → SQL
# -----------------------------
run-pipeline-ingestion:
	@echo "=== INGESTION SQL ==="
	python3 -m data.ingestion_pipeline.pipeline

# -----------------------------
# PIPELINE NETTOYAGE
# -----------------------------
clean-data:
	@echo "=== NETTOYAGE DES DONNÉES ==="
	python3 -m models.pipeline.cleaning

# -----------------------------
# PIPELINE FEATURES → data/processed/run/<timestamp>/
# -----------------------------
build-dataset:
	@echo "=== CONSTRUCTION DU DATASET ==="
	python3 -m models.pipeline.build_dataset

# -----------------------------
# EXTRACTION DU RUN COURANT (robuste)
# -----------------------------
GET_LATEST_RUN = $(shell grep -oP '(?<=run/)[^"]+' data/processed/latest_run.json)

# -----------------------------
# PIPELINE ML COMPLET
# -----------------------------
run-pipeline-ml:
	@echo "=== PIPELINE ML : ENTRAINEMENT ==="
	python3 -m models.train_test.train_model || (echo "❌ ERREUR ENTRAINEMENT" && exit 1)

	@echo "=== PIPELINE ML : EVALUATION ==="
	python3 -m models.train_test.evaluate_model || (echo "❌ ERREUR EVALUATION" && exit 1)

	@echo "=== PIPELINE ML : VALIDATION CROISÉE ==="
	python3 -m models.train_test.cross_validation || (echo "❌ ERREUR VALIDATION" && exit 1)

	@echo "=== VERIFICATION DES ARTEFACTS ==="
	test -f models/run/$(call GET_LATEST_RUN)/model_risque.joblib || (echo "❌ modèle manquant" && exit 1)
	test -f models/run/$(call GET_LATEST_RUN)/metadata.json || (echo "❌ metadata manquants" && exit 1)
	test -f models/run/$(call GET_LATEST_RUN)/scores_risque.csv || (echo "❌ scores manquants" && exit 1)
	test -f models/run/$(call GET_LATEST_RUN)/features_risque.csv || (echo "❌ features manquants" && exit 1)

	@echo "=== PIPELINE ML COMPLET : OK ==="

# -----------------------------
# STREAMLIT
# -----------------------------
run-streamlit:
	streamlit run api/streamlit/app.py

# -----------------------------
# REPLAY RUN
# -----------------------------
replay-run:
	python3 -m models.pipeline.replay_run $(RUN)

#-----------------------------
# SHAP
#----------------------------
shap:
	python shap/compute_shap.py
