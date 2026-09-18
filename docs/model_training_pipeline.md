# 🔥 Pipeline ML — Terre-Vent-Feu-Eau (TVFE)
Branche : `feature/model-training`
Auteur : Pierre Mazard
Date : 2026-09-14

Ce document décrit l’état actuel du pipeline ML, les améliorations réalisées, la structure des données, les artefacts générés, ainsi que les prochaines étapes (Streamlit, comparaison de runs, dashboard MLOps).

---

## 1. 🎯 Objectifs du pipeline ML

Le pipeline TVFE vise à :

- nettoyer les données incendies + communes
- construire un dataset de features complet
- entraîner un modèle de prédiction du risque d’incendie
- scorer les communes
- versionner chaque exécution du pipeline
- assurer la reproductibilité totale (split, modèle, dataset, artefacts)

---

## 2. 📁 Structure des dossiers (nouvelle architecture MLOps)

### Données traitées (versionnées par run)
```
data/processed/run/<timestamp>/
├── incendies_clean.csv
├── communes_clean.csv
├── features_base.csv
├── features_final.csv
├── cleaning_report_incendies.json
├── cleaning_report_communes.json
├── features_report.json
├── dataset_report.json
├── run_manifest.json
```


### Artefacts ML (versionnés par run)

```
models/run/<timestamp>/
├── model_risque.joblib
├── metadata.json
├── scores_risque.csv
├── features_risque.csv
├── split_report.json
```


### Fichier de synchronisation

```
data/processed/latest_run.json
```

Ce fichier indique au pipeline ML **quel run doit être utilisé**.

---

## 3. ⚙️ Fonctionnement du pipeline

### Étape 1 — Nettoyage
```
make clean-data
```
→ exécute `models.pipeline.cleaning`

### Étape 2 — Construction du dataset
```
make build-dataset
```
→ crée un dossier horodaté
→ génère les CSV + rapports + manifest
→ met à jour `latest_run.json`

### Étape 3 — Entraînement du modèle
```
make run-pipeline-ml
```
→ lit le dossier du dernier run
→ ajoute les clusters
→ entraîne le modèle
→ génère les scores
→ écrit les artefacts ML dans `models/run/<timestamp>/`

### Étape 4 — Évaluation
→ métriques globales (AUC, PR-AUC, balanced accuracy, top-5%)

### Étape 5 — Validation croisée
→ CV temporelle
→ CV géographique

### Étape 6 — Vérification des artefacts
→ le Makefile vérifie que tout est bien généré

---

## 4. 🔐 Reproductibilité totale

### ✔ Split reproductible
`split_report.json` contient :

- années train/test
- nombre de lignes
- nombre de communes
- hash cryptographique du split

### ✔ Dataset reproductible
`run_manifest.json` contient :

- timestamp
- nombre de lignes
- colonnes
- hash possible (à ajouter)

### ✔ Modèle reproductible
`metadata.json` contient :

- hyperparamètres
- métriques
- clusters
- année de scoring

---

## 5. 🧪 Mode replay-run

Un script permet de rejouer un run :

```
make replay-run RUN=data/processed/run/<timestamp>
```


Il recharge :

- dataset
- modèle
- split
- scores

---

## 6. 🧰 Makefile (corrigé et MLOps-ready)

Le Makefile :

- reconstruit le dataset
- entraîne le modèle
- évalue
- valide
- vérifie les artefacts
- utilise `latest_run.json` pour synchroniser les runs

---

## 7. 📌 Prochaines étapes (feature/streamlit-ui)

### 7.1 Dashboard Streamlit MLOps

- Sélecteur de run
- Affichage du manifest
- Affichage du split
- Affichage des métriques
- Visualisation des features
- Visualisation des scores
- Carte géographique des risques
- Comparaison de runs
- Mode replay-run depuis l’UI

### 7.2 Pages Streamlit proposées

01_Overview.py
02_Dataset.py
03_Model.py
04_Scoring.py
05_Run_Explorer.py


---

## 8. 🚀 Conclusion

Le pipeline ML TVFE est maintenant :

- versionné
- reproductible
- structuré
- prêt pour l’intégration Streamlit
- prêt pour CI/CD
- prêt pour la revue de code
- prêt pour merge dans `develop`

Prochaine étape : **intégration Streamlit + dashboard MLOps complet**.
