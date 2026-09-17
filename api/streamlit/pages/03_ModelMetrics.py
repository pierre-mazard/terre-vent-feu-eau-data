# api/streamlit/pages/03_ModelMetrics.py

# --- BOOTSTRAP ---
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

# --- Imports projet ---
from config import DATA_PROCESSED, MODELS

# --- Imports Streamlit ---
import streamlit as st
import json
import pandas as pd
import numpy as np

# --- ML ---
from sklearn.metrics import (
    roc_curve,
    auc,
    precision_recall_curve,
    confusion_matrix,
)
from sklearn.calibration import calibration_curve

st.set_page_config(page_title="Model metrics", layout="wide")
st.title("📊 Metrics du modèle")

# Charger latest_run
latest_path = DATA_PROCESSED / "latest_run.json"
with open(latest_path) as f:
    latest = json.load(f)

run_dir = Path(latest["run_dir"])
model_run_dir = MODELS / "run" / run_dir.name

# Charger metadata
metadata_path = model_run_dir / "metadata.json"
with open(metadata_path) as f:
    metadata = json.load(f)

st.subheader("ℹ️ Metadata du modèle")
st.json(metadata)

# Charger scores
scores_path = model_run_dir / "scores_risque.csv"
scores = pd.read_csv(scores_path)

y_true = scores["cible_incendie_suivant"].astype(int)
y_proba = scores["proba_incendie_suivant"].astype(float)
y_pred = (y_proba >= 0.5).astype(int)

# Vérifier si y_true contient au moins un positif
if y_true.sum() == 0:
    st.warning("""
### ⚠️ Aucun incendie réel dans les données de scoring futur
Le scoring futur (année N+1) ne contient **aucun incendie réel**.
C’est normal : la cible n’existe pas encore.

Dans ce cas :
- ROC / PR ne peuvent pas être calculées
- La matrice de confusion est 1×1
- La calibration est non pertinente

👉 On affiche uniquement les métriques disponibles.
""")

    st.subheader("📊 Distribution des probabilités")
    st.bar_chart(y_proba)

    st.subheader("📌 Statistiques")
    st.write(
        {
            "Nombre de communes scorées": len(scores),
            "Taux d'incendie réel": float(y_true.mean()),
            "Taux d'incendie prédit (>=0.5)": float(y_pred.mean()),
            "Probabilité moyenne": float(y_proba.mean()),
            "Probabilité max": float(y_proba.max()),
        }
    )

    st.stop()

# --- Si positifs présents : calcul complet ---

# ROC
fpr, tpr, _ = roc_curve(y_true, y_proba)
roc_auc = auc(fpr, tpr)

st.subheader("📈 Courbe ROC")
st.line_chart(pd.DataFrame({"FPR": fpr, "TPR": tpr}))
st.write(f"**AUC ROC : {roc_auc:.4f}**")

# PR
precision, recall, _ = precision_recall_curve(y_true, y_proba)
pr_auc = auc(recall, precision)

st.subheader("📈 Courbe PR")
st.line_chart(pd.DataFrame({"Recall": recall, "Precision": precision}))
st.write(f"**AUC PR : {pr_auc:.4f}**")

# Calibration
prob_true, prob_pred = calibration_curve(y_true, y_proba, n_bins=20)

st.subheader("🎯 Calibration")
st.line_chart(
    pd.DataFrame({"Probabilité prédite": prob_pred, "Probabilité réelle": prob_true})
)

# Confusion matrix
cm = confusion_matrix(y_true, y_pred, labels=[0, 1])
cm_df = pd.DataFrame(cm, columns=["Prédit 0", "Prédit 1"], index=["Réel 0", "Réel 1"])

st.subheader("🧮 Matrice de confusion")
st.dataframe(cm_df)

# Histogramme
st.subheader("📊 Distribution des probabilités")
st.bar_chart(y_proba)

# Stats
st.subheader("📌 Statistiques")
st.write(
    {
        "Nombre de communes scorées": len(scores),
        "Taux d'incendie réel": float(y_true.mean()),
        "Taux d'incendie prédit (>=0.5)": float(y_pred.mean()),
        "AUC ROC": roc_auc,
        "AUC PR": pr_auc,
    }
)
