# Jour 3 - Application Streamlit

## Bloc recapitulatif : changements observes apres l'actualisation GitHub

Depuis l'etat precedent, l'actualisation du depot a surtout apporte une structure de tests (`tests/`), une nouvelle organisation des imports du pipeline et une CI plus complete. La documentation du jour 2 et les controles qualite ont aussi ete ajoutes ou enrichis. L'application Streamlit etait encore un squelette : elle affichait un compteur et des onglets, mais pas encore la carte ni les filtres.

## Objectif du jour 3

Le jour 3 transforme la base consolidee en outil d'exploration utilisable. Le but est de permettre a un utilisateur de filtrer les incendies historiques, de voir les indicateurs correspondants, d'observer leur evolution et de les localiser.

Le modele de risque n'est pas implemente ici : il appartient au jour 4, apres le feature engineering et le choix de la methode de clustering.

## Ce qui a ete fait

### 1. Chargement des donnees

`api/streamlit/app.py` charge les donnees depuis PostgreSQL avec une requete SQL unique. La requete joint `fires` au referentiel `ref_communes` avec une jointure gauche.

Pourquoi une jointure gauche ? Les incendies non geocodes doivent rester dans les compteurs et les graphiques. Une jointure interne les ferait disparaitre silencieusement.

Les donnees sont mises en cache pendant une heure avec `st.cache_data`. Cela evite de relire 140000 lignes a chaque interaction avec un filtre.

### 2. Preparation des variables d'affichage

Le code convertit `date_alerte` en date pandas, cree une saison a partir du mois et remplace les valeurs manquantes de `nature` par `Non renseignee`.

La vegetation est classee simplement pour l'interface :

- `Foret` si une surface forestiere est renseignee et positive ;
- `Maquis / garrigues` si le maquis est present sans surface forestiere ;
- `Agricole` si une surface agricole est presente sans les deux categories precedentes ;
- `Autres / non renseignee` dans les autres cas.

Cette categorie est un filtre de lecture, pas encore une variable de modele. Le feature engineering sera formalise au jour 4.

### 3. Filtres historiques

Les filtres sont places dans la barre laterale :

- intervalle d'annees ;
- mois ;
- saison ;
- departement ;
- nature du feu ;
- vegetation dominante ;
- surface minimale en hectares.

Le DataFrame est filtre en memoire apres son chargement. Cette solution est adaptee a la taille actuelle du prototype et rend les interactions rapides.

Si aucun filtre n'est selectionne, la condition n'est pas appliquee. Si aucun incendie ne correspond, l'application affiche un message clair au lieu d'un graphique vide ou d'une erreur.

### 4. Indicateurs

Pour la selection courante, l'application affiche :

- le nombre d'incendies ;
- la surface totale parcourue ;
- la surface moyenne ;
- le taux de communes geocodees.

Ces indicateurs sont recalcules apres chaque modification des filtres. Ils permettent de relier directement une selection a une mesure interpretable.

### 5. Graphiques historiques

Deux graphiques Streamlit affichent par annee :

- le nombre d'incendies ;
- la surface totale parcourue.

Ils ne recalculent pas de nouvelles features de machine learning. Ils decrivent uniquement la selection historique issue de la base.

### 6. Carte

La carte utilise `st.map`, disponible nativement dans Streamlit. Elle affiche les lignes qui possedent une latitude et une longitude.

La taille des points est proportionnelle a la racine carree de la surface parcourue. La racine carree evite qu'un tres grand incendie rende les petits points invisibles. Les feux non geocodes restent dans les indicateurs, mais ne peuvent pas etre places sur la carte.

Le choix de `st.map` evite d'ajouter Folium et `streamlit-folium` au prototype. Il est suffisant pour le jour 3 ; une carte Folium ou PostGIS plus riche pourra etre ajoutee si les besoins de la soutenance l'exigent.

### 7. Classement departemental

Un tableau affiche les quinze departements les plus representes dans la selection, avec le nombre d'incendies et la surface totale. Il permet de passer d'une observation visuelle a une comparaison chiffrable.

### 8. Onglets restants

L'onglet `Prediction du risque` indique clairement que le modele sera construit au jour 4. L'onglet `Methodologie` explique la source des donnees et le traitement des feux non geocodes.

Il est preferable de laisser cette limite explicite plutot que d'afficher une fausse prediction avant d'avoir construit et valide le modele.

## Correspondance avec le PDF

| Exigence du jour 3 | Etat |
|---|---|
| Structure multi-onglets | Fait |
| Connexion base de donnees | Fait |
| Interface cartographique de base | Fait |
| Filtre temporel | Fait |
| Filtre gravite / surface | Fait |
| Filtre vegetation | Fait, categorie d'affichage |
| Filtre origine | Fait avec `nature` |
| Statistiques descriptives | Fait |
| Evolution temporelle | Fait |
| Classement geographique | Fait |
| Carte avancee avec fond geographique | Non necessaire pour le prototype initial |
| Prediction ML | Jour 4 |

## Limites connues

- `st.map` est une carte de points simple, sans fond de departements ni popup detaillee ;
- la categorie de vegetation est une simplification pour filtrer, pas une nomenclature scientifique complete ;
- la base doit etre demarree avec Docker/PostGIS ;
- les incendies non geocodes ne sont pas visibles sur la carte ;
- l'onglet prediction ne sera complet qu'apres le feature engineering et la validation du modele.

## Lancer l'application

Depuis la racine du projet, avec Docker et PostgreSQL demarres :

```powershell
streamlit run api/streamlit/app.py
```

Puis ouvrir l'adresse locale affichee par Streamlit. Les filtres sont dans la barre laterale et les graphiques se recalculent pour la selection courante.
