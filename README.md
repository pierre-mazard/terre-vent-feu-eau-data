# Terre, Vent, Feu, Eau, Data

Prediction du risque d'incendie de foret par commune, en France.

Projet de MSc Intelligence Artificielle & Data, La Plateforme_ (Marseille).
Lucien Nzeutom et Pierre Mazard, septembre 2026.

---

## La question posee

Les moyens de prevention sont limites : on ne peut pas surveiller 34 863
communes en meme temps. Il faut choisir ou regarder.

Ce projet construit un score de risque par commune, a partir de la base BDIFF
(Base de Donnees sur les Incendies de Forets en France) croisee avec le
referentiel geographique des communes. Le systeme repond a deux questions,
a deux echelles de temps :

| | Question | Granularite | Page de l'application |
|---|---|---|---|
| Modele annuel | cette commune connaitra-t-elle au moins un incendie l'annee prochaine ? | commune x annee | 08 - Fiche commune |
| Modeles a horizon | y aura-t-il un depart de feu dans les 10, 30 ou 60 jours qui suivent cette date ? | commune x date | 11 - Prediction datee |

Ce que le systeme ne fait pas, et qu'il faut dire clairement : il ne predit ni
la date exacte d'un depart de feu, ni la surface qui brulera, et il n'explique
aucune cause. Il classe les communes par exposition. Aucune donnee
meteorologique n'entre dans le modele : c'est la limite la plus structurante,
et la principale piste d'amelioration.

---

## Resultats mesures

Toutes les mesures ci-dessous portent sur des annees que le modele n'a jamais
vues pendant son entrainement.

### Donnees

| Mesure | Valeur |
|---|---|
| Incendies charges en base | 140 246 |
| Periode couverte | 1973 - 2024 |
| Communes du referentiel | 34 863 |
| Taux de geocodage | 99,31 % |
| Doublons sur la cle metier (annee, numero) | 0 |
| Controles d'integrite | 6 / 6 au vert |
| Panel commune x annee | 662 397 lignes |

### Modele annuel - comparaison des trois familles

Entrainement 2011-2022 (418 356 lignes), test sur 2023 (34 863 communes, dont
2,53 % ont connu un feu l'annee suivante). Meme decoupage, memes variables,
meme calibration sigmoide pour les trois.

| Modele | PR-AUC | Gain sur le hasard | ROC-AUC | Brier | Precision top 5 % | Rappel top 5 % | Entrainement |
|---|---|---|---|---|---|---|---|
| Regression logistique | 0,222 | x 8,8 | 0,921 | 0,0237 | 25,4 % | 50,2 % | 3 s |
| Random Forest | 0,328 | x 12,9 | 0,937 | 0,0210 | 27,7 % | 54,8 % | 62 s |
| XGBoost | 0,331 | x 13,1 | 0,935 | 0,0211 | 28,5 % | 56,3 % | 13 s |

Lecture : le plancher de la PR-AUC n'est pas 0,5 mais le taux de communes qui
brulent, soit 0,0253. Un modele a 0,33 est donc a treize fois le hasard, et non
a un tiers de la note maximale. La regression logistique sert de reference :
les modeles a arbres apportent 48 % de PR-AUC en plus, ce qui montre que la
relation entre historique et risque n'est pas lineaire.

En pratique : en surveillant les 5 % de communes les mieux classees, on couvre
plus de la moitie des communes qui bruleront l'annee suivante.

### Modeles a horizon court

Entrainement 2010-2022, test de janvier 2023 a novembre 2024.

| Horizon | PR-AUC | Gain sur le hasard | Precision top 5 % | Rappel top 5 % |
|---|---|---|---|---|
| 10 jours | 0,216 | x 7,5 | 22,4 % | 39,1 % |
| 30 jours | 0,485 | x 6,1 | 55,4 % | 34,9 % |
| 60 jours | 0,764 | x 5,3 | 90,3 % | 31,1 % |

Exemple de lecture, pour Aix-en-Provence :

| Date interrogee | 10 jours | 30 jours | 60 jours |
|---|---|---|---|
| 20 janvier 2025 | 7,8 % | 14,7 % | 58,7 % |
| 15 juin 2025 | 20,8 % | 42,1 % | 92,3 % |
| 10 aout 2025 | 26,5 % | 43,4 % | 81,4 % |

---

## Les variables

### Modele annuel - 18 variables

| Famille | Variables |
|---|---|
| Historique des feux | nb_feux_5a, nb_feux_10a, surface_5a_ha, surface_10a_ha, surface_foret_5a_ha, surface_moyenne_5a_ha |
| Saisonnalite | part_feux_ete_5a, mois_reference, mois_sin, mois_cos |
| Groupes | cluster_risque (KMeans), cluster_spatial (DBSCAN) |
| Geographie et contexte | latitude, longitude, altitude_moy, superficie_km2, population, densite |

Regle appliquee a toutes les fenetres glissantes : elles sont decalees d'un an.
Pour predire l'annee A, seules les annees A-5 a A-1 sont utilisees. Une ligne du
tableau represente donc exactement ce que l'on savait au 1er janvier de l'annee
A. La cible, elle, est observee en A+1 et n'entre jamais dans les variables.

### Modeles a horizon - 22 variables

| Famille | Variables | Fenetre |
|---|---|---|
| Activite recente | feux_7j, feux_30j, feux_90j, feux_365j, surface_30j_ha, surface_365j_ha, jours_depuis_dernier_feu | arretee la veille de la date evaluee |
| Saisonnalite | feux_meme_mois_5a, jour_annee_sin, jour_annee_cos, mois | au jour pres |
| Voisinage | feux_voisinage_30j, feux_voisinage_5a | communes situees a moins de 20 km, commune exclue |
| Historique long | nb_feux_5a, nb_feux_10a, surface_10a_ha | repris du panel annuel |
| Contexte fixe | latitude, longitude, population, densite, altitude_moy, superficie_km2 | - |

Deux choix meritent d'etre expliques.

**Le voisinage remplace le cluster spatial.** DBSCAN est calcule sur l'ensemble
des feux 2006-2024, periode de test comprise : l'utiliser dans un modele a
horizon reviendrait a lui donner une information qu'il ne peut pas avoir au
moment de la prediction. Mesure faite sur l'horizon 30 jours, la densite de
feux dans un rayon de 20 km, calculee strictement sur le passe, recupere la
quasi-totalite de la performance (PR-AUC 0,486 contre 0,487) et ameliore la
precision (55,6 % contre 54,2 %).

**L'echantillonnage negatif rend le probleme traitable.** Une ligne par commune
et par jour sur vingt ans represente 242 millions d'enregistrements. On conserve
donc tous les couples (commune, date) suivis d'un feu, et seulement une fraction
tiree au hasard des autres : 1 498 374 lignes au lieu de 27 millions de couples
possibles sur la grille, sans perdre un seul positif. La probabilite predite est
ensuite corrigee pour revenir au taux reel ; sans cette correction elle serait
environ vingt fois trop elevee.

---

## Architecture

```
52 fichiers CSV BDIFF
        |
        v
  stg_bdiff (tout en TEXT)        nettoyage en SQL, aucune ligne perdue
        |
        v
  fires + ref_communes            PostgreSQL 16 + PostGIS, index GIST
        |
        +-------------------------------+
        |                               |
        v                               v
  panel commune x annee           panel commune x date
  (662 397 lignes)                (echantillonnage negatif)
        |                               |
        v                               v
  clustering + Random Forest      XGBoost par horizon
        |                               |
        +-------------------------------+
                        |
                        v
              application Streamlit
```

La table de staging n'est pas un detail : les 52 exports annuels de la BDIFF
n'ont pas le meme nombre de lignes d'en-tete (2, 3, 5 ou 6 selon l'annee).
En chargeant tout en texte brut avant de nettoyer en SQL, aucune ligne n'est
perdue a cause d'un format, et le nettoyage est rejouable sans retelecharger.

### Organisation du depot

```
terre-vent-feu-eau-data/
  config.py                     connexion a la base, chemins, lecture du .env
  makefile                      toutes les commandes du projet
  docker-compose.yml            PostgreSQL + PostGIS, schema precharge
  data/
    sql/create_tables.sql       3 tables, 5 index, 1 index geographique GIST
    raw/                        exports BDIFF et referentiel des communes
    processed/run/<horodatage>/ un dossier par execution du pipeline
    ingestion_pipeline/         telechargement, nettoyage, chargement en base
  models/
    config_pipeline.py          plage temporelle et liste des variables
    pipeline/                   ingestion, nettoyage, variables, clustering,
                                entrainement, scoring, variables a horizon
    train_test/                 entrainement, evaluation, validation croisee,
                                comparaison de modeles, modeles a horizon
    run/<horodatage>/           modeles et metriques d'une execution
  api/streamlit/                application, 11 pages
  analysis/                     deux notebooks d'analyse exploratoire
  docs/                         documentation du projet
  tests/                        tests automatises
```

---

## Demarrage

### Prerequis

Python 3.10 ou plus, Docker Desktop, et un fichier `.env` a la racine :

```
DB_USER=tvfed
DB_PASSWORD=choisis_un_mot_de_passe
DB_NAME=tvfed
DB_HOST=localhost
DB_PORT=55432
SSL_VERIFY=true
```

Attention au port : `docker-compose.yml` publie la base sur **55432** et non
5432, pour ne pas entrer en conflit avec un PostgreSQL deja installe sur la
machine. Depuis un conteneur, en revanche, l'hote est `db` et le port 5432.

### Installation

```
python -m venv .venv
.venv\Scripts\activate          (Windows)
source .venv/bin/activate        (Linux, macOS)
pip install -r requirements.txt
```

### Lancement complet, depuis zero

```
docker compose up -d                              demarre la base
python -m data.ingestion_pipeline.pipeline        telecharge et charge les donnees
python -m models.pipeline.build_dataset           construit le jeu de variables
python -m models.train_test.train_model           entraine le modele annuel
python -m models.train_test.evaluate_model        mesure ses performances
python -m models.train_test.cross_validation      validation temporelle et geographique
python -m models.train_test.comparaison_modeles   compare logistique, foret, XGBoost
python -m models.train_test.train_horizons        entraine les modeles 10, 30, 60 jours
python shap/compute_shap.py                       calcule les explications SHAP
streamlit run api/streamlit/app.py                ouvre l'application
```

Avec `make` installe, chaque ligne a sa cible equivalente : `make build-dataset`,
`make run-pipeline-ml`, `make comparer-modeles`, `make train-horizons`,
`make run-streamlit`. Voir la section suivante.

### Relance quotidienne

Si la base et les modeles sont deja construits :

```
docker compose up -d
streamlit run api/streamlit/app.py
```

Le detail de tous les cas de figure se trouve dans `docs/DEMARRAGE.md`.

---

## Pourquoi un makefile

Le makefile n'est pas un outil de confort : c'est la memoire operationnelle du
projet.

**Il documente les commandes reelles.** Un projet de donnees accumule vite une
dizaine de commandes longues, avec des modules, des options et un ordre precis.
Ecrites dans un README, elles se desynchronisent du code. Ecrites dans un
makefile, elles sont executees a chaque fois, donc toujours justes : si une
commande casse, on le sait le jour meme.

**Il fixe l'ordre des etapes.** Construire le jeu de variables avant d'entrainer,
entrainer avant d'evaluer, evaluer avant de lancer l'application. Une cible
comme `ml-complet` enchaine les quatre dans le bon ordre et s'arrete a la
premiere erreur, au lieu de produire des artefacts a moitie a jour.

**Il verifie ce qui a ete produit.** Chaque cible du projet se termine par des
`test -f` sur les fichiers qu'elle doit avoir ecrits. Un entrainement qui
echoue silencieusement, sans lever d'exception mais sans ecrire son modele, est
detecte immediatement plutot que trois jours plus tard, quand l'application
affiche des chiffres perimes.

**Il donne un point d'entree unique a l'equipe.** Un collegue qui recupere le
depot n'a pas a deviner quel script lancer ni dans quel ordre : il lit les noms
des cibles. C'est aussi ce que reprend l'integration continue, qui appelle les
memes commandes que nous en local, donc teste exactement ce que nous executons.

**Ses limites, dans notre cas.** `make` n'est pas installe par defaut sous
Windows, ou la commande echoue avec un message peu clair. Le makefile du projet
indique donc, en commentaire au-dessus de chaque cible, la commande Python
equivalente a lancer directement. Deuxieme piege rencontre : les recettes
doivent etre indentees par une tabulation et non par des espaces, faute de quoi
make refuse le fichier.

---

## L'application

Onze pages, lancees par `streamlit run api/streamlit/app.py`.

| Page | Contenu |
|---|---|
| 01 - Overview | rapports du run courant : nettoyage, variables, clustering, decoupage |
| 02 - Validation croisee | performance annee par annee, et sur des communes tenues a l'ecart |
| 03 - Metriques | performance du modele, distribution des probabilites, niveaux de risque |
| 04 - Variables | statistiques descriptives et correlations des variables d'entree |
| 05 - Scores | carte nationale et classement des communes |
| 06 - Explorateur de runs | contenu et taille des artefacts de chaque execution |
| 07 - Explicabilite | SHAP global, effet de chaque variable |
| 08 - Fiche commune | une commune, sa prediction annuelle, son historique, sa comparaison |
| 09 - Dashboard | synthese nationale et par departement |
| 10 - Comparaison | regression logistique, Random Forest et XGBoost, chiffres a l'appui |
| 11 - Prediction datee | une commune et une date, risque a 10, 30 et 60 jours |

Deux principes d'architecture. Le modele n'est **jamais recalcule a l'ecran** :
le pipeline produit les scores, l'application les charge en cache. Et tous les
chargements passent par `api/streamlit/donnees.py`, qui met en cache les
fichiers volumineux et remplace les erreurs Python par un message indiquant la
commande a lancer.

---

## Reproductibilite

Chaque execution du pipeline ecrit ses resultats dans un dossier horodate :
donnees nettoyees, variables, rapports de nettoyage, manifeste, modeles,
metriques. Rien n'est ecrase.

Le fichier `split_report.json` contient une **empreinte SHA-256 du decoupage
train / test**. Elle prouve que deux executions ont bien utilise exactement les
memes lignes d'entrainement et de test : si l'empreinte change, la comparaison
des metriques n'est plus valable.

L'integration continue verifie a chaque proposition de fusion le formatage
(black), l'analyse statique (flake8), la securite des dependances (bandit et
pip-audit) et les tests (pytest).

---

## Limites assumees

- **Aucune donnee meteorologique.** Ni vent, ni temperature, ni indice de
  secheresse. Le modele apprend ou et quand ca brule habituellement, pas si la
  semaine a venir sera seche et ventee. C'est ce qui separe une carte de risque
  d'une alerte operationnelle.
- **La vegetation n'est connue qu'indirectement**, a travers les surfaces deja
  brulees, donc uniquement pour les communes qui ont deja connu un feu.
- **La maille communale est heterogene.** Une commune de 200 km2 et une de
  3 km2 ne portent pas le meme sens, et le score n'est pas ramene a la surface.
- **La validation geographique est optimiste** : les communes tenues a l'ecart
  sont tirees au hasard sur toute la France, donc leurs voisines restent dans
  l'entrainement. Un decoupage par departement entier serait plus severe.
- **Correlation, pas causalite.** Un score eleve signale un historique
  compatible avec une occurrence. Il n'explique pas pourquoi un feu se declare.

### Pistes suivantes

Par ordre de gain attendu : integrer les donnees meteo (Meteo-France SYNOP,
ERA5), ajouter l'occupation du sol (Corine Land Cover) pour connaitre la
vegetation de toutes les communes et non des seules communes brulees, passer a
une maille en grille reguliere plutot que communale, predire la gravite et non
seulement l'occurrence, et automatiser le reentrainement a chaque mise a jour
annuelle de la BDIFF.

---

## Documentation

| Document | Contenu |
|---|---|
| `docs/DEMARRAGE.md` | installation et lancement, tous les cas de figure |
| `docs/SCHEMA.md` | schema de la base, colonnes, index, regles de dedoublonnage |
| `docs/QUALITE.md` | les six controles d'integrite et leurs resultats |
| `docs/JOUR2.md` | analyse exploratoire des donnees brutes |
| `docs/JOUR3.md` | consolidation de la base |
| `docs/JOUR4.md` | variables, clustering, modeles, comparaison, horizons |
| `docs/RESUME_PROJET_CHECKUP.md` | historique des problemes resolus et des reglages |
| `docs/model_training_pipeline.md` | architecture du pipeline ML |
| `analysis/eda_jour2.ipynb` | notebook d'exploration des donnees brutes |
| `analysis/eda_features.ipynb` | notebook d'exploration des variables construites |

---

## Sources

- BDIFF, Base de Donnees sur les Incendies de Forets en France
  (Ministere de l'Agriculture) : https://bdiff.agriculture.gouv.fr
- Referentiel geographique des communes francaises : data.gouv.fr
