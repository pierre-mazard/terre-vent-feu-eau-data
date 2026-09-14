# Démarrage du projet

Ce guide te mène de l'ordinateur allumé jusqu'à l'application Streamlit.

> **Toutes les commandes s'exécutent dans PowerShell, depuis le dossier du
> projet.** Pour y arriver :
>
> ```powershell
> cd C:\Users\User\Documents\terre-vent-feu-eau-data
> ```

---

## 👉 Commence ici : dans quelle situation es-tu ?

| Ta situation | Va à | Durée |
|---|---|---|
| **J'ai éteint ou redémarré mon ordinateur**, tout marchait avant | **Partie 1** | ⏱️ **2 min** |
| Le projet est installé mais **la base est vide** ou l'onglet prédiction plante | **Partie 2** | ⏱️ 20 min |
| **Je pars de zéro** : nouvel ordinateur, ou premier clone du dépôt | **Partie 3** | ⏱️ 45 min |

---
---

# Partie 1 · Redémarrage quotidien — 2 minutes

> **C'est le cas le plus fréquent.** Tu as éteint ton PC hier, tu veux relancer
> l'application aujourd'hui.

## Ce que tu n'as PAS à refaire

**Rien n'est perdu quand tu éteins l'ordinateur.** Trois choses survivent :

| Ce qui survit | Pourquoi |
|---|---|
| **Les données de la base** | elles sont dans un volume Docker nommé `pgdata`, stocké sur ton disque |
| **Le modèle entraîné** | `models/modele_risque.joblib` est un fichier comme un autre |
| **Les scores des communes** | `data/processed/scores_risque.csv`, pareil |

**Donc : pas de re-téléchargement, pas de re-chargement, pas de ré-entraînement.**
Il faut seulement **rallumer** ce qui était allumé.

## Les 3 étapes

### 1. Démarrer Docker Desktop

Ouvre **Docker Desktop** depuis le menu Démarrer et attends que l'icône baleine
en bas à gauche passe au **vert** (« Engine running »). Compter 30 secondes.

> Docker ne redémarre pas toujours tout seul avec Windows. C'est l'oubli n° 1.

### 2. Rallumer la base

```powershell
cd C:\Users\User\Documents\terre-vent-feu-eau-data
docker compose up -d
docker compose ps
```

**Ce que tu dois voir :** une ligne `tvfed_db` avec le statut `healthy`.

### 3. Activer l'environnement Python et lancer l'application

```powershell
.venv\Scripts\Activate.ps1
streamlit run api/streamlit/app.py
```

**Ce que tu dois voir :** ton invite PowerShell commence maintenant par
`(.venv)`, puis une adresse s'affiche :

```text
Local URL: http://localhost:8501
```

**C'est tout.** Les deux onglets fonctionnent.

---

### Récapitulatif à copier-coller

```powershell
cd C:\Users\User\Documents\terre-vent-feu-eau-data
docker compose up -d
.venv\Scripts\Activate.ps1
streamlit run api/streamlit/app.py
```

*(après avoir lancé Docker Desktop)*

### Pour arrêter proprement le soir

```powershell
# dans la fenêtre Streamlit : Ctrl + C
docker compose stop
```

`docker compose stop` éteint la base **sans rien effacer**.

> ⚠️ **Ne jamais faire `docker compose down -v`.** Le `-v` supprime le volume
> `pgdata`, donc **toute la base**. Il faudrait tout recharger (20 minutes).
> `down` seul est sans danger, `down -v` est destructeur.

---
---

# Partie 2 · La base est vide, ou l'onglet prédiction plante

Symptômes possibles :

- l'onglet historique n'affiche aucun incendie ;
- l'onglet prédiction affiche une erreur de fichier introuvable ;
- tu viens de faire `docker compose down -v`.

## Étape A · Vérifier que la base répond

```powershell
cd C:\Users\User\Documents\terre-vent-feu-eau-data
docker compose up -d
.venv\Scripts\Activate.ps1
python config.py
```

**Attendu :** `Connexion OK`. Si non, va voir **Problèmes fréquents** en bas.

## Étape B · Recharger les données

```powershell
python -m data.ingestion_pipeline.pipeline --skip-download
```

`--skip-download` réutilise les CSV déjà présents dans `data/raw` au lieu de
retélécharger la BDIFF. Compter 3 à 5 minutes.

**Attendu en fin de commande :**

```text
fires : 140246 incendies (1973-2024), ... geocodes (99.3%)
```

## Étape C · Vérifier la qualité

```powershell
python data\ingestion_pipeline\qualite.py
```

**Attendu :** `6/6 tests passes`, et `docs/QUALITE.md` régénéré.

## Étape D · Réentraîner le modèle

```powershell
python data\ingestion_pipeline\jour4_model.py
```

Compter quelques minutes. Cette commande produit les fichiers **absents du
dépôt** :

| Fichier | Utilité |
|---|---|
| `data/processed/scores_risque.csv` | **lu par l'onglet prédiction** |
| `data/processed/features_risque.csv` | les variables, pour inspection |
| `models/modele_risque.joblib` | le modèle entraîné (~90 Mo) |
| `models/metriques_risque.json` | les métriques affichées dans l'application |

> **Pourquoi ces fichiers ne sont pas sur GitHub.** Ils sont lourds et
> **regénérables** — les mettre dans Git alourdirait le dépôt pour rien. C'est
> voulu. Mais ça veut dire qu'après un clone, **cette étape est obligatoire**,
> sinon l'onglet prédiction n'a rien à lire.

## Étape E · Lancer

```powershell
streamlit run api/streamlit/app.py
```

---
---

# Partie 3 · Installation complète, depuis zéro

## 3.1 · Installer les outils (une seule fois)

| Outil | Pourquoi |
|---|---|
| **Git** | récupérer le dépôt |
| **Docker Desktop** | fait tourner PostgreSQL sans l'installer sur Windows |
| **Python 3.12** | exécute le code du projet |
| VS Code | facultatif, mais pratique |

## 3.2 · Récupérer le projet

```powershell
git clone https://github.com/pierre-mazard/terre-vent-feu-eau-data.git
cd terre-vent-feu-eau-data
git switch develop
```

Si le dépôt existe déjà :

```powershell
cd C:\Users\User\Documents\terre-vent-feu-eau-data
git switch develop
git pull origin develop
```

## 3.3 · Créer le fichier `.env`

```powershell
Copy-Item .env.example .env
notepad .env
```

Contenu minimal :

```dotenv
DB_USER=tvfed
DB_PASSWORD=tvfed
DB_NAME=tvfed
DB_HOST=localhost
DB_PORT=5432
SSL_VERIFY=true
```

> `DB_PASSWORD` doit être **non vide** : Docker refuse de démarrer sinon, et
> c'est volontaire — ça évite qu'un mot de passe se retrouve écrit en dur dans
> le dépôt. Le fichier `.env` reste local, il est dans `.gitignore`.

## 3.4 · Créer l'environnement Python

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Dans VS Code, sélectionner ensuite l'interpréteur `.venv\Scripts\python.exe`.

> **Le prompt doit commencer par `(.venv)`.** Sinon les paquets s'installent
> dans le Python global et rien ne fonctionnera. C'est la cause n° 1 des
> `ModuleNotFoundError`.

## 3.5 · Démarrer la base

Lancer **Docker Desktop**, attendre l'icône verte, puis :

```powershell
docker compose up -d
docker compose ps
```

**Attendu :** `tvfed_db` en `healthy`.

À la toute première création, Docker joue automatiquement
`data/sql/create_tables.sql` : les tables sont créées seules.

## 3.6 · Télécharger et charger les données

```powershell
python -m data.ingestion_pipeline.pipeline
```

Compter 10 à 15 minutes la première fois (52 fichiers à télécharger). Les
fichiers déjà présents dans `data/raw` sont ignorés grâce au cache.

## 3.7 · Vérifier, entraîner, lancer

```powershell
python data\ingestion_pipeline\qualite.py
python data\ingestion_pipeline\jour4_model.py
streamlit run api/streamlit/app.py
```

**L'ordre compte** : les données d'abord, le modèle ensuite, l'application en
dernier. Le modèle lit la base, l'application lit les fichiers du modèle.

---
---

# ❓ Pourquoi `make` ne marche pas chez toi

```text
make : Le terme «make» n'est pas reconnu comme nom d'applet de commande...
```

**C'est normal. `make` est un outil Unix — il n'existe pas sur Windows.**

Le fichier `makefile` du projet est là pour Linux, macOS et la CI GitHub. Sous
PowerShell, il faut taper les commandes Python directement.

| Le raccourci du makefile | La commande à taper sous Windows |
|---|---|
| `make run-pipeline` | `python -m data.ingestion_pipeline.pipeline` |
| `make run-model` | `python data\ingestion_pipeline\jour4_model.py` |
| `make run-streamlit` | `streamlit run api/streamlit/app.py` |
| `make test` | `pytest -q` |
| `make lint` | `black .` puis `flake8 .` |
| `make security` | `bandit -r . -x .venv` puis `pip-audit` |

**Pas besoin d'installer `make`.** Les commandes de droite font exactement la
même chose — le makefile ne fait que les raccourcir.

---

# 🔧 Problèmes fréquents

### `make : Le terme «make» n'est pas reconnu`

Voir juste au-dessus : utilise la commande Python équivalente.

### `ModuleNotFoundError: No module named 'pandas'` (ou `sqlalchemy`, `streamlit`)

L'environnement virtuel n'est pas activé. **Vérifie que ton prompt commence par
`(.venv)`.**

```powershell
.venv\Scripts\Activate.ps1
```

Si le message persiste, les paquets ne sont pas installés dans ce `.venv` :

```powershell
python -m pip install -r requirements.txt
```

### `ModuleNotFoundError: No module named 'config'`

`config.py` est à la **racine** du dépôt. Les scripts l'ajoutent eux-mêmes au
chemin de recherche de Python, mais seulement s'ils sont à jour :

```powershell
git pull origin develop
```

Et lance toujours depuis la racine du projet, pas depuis un sous-dossier.

### `Activate.ps1 ... l'exécution de scripts est désactivée sur ce système`

Windows bloque les scripts PowerShell par défaut. À faire une seule fois :

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

### Connexion refusée sur `localhost:5432`

Docker Desktop n'est pas lancé, ou le conteneur est arrêté :

```powershell
docker compose up -d
docker compose ps
```

Si `docker` lui-même n'est pas reconnu, c'est que Docker Desktop n'est pas
démarré du tout.

### L'onglet prédiction affiche une erreur

`data/processed/scores_risque.csv` n'existe pas. C'est normal après un clone :

```powershell
python data\ingestion_pipeline\jour4_model.py
```

### L'onglet historique est vide

La base est vide. Voir **Partie 2**.

### `SSLCertVerificationError` pendant le téléchargement

Le réseau utilisé inspecte le trafic HTTPS. Le projet lit le magasin de
certificats de Windows pour contourner ça. Pour diagnostiquer :

```powershell
python data\ingestion_pipeline\diag_ssl.py
```

> Ne jamais désactiver la vérification TLS pour contourner l'erreur : ça marche,
> et ça apprend à ignorer les alertes de sécurité.

### Streamlit ne s'ouvre pas dans le navigateur

Ouvre l'adresse à la main : **http://localhost:8501**

### Lancer depuis VS Code

Ne pas utiliser le bouton ▶ Run de VS Code sur `app.py` : Streamlit a besoin de
son propre lanceur. Ouvrir un terminal, activer `.venv`, puis
`streamlit run api/streamlit/app.py`.

---

# ✅ Avant le rendu : le test du clone vierge

Le jury fera ça. Autant le faire avant lui : cloner dans un dossier **vide** et
suivre ce guide à la lettre, sans rien improviser.

```powershell
cd C:\Users\User\Documents
git clone https://github.com/pierre-mazard/terre-vent-feu-eau-data.git test-clone
cd test-clone
git switch develop
Copy-Item .env.example .env          # puis renseigner DB_PASSWORD
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
docker compose up -d
python -m data.ingestion_pipeline.pipeline
python data\ingestion_pipeline\qualite.py
python data\ingestion_pipeline\jour4_model.py
streamlit run api/streamlit/app.py
```

**Si une seule de ces commandes demande une manipulation qui n'est pas écrite
ici, c'est ce guide qu'il faut corriger — pas la manipulation qu'il faut retenir
de tête.**

---

*Dernière mise à jour : 13 septembre 2026.*
