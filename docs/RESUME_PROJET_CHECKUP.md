# Résumé du projet et historique des correctifs

## 1. Contexte

Le projet vise à construire un système d’aide à la décision pour évaluer le risque d’incendie de forêt par commune, avec une logique d’analyses historiques, de clustering spatial, de modélisation prédictive et d’interface de consultation.

Les livrables attendus incluent :

- un pipeline de données robuste ;
- des features géo-temporelles cohérentes ;
- des modèles de risque avec validation temporelle ;
- des sorties interprétables (SHAP, clustering) ;
- une interface Streamlit pour consultation et exploration.

---

## 2. État du projet

### Ce qui a été mis en place

- Pipeline de chargement et d’ingestion des données BDIFF et communales ;
- construction d’un panel par commune/an ;
- historisation des feux et surfaces sur 5/10 ans ;
- clustering spatial et profiles de risque ;
- modélisation binaire de risque ;
- export des scores par commune ;
- application Streamlit d’exploration ;
- génération de métadonnées et de rapports d’évaluation.

### Ce qui a été corrigé pendant la phase de vérification

Le projet a connu plusieurs régressions et blocages techniques. Voici l’historique complet des problèmes résolus.

---

## 3. Historique complet des problèmes résolus

### 1) Régression sur la configuration globale

Problème : le fichier de configuration central ne contenait plus la racine du projet, ce qui cassait des importations internes.

Correction : restauration de la variable racine globale et vérification des chemins de chargement / export.

Fichiers impactés : `config.py` et modules dépendants.

### 2) Port PostgreSQL non aligné avec l’environnement local

Problème : la base locale et le docker-compose avaient divergé sur le port exposé.

Correction : alignement de la configuration locale sur le port effectif de la base, évitant les erreurs de connexion et les blocages d’intégration.

Fichiers impactés : `.env`, `docker-compose.yml`, configuration de connexion.

### 3) Crash du clustering KMeans sur échantillons dégénérés

Problème : le calcul de silhouette pouvait planter sur des sous-échantillons comportant une seule classe effective.

Correction : gestion explicite des cas dégénérés avec fallback sûr, sans faire exploser le pipeline.

Fichiers impactés : modules de clustering, notamment `models/pipeline/clustering.py`.

### 4) Pipeline non réellement exécutée et données de sortie non générées

Problème : un run complet de pipeline n’avait pas été relancé correctement. Les sorties produites étaient incomplètes ou les métadonnées n’étaient pas remplies.

Correction : exécution du pipeline complet avec génération des datasets traités et des fichiers de sortie attendus.

Fichiers produits : `data/processed/features_risque.csv`, `data/processed/scores_risque.csv`, fichiers de modèles, rapports.

### 5) Collision de modules Python avec la librairie SHAP

Problème : un dossier local nommé `shap` masquait la vraie librairie SHAP installée, provoquant des erreurs d’import et des attributs manquants.

Correction : renommage du dossier local et suivi de la bonne librairie au runtime.

Impact : élimination de l’erreur de type `module 'shap' has no attribute 'TreeExplainer'`.

### 6) Librairie SHAP absente de l’environnement

Problème : SHAP était référencé dans les dépendances, mais n’était pas installée dans l’environnement de travail.

Correction : installation de la dépendance correcte et vérification de son utilisation effective.

### 7) Changement d’API SHAP majeur sur la version installée

Problème : la version SHAP utilisée exposait une convention d’axes différente pour les valeurs d’explication. Les calculs de classement de classes étaient mal indexés.

Correction : normalisation de la lecture des arrays SHAP selon la convention réelle `(N, F, classes)` et adaptation de la logique d’extraction de la classe positive.

Impact : correction du calcul et génération de résultats SHAP cohérents.

### 8) Appels legacy `shap.waterfall_plot` incompatibles avec la version actuelle

Problème : les pages Streamlit utilisaient encore l’ancienne API de SHAP, supprimée sur les versions récentes.

Correction : migration vers la forme actuelle basée sur `shap.plots.waterfall` avec `shap.Explanation(...)`.

Fichiers impactés : pages Streamlit d’explication et de commune explorer.

### 9) Colonnes dupliquées après merge de tableaux

Problème : des colonnes identiques entre jeux de données provoquaient des suffixes `_x` / `_y` et des erreurs de clé pendant les vues Streamlit.

Correction : nettoyage des colonnes de jointure et harmonisation du dataframe avant fusion.

Impact : stabilisation des pages `08_CommuneExplorer.py` et `09_Dashboard.py`.

### 10) Parsing des CSV BDIFF avec en-têtes libres non gérés

Problème : les fichiers BDIFF contiennent des lignes d’en-tête variables avant les colonnes réelles. Le chargement naïf tombait sur un `ParserError`.

Correction : utilisation de la logique de saut d’en-tête adaptée au format BDIFF, avec chargement sécurisé des fichiers.

Fichiers impactés : chargeurs de données et pages d’exploration.

### 11) Rapport de cross-validation absent

Problème : les pages de validation dépendaient d’un fichier JSON qui n’était pas généré à la suite du pipeline.

Correction : génération du rapport de validation, puis alimentation des pages qui affichent les résultats.

### 12) Problèmes de fiabilité de terminal / sortie stales

Problème : plusieurs sorties de pytest semblaient rester figées et ne reflétaient pas l’état réel du code. Cela a créé des ambiguïtés sur l’état du projet.

Correction : bascule vers une méthode de vérification plus fiable, avec redirection vers fichier et validation directe des sorties produites.

Ce point a révélé un besoin fondamental de ne pas se fier à des sorties de terminal anciennement mises en cache.

---

---

## 3bis. Reglages du 18 septembre : avant / apres

Les douze points ci-dessus concernaient des **blocages** : des choses qui ne
demarraient pas. Cette section couvre des **reglages** : des choses qui
demarraient, mais mal. Chaque ligne indique ce qui etait en place, ce qui a ete
mis a la place, et pourquoi.

### A. Ce qui faisait planter Streamlit a chaque changement de commune

| | Avant | Apres |
|---|---|---|
| Lecture des donnees | `pd.read_csv` de `features_risque.csv` (**157 Mo**) a chaque reexecution | `@st.cache_data(persist="disk")`, 5 colonnes sur 30, lu une seule fois |
| Chargement du modele | `joblib.load` de `model_risque_raw.joblib` (**730 Mo**) a chaque reexecution | `@st.cache_resource`, charge une seule fois, et **seulement** si l'utilisateur demande le SHAP |
| Modele dans `09_Dashboard` | `@st.cache_data`, qui **serialise** l'objet a chaque appel | `@st.cache_resource`, qui le garde en memoire sans le copier |
| SHAP d'interactions | `shap_interaction_values()` sur 300 a 500 lignes, sur trois pages, a chaque clic | supprime ; le dependence plot classique repond a la meme question pour une fraction du cout |
| Source de la prediction | jointure de `features_risque.csv` (662 397 lignes) avec les scores | `scores_risque.csv` seul (34 863 lignes, **9 Mo**) : la probabilite y est deja calculee |
| Selecteur de commune | 34 863 entrees d'un coup | departement puis commune, ou recherche par nom : au plus 887 entrees |

**Effet mesure**, sur 30 changements de commune consecutifs : **65 ms** par
changement, memoire stable a 463 Mo, zero exception. Avant, l'application
tombait au bout de quelques clics.

### B. Ce qui produisait un modele de 3,4 Go

Cause racine des lenteurs ci-dessus.

| Reglage | Avant | Apres | Pourquoi |
|---|---|---|---|
| `max_depth` | absent | `12` | sans borne, les arbres grandissent jusqu'a isoler chaque observation : 730 Mo pour le modele brut |
| `class_weight` | absent | `"balanced"` | 2,53 % de positifs : sans ponderation, le modele apprend surtout a dire « non » |
| `min_samples_leaf` | `2` | `3` | limite le surapprentissage |
| `CalibratedClassifierCV` | sans `cv` | `cv=3` | sans `cv`, scikit-learn en utilise 5 et **stocke cinq forets** : d'ou les 3,4 Go |
| Debut de l'entrainement | `2006` | `2011` | avant 2011, `nb_feux_10a` est calcule sur moins de dix ans : la variable ment |

### C. Metriques et chiffres annonces

| | Avant | Apres |
|---|---|---|
| `rappel_top_5pct` | valait en realite la **precision** (`vrais_top5.mean()`) | deux cles distinctes : `precision_top_5pct` **et** `rappel_top_5pct` |
| Chiffre annonce | « 28,3 % de rappel » | precision **28,3 %** (494 / 1 744) et rappel **56,0 %** (494 / 882) |
| Niveaux de risque | seuils fixes sur 100 : le niveau « Tres eleve » etait **vide** | deciles : 3 487 communes en « Tres eleve », repartition exploitable |
| Validation geographique | communes tirees au hasard sur toute la France, donc leurs voisines restaient dans l'entrainement | limite documentee ; le decoupage par departement entier reste a faire |

### D. Robustesse du chargement

| | Avant | Apres |
|---|---|---|
| `latest_run.json` vide ou sans cle | `KeyError: 'run_dir'` au niveau module, donc **a l'import** | message clair indiquant la commande a lancer, plus repli sur le dernier run present sur le disque |
| Chemin Windows dans `latest_run.json` | `Path(...).name` sous Linux renvoyait le chemin entier | normalisation manuelle des separateurs |
| Code INSEE | lu comme un nombre : `01001` devenait `1001`, et le departement `01` devenait `10` | `zfill(5)` systematique au chargement |
| `api/streamlit/app.py` | `from api.streamlit.bootstrap import ROOT` **avant** d'avoir mis la racine sur `sys.path` : import impossible | bootstrap en tete de fichier, avant tout import projet |
| Artefact manquant | traceback Python brut affichee a l'utilisateur | message en francais + commande de regeneration |

### E. Ce qui a ete ajoute le 18 septembre

| Ajout | Ce que ca apporte | Ou |
|---|---|---|
| Comparaison de trois modeles | repond a « Random Forest ou XGBoost ? » avec des chiffres : XGBoost 0,331 de PR-AUC contre 0,328, et cinq fois plus rapide ; la regression logistique plafonne a 0,222 | `models/train_test/comparaison_modeles.py`, page 10 |
| Variables temporelles a 10 / 30 / 60 jours | permet d'interroger une **date precise** (« Aix-en-Provence, le 15 juin 2025 ») au lieu d'une annee | `models/pipeline/features_horizon.py`, page 11 |
| Echantillonnage negatif + correction du prior | rend traitables les 242 millions de lignes theoriques : 1,5 million de lignes conservees, probabilites ramenees au taux reel | idem |
| Densite de voisinage a 20 km | remplace le cluster DBSCAN, qui etait calcule en regardant aussi la periode de test ; meilleure precision **sans fuite** | idem |
| Date d'alerte dans l'ingestion | `date_alerte` etait dans la base mais jamais lue : sans elle, aucune prediction a la journee n'est possible | `models/pipeline/ingestion.py` |
| `ORDER BY` sur les requetes SQL | sans tri explicite, PostgreSQL renvoie l'ordre physique, qui change apres un VACUUM ; plusieurs etapes en aval supposent un ordre stable | idem |

### F. Ce qui reste a faire

- decoupage geographique par **departement entier** dans la validation croisee ;
- **clustering temporel** (regrouper les annees par profil) ;
- **rapport methodologique** ;
- donnees **meteo** : c'est le plus gros levier restant, et la seule facon de
  passer d'une carte de risque a une alerte operationnelle.

---

## 4. Livrables de validation

Les livrables suivants ont été produits ou vérifiés :

- `data/processed/features_risque.csv`
- `data/processed/scores_risque.csv`
- fichiers modèles de prédiction ;
- rapports de validation et de métriques ;
- artefacts SHAP générés et exploités ;
- application Streamlit fonctionnelle sur les pages principales ;
- métadonnées de run et résultats d’explication.

---

## 5. Conclusion technique

Le projet est dans un état fonctionnel solide sur le plan produit et pipeline : les données, les features, les modèles, les interfaces et les explications ont été corrigés et alignés sur les versions réelles des dépendances et des données.

Le point restant à confirmer de manière totalement décisive relève de la vérification automatisée du dépôt complet : la boucle `pytest` doit être relancée dans un environnement terminal stable pour obtenir une preuve finale sans ambiguïté. Aucune affirmation de “tous les tests passent” n’a été faite sans sortie fiable.

---

## 6. Actions de fin

Le projet est prêt pour :

- la soutenance technique ;
- la présentation des corrections historiques ;
- la démonstration du pipeline finalisé ;
- la synthèse des améliorations effectuées et de leur impact.
