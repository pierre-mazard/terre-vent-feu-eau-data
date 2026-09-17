import numpy as np
import pandas as pd
from sklearn.cluster import KMeans, DBSCAN
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import silhouette_score

from models.config_pipeline import (
    ANNEE_TEST,
    FEATURE_COLUMNS,
    CLUSTER_INPUT_COLUMNS,
)


def add_clusters(features: pd.DataFrame, incendies: pd.DataFrame):
    """
    Ajoute deux types de clusters :
    - cluster_risque : KMeans sur les colonnes CLUSTER_INPUT_COLUMNS,
      calibré sur l'année de référence ANNEE_TEST - 1.
    - cluster_spatial : DBSCAN sur les coordonnées des feux (latitude/longitude),
      puis agrégation au niveau commune.
    Retourne (features_avec_clusters, metadata).
    """
    print(">> Clustering : année de référence =", ANNEE_TEST - 1)

    reference = features[features["annee"] == ANNEE_TEST - 1].copy()
    print("   - lignes dans reference:", len(reference))

    if reference.empty:
        print("⚠️ Aucune donnée pour l'année de référence, clustering désactivé.")
        features["cluster_risque"] = -1
        features["cluster_spatial"] = -1
        return features, {}

    # --- KMEANS RISQUE ---
    matrice = (
        reference[CLUSTER_INPUT_COLUMNS].replace([np.inf, -np.inf], np.nan).fillna(0)
    )
    print("   - matrice shape:", matrice.shape)

    scaler = StandardScaler()
    matrice_std = scaler.fit_transform(matrice)

    inerties = {}
    silhouettes = {}

    for k in range(2, 8):
        km = KMeans(n_clusters=k, random_state=42, n_init=20)
        labels_k = km.fit_predict(matrice_std)
        inerties[k] = float(km.inertia_)
        silhouettes[k] = float(
            silhouette_score(
                matrice_std,
                labels_k,
                sample_size=min(10000, len(reference)),
                random_state=42,
            )
        )

    best_k = max(silhouettes, key=silhouettes.get)
    print("   - meilleur k (risque):", best_k)

    kmeans = KMeans(n_clusters=best_k, random_state=42, n_init=20)
    reference["cluster_risque"] = kmeans.fit_predict(matrice_std)

    silhouette = float(
        silhouette_score(
            matrice_std,
            reference["cluster_risque"],
            sample_size=min(10000, len(reference)),
            random_state=42,
        )
    )

    # --- DBSCAN SPATIAL ---
    feux_geo = incendies.dropna(subset=["latitude", "longitude"])[
        ["code_insee", "latitude", "longitude"]
    ].drop_duplicates()

    radians = np.radians(feux_geo[["latitude", "longitude"]].to_numpy())

    dbscan = DBSCAN(
        eps=20 / 6371,  # rayon 20 km
        min_samples=8,
        metric="haversine",
    )

    labels = dbscan.fit_predict(radians)
    feux_geo["cluster_spatial"] = labels

    clusters_communes = (
        feux_geo[feux_geo["cluster_spatial"] >= 0]
        .groupby("code_insee")["cluster_spatial"]
        .agg(lambda v: int(v.mode().iloc[0]))
    )

    reference["cluster_spatial"] = (
        reference["code_insee"].map(clusters_communes).fillna(-1).astype(int)
    )

    # --- MERGE DANS TOUTES LES FEATURES ---
    features = features.merge(
        reference[["code_insee", "cluster_risque", "cluster_spatial"]],
        on="code_insee",
        how="left",
    )

    metadata = {
        "kmeans_groupes": int(best_k),
        "kmeans_inerties": inerties,
        "kmeans_silhouettes": silhouettes,
        "silhouette_kmeans": silhouette,
        "dbscan_distance_km": 20,
        "dbscan_groupes_hors_bruit": int(len(set(labels)) - (1 if -1 in labels else 0)),
        "dbscan_points_bruit": int((labels == -1).sum()),
        "annee_reference_clusters": int(ANNEE_TEST - 1),
        "feature_columns": FEATURE_COLUMNS,
    }

    return features, metadata
