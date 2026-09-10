"""Tests d'integrite et de coherence de la base (point 2.3 du sujet).

Chaque test est une requete SQL dont on connait d'avance le resultat
attendu. Le script affiche OK / ECHEC pour chacun, puis ecrit les
chiffres dans docs/QUALITE.md.

Lancement :  python data/ingestion_pipeline/qualite.py
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import text

from config import ROOT, get_engine

SEUIL_GEOCODAGE = 0.97


def _scalaire(conn, sql: str):
    return conn.execute(text(sql)).scalar()


def lancer_tests() -> list[dict]:
    """Execute les 6 tests et renvoie une liste de resultats."""
    resultats: list[dict] = []
    with get_engine().connect() as conn:
        # 1 - unicite de la cle metier (annee, numero)
        doublons = _scalaire(
            conn, "SELECT count(*) - count(DISTINCT fire_id) FROM fires"
        )
        resultats.append(
            {
                "n": 1,
                "nom": "Unicite de la cle metier (annee, numero)",
                "valeur": f"{doublons} doublon(s)",
                "attendu": "0",
                "ok": doublons == 0,
            }
        )

        # 2 - taux de geocodage : combien de feux ont trouve leur commune
        taux = float(_scalaire(conn, "SELECT avg(is_geocoded::int) FROM fires") or 0)
        resultats.append(
            {
                "n": 2,
                "nom": "Taux de geocodage (jointure INSEE reussie)",
                "valeur": f"{taux:.2%}",
                "attendu": f">= {SEUIL_GEOCODAGE:.0%}",
                "ok": taux >= SEUIL_GEOCODAGE,
            }
        )

        # 3 - les annees restent dans la plage annoncee par la BDIFF
        amin, amax = conn.execute(
            text("SELECT min(annee), max(annee) FROM fires")
        ).one()
        resultats.append(
            {
                "n": 3,
                "nom": "Plage temporelle",
                "valeur": f"{amin} - {amax}",
                "attendu": "1973 - 2024",
                "ok": amin == 1973 and amax == 2024,
            }
        )

        # 4 - une surface brulee ne peut pas etre negative
        neg = _scalaire(
            conn,
            "SELECT count(*) FROM fires WHERE surface_parcourue_ha < 0",
        )
        resultats.append(
            {
                "n": 4,
                "nom": "Aucune surface negative",
                "valeur": f"{neg} ligne(s)",
                "attendu": "0",
                "ok": neg == 0,
            }
        )

        # 5 - la surface de foret est une PARTIE de la surface parcourue :
        #     elle ne peut donc pas lui etre superieure
        incoh = _scalaire(
            conn,
            "SELECT count(*) FROM fires "
            "WHERE surface_foret_ha > surface_parcourue_ha",
        )
        total = _scalaire(conn, "SELECT count(*) FROM fires") or 1
        part = incoh / total
        resultats.append(
            {
                "n": 5,
                "nom": "Surface foret <= surface parcourue",
                "valeur": f"{incoh} ligne(s) ({part:.3%})",
                "attendu": "< 1 %",
                "ok": part < 0.01,
            }
        )

        # 6 - controle croise : le nombre de lignes chargees doit egaler
        #     le nombre de lignes brutes distinctes du staging
        brut = _scalaire(
            conn,
            "SELECT count(DISTINCT (annee, numero)) FROM stg_bdiff "
            "WHERE annee ~ '^[0-9]{4}$' AND numero ~ '^[0-9]+$'",
        )
        ecart = abs(total - brut) / max(brut, 1)
        resultats.append(
            {
                "n": 6,
                "nom": "Controle croise staging -> fires",
                "valeur": f"{brut} brut distinct / {total} charges",
                "attendu": "ecart < 0,1 %",
                "ok": ecart < 0.001,
            }
        )
    return resultats


def ecrire_rapport(resultats: list[dict]) -> None:
    chemin = ROOT / "docs" / "QUALITE.md"
    chemin.parent.mkdir(parents=True, exist_ok=True)
    lignes = [
        "# Qualite des donnees",
        "",
        f"Genere le {datetime.now():%d/%m/%Y a %H:%M} "
        "par `data/ingestion_pipeline/qualite.py`.",
        "",
        "| # | Test | Mesure | Attendu | Verdict |",
        "|---|------|--------|---------|---------|",
    ]
    for r in resultats:
        verdict = "OK" if r["ok"] else "ECHEC"
        lignes.append(
            f"| {r['n']} | {r['nom']} | {r['valeur']} | "
            f"{r['attendu']} | **{verdict}** |"
        )
    lignes.append("")
    chemin.write_text("\n".join(lignes), encoding="utf-8")
    print(f"\nRapport ecrit dans {chemin}")


def main() -> None:
    resultats = lancer_tests()
    print("Tests d'integrite et de coherence")
    print("-" * 60)
    for r in resultats:
        etat = "OK   " if r["ok"] else "ECHEC"
        print(f"[{etat}] {r['n']}. {r['nom']}")
        print(f"         mesure : {r['valeur']}  (attendu {r['attendu']})")
    echecs = sum(1 for r in resultats if not r["ok"])
    print("-" * 60)
    print(f"{len(resultats) - echecs}/{len(resultats)} tests passes")
    ecrire_rapport(resultats)


if __name__ == "__main__":
    main()
