"""Orchestrateur du pipeline d'ingestion.

Point d'entree unique appele par le makefile du projet :
    make run-pipeline   ->   python data/ingestion_pipeline/pipeline.py

Il enchaine les trois etapes du tuyau de donnees :
    1. referentiel geographique des communes (data.gouv)
    2. incendies BDIFF, par tranches d'annees
    3. nettoyage et chargement dans PostgreSQL + PostGIS

Usage :
    python data/ingestion_pipeline/pipeline.py                # tout
    python data/ingestion_pipeline/pipeline.py --skip-download # charge seulement
"""

import argparse
import sys
from pathlib import Path as _Path

# config.py et le paquet data/ vivent a la RACINE du depot : on l'ajoute au
# chemin de recherche pour que ce script reste lancable directement.
_RACINE = _Path(__file__).resolve().parents[2]
if str(_RACINE) not in sys.path:
    sys.path.insert(0, str(_RACINE))

from data.ingestion_pipeline import ingest_bdiff, ingest_communes, load  # noqa: E402


def main() -> int:
    parseur = argparse.ArgumentParser(description="Pipeline d'ingestion BDIFF")
    parseur.add_argument(
        "--skip-download",
        action="store_true",
        help="ne rien telecharger, charger ce qui est deja dans data/raw",
    )
    parseur.add_argument("--annee-min", type=int, default=ingest_bdiff.ANNEE_MIN)
    parseur.add_argument("--annee-max", type=int, default=ingest_bdiff.ANNEE_MAX)
    args = parseur.parse_args()

    if not args.skip_download:
        print("[1/3] Referentiel des communes")
        ingest_communes.main()
        print("[2/3] Incendies BDIFF")
        ingest_bdiff.main(args.annee_min, args.annee_max)
    else:
        print("[1-2/3] Telechargements ignores (--skip-download)")

    print("[3/3] Nettoyage et chargement en base")
    load.main()
    return 0


if __name__ == "__main__":
    sys.exit(main())
