# models/train_test/train_horizons.py
"""Entraine un modele par horizon : 10, 30 et 60 jours.

Produit, dans `models/run/<run>/` :

* `modele_horizon_10j.json`, `_30j`, `_60j` : les modeles XGBoost (2 a 3 Mo
  chacun, format natif JSON, lisible et portable) ;
* `horizons_metriques.json` : les metriques et la fraction de negatifs
  conservee, indispensable a la correction du prior ;
* `feux_historique.csv` : la chronologie des feux (commune, date, surface),
  utilisee par l'application pour recalculer les variables a n'importe quelle
  date ;
* `panel_horizon.parquet` : l'etat annuel de chaque commune.

Lancer : `python -m models.train_test.train_horizons`
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
if str(RACINE) not in sys.path:
    sys.path.insert(0, str(RACINE))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.metrics import average_precision_score, roc_auc_score  # noqa: E402

from config import DATA_PROCESSED, MODELS  # noqa: E402
from models.pipeline.features_horizon import (  # noqa: E402
    COLONNES_HORIZON,
    HORIZONS,
    HistoriqueFeux,
    Voisinage,
    calculer_variables,
    construire_echantillon,
    corriger_prior,
    grille_dates,
)
from models.pipeline.ingestion import load_feux_dates  # noqa: E402


def nom_de_run(chemin: str) -> str:
    """Dernier segment d'un chemin, que les separateurs soient / ou \\.

    `latest_run.json` est ecrit par la machine qui lance le pipeline. Sous
    Windows il contient des antislash ; `Path(...).name` sous Linux ne les
    reconnait pas comme separateurs et renvoie alors le chemin entier. On
    normalise donc a la main.
    """
    return chemin.replace("\\", "/").rstrip("/").split("/")[-1]


ANNEE_DEBUT_GRILLE = 2010
DATE_BASCULE = "2023-01-01"  # tout ce qui precede sert a apprendre


def ajouter_voisinage(
    df: pd.DataFrame,
    voisinage: Voisinage,
    historique: HistoriqueFeux,
    communes: list[str],
    jours_grille: np.ndarray,
) -> pd.DataFrame:
    """Densite de feux chez les voisins : sur 30 jours et sur 5 ans."""
    A = voisinage.matrice()
    n = len(communes)

    # 30 jours : une colonne par date de la grille, puis produit matriciel.
    compte_30 = np.zeros((n, len(jours_grille)), "float32")
    tous = np.arange(n, dtype="int64")
    for k, j in enumerate(jours_grille):
        compte_30[:, k] = historique.compter(tous, np.full(n, int(j), "int64"), 30)
    v30 = A @ compte_30
    position = {int(j): k for k, j in enumerate(jours_grille)}

    # 5 ans : une colonne par annee.
    annees = np.arange(2000, 2026)
    compte_5a = np.zeros((n, len(annees)), "float32")
    for k, a in enumerate(annees):
        fin = np.datetime64(f"{a}-01-01").astype("datetime64[D]").astype("int64")
        compte_5a[:, k] = historique.compter(tous, np.full(n, fin, "int64"), 365 * 5)
    v5 = A @ compte_5a
    pos_annee = {int(a): k for k, a in enumerate(annees)}

    df = df.copy()
    df["feux_voisinage_30j"] = v30[
        df["cid"].to_numpy(), df["jour"].map(position).fillna(0).astype(int).to_numpy()
    ]
    df["feux_voisinage_5a"] = v5[
        df["cid"].to_numpy(),
        df["annee"].map(pos_annee).fillna(0).astype(int).to_numpy(),
    ]
    return df


def main() -> None:
    from xgboost import XGBClassifier

    latest = json.loads(
        (DATA_PROCESSED / "latest_run.json").read_text(encoding="utf-8") or "{}"
    )
    if "run_dir" not in latest:
        raise SystemExit("latest_run.json vide : lance d'abord build_dataset.")
    run_dir = Path(latest["run_dir"])
    if not run_dir.exists():
        run_dir = DATA_PROCESSED / "run" / nom_de_run(latest["run_dir"])
    model_run_dir = MODELS / "run" / run_dir.name
    model_run_dir.mkdir(parents=True, exist_ok=True)

    print(">> Chargement des feux dates et des communes…", flush=True)
    feux = load_feux_dates()

    panel = pd.read_csv(
        (
            (model_run_dir / "features_risque.csv")
            if (model_run_dir / "features_risque.csv").exists()
            else (run_dir / "features_final.csv")
        ),
        usecols=[
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
        ],
        low_memory=False,
    )
    panel["code_insee"] = (
        panel["code_insee"]
        .astype(str)
        .str.replace(r"\.0$", "", regex=True)
        .str.zfill(5)
    )
    panel["annee"] = panel["annee"].astype("int16")

    communes = sorted(panel["code_insee"].unique().tolist())
    geo = (
        panel.drop_duplicates("code_insee")
        .set_index("code_insee")
        .loc[communes, ["latitude", "longitude"]]
        .to_numpy("float64")
    )

    print(">> Index des feux et voisinage 20 km…", flush=True)
    historique = HistoriqueFeux(feux, communes)
    voisinage = Voisinage(communes, geo)

    jours = grille_dates(f"{ANNEE_DEBUT_GRILLE}-01-01", "2024-11-01", 7)
    espace = f"{len(communes) * len(jours):,}".replace(",", " ")
    print(f"   espace complet : {espace} couples commune x date")

    print(
        ">> Echantillonnage (tous les positifs + 5 negatifs par positif)…", flush=True
    )
    echantillon, fraction = construire_echantillon(historique, len(communes), jours)
    part = len(echantillon) / (len(communes) * len(jours)) * 100
    retenues = f"{len(echantillon):,}".replace(",", " ")
    print(f"   {retenues} lignes retenues, soit {part:.1f} % de l'espace")
    print(f"   fraction de negatifs conservee : {fraction:.6f}")

    print(">> Calcul des variables…", flush=True)
    X = calculer_variables(echantillon, historique, panel, communes)
    X = ajouter_voisinage(X, voisinage, historique, communes, jours)
    X["date"] = pd.to_datetime(X["jour"], unit="D")

    for h in HORIZONS:
        X[f"cible_{h}j"] = historique.feu_dans_les(
            X["cid"].to_numpy("int64"), X["jour"].to_numpy("int64"), h
        )

    train = X[X["date"] < DATE_BASCULE]
    test = X[X["date"] >= DATE_BASCULE]
    n_tr = f"{len(train):,}".replace(",", " ")
    n_te = f"{len(test):,}".replace(",", " ")
    print(f"   train {n_tr} | test {n_te}")

    resultats = {}
    for h in HORIZONS:
        y_train = train[f"cible_{h}j"].to_numpy()
        y_test = test[f"cible_{h}j"].to_numpy()
        poids = float((y_train == 0).sum() / max(1, (y_train == 1).sum()))

        modele = XGBClassifier(
            n_estimators=400,
            max_depth=6,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            min_child_weight=10,
            reg_lambda=1.0,
            scale_pos_weight=poids,
            eval_metric="aucpr",
            tree_method="hist",
            n_jobs=-1,
            random_state=42,
        )
        debut = time.time()
        modele.fit(train[COLONNES_HORIZON], y_train)
        proba = modele.predict_proba(test[COLONNES_HORIZON])[:, 1]
        duree = time.time() - debut

        base = float(y_test.mean())
        pr_auc = float(average_precision_score(y_test, proba))
        seuil = float(np.quantile(proba, 0.95))
        designees = y_test[proba >= seuil]
        reelle = corriger_prior(proba, fraction)

        resultats[f"{h}j"] = {
            "pr_auc": pr_auc,
            "pr_auc_baseline_echantillon": base,
            "gain_sur_le_hasard": pr_auc / base if base else float("nan"),
            "roc_auc": float(roc_auc_score(y_test, proba)),
            "precision_top_5pct": float(designees.mean()),
            "rappel_top_5pct": float(designees.sum() / max(1, y_test.sum())),
            "proba_reelle_moyenne": float(reelle.mean()),
            "proba_reelle_max": float(reelle.max()),
            "duree_entrainement_s": round(duree, 1),
            "importance": {
                c: float(v)
                for c, v in sorted(
                    zip(COLONNES_HORIZON, modele.feature_importances_),
                    key=lambda kv: -kv[1],
                )
            },
        }
        modele.save_model(model_run_dir / f"modele_horizon_{h}j.json")
        r = resultats[f"{h}j"]
        print(
            f"   horizon {h:>2}j : PR-AUC {pr_auc:.4f} "
            f"(x{r['gain_sur_le_hasard']:.1f}) "
            f"· precision@5% {r['precision_top_5pct'] * 100:.1f} % "
            f"· rappel@5% {r['rappel_top_5pct'] * 100:.1f} % · {duree:.0f}s",
            flush=True,
        )

    (model_run_dir / "horizons_metriques.json").write_text(
        json.dumps(
            {
                "fraction_negatifs": fraction,
                "variables": COLONNES_HORIZON,
                "grille_pas_jours": 7,
                "annees_entrainement": f"{ANNEE_DEBUT_GRILLE}-2022",
                "periode_test": f"{DATE_BASCULE} -> 2024-11-01",
                "lignes_entrainement": int(len(train)),
                "lignes_test": int(len(test)),
                "espace_complet": int(len(communes) * len(jours)),
                "horizons": resultats,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    # Artefacts dont l'application a besoin pour recalculer les variables a la
    # volee, pour n'importe quelle date demandee.
    feux[["code_insee", "date", "surface_ha"]].to_csv(
        model_run_dir / "feux_historique.csv", index=False
    )
    panel.to_parquet(model_run_dir / "panel_horizon.parquet", index=False)

    print(f"\nEcrit dans {model_run_dir}")


if __name__ == "__main__":
    main()
