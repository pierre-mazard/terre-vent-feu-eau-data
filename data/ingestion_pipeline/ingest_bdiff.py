"""ETAPE 1 DE L'INGESTION : telecharger la BDIFF, annee par annee.

POURQUOI ANNEE PAR ANNEE ?
    Le site limite chaque export a 30 000 lignes. Sur 1973-2024 il y a
    ~140 000 incendies au total, mais au maximum ~6 000 par annee : une
    requete par annee passe donc toujours sous la limite, avec de la marge.

COMMENT MARCHE L'EXPORT (trouve en inspectant le site) ?
    1. Le formulaire de recherche est un simple GET :
         /incendies?if[dateAlerteDeb][date]=01/01/2024&if[dateAlerteFin][date]=...
       Les criteres sont ensuite memorises dans la SESSION cote serveur.
    2. Le bouton "CSV" pointe vers /incendies/zip et renvoie un ZIP contenant :
         - Incendies.csv        (les donnees, separateur ';', UTF-8)
         - Definitions.pdf      (les definitions officielles)
         - Mention legales.pdf
    => Donc : on ouvre la recherche avec une Session requests, PUIS on demande
       le zip avec la MEME session (sinon le serveur ne sait pas quoi exporter).

    Le CSV a 2 lignes d'en-tete parasites avant la vraie ligne de colonnes :
       ligne 1 : "Nombre d'incendies suivant les criteres de selection : 1367"
       ligne 2 : les criteres
       ligne 3 : les vrais noms de colonnes   -> d'ou skiprows=2 a la lecture.
"""

from __future__ import annotations

import io
import re
import sys
import time
import zipfile

from config import DATA_RAW, SSL_VERIFY
import requests

BASE = "https://bdiff.agriculture.gouv.fr"
SEARCH = BASE + "/incendies"
ZIP = BASE + "/incendies/zip"

ANNEE_MIN, ANNEE_MAX = 1973, 2024
PAUSE_SECONDES = 2  # on reste poli avec un service public
LIMITE_LIGNES = 30_000  # limite annoncee par le site


def criteres_annee(annee: int) -> dict:
    """Construit les parametres du formulaire pour une annee complete."""
    return {
        "if[idIncendie]": "",
        "if[dateAlerteDeb][date]": f"01/01/{annee}",
        "if[dateAlerteDeb][time][hour]": "0",
        "if[dateAlerteDeb][time][minute]": "0",
        "if[dateAlerteFin][date]": f"31/12/{annee}",
        "if[dateAlerteFin][time][hour]": "23",
        "if[dateAlerteFin][time][minute]": "59",
        "if[periodeDeb][jour]": "",
        "if[periodeDeb][mois]": "",
        "if[periodeFin][jour]": "",
        "if[periodeFin][mois]": "",
        "if[periodeAnnees][anneeDeb]": "",
        "if[periodeAnnees][anneeFin]": "",
        "if[heureDeb]": "",
        "if[heureFin]": "",
        "if[surfaceDeInc]": "1",
        "if[surfaceDe]": "",
        "if[surfaceA]": "",
        "if[surfaceAInc]": "1",
        "if[fr]": "1",  # 1 = feux de foret (Type de feu : F)
        "if[zone]": "",
        "if[ra]": "",
        "if[deprts][value]": "",  # vide = France entiere
        "if[commune]": "",
        "if[bbox][value]": "",
        "if[submit]": "",
    }


def telecharger_annee(session: requests.Session, annee: int) -> int:
    """Telecharge une annee dans data/raw/bdiff_<annee>.csv.

    Retourne le nombre de lignes annonce par le site, ou -1.
    """
    cible = DATA_RAW / f"bdiff_{annee}.csv"
    if cible.exists():  # CACHE : on ne retelecharge jamais
        print(f"  {annee} : deja present, on saute")
        return -1

    # 1) on "fait la recherche" -> le serveur memorise les criteres
    r = session.get(SEARCH, params=criteres_annee(annee), timeout=90, verify=SSL_VERIFY)
    r.raise_for_status()

    # 2) on demande le ZIP avec la meme session
    z = session.get(ZIP, timeout=180, verify=SSL_VERIFY)
    z.raise_for_status()

    with zipfile.ZipFile(io.BytesIO(z.content)) as archive:
        nom_csv = next(n for n in archive.namelist() if n.lower().endswith(".csv"))
        contenu = archive.read(nom_csv).decode("utf-8", errors="replace")
        # on garde aussi les PDF de definitions, une seule fois
        for nom_pdf in (n for n in archive.namelist() if n.lower().endswith(".pdf")):
            dest = DATA_RAW / nom_pdf
            if not dest.exists():
                dest.write_bytes(archive.read(nom_pdf))

    # 3) controle : le site annonce lui-meme le nombre de lignes en 1re ligne
    # le compteur n'est pas toujours en 1re ligne : certaines annees ajoutent
    # d'abord un avertissement "ancienne version du formulaire". On le cherche
    # dans les 5 premieres lignes.
    nb = -1
    for ligne in contenu.splitlines()[:5]:
        m = re.search(r"crit[^:]*:\s*(\d+)", ligne)
        if m:
            nb = int(m.group(1))
            break
    if nb >= LIMITE_LIGNES:
        print(
            f"  !! {annee} : {nb} lignes = limite atteinte, il faut decouper "
            f"cette annee par departement ou par mois."
        )

    cible.write_text(contenu, encoding="utf-8")
    print(f"  {annee} : {nb} incendies -> {cible.name}")
    return nb


def main(annee_min: int = ANNEE_MIN, annee_max: int = ANNEE_MAX) -> None:
    print(f"Telechargement BDIFF {annee_min}-{annee_max} vers {DATA_RAW}")
    total = 0
    with requests.Session() as s:
        s.headers.update({"User-Agent": "projet-etudiant-msc-ia-data/1.0"})
        for annee in range(annee_min, annee_max + 1):
            try:
                nb = telecharger_annee(s, annee)
                if nb > 0:
                    total += nb
                    time.sleep(PAUSE_SECONDES)
            except Exception as e:  # on n'arrete pas tout pour une annee
                print(f"  ECHEC {annee} : {type(e).__name__} : {e}")
    print(f"Termine. {total} incendies telecharges dans cette execution.")


if __name__ == "__main__":
    a = int(sys.argv[1]) if len(sys.argv) > 1 else ANNEE_MIN
    b = int(sys.argv[2]) if len(sys.argv) > 2 else ANNEE_MAX
    main(a, b)
