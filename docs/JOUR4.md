# Jour 4 - Feature engineering, clustering et risque

## Objectif du jour

Le PDF demande de preparer des variables geo-temporelles, de mettre en oeuvre un clustering spatial et temporel, d'entrainer un modele de risque, puis de valider les resultats sur une periode non vue.

Le script principal est `data/ingestion_pipeline/jour4_model.py`.

## 1. Cible choisie

La cible est binaire :

> la commune aura-t-elle au moins un incendie l'annee suivante ?

Pour chaque commune et chaque annee `t`, la cible vaut 1 si la commune connait au moins un feu en `t + 1`, sinon 0.

Ce choix correspond a l'approche « occurrence d'incendie » du sujet. Il est plus simple a expliquer qu'une prediction de surface et compatible avec les donnees disponibles.

Le score n'est pas presente comme une alerte operationnelle : aucune donnee de vent, de temperature ou de secheresse n'est encore integree.

## 2. Perimetre temporel

Le modele utilise les annees 2006 a 2024, car la couverture BDIFF est plus large a partir de 2006.

- entrainement : 2011 a 2022 ;
- test temporel : 2023, avec une cible observee en 2024 ;
- scores affiches dans l'application : prediction de l'occurrence en 2025 a partir de l'historique jusqu'en 2024.

Cette separation evite de melanger le passe et le futur. Les variables de l'annee `t` utilisent uniquement les annees precedentes ; les informations de `t + 1` servent uniquement de cible.

## 3. Construction du panel

Le script construit une ligne par commune et par annee pour les communes geocodees du referentiel. Les communes sans incendie sont conservees avec des valeurs nulles remplacees par zero pour les compteurs et les surfaces.

Ce choix est important : si l'on ne gardait que les communes ayant deja brule, le modele ne verrait jamais les communes sans incendie et surestimerait le risque.

## 4. Features creees

Les variables historiques sont calculees avec des fenetres glissantes decalees d'un an :

- nombre de feux sur les 5 annees precedentes ;
- surface totale sur les 5 annees precedentes ;
- surface forestiere sur les 5 annees precedentes ;
- nombre de feux sur les 10 annees precedentes ;
- surface totale sur les 10 annees precedentes ;
- surface moyenne sur les 5 annees precedentes ;
- part des feux de juin a septembre ;
- latitude et longitude ;
- population, densite, altitude et superficie.

Les fenetres glissantes sont decalees avec `shift(1)`. Ainsi, pour predire 2023, aucune donnee de 2023 ou 2024 n'entre dans les features.

## 5. Clustering

### KMeans : profils de risque

KMeans est applique aux features standardisees de l'annee de reference 2023. La standardisation est necessaire car les variables ne sont pas dans les memes unites : hectares, habitants, altitude et coordonnees.

Le nombre de groupes retenu est 4. Le choix est volontairement interpretable pour un prototype. Le score de silhouette obtenu est :

- silhouette KMeans : **0,559**.

Les groupes representent des profils de communes, pas des classes administratives definitives. Il faudra les decrire dans l'EDA du jour 4 avec leurs moyennes de feux, de surfaces et de contexte.

### DBSCAN : voisinage spatial

DBSCAN est applique aux coordonnees geographiques avec une distance haversine. Le rayon choisi est de 50 km et le minimum de voisins est 5.

Resultat observe :

- 7 groupes spatiaux hors bruit ;
- 14 points classes comme bruit.

DBSCAN sert ici a identifier des zones geographiques concentrees. Il ne remplace pas le modele de risque.

## 6. Modele de prediction

Le modele retenu est une `RandomForestClassifier` avec :

- 200 arbres ;
- profondeur maximale de 12 ;
- minimum de 3 observations par feuille ;
- ponderation `balanced` pour compenser la rarete des communes incendiees.

Le modele produit une probabilite d'occurrence. Cette probabilite est convertie en score sur 100 :

```text
score_risque = probabilite_incendie * 100
```

Les niveaux d'affichage sont :

- Faible : score <= 10 ;
- Modere : 10 < score <= 25 ;
- Eleve : 25 < score <= 50 ;
- Tres eleve : score > 50.

Ces seuils sont des seuils de lecture pour l'interface, pas des seuils reglementaires.

## 7. Validation

Le test est temporel : le modele apprend sur 2011-2022 et est evalue sur 2023. Les metriques produites lors de l'execution sont :

- ROC-AUC : **0,917** ;
- ROC-AUC validation geographique : **0,931** sur 6 973 communes tenues a l'ecart ;
- accuracy : **0,857** ;
- balanced accuracy : **0,836** ;
- taux d'occurrence dans le test : **2,53 %**.

La balanced accuracy est conservee car la classe positive est rare. L'accuracy seule serait trompeuse : un modele qui predit toujours « aucun feu » pourrait obtenir une bonne accuracy sans etre utile.

## 8. Fichiers produits

L'execution du script produit :

- `data/processed/features_risque.csv` : lignes de features pour 2023 et 2024 ;
- `data/processed/scores_risque.csv` : score et groupes par commune ;
- `models/modele_risque.joblib` : modele Random Forest ;
- `models/metriques_risque.json` : metriques, parametres et liste des features.

Commande :

```powershell
python data/ingestion_pipeline/jour4_model.py
```

## 9. Integration Streamlit

L'onglet `Prediction du risque` charge `scores_risque.csv` et permet de :

1. choisir une commune ;
2. voir la periode predite, 2025 ;
3. voir le score sur 100 ;
4. voir le niveau Faible, Modere, Eleve ou Tres eleve ;
5. voir la probabilite estimee ;
6. voir l'historique des 5 annees precedentes ;
7. voir le profil KMeans et la zone DBSCAN ;
8. voir le ROC-AUC du test temporel.

Le modele n'est pas recalcule a chaque interaction Streamlit. Les scores sont calcules par le script et charges en cache par l'application. Cela rend l'interface rapide et separe clairement entrainement et consultation.

## 10. Limites

- le modele ne contient pas encore les donnees meteorologiques ;
- le voisinage est represente par DBSCAN, mais pas encore comme une feature numerique dans la Random Forest ;
- la couverture avant 2006 n'est pas utilisee pour l'entrainement principal ;
- le test 2023 est complete par une validation geographique sur des communes exclues de l'entrainement ;
- un score eleve indique un historique compatible avec une occurrence, pas une causalite ;
- les seuils de niveaux doivent etre calibres avec davantage de donnees et un objectif metier.

## Correspondance avec le PDF

| Demande du jour 4 | Etat |
|---|---|
| Features geo-temporelles | Fait |
| Historique communal 5/10 ans | Fait |
| Saisonnalite | Fait avec la part juin-septembre |
| Clustering spatial | Fait avec DBSCAN 50 km |
| Clustering de profils | Fait avec KMeans |
| Modele de prediction | Fait avec Random Forest binaire |
| Validation temporelle et geographique | Fait sur 2023 et 6 973 communes tenues a l'ecart |
| Score par commune | Fait |
| Interface predictive Streamlit | Fait |
| Donnees meteorologiques | Non disponibles, a ajouter dans une version suivante |
