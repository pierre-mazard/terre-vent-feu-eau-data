"""ETAPE 1 BIS : telecharger le referentiel geocode des communes de France.

La BDIFF donne le CODE INSEE mais PAS la latitude/longitude. Sans coordonnees,
pas de carte et pas de calcul de voisinage : ce fichier est donc indispensable.

Source : data.gouv.fr, jeu "Communes et villes de France" (licence ouverte).
On passe par l'API de data.gouv pour retrouver l'URL du CSV automatiquement,
plutot que de coder en dur une URL qui changera a la prochaine mise a jour.
"""

from __future__ import annotations

import requests

from config import DATA_RAW, SSL_VERIFY

DATASET = "communes-et-villes-de-france-en-csv-excel-json-parquet-et-feather"
API = f"https://www.data.gouv.fr/api/1/datasets/{DATASET}/"
CIBLE = DATA_RAW / "communes_france.csv"


def trouver_url_csv() -> str:
    r = requests.get(API, timeout=60, verify=SSL_VERIFY)
    r.raise_for_status()
    ressources = r.json()["resources"]
    # on veut le CSV principal (pas les versions archivees des annees passees)
    candidats = [
        x
        for x in ressources
        if x.get("format", "").lower() == "csv" and "gz" not in x["title"].lower()
    ]
    if not candidats:
        raise RuntimeError("Aucune ressource CSV trouvee sur data.gouv")
    candidats.sort(key=lambda x: x.get("last_modified", ""), reverse=True)
    print("Ressource retenue :", candidats[0]["title"])
    return candidats[0]["url"]


def main() -> None:
    if CIBLE.exists():
        print(f"{CIBLE.name} deja present, rien a faire.")
        return
    url = trouver_url_csv()
    print("Telechargement :", url)
    with requests.get(url, stream=True, timeout=300, verify=SSL_VERIFY) as r:
        r.raise_for_status()
        with open(CIBLE, "wb") as f:
            for bloc in r.iter_content(chunk_size=1 << 20):
                f.write(bloc)
    print(f"OK -> {CIBLE} ({CIBLE.stat().st_size/1e6:.1f} Mo)")


if __name__ == "__main__":
    main()
