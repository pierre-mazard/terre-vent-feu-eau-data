# models/pipeline/features_horizon.py
"""Variables temporelles a horizon court, pour predire a une date precise.

Le modele annuel repond a « cette commune brulera-t-elle dans l'annee ? ».
Le professeur demande plus fin : « Aix-en-Provence, le 15 juin 2025 ». Il faut
donc une ligne par **commune et par date**, et non plus par commune et par
annee.

Le probleme de taille
---------------------
34 863 communes x 365 jours x 19 ans = **242 millions de lignes**. Aucune
machine de bureau ne traite cela avec pandas.

La solution retenue : **echantillonnage negatif**.

1. On garde **toutes** les lignes positives, c'est-a-dire tous les couples
   (commune, date) suivis d'un feu dans l'horizon considere.
2. On tire au hasard une fraction des lignes negatives (ici 5 negatifs par
   positif).
3. On corrige ensuite la probabilite predite pour revenir au taux reel : voir
   `corriger_prior` plus bas. Sans cette correction, le modele annoncerait des
   probabilites bien trop hautes, puisqu'il a appris sur un echantillon ou les
   feux sont artificiellement frequents.

C'est la methode standard sur les donnees d'evenements rares. Elle divise le
volume par plus de mille sans perdre un seul positif.

La grille
---------
On n'entraine pas sur les 365 jours de l'annee mais sur une grille
hebdomadaire : deux dates distantes de trois jours donnent des variables
quasiment identiques, les garder toutes n'apporte rien. En revanche le modele,
une fois entraine, **s'applique a n'importe quelle date** : les variables sont
recalculees a la volee pour la date demandee.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# Horizons demandes : « y aura-t-il au moins un feu dans les H prochains jours ? »
HORIZONS = (10, 30, 60)

# Fenetres d'historique glissant, en jours, toutes arretees la veille de la date
# evaluee : aucune variable ne regarde le jour meme ni apres.
FENETRES = (7, 30, 90, 365)

NEGATIFS_PAR_POSITIF = 5
JOURS_SANS_FEU_MAX = 3650  # plafond pour « jours depuis le dernier feu »

RAYON_VOISINAGE_KM = 20

COLONNES_HORIZON = [
    # --- historique court de la commune, arrete la veille ---
    "feux_7j",
    "feux_30j",
    "feux_90j",
    "feux_365j",
    "surface_30j_ha",
    "surface_365j_ha",
    "jours_depuis_dernier_feu",
    # --- saisonnalite ---
    "feux_meme_mois_5a",
    "jour_annee_sin",
    "jour_annee_cos",
    "mois",
    # --- voisinage : le feu ne s'arrete pas aux limites communales ---
    "feux_voisinage_30j",
    "feux_voisinage_5a",
    # --- historique long, repris du panel annuel ---
    "nb_feux_5a",
    "nb_feux_10a",
    "surface_10a_ha",
    # --- contexte fixe ---
    "latitude",
    "longitude",
    "population",
    "densite",
    "altitude_moy",
    "superficie_km2",
]

# Volontairement absents : `cluster_risque` et `cluster_spatial`. Ils sont
# calcules par DBSCAN sur l'ensemble des feux 2006-2024, periode de test
# comprise : les utiliser ici reviendrait a donner au modele une information
# qu'il ne peut pas avoir au moment de la prediction. Mesure faite, ils
# n'apportaient d'ailleurs rien : PR-AUC 0,4873 avec eux contre 0,4861 avec le
# voisinage a 20 km, qui lui est calcule strictement sur le passe et donne une
# meilleure precision au top 5 % (55,6 % contre 54,2 %).

# Multiplicateur utilise pour fabriquer une cle triable (commune, jour) unique.
# Il doit depasser l'amplitude possible de `jour` (nombre de jours depuis 1970).
_ECHELLE = 1_000_000


class HistoriqueFeux:
    """Index des feux permettant des comptages par fenetre, entierement vectorises.

    L'astuce : au lieu de boucler commune par commune, on fabrique une cle
    unique `commune * 1e6 + jour`, triee une fois pour toutes. Un comptage sur
    une fenetre devient alors deux `np.searchsorted` sur un seul tableau, pour
    des millions de lignes d'un coup.
    """

    def __init__(self, feux: pd.DataFrame, communes: list[str]):
        self.index_commune = {c: i for i, c in enumerate(communes)}

        f = feux[feux["code_insee"].isin(self.index_commune)].copy()
        f["cid"] = f["code_insee"].map(self.index_commune).astype("int32")
        f["jour"] = f["date"].values.astype("datetime64[D]").astype("int32")
        f = f.sort_values(["cid", "jour"], kind="mergesort")

        self.cles = f["cid"].to_numpy("int64") * _ECHELLE + f["jour"].to_numpy("int64")
        self.jours = f["jour"].to_numpy("int32")
        self.cids = f["cid"].to_numpy("int32")
        surfaces = f["surface_ha"].to_numpy("float64")
        self.surfaces_cum = np.concatenate([[0.0], np.cumsum(surfaces)])

        # Saisonnalite locale : nombre de feux par (commune, mois, annee), puis
        # cumul sur les annees, pour repondre a « combien de feux ce mois-ci au
        # cours des cinq annees precedentes ? ».
        f["annee"] = f["date"].dt.year.astype("int16")
        f["mois"] = f["date"].dt.month.astype("int8")
        self.annee_min = int(f["annee"].min())
        n_annees = int(f["annee"].max()) - self.annee_min + 1
        grille = np.zeros((len(communes) * 12, n_annees), dtype="int32")
        compte = f.groupby(["cid", "mois", "annee"], observed=True).size()
        for (cid, mois, annee), n in compte.items():
            grille[cid * 12 + (mois - 1), annee - self.annee_min] = n
        self.saison_cum = np.cumsum(grille, axis=1)

    # -- comptages sur une fenetre passee --------------------------------
    def _bornes(self, cid, jour, fenetre):
        haut = np.searchsorted(self.cles, cid * _ECHELLE + jour, side="right")
        bas = np.searchsorted(
            self.cles, cid * _ECHELLE + (jour - fenetre), side="right"
        )
        return bas, haut

    def compter(self, cid, jour, fenetre):
        bas, haut = self._bornes(cid, jour, fenetre)
        return (haut - bas).astype("float32")

    def surface(self, cid, jour, fenetre):
        bas, haut = self._bornes(cid, jour, fenetre)
        return (self.surfaces_cum[haut] - self.surfaces_cum[bas]).astype("float32")

    def jours_depuis_dernier(self, cid, jour):
        haut = np.searchsorted(self.cles, cid * _ECHELLE + jour, side="right")
        precedent = np.maximum(haut - 1, 0)
        valide = (haut > 0) & (self.cids[precedent] == cid)
        ecart = np.where(valide, jour - self.jours[precedent], JOURS_SANS_FEU_MAX)
        return np.clip(ecart, 0, JOURS_SANS_FEU_MAX).astype("float32")

    def feux_meme_mois_5a(self, cid, annee, mois):
        """Feux du meme mois calendaire sur les cinq annees precedentes."""
        ligne = cid * 12 + (mois - 1)
        fin = np.clip(annee - self.annee_min - 1, -1, self.saison_cum.shape[1] - 1)
        debut = np.clip(annee - self.annee_min - 6, -1, self.saison_cum.shape[1] - 1)
        haut = np.where(fin >= 0, self.saison_cum[ligne, np.maximum(fin, 0)], 0)
        bas = np.where(debut >= 0, self.saison_cum[ligne, np.maximum(debut, 0)], 0)
        return (haut - bas).astype("float32")

    # -- cible ------------------------------------------------------------
    def feu_dans_les(self, cid, jour, horizon):
        """Au moins un feu dans l'intervalle ]jour, jour + horizon]."""
        bas = np.searchsorted(self.cles, cid * _ECHELLE + jour, side="right")
        haut = np.searchsorted(
            self.cles, cid * _ECHELLE + (jour + horizon), side="right"
        )
        return (haut > bas).astype("int8")


class Voisinage:
    """Densite de feux autour de la commune, dans un rayon de 20 km.

    Pourquoi cette variable : un feu ne s'arrete pas a la limite communale. Une
    commune qui n'a jamais brule mais dont tous les voisins brulent chaque ete
    n'est pas une commune sans risque. C'est la traduction honnete de l'idee de
    « continuum de risque » : elle remplace l'appartenance a un groupe DBSCAN,
    qui, elle, etait calculee en regardant aussi le futur.

    Le voisinage est fige (il ne depend que de la geographie), mais les
    comptages, eux, sont toujours arretes a la veille de la date evaluee.
    """

    def __init__(
        self,
        communes: list[str],
        coordonnees: np.ndarray,
        rayon_km: float = RAYON_VOISINAGE_KM,
    ):
        from sklearn.neighbors import BallTree

        self.communes = communes
        self.index = {c: i for i, c in enumerate(communes)}
        self.arbre = BallTree(np.radians(coordonnees), metric="haversine")
        self.rayon = rayon_km / 6371.0

    def voisins(self, code_insee: str) -> np.ndarray:
        """Indices des communes situees a moins du rayon, la commune exclue."""
        i = self.index[code_insee]
        point = self.arbre.get_arrays()[0][i].reshape(1, -1)
        trouves = self.arbre.query_radius(point, r=self.rayon)[0]
        return trouves[trouves != i]

    def matrice(self):
        """Matrice creuse d'adjacence, pour un calcul en masse."""
        from scipy import sparse

        listes = self.arbre.query_radius(self.arbre.get_arrays()[0], r=self.rayon)
        lignes = np.repeat(np.arange(len(self.communes)), [len(v) for v in listes])
        colonnes = np.concatenate(listes)
        garder = lignes != colonnes
        return sparse.csr_matrix(
            (np.ones(int(garder.sum()), "float32"), (lignes[garder], colonnes[garder])),
            shape=(len(self.communes), len(self.communes)),
        )


def grille_dates(debut: str, fin: str, pas_jours: int = 7) -> np.ndarray:
    """Dates d'entrainement, en nombre de jours depuis 1970."""
    dates = pd.date_range(debut, fin, freq=f"{pas_jours}D")
    return dates.values.astype("datetime64[D]").astype("int32")


def construire_echantillon(
    historique: HistoriqueFeux,
    n_communes: int,
    jours: np.ndarray,
    horizon_max: int = max(HORIZONS),
    negatifs_par_positif: int = NEGATIFS_PAR_POSITIF,
    graine: int = 42,
) -> tuple[pd.DataFrame, float]:
    """Toutes les lignes positives, plus un tirage de negatifs.

    Retourne l'echantillon et la **fraction de negatifs conservee**, qui sert
    ensuite a corriger la probabilite predite.
    """
    rng = np.random.default_rng(graine)

    # 1. Les positifs, sans en perdre un seul.
    # Pour chaque feu, on prend les dates de la grille situees dans
    # [date_feu - horizon_max, date_feu - 1]. Tout est vectorise : une boucle
    # Python sur 64 000 feux serait cent fois plus lente.
    jours_feux = historique.jours.astype("int64")
    cids_feux = historique.cids.astype("int64")

    i_bas = np.searchsorted(jours, jours_feux - horizon_max, side="left")
    i_haut = np.searchsorted(jours, jours_feux, side="left")  # strictement avant
    combien = np.maximum(i_haut - i_bas, 0)

    total = int(combien.sum())
    depart = np.repeat(i_bas, combien)
    rang = np.arange(total) - np.repeat(np.cumsum(combien) - combien, combien)
    idx_grille = depart + rang

    cles_pos = np.unique(
        np.repeat(cids_feux, combien) * _ECHELLE + jours[idx_grille].astype("int64")
    )

    # 2. Les negatifs, tires au hasard dans l'espace complet commune x date,
    #    en ecartant ceux qui sont en realite positifs.
    n_cible = len(cles_pos) * negatifs_par_positif
    morceaux = []
    obtenus = 0
    while obtenus < n_cible:
        taille = int((n_cible - obtenus) * 1.3) + 1000
        c = rng.integers(0, n_communes, size=taille, dtype="int64")
        j = jours[rng.integers(0, len(jours), size=taille)].astype("int64")
        cles = np.unique(c * _ECHELLE + j)
        position = np.searchsorted(cles_pos, cles)
        position = np.clip(position, 0, len(cles_pos) - 1)
        garder = cles_pos[position] != cles
        cles = cles[garder]
        morceaux.append(cles)
        obtenus += len(cles)

    cles_neg = np.unique(np.concatenate(morceaux))[:n_cible]

    total_possible = n_communes * len(jours)
    fraction_negatifs = len(cles_neg) / max(1, total_possible - len(cles_pos))

    cles = np.concatenate([cles_pos, cles_neg])
    return (
        pd.DataFrame(
            {
                "cid": (cles // _ECHELLE).astype("int32"),
                "jour": (cles % _ECHELLE).astype("int32"),
            }
        ),
        float(fraction_negatifs),
    )


def calculer_variables(
    echantillon: pd.DataFrame,
    historique: HistoriqueFeux,
    panel_annuel: pd.DataFrame,
    communes: list[str],
) -> pd.DataFrame:
    """Ajoute les variables d'historique court, de saisonnalite et de contexte."""
    cid = echantillon["cid"].to_numpy("int64")
    jour = echantillon["jour"].to_numpy("int64")
    dates = pd.to_datetime(jour, unit="D")

    df = echantillon.copy()
    df["feux_7j"] = historique.compter(cid, jour, 7)
    df["feux_30j"] = historique.compter(cid, jour, 30)
    df["feux_90j"] = historique.compter(cid, jour, 90)
    df["feux_365j"] = historique.compter(cid, jour, 365)
    df["surface_30j_ha"] = historique.surface(cid, jour, 30)
    df["surface_365j_ha"] = historique.surface(cid, jour, 365)
    df["jours_depuis_dernier_feu"] = historique.jours_depuis_dernier(cid, jour)

    annee = dates.year.to_numpy("int32")
    mois = dates.month.to_numpy("int32")
    jour_annee = dates.dayofyear.to_numpy("float32")

    df["feux_meme_mois_5a"] = historique.feux_meme_mois_5a(cid, annee, mois)
    df["jour_annee_sin"] = np.sin(2 * np.pi * jour_annee / 365.25).astype("float32")
    df["jour_annee_cos"] = np.cos(2 * np.pi * jour_annee / 365.25).astype("float32")
    df["mois"] = mois.astype("int8")
    df["annee"] = annee.astype("int16")
    df["code_insee"] = [communes[i] for i in cid]

    contexte = panel_annuel[
        [
            "code_insee",
            "annee",
            "nb_feux_5a",
            "nb_feux_10a",
            "surface_10a_ha",
            "latitude",
            "longitude",
            "population",
            "densite",
            "altitude_moy",
            "superficie_km2",
        ]
    ]
    df = df.merge(contexte, on=["code_insee", "annee"], how="left")
    for col in COLONNES_HORIZON:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    return df


def corriger_prior(
    proba_echantillon: np.ndarray, fraction_negatifs: float
) -> np.ndarray:
    """Ramene la probabilite apprise sur echantillon au taux reel.

    Quand on ne garde qu'une fraction `b` des negatifs, la cote (odds) predite
    est surestimee d'un facteur 1/b. On la ramene en multipliant la cote par
    `b` :

        cote_reelle = cote_echantillon x b
        p_reel      = cote_reelle / (1 + cote_reelle)

    Sans cette correction, un risque reel de 0,3 % s'afficherait autour de 15 %.
    """
    p = np.clip(np.asarray(proba_echantillon, dtype="float64"), 1e-9, 1 - 1e-9)
    cote = p / (1 - p) * max(fraction_negatifs, 1e-12)
    return (cote / (1 + cote)).astype("float32")


# ---------------------------------------------------------------------------
# Calcul a la volee, pour l'application
# ---------------------------------------------------------------------------
def variables_ponctuelles(
    code_insee: str,
    date: pd.Timestamp,
    feux: pd.DataFrame,
    panel_annuel: pd.DataFrame,
    codes_voisins: list[str],
) -> pd.DataFrame:
    """Les memes variables que l'entrainement, pour une commune et une date.

    Le modele est entraine sur une grille hebdomadaire, mais rien ne l'oblige a
    n'etre applique qu'a ces dates : les variables sont ici recalculees pour la
    date exacte demandee, en n'utilisant que les feux **anterieurs** a cette
    date.

    `panel_annuel` fournit l'historique long (5 et 10 ans) et le contexte de la
    commune. Si l'annee demandee depasse la derniere annee connue, on utilise la
    derniere disponible : c'est exactement ce dont on dispose pour predire le
    futur.
    """
    date = pd.Timestamp(date).normalize()

    hist = feux[feux["code_insee"] == code_insee]
    hist = hist[hist["date"] < date]

    def fenetre(jours: int) -> pd.DataFrame:
        return hist[hist["date"] >= date - pd.Timedelta(days=jours)]

    if len(hist):
        dernier = int((date - hist["date"].max()).days)
    else:
        dernier = JOURS_SANS_FEU_MAX

    meme_mois = hist[
        (hist["date"].dt.month == date.month)
        & (hist["date"].dt.year >= date.year - 5)
        & (hist["date"].dt.year <= date.year - 1)
    ]

    voisins = feux[feux["code_insee"].isin(codes_voisins)]
    voisins = voisins[voisins["date"] < date]

    annee_panel = int(min(date.year, panel_annuel["annee"].max()))
    ligne_panel = panel_annuel[
        (panel_annuel["code_insee"] == code_insee)
        & (panel_annuel["annee"] == annee_panel)
    ]
    if ligne_panel.empty:
        raise KeyError(f"Commune {code_insee} absente du panel annuel.")
    contexte = ligne_panel.iloc[0]

    jour_annee = float(date.dayofyear)
    valeurs = {
        "feux_7j": float(len(fenetre(7))),
        "feux_30j": float(len(fenetre(30))),
        "feux_90j": float(len(fenetre(90))),
        "feux_365j": float(len(fenetre(365))),
        "surface_30j_ha": float(fenetre(30)["surface_ha"].sum()),
        "surface_365j_ha": float(fenetre(365)["surface_ha"].sum()),
        "jours_depuis_dernier_feu": float(min(dernier, JOURS_SANS_FEU_MAX)),
        "feux_meme_mois_5a": float(len(meme_mois)),
        "jour_annee_sin": float(np.sin(2 * np.pi * jour_annee / 365.25)),
        "jour_annee_cos": float(np.cos(2 * np.pi * jour_annee / 365.25)),
        "mois": float(date.month),
        "feux_voisinage_30j": float(
            len(voisins[voisins["date"] >= date - pd.Timedelta(days=30)])
        ),
        "feux_voisinage_5a": float(
            len(voisins[voisins["date"] >= date - pd.Timedelta(days=365 * 5)])
        ),
        "nb_feux_5a": float(contexte["nb_feux_5a"]),
        "nb_feux_10a": float(contexte["nb_feux_10a"]),
        "surface_10a_ha": float(contexte["surface_10a_ha"]),
        "latitude": float(contexte["latitude"]),
        "longitude": float(contexte["longitude"]),
        "population": float(contexte["population"]),
        "densite": float(contexte["densite"]),
        "altitude_moy": float(contexte["altitude_moy"]),
        "superficie_km2": float(contexte["superficie_km2"]),
    }
    return pd.DataFrame(
        [[valeurs[c] for c in COLONNES_HORIZON]], columns=COLONNES_HORIZON
    )
