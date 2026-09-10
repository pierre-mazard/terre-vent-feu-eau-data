# Demarrage du projet

Ce guide te permet de partir d'un ordinateur allume et d'arriver a l'application Streamlit.

## Prerequis

Installer une seule fois :

- Git ;
- Docker Desktop ;
- Python 3.12 ;
- VS Code, facultatif mais pratique.

Docker Desktop doit etre demarre avant PostgreSQL. PostgreSQL n'est pas installe directement sur Windows : il tourne dans le conteneur PostGIS du projet.

## 1. Recuperer le projet(ca, tu sais deja)

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

## 2. Verifier le fichier `.env`

Le fichier `.env` contient les parametres locaux de la base. Il ne doit pas etre publie sur GitHub.

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

Puis modifier `DB_PASSWORD` dans `.env` avec une valeur non vide, par exemple
`DB_PASSWORD=tvfed` pour un usage local. Docker refuse de demarrer si cette
variable est vide. Le fichier `.env` reste local et ne doit jamais etre pousse
sur GitHub.

## 3. Installer les dependances Python

Depuis la racine du depot :

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Dans VS Code, selectionner ensuite l'interpreteur `.venv\Scripts\python.exe`.

## 4. Demarrer PostgreSQL/PostGIS

Demarrer Docker Desktop, puis executer :

```powershell
docker compose up -d
Docker compose ps
```

Le service `tvfed_db` doit apparaitre avec un statut `healthy` apres quelques secondes. Le port local est `5432`.

Commandes utiles :

```powershell
docker compose logs db
docker compose stop
docker compose start
docker compose down
```

`docker compose down` arrete et supprime le conteneur mais conserve le volume de donnees. Ne pas utiliser `docker compose down -v` sauf pour reinitialiser completement la base.

## 5. Charger les donnees

Si la base est vide ou si les fichiers bruts doivent etre charges :

```powershell
python -m data.ingestion_pipeline.pipeline --skip-download
```

Cette commande utilise les CSV deja presents dans `data/raw` et reconstruit le referentiel, le staging et la table `fires`.

Pour lancer aussi les telechargements BDIFF et du referentiel :

```powershell
python -m data.ingestion_pipeline.pipeline
```

Le telechargement peut durer longtemps. Les fichiers deja presents sont normalement ignores par le cache du pipeline.

## 6. Verifier la base

```powershell
python data\ingestion_pipeline\config.py
python data\ingestion_pipeline\qualite.py
```

Le premier test doit afficher `Connexion OK`. Le second doit afficher les controles qualite et produire `docs/QUALITE.md`.

## 7. Lancer l'application

Avec Docker et la base demarres :

```powershell
streamlit run api/streamlit/app.py
```

Ouvrir ensuite l'adresse affichee, generalement :

```text
http://localhost:8501
```

L'application contient actuellement :

- l'onglet cartographie et historique ;
- les filtres temporels, geographiques et metier ;
- les indicateurs et graphiques ;
- la carte des feux geocodes ;
- l'onglet methodologie.

L'onglet prediction sera complete apres le feature engineering et le modele du jour 4.

## 8. Lancer depuis VS Code

Ne pas lancer `app.py` avec le bouton Python classique comme un script ordinaire. Pour Streamlit, utiliser :

1. ouvrir un terminal a la racine du projet ;
2. activer `.venv` ;
3. executer `streamlit run api/streamlit/app.py`.

Le bouton Run Python execute le fichier dans un contexte different de Streamlit. L'import de `config` est maintenant robuste, mais Streamlit reste le mode de lancement recommande.

## Problemes frequents

### `No module named config`

Mettre a jour le depot, installer les dependances et lancer depuis la racine :

```powershell
git pull origin develop
.venv\Scripts\Activate.ps1
streamlit run api/streamlit/app.py
```

L'application utilise maintenant `data.ingestion_pipeline.config`, qui ne depend plus du dossier courant.

### Connexion refusee sur localhost:5432

Docker Desktop ou le conteneur n'est pas demarre :

```powershell
docker compose up -d
docker compose ps
```

### Base vide

Lancer :

```powershell
python -m data.ingestion_pipeline.pipeline --skip-download
```

Il faut que les fichiers BDIFF et `communes_france.csv` soient presents dans `data/raw`.
