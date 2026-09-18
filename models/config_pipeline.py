"""
Configuration centrale du pipeline ML.
"""

# Plage temporelle
ANNEE_DEBUT = 2006
ANNEE_FIN = 2024
ANNEE_TEST = 2023

# Premiere annee utilisee pour l'entrainement. Avant 2011, la fenetre glissante
# de dix ans est calculee sur moins de dix ans d'historique (min_periods=1) :
# la variable nb_feux_10a ne veut alors rien dire.
ANNEE_DEBUT_TRAIN = 2011

# Colonnes utilisées pour l'entraînement
FEATURE_COLUMNS = [
    "nb_feux_5a",
    "surface_5a_ha",
    "surface_foret_5a_ha",
    "nb_feux_10a",
    "surface_10a_ha",
    "surface_moyenne_5a_ha",
    "part_feux_ete_5a",
    "mois_reference",
    "mois_sin",
    "mois_cos",
    "cluster_risque",
    "cluster_spatial",
    "latitude",
    "longitude",
    "population",
    "densite",
    "altitude_moy",
    "superficie_km2",
]

# Colonnes utilisées pour le clustering
CLUSTER_INPUT_COLUMNS = [
    col for col in FEATURE_COLUMNS if col not in {"cluster_risque", "cluster_spatial"}
]
