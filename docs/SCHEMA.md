# Dictionnaire de donnees et definitions officielles

## 1. Source BDIFF — ce qu'on a verifie nous-memes (07/09/2026)

| Constat | Valeur |
|---|---|
| Volume total 1973 → 2024 | **140 248 incendies**, 1 057 973 ha parcourus |
| Volume 2024 seul | 1 367 incendies, 2 768 ha |
| Limite d'export | 30 000 lignes → **une requete par annee suffit** (max ~6 000/an) |
| Formulaire | GET sur `/incendies` avec des parametres `if[...]`, criteres memorises en session |
| Export | `GET /incendies/zip` → ZIP contenant `Incendies.csv`, `Definitions.pdf`, `Mention legales.pdf` |
| Format CSV | UTF-8, separateur `;`, **2 lignes d'en-tete parasites** avant les noms de colonnes |
| Surfaces | exprimees en **m²** (et non en hectares) |
| Cle metier | `(Annee, Numero)` — unique, verifie sur l'export 2024 |
| Perimetre par defaut | `if[fr]=1` = « Type de feu : F » (feux de foret) |

### Limites annoncees par le site lui-meme (à citer en soutenance)

- « L'application ne contient pas de donnees incendies **avant 2006 en dehors de
  la zone mediterraneenne Promethee** » → toute analyse de tendance sur
  1973-2005 ne porte QUE sur le Sud. C'est un **biais majeur**.
- Departement 64 : donnees **perdues** en 2010 (incident technique), **absentes** en 2011.
- Campagnes 2024 encore incompletes pour les departements 75, 92, 93, 94.
- La saisie est collaborative → prudence sur les feux anterieurs a 2020 hors zone mediterraneenne.

### Evolution de structure en 2023 (point important)

Les colonnes de surface par vegetation **ont change a partir de la campagne 2023** :

| Fiches **>= 2023** | Fiches **< 2023** |
|---|---|
| Surface foret | Surface foret |
| Maquis / garrigues (zone medit.) | Maquis / garrigues (zone medit.) |
| Autres surfaces naturelles hors foret | Surface autres terres boisees |
| Surfaces agricoles | Surfaces non boisees naturelles |
| Autres surfaces | Surfaces non boisees artificialisees |

→ Consequence pour nous : **seules `Surface parcourue` et `Surface foret` sont
comparables sur toute la periode.** Les autres colonnes doivent etre utilisees
par sous-periode, ou agregees prudemment. On garde les deux jeux de colonnes en
base (elles sont simplement nulles hors de leur periode).

## 2. Definitions officielles (extraites de `Definitions.pdf` fourni dans l'export)

**Incendie de foret** : incendie qui demarre en foret ou s'y propage au cours de
son evolution. Dans l'aire mediterraneenne, un feu de maquis ou garrigue compte
comme feu de foret.

**Date d'alerte** : date et heure ou l'information d'un depart de feu parvient au CODIS.

**Surface parcourue** : surface totale parcourue par le feu, quelle que soit la
vegetation touchee.

**Precision des surfaces** : `Estimees` (non mesurees) / `Mesurees` (terrain ou SIG).
→ 2024 : 741 estimees vs 626 mesurees. A signaler comme limite.

**Foret** (criteres cumulatifs, avant incendie) : couvert arbore > 10 %,
surface d'un seul tenant > 0,5 ha, largeur > 20 m.

**Aire mediterraneenne** (colonnes de surface specifiques) :
`04, 05, 06, 07, 11, 13, 2A, 2B, 26, 30, 34, 48, 66, 83, 84`.

**Nature** (origine, renseignee dans ~59 % des cas seulement) :

| Valeur | Definition |
|---|---|
| Naturelle | non causee par une activite humaine (foudre…) |
| Accidentelle | cause humaine indirecte (ligne electrique, echappement…) |
| Malveillance | volontaire |
| Involontaire (travaux) | activite professionnelle sans intention |
| Involontaire (particulier) | activite privee ou de loisir sans intention |

**Type de peuplement** (code 1 a 6, renseigne dans ~42 % des cas) :
landes/garrigues/maquis, taillis, futaies feuillues, futaies resineuses,
futaies melangees, regeneration et reboisement.

## 3. Referentiel des communes

Source : data.gouv.fr, « Communes et villes de France » (Licence Ouverte 2.0),
62 colonnes, MAJ annuelle. Colonnes retenues : `code_insee`, `nom_standard`,
`code_postal`, `dep_code`, `reg_code`, `population`, `superficie_km2`,
`densite`, `altitude_moyenne`, `latitude_centre`, `longitude_centre`.

## 4. Tables de la base

Voir `sql/01_schema.sql` (commente ligne a ligne).

| Table | Role |
|---|---|
| `ref_communes` | referentiel geocode, 1 ligne par commune, colonne `geom` PostGIS |
| `stg_bdiff` | copie **brute** des CSV, tout en TEXT + `fichier_source` |
| `fires` | table de faits propre et typee, surfaces converties en hectares |
| `v_fires_geo` | vue : `fires` + coordonnees et attributs de la commune |

## 5. Pièges de format découverts en exécution réelle (08/09/2026)

### 5.1 · Le nombre de lignes d'en-tête VARIE selon l'année

Le CSV BDIFF est précédé d'un nombre **variable** de lignes de texte libre :

| Export | Lignes avant l'en-tête | Contenu |
|---|---|---|
| 2023, 2024 | **2** | compteur · critères de sélection |
| 2020, 2021, 2022 | **3** | ⚠️ avertissement « Certaines données sont associées à l'**ancienne version du formulaire** incendie » · compteur · critères |

**Pourquoi c'est dangereux :** un `skiprows=2` codé en dur décale toutes les
colonnes des années anciennes **sans provoquer la moindre erreur**. Les données
se chargent, les types passent, et tout est faux d'une colonne. C'est le pire
type de bug : celui qui ne fait pas de bruit.

**Parade retenue** (`src/load.py`, fonction `ligne_entete`) : on cherche la vraie
ligne d'en-tête, celle qui commence par `Année;`, au lieu de supposer sa position.

**Ce que cet avertissement confirme :** la bascule de formulaire de 2023,
déjà identifiée dans la section 1. La BDIFF le signale elle-même sur les exports
antérieurs.

### 5.2 · Volumes réels par année (téléchargés)

| Année | Incendies | En-tête |
|---|---|---|
| 2020 | 2 971 | ligne 3 |
| 2021 | 2 362 | ligne 3 |
| 2022 | **4 433** | ligne 3 |
| 2023 | 2 682 | ligne 2 |
| 2024 | 1 367 | ligne 2 |
| **Total 2020-2024** | **13 815** | |

2022 est bien l'année exceptionnelle attendue (canicules et méga-feux de Gironde).
Le maximum observé, 4 433, reste **très en dessous de la limite de 30 000** :
la décision D7 (découpage par année) est confirmée par les données.

### 5.3 · Contrainte d'environnement : inspection TLS

Sur le poste de développement, `requests` échoue avec
`SSLCertVerificationError: unable to get local issuer certificate`, alors que le
navigateur accède au site sans problème. Cause : le réseau (établissement ou
antivirus) inspecte le trafic HTTPS et re-signe les certificats.

Mesures prises : `src/config.py` lit le magasin de certificats du système au lieu
du magasin interne de Python (47 autorités chargées). Diagnostic complémentaire
disponible via `python src/diag_ssl.py`. Les exports 2020-2024 ont été récupérés
par le navigateur en attendant — voie explicitement autorisée par le sujet (p.3 :
« la collecte de ces données est réalisée manuellement »).
