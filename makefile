.PHONY: lint security test run-pipeline-ingestion clean-data build-dataset run-pipeline-ml \
        comparer-modeles train-horizons run-streamlit replay-run shap

# =============================================================================
#  Rappel : `make` n'existe pas dans PowerShell. Sous Windows, soit tu installes
#  make (`winget install GnuWin32.Make`), soit tu lances directement la commande
#  python indiquee sous chaque cible. Les deux font exactement la meme chose.
# =============================================================================

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
# PIPELINE INGESTION -> SQL
# -----------------------------
# python -m data.ingestion_pipeline.pipeline
run-pipeline-ingestion:
	@echo "=== INGESTION SQL ==="
	python -m data.ingestion_pipeline.pipeline

# -----------------------------
# PIPELINE NETTOYAGE
# -----------------------------
# ATTENTION : models/pipeline/cleaning.py n'expose aucun main(), cette cible ne
# produit donc rien. Le nettoyage est de toute facon effectue par build-dataset.
clean-data:
	@echo "=== NETTOYAGE DES DONNÉES (inclus dans build-dataset) ==="
	python -m models.pipeline.build_dataset

# -----------------------------
# PIPELINE FEATURES -> data/processed/run/<timestamp>/
# -----------------------------
# python -m models.pipeline.build_dataset
build-dataset:
	@echo "=== CONSTRUCTION DU DATASET ==="
	python -m models.pipeline.build_dataset

# -----------------------------
# EXTRACTION DU RUN COURANT
# -----------------------------
# L'ancienne version utilisait `grep -oP '(?<=run/)[^"]+'`. Deux problemes :
#   1. sous Windows, latest_run.json contient des ANTISLASH, donc la regex qui
#      cherche "run/" ne trouve jamais rien -> $(GET_LATEST_RUN) est vide et
#      `test -f models/run//model_risque.joblib` echoue systematiquement ;
#   2. `grep -oP` (PCRE) n'est pas disponible dans toutes les versions de grep.
# On passe donc par Python, qui lit le JSON correctement partout.
GET_LATEST_RUN = $(shell python -c "import json;p=json.load(open('data/processed/latest_run.json'))['run_dir'];print(p.replace(chr(92),'/').rstrip('/').split('/')[-1])")

# -----------------------------
# PIPELINE ML COMPLET  (modele annuel)
# -----------------------------
run-pipeline-ml:
	@echo "=== PIPELINE ML : ENTRAINEMENT ==="
	python -m models.train_test.train_model || (echo "ERREUR ENTRAINEMENT" && exit 1)

	@echo "=== PIPELINE ML : EVALUATION ==="
	python -m models.train_test.evaluate_model || (echo "ERREUR EVALUATION" && exit 1)

	@echo "=== PIPELINE ML : VALIDATION CROISÉE ==="
	python -m models.train_test.cross_validation || (echo "ERREUR VALIDATION" && exit 1)

	@echo "=== VERIFICATION DES ARTEFACTS ==="
	test -f models/run/$(call GET_LATEST_RUN)/model_risque.joblib || (echo "modele manquant" && exit 1)
	test -f models/run/$(call GET_LATEST_RUN)/metadata.json || (echo "metadata manquants" && exit 1)
	test -f models/run/$(call GET_LATEST_RUN)/scores_risque.csv || (echo "scores manquants" && exit 1)
	test -f models/run/$(call GET_LATEST_RUN)/features_risque.csv || (echo "features manquants" && exit 1)

	@echo "=== PIPELINE ML COMPLET : OK ==="

# -----------------------------
# COMPARAISON DE MODELES  (regression logistique / Random Forest / XGBoost)
# -----------------------------
# Meme decoupage, memes variables, memes metriques pour les trois.
# Ecrit models/run/<run>/comparaison_modeles.json, lu par la page 10.
# python -m models.train_test.comparaison_modeles
comparer-modeles:
	@echo "=== COMPARAISON DES MODELES ==="
	python -m models.train_test.comparaison_modeles
	test -f models/run/$(call GET_LATEST_RUN)/comparaison_modeles.json || (echo "rapport manquant" && exit 1)

# -----------------------------
# MODELES A HORIZON COURT  (10 / 30 / 60 jours)
# -----------------------------
# Construit le panel commune x date par echantillonnage negatif, entraine un
# modele XGBoost par horizon, et ecrit les artefacts lus par la page 11.
# python -m models.train_test.train_horizons
train-horizons:
	@echo "=== MODELES A HORIZON 10 / 30 / 60 JOURS ==="
	python -m models.train_test.train_horizons
	test -f models/run/$(call GET_LATEST_RUN)/modele_horizon_30j.json || (echo "modele 30j manquant" && exit 1)
	test -f models/run/$(call GET_LATEST_RUN)/feux_historique.csv || (echo "chronologie manquante" && exit 1)
	test -f models/run/$(call GET_LATEST_RUN)/panel_horizon.parquet || (echo "panel manquant" && exit 1)

# -----------------------------
# TOUT LE ML D'UN COUP
# -----------------------------
ml-complet: run-pipeline-ml comparer-modeles train-horizons shap
	@echo "=== TOUS LES MODELES SONT A JOUR ==="

# -----------------------------
# STREAMLIT
# -----------------------------
# streamlit run api/streamlit/app.py
run-streamlit:
	streamlit run api/streamlit/app.py

# -----------------------------
# REPLAY RUN
# -----------------------------
# ATTENTION : models/pipeline/replay_run.py definit replay() mais ne lit pas
# sys.argv et n'a pas de bloc __main__ : la variable RUN est ignoree. A corriger
# avant de compter dessus.
replay-run:
	python -m models.pipeline.replay_run $(RUN)

# -----------------------------
# SHAP  (modele annuel)
# -----------------------------
# Lance depuis la racine, sinon le dossier local shap/ masque la librairie shap.
# python shap/compute_shap.py
shap:
	python shap/compute_shap.py
