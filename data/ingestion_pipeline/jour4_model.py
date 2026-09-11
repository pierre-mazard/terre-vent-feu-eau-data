"""Feature engineering, clustering et modele de risque du jour 4."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.cluster import DBSCAN, KMeans
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    roc_auc_score,
    silhouette_score,
)
from sklearn.preprocessing import StandardScaler
from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from config import DATA_PROCESSED, MODELS, get_engine  # noqa: E402

ANNEE_DEBUT = 2006
ANNEE_FIN = 2024
ANNEE_TEST = 2023
FEATURE_COLUMNS = [
    "nb_feux_5a",
    "surface_5a_ha",
    "surface_foret_5a_ha",
    "nb_feux_10a",
    "surface_10a_ha",
    "surface_moyenne_5a_ha",
    "part_feux_ete_5a",
    "latitude",
    "longitude",
    "population",
    "densite",
    "altitude_moy",
    "superficie_km2",
]


def charger_donnees() -> tuple[pd.DataFrame, pd.DataFrame]:
    incendies_sql = text(
        """
        SELECT code_insee, annee, mois, surface_parcourue_ha,
               surface_foret_ha
        FROM fires
        WHERE annee >= :annee_debut
        """
    )
    communes_sql = text(
        """
        SELECT code_insee, latitude, longitude, population, densite,
             altitude_moy, superficie_km2, nom
        FROM ref_communes
        WHERE latitude IS NOT NULL AND longitude IS NOT NULL
        """
    )
    with get_engine().connect() as conn:
        incendies = pd.read_sql(incendies_sql, conn, params={"annee_debut": ANNEE_DEBUT})
        communes = pd.read_sql(communes_sql, conn)
    incendies["code_insee"] = incendies["code_insee"].astype(str)
    communes["code_insee"] = communes["code_insee"].astype(str)
    return incendies, communes


def construire_features(incendies: pd.DataFrame, communes: pd.DataFrame) -> pd.DataFrame:
    annees = pd.DataFrame({"annee": range(ANNEE_DEBUT, ANNEE_FIN + 1)})
    communes_actives = communes[["code_insee"]].drop_duplicates()
    communes_actives["cle"] = 1
    annees["cle"] = 1
    panel = communes_actives.merge(annees, on="cle").drop(columns="cle")
    panel = panel.merge(communes, on="code_insee", how="left")

    incendies = incendies.copy()
    incendies["surface_parcourue_ha"] = pd.to_numeric(
        incendies["surface_parcourue_ha"], errors="coerce"
    ).fillna(0)
    incendies["surface_foret_ha"] = pd.to_numeric(
        incendies["surface_foret_ha"], errors="coerce"
    ).fillna(0)
    incendies["est_ete"] = incendies["mois"].isin([6, 7, 8, 9]).astype(int)
    annuel = (
        incendies.groupby(["code_insee", "annee"], as_index=False)
        .agg(
            nb_feux=("code_insee", "size"),
            surface_ha=("surface_parcourue_ha", "sum"),
            surface_foret_ha=("surface_foret_ha", "sum"),
            surface_moyenne_ha=("surface_parcourue_ha", "mean"),
            feux_ete=("est_ete", "sum"),
        )
    )
    panel = panel.merge(annuel, on=["code_insee", "annee"], how="left")
    for column in ["nb_feux", "surface_ha", "surface_foret_ha", "surface_moyenne_ha", "feux_ete"]:
        panel[column] = panel[column].fillna(0)

    panel = panel.sort_values(["code_insee", "annee"])
    groupe = panel.groupby("code_insee", sort=False)
    panel["nb_feux_5a"] = groupe["nb_feux"].transform(
        lambda serie: serie.shift(1).rolling(5, min_periods=1).sum()
    )
    panel["surface_5a_ha"] = groupe["surface_ha"].transform(
        lambda serie: serie.shift(1).rolling(5, min_periods=1).sum()
    )
    panel["surface_foret_5a_ha"] = groupe["surface_foret_ha"].transform(
        lambda serie: serie.shift(1).rolling(5, min_periods=1).sum()
    )
    panel["nb_feux_10a"] = groupe["nb_feux"].transform(
        lambda serie: serie.shift(1).rolling(10, min_periods=1).sum()
    )
    panel["surface_10a_ha"] = groupe["surface_ha"].transform(
        lambda serie: serie.shift(1).rolling(10, min_periods=1).sum()
    )
    panel["surface_moyenne_5a_ha"] = groupe["surface_moyenne_ha"].transform(
        lambda serie: serie.shift(1).rolling(5, min_periods=1).mean()
    )
    panel["part_feux_ete_5a"] = groupe["feux_ete"].transform(
        lambda serie: serie.shift(1).rolling(5, min_periods=1).sum()
    ) / panel["nb_feux_5a"].replace(0, np.nan)
    panel["part_feux_ete_5a"] = panel["part_feux_ete_5a"].fillna(0)
    panel["feux_annee_suivante"] = groupe["nb_feux"].shift(-1).fillna(0)
    panel["cible_incendie_suivant"] = (panel["feux_annee_suivante"] > 0).astype(int)
    return panel


def ajouter_clusters(features: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    reference = features[features["annee"] == ANNEE_TEST].copy()
    matrice = reference[FEATURE_COLUMNS].replace([np.inf, -np.inf], np.nan).fillna(0)
    scaler = StandardScaler()
    matrice_standardisee = scaler.fit_transform(matrice)
    nombre_groupes = 4
    kmeans = KMeans(n_clusters=nombre_groupes, random_state=42, n_init=20)
    reference["cluster_risque"] = kmeans.fit_predict(matrice_standardisee)
    silhouette = silhouette_score(
        matrice_standardisee,
        reference["cluster_risque"],
        sample_size=min(10000, len(reference)),
        random_state=42,
    )

    coordonnees = reference[["latitude", "longitude"]].dropna().copy()
    radians = np.radians(coordonnees.to_numpy())
    dbscan = DBSCAN(
        eps=50 / 6371,
        min_samples=5,
        metric="haversine",
    )
    labels = dbscan.fit_predict(radians)
    reference["cluster_spatial"] = -1
    reference.loc[coordonnees.index, "cluster_spatial"] = labels

    features = features.merge(
        reference[["code_insee", "cluster_risque", "cluster_spatial"]],
        on="code_insee",
        how="left",
    )
    return features, {
        "kmeans_groupes": nombre_groupes,
        "silhouette_kmeans": float(silhouette),
        "dbscan_distance_km": 50,
        "dbscan_groupes_hors_bruit": int(len(set(labels)) - (1 if -1 in labels else 0)),
        "dbscan_points_bruit": int((labels == -1).sum()),
        "annee_reference_clusters": ANNEE_TEST,
        "feature_columns": FEATURE_COLUMNS,
    },


def entrainer_modele(features: pd.DataFrame) -> tuple[RandomForestClassifier, dict, pd.DataFrame]:
    utilisables = features[features["annee"].between(2011, ANNEE_TEST)].copy()
    entrainement = utilisables[utilisables["annee"] < ANNEE_TEST]
    test = utilisables[utilisables["annee"] == ANNEE_TEST]
    matrice_train = entrainement[FEATURE_COLUMNS].replace([np.inf, -np.inf], np.nan).fillna(0)
    matrice_test = test[FEATURE_COLUMNS].replace([np.inf, -np.inf], np.nan).fillna(0)
    cible_train = entrainement["cible_incendie_suivant"]
    cible_test = test["cible_incendie_suivant"]
    modele = RandomForestClassifier(
        n_estimators=200,
        max_depth=12,
        min_samples_leaf=3,
        class_weight="balanced",
        random_state=42,
        n_jobs=-1,
    )
    modele.fit(matrice_train, cible_train)
    probabilites = modele.predict_proba(matrice_test)[:, 1]
    predictions = (probabilites >= 0.5).astype(int)
    metriques = {
        "annees_entrainement": "2011-2022",
        "annee_test": ANNEE_TEST,
        "roc_auc": float(roc_auc_score(cible_test, probabilites)),
        "accuracy": float(accuracy_score(cible_test, predictions)),
        "balanced_accuracy": float(balanced_accuracy_score(cible_test, predictions)),
        "taux_incendie_test": float(cible_test.mean()),
    }
    rng = np.random.default_rng(42)
    codes = entrainement["code_insee"].drop_duplicates().to_numpy()
    rng.shuffle(codes)
    decoupage = int(len(codes) * 0.8)
    codes_train = set(codes[:decoupage])
    codes_test = set(codes[decoupage:])
    entrainement_geo = entrainement[entrainement["code_insee"].isin(codes_train)]
    test_geo = test[test["code_insee"].isin(codes_test)]
    modele_geo = RandomForestClassifier(
        n_estimators=150,
        max_depth=12,
        min_samples_leaf=3,
        class_weight="balanced",
        random_state=42,
        n_jobs=-1,
    )
    modele_geo.fit(
        entrainement_geo[FEATURE_COLUMNS].replace([np.inf, -np.inf], np.nan).fillna(0),
        entrainement_geo["cible_incendie_suivant"],
    )
    probabilites_geo = modele_geo.predict_proba(
        test_geo[FEATURE_COLUMNS].replace([np.inf, -np.inf], np.nan).fillna(0)
    )[:, 1]
    metriques["roc_auc_validation_geographique"] = float(
        roc_auc_score(test_geo["cible_incendie_suivant"], probabilites_geo)
    )
    metriques["communes_test_geographique"] = int(len(codes_test))
    future = features[features["annee"] == ANNEE_FIN].copy()
    future_matrix = future[FEATURE_COLUMNS].replace([np.inf, -np.inf], np.nan).fillna(0)
    future["probabilite_incendie"] = modele.predict_proba(future_matrix)[:, 1]
    future["annee_prediction"] = future["annee"] + 1
    future["score_risque"] = (future["probabilite_incendie"] * 100).round(2)
    future["niveau_risque"] = pd.cut(
        future["score_risque"],
        bins=[-np.inf, 10, 25, 50, np.inf],
        labels=["Faible", "Modere", "Eleve", "Tres eleve"],
    ).astype(str)
    return modele, metriques, future


def main() -> None:
    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    MODELS.mkdir(parents=True, exist_ok=True)
    incendies, communes = charger_donnees()
    features = construire_features(incendies, communes)
    features, clusters = ajouter_clusters(features)
    modele, metriques, scores = entrainer_modele(features)
    features[features["annee"].isin([ANNEE_TEST, ANNEE_FIN])].to_csv(
        DATA_PROCESSED / "features_risque.csv", index=False
    )
    scores[
        [
            "code_insee", "nom", "annee", "annee_prediction", "latitude", "longitude",
            "cluster_risque", "cluster_spatial", "nb_feux_5a", "surface_5a_ha",
            "probabilite_incendie", "score_risque", "niveau_risque",
        ]
    ].to_csv(DATA_PROCESSED / "scores_risque.csv", index=False)
    joblib.dump(modele, MODELS / "modele_risque.joblib")
    metadata = {**clusters, **metriques, "annee_score": ANNEE_FIN + 1}
    (MODELS / "metriques_risque.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )
    print(json.dumps(metadata, indent=2))
    print(f"Features ecrites : {len(features):,}")
    print(f"Scores ecrits : {len(scores):,}")


if __name__ == "__main__":
    main()
