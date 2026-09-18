# models/train_test/comparaison_modeles.py
"""Compare trois familles de modeles sur exactement le meme decoupage.

Le professeur a demande « Random Forest ou XGBoost ? ». Sans point de
comparaison chiffre, choisir la Random Forest n'est pas un choix, c'est une
preference. Ce script entraine les trois candidats sur les memes lignes, avec
les memes variables, et les evalue avec les memes metriques :

* la **regression logistique** donne le plancher : ce qu'on obtient avec un
  modele lineaire, sans interaction ;
* la **Random Forest** capte les seuils et les interactions ;
* **XGBoost** (gradient boosting) construit les arbres les uns apres les
  autres, chacun corrigeant les erreurs du precedent.

Sortie : `models/run/<run>/comparaison_modeles.json`, lu par la page Streamlit
« 10 · Comparaison des modeles ».
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
from sklearn.calibration import CalibratedClassifierCV  # noqa: E402
from sklearn.ensemble import RandomForestClassifier  # noqa: E402
from sklearn.linear_model import LogisticRegression  # noqa: E402
from sklearn.metrics import (  # noqa: E402
    average_precision_score,
    brier_score_loss,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline  # noqa: E402
from sklearn.preprocessing import StandardScaler  # noqa: E402

from config import DATA_PROCESSED, MODELS  # noqa: E402
from models.config_pipeline import (  # noqa: E402
    ANNEE_DEBUT_TRAIN,
    ANNEE_TEST,
    FEATURE_COLUMNS,
)


def nom_de_run(chemin: str) -> str:
    """Dernier segment d'un chemin, que les separateurs soient / ou \\.

    `latest_run.json` est ecrit par la machine qui lance le pipeline. Sous
    Windows il contient des antislash ; `Path(...).name` sous Linux ne les
    reconnait pas comme separateurs et renvoie alors le chemin entier. On
    normalise donc a la main.
    """
    return chemin.replace("\\", "/").rstrip("/").split("/")[-1]


def metriques(y_true, proba) -> dict:
    """Le meme jeu de metriques pour tous les modeles.

    `precision_top_5pct` et `rappel_top_5pct` ont le meme numerateur mais des
    denominateurs differents : les confondre divise le chiffre annonce par deux.
    """
    y_true = np.asarray(y_true)
    seuil = float(np.quantile(proba, 0.95))
    designees = y_true[proba >= seuil]
    positifs = float(y_true.sum())
    base = float(y_true.mean())

    pr_auc = float(average_precision_score(y_true, proba))
    precision = float(designees.mean()) if len(designees) else 0.0

    return {
        "pr_auc": pr_auc,
        "pr_auc_baseline": base,
        "gain_sur_le_hasard": pr_auc / base if base else float("nan"),
        "roc_auc": float(roc_auc_score(y_true, proba)),
        "brier_score": float(brier_score_loss(y_true, proba)),
        "precision_top_5pct": precision,
        "rappel_top_5pct": (float(designees.sum() / positifs) if positifs else 0.0),
        "communes_designees": int(len(designees)),
        "communes_brulees": int(positifs),
        "communes_attrapees": int(designees.sum()),
    }


def candidats(poids_classe: float):
    """Les trois modeles compares, tous calibres de la meme facon."""
    foret = RandomForestClassifier(
        n_estimators=200,
        max_depth=12,
        min_samples_leaf=3,
        class_weight="balanced",
        n_jobs=-1,
        random_state=42,
    )

    from xgboost import XGBClassifier

    boosting = XGBClassifier(
        n_estimators=400,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        min_child_weight=5,
        reg_lambda=1.0,
        # equivalent de class_weight="balanced" pour XGBoost : on donne aux
        # rares positifs un poids egal au rapport negatifs / positifs.
        scale_pos_weight=poids_classe,
        eval_metric="aucpr",
        tree_method="hist",
        n_jobs=-1,
        random_state=42,
    )

    logistique = Pipeline(
        [
            ("echelle", StandardScaler()),
            (
                "modele",
                LogisticRegression(
                    max_iter=2000,
                    class_weight="balanced",
                    random_state=42,
                ),
            ),
        ]
    )

    return {
        "Regression logistique": logistique,
        "Random Forest": foret,
        "XGBoost": boosting,
    }


def comparer(features: pd.DataFrame) -> dict:
    train = features[
        (features["annee"] >= ANNEE_DEBUT_TRAIN) & (features["annee"] < ANNEE_TEST)
    ]
    test = features[features["annee"] == ANNEE_TEST]

    X_train = train[FEATURE_COLUMNS].astype("float32")
    y_train = train["cible_incendie_suivant"].astype(int)
    X_test = test[FEATURE_COLUMNS].astype("float32")
    y_test = test["cible_incendie_suivant"].astype(int)

    poids = float((y_train == 0).sum() / max(1, (y_train == 1).sum()))

    resultats = {}
    for nom, modele in candidats(poids).items():
        print(f">> {nom}…", flush=True)
        debut = time.time()
        calibre = CalibratedClassifierCV(modele, method="sigmoid", cv=3)
        calibre.fit(X_train, y_train)
        proba = calibre.predict_proba(X_test)[:, 1]
        duree = time.time() - debut

        resultats[nom] = {
            **metriques(y_test, proba),
            "duree_entrainement_s": round(duree, 1),
        }
        print(
            f"   PR-AUC {resultats[nom]['pr_auc']:.4f} · "
            f"rappel@5% {resultats[nom]['rappel_top_5pct']:.3f} · "
            f"{duree:.0f}s",
            flush=True,
        )

    return {
        "protocole": {
            "annees_entrainement": f"{ANNEE_DEBUT_TRAIN}-{ANNEE_TEST - 1}",
            "annee_test": int(ANNEE_TEST),
            "lignes_entrainement": int(len(train)),
            "lignes_test": int(len(test)),
            "variables": FEATURE_COLUMNS,
            "taux_positifs_test": float(y_test.mean()),
            "calibration": "sigmoide, cv=3, identique pour les trois modeles",
        },
        "modeles": resultats,
    }


def main() -> None:
    latest = json.loads(
        (DATA_PROCESSED / "latest_run.json").read_text(encoding="utf-8") or "{}"
    )
    if "run_dir" not in latest:
        raise SystemExit(
            "latest_run.json est vide : lance d'abord "
            "`python -m models.pipeline.build_dataset`"
        )

    run_dir = Path(latest["run_dir"])
    if not run_dir.exists():
        run_dir = DATA_PROCESSED / "run" / nom_de_run(latest["run_dir"])
    model_run_dir = MODELS / "run" / run_dir.name
    model_run_dir.mkdir(parents=True, exist_ok=True)

    source = model_run_dir / "features_risque.csv"
    if not source.exists():
        source = run_dir / "features_final.csv"

    print(f"Lecture de {source}…", flush=True)
    colonnes = list(
        dict.fromkeys(FEATURE_COLUMNS + ["annee", "cible_incendie_suivant"])
    )
    features = pd.read_csv(source, usecols=colonnes, low_memory=False)

    rapport = comparer(features)
    (model_run_dir / "comparaison_modeles.json").write_text(
        json.dumps(rapport, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"\nEcrit : {model_run_dir / 'comparaison_modeles.json'}")


if __name__ == "__main__":
    main()
