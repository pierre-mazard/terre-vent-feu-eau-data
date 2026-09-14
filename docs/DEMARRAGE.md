# Demarrage du projet

Ce guide te permet de partir d'un ordinateur allume et d'arriver a l'application
Streamlit complete, les deux onglets fonctionnels.

> Derniere mise a jour : 11 septembre 2026, apres le jour 4.
> Si une commande de ce guide echoue, va directement a la section
> **Problemes frequents** en bas de page.

---

## Prerequis

Installer une seule fois :

- Git ;
- Docker Desktop ;
- Python 3.12 ;
- VS Code, facultatif mais pratique.

Docker Desktop doit etre demarre avant PostgreSQL. PostgreSQL n'est pas installe
directement sur Windows : il tourne dans le conteneur PostGIS du projet.

---

## 1. Recuperer le projet

Dans PowerShell :

```powershell
git clone https://github.com/pierre-mazard/terre-vent-feu-eau-data.git
cd terre-vent-feu-eau-data
git switch develop
```

Si le depot existe deja :

```powershell
cd chemin\vers\terre-vent-feu-eau-data
git switch develop
git pull origin develop
```

---

## 2. Verifier le fichier `.env`

Le fichier `.env` contient les parametres locaux de la base. Il ne doit jamais
etre publie sur GitHub (il est deja dans `.gitignore`).

Contenu minimal attendu :

```dotenv
DB_USER=tvfed
DB_PASSWORD=tvfed
DB_NAME=tvfed
DB_HOST=localhost
DB_PORT=5432
SSL_VERIFY=true
```

Si `.env` n'existe pas, copier `.env.example` :

```powershell
Copy-Item .env.example .env
```

Puis mettre une valeur non vide dans `DB_PASSWORD`, par exemple `tvfed` pour un
usage local. **Docker refuse de demarrer si cette variable est vide.**

---

## 3. Installer les dependances Python

Depuis la racine du depot :

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Dans VS Code, selectionner ensuite l'interpreteur `.venv\Scripts\python.exe`.

> **Important.** Plusieurs versions de Python peuvent cohabiter sur la machine.
> Toutes les commandes de ce guide supposent que le `.venv` est **active** :
> le prompt PowerShell doit commencer par `(.venv)`. Si ce n'est pas le cas,
> refaire `.venv\Scripts\Activate.ps1`.

---

## 4. Demarrer PostgreSQL/PostGIS

Demarrer Docker Desktop, puis :

```powershell
docker compose up -d
docker compose ps
```

Le service `tvfed_db` doit apparaitre avec le statut `healthy` apres quelques
secondes. Le port local est `5432`.

Commandes utiles :

```powershell
docker compose logs db
docker compose stop
docker compose start
docker compose down
```

`docker compose down` arrete et supprime le conteneur mais **conserve** le
volume de donnees. Ne pas utiliser `docker compose down -v` sauf pour
reinitialiser completement la base.

---

## 5. Charger les donnees

Si la base est vide, ou si les fichiers bruts doivent etre charges :

```powershell
python -m data.ingestion_pipeline.pipeline --skip-download
```

Cette commande utilise les CSV deja presents dans `data/raw` et reconstruit le
referentiel des communes, la table de staging et la table `fires`.

Pour lancer aussi les telechargements BDIFF et du referentiel :

```powershell
python -m data.ingestion_pipeline.pipeline
```

Le telechargement complet dure une dizaine de minutes. Les fichiers deja
presents dans `data/raw` sont ignores grace au cache du pipeline.

**Resultat attendu :** environ 140 246 incendies dans la table `fires`,
periode 1973-2024.

---

## 6. Verifier la base

```powershell
python config.py
python data\ingestion_pipeline\qualite.py
```

- `config.py` doit afficher `Connexion OK`.
- `qualite.py` doit afficher **6 controles sur 6 en OK** et regenerer
  `docs/QUALITE.md`.

> `config.py` est a la **racine** du depot depuis le 10 septembre, plus dans
> `data/ingestion_pipeline/`. Une ancienne version de ce guide indiquait
> `python data\ingestion_pipeline\config.py` : ce chemin n'existe plus.

---

## 7. Entrainer le modele de risque — **etape obligatoire**

```powershell
python data\ingestion_pipeline\jour4_model.py
```

Ou, en raccourci :

```powershell
make run-model
```

Cette etape construit les variables du jour 4, lance les deux clusterings,
entraine le modele calibre, et ecrit trois fichiers :

| Fichier | Contenu |
|---|---|
| `data/processed/scores_risque.csv` | le score de risque de chaque commune |
| `data/processed/features_risque.csv` | les variables, pour inspection |
| `models/modele_risque.joblib` | le modele entraine (~90 Mo) |
| `models/metriques_risque.json` | les metriques d'evaluation |

Compter quelques minutes.

> ### Pourquoi cette etape ne peut pas etre sautee
>
> `models/` et `data/processed/` sont volontairement exclus du depot par le
> `.gitignore` : ce sont des fichiers lourds et regenerables, ils n'ont rien a
> faire dans Git.
>
> **Consequence : apres un `git clone`, ces fichiers n'existent pas.** Si on
> lance l'application sans avoir fait cette etape, l'onglet historique
> fonctionne mais **l'onglet prediction affiche une erreur**.

---

## 8. Lancer l'application

Avec Docker et la base demarres :

```powershell
streamlit run api/streamlit/app.py
```

Ou :

```powershell
make run-streamlit
```

Ouvrir ensuite l'adresse affichee, generalement :

```text
http://localhost:8501
```

L'application contient trois onglets :

**Onglet 1 — Cartographie et historique**

- filtres : annees, mois, saison, departement, nature du feu, vegetation
  dominante, surface minimale ;
- quatre indicateurs : nombre d'incendies, surface totale, surface moyenne,
  taux de geocodage ;
- evolution du nombre de feux et des surfaces ;
- carte des feux geocodes ;
- classement des departements.

**Onglet 2 — Prediction du risque**

- selection d'une commune ;
- score de risque et niveau pour l'annee a venir ;
- historique des cinq annees precedentes ;
- profil KMeans et zone DBSCAN de la commune ;
- metriques du modele (ROC-AUC et PR-AUC).

**Onglet 3 — Methodologie**

---

## 9. Lancer depuis VS Code

Ne pas lancer `app.py` avec le bouton Run de VS Code : Streamlit a besoin de son
propre lanceur. La bonne methode :

1. ouvrir un terminal a la racine du projet ;
2. activer `.venv` (`.venv\Scripts\Activate.ps1`) ;
3. executer `streamlit run api/streamlit/app.py`.

---

## Les commandes du `makefile`, en resume

| Commande | Effet |
|---|---|
| `make run-pipeline` | telecharge et charge les donnees en base |
| `make run-model` | entraine le modele et produit les scores |
| `make run-streamlit` | lance l'application |
| `make test` | lance les tests pytest |
| `make lint` | `black` puis `flake8` |
| `make security` | `bandit` puis `pip-audit` |

**L'ordre a respecter apres un clone :** `run-pipeline` → `run-model` →
`run-streamlit`.

---

## Problemes frequents

### `ModuleNotFoundError: No module named 'config'`

`config.py` est a la racine du depot. Les scripts l'ajoutent eux-memes au chemin
de recherche de Python, mais seulement s'ils sont a jour :

```powershell
git pull origin develop
.venv\Scripts\Activate.ps1
streamlit run api/streamlit/app.py
```

> Une ancienne version de ce guide affirmait que l'application utilisait
> `data.ingestion_pipeline.config`. **C'est faux** : ce module n'existe pas.
> L'import se fait sur `config` a la racine, rendu accessible par un ajout a
> `sys.path` en tete de chaque point d'entree.

### `ModuleNotFoundError: No module named 'pandas'` (ou `sqlalchemy`, `streamlit`)

Le `.venv` n'est pas active, ou les dependances ont ete installees dans un autre
Python. Verifier que le prompt commence par `(.venv)`, puis :

```powershell
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

### L'onglet prediction affiche une erreur

Le fichier `data/processed/scores_risque.csv` n'existe pas. C'est normal apres
un clone : il faut lancer l'etape 7.

```powershell
python data\ingestion_pipeline\jour4_model.py
```

### Connexion refusee sur `localhost:5432`

Docker Desktop ou le conteneur n'est pas demarre :

```powershell
docker compose up -d
docker compose ps
```

### Base vide

```powershell
python -m data.ingestion_pipeline.pipeline --skip-download
```

Il faut que les fichiers BDIFF et `communes_france.csv` soient presents dans
`data/raw`.

### `SSLCertVerificationError` au telechargement

Le reseau utilise inspecte le trafic HTTPS. Le projet lit le magasin de
certificats de Windows pour contourner le probleme. Pour diagnostiquer :

```powershell
python data\ingestion_pipeline\diag_ssl.py
```

Ne jamais desactiver la verification TLS pour contourner l'erreur.

---

## Verification finale : le test du clone vierge

Avant le rendu, ce parcours doit fonctionner de bout en bout sur un dossier
vide, sans aucune etape improvisee :

```powershell
git clone <url> test-clone
cd test-clone
git switch develop
Copy-Item .env.example .env        # puis renseigner DB_PASSWORD
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
docker compose up -d
python -m data.ingestion_pipeline.pipeline    # ou --skip-download
python data\ingestion_pipeline\qualite.py
python data\ingestion_pipeline\jour4_model.py
streamlit run api/streamlit/app.py
```

Si une seule de ces commandes demande une manipulation qui n'est pas ecrite
ici, c'est ce guide qu'il faut corriger — pas la manipulation qu'il faut
retenir de tete.
