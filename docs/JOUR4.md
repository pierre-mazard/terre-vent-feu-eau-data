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
- mois historique dominant et variables cycliques sinus/cosinus ;
- latitude et longitude ;
- population, densite, altitude et superficie.

Les fenetres glissantes sont decalees avec `shift(1)`. Ainsi, pour predire 2023, aucune donnee de 2023 ou 2024 n'entre dans les features.

## 5. Clustering

### DBSCAN : zones de feux

DBSCAN est applique aux coordonnees des feux, et non a toutes les communes.
Cela permet de reperer les zones ou les incendies sont effectivement
concentres. Le rayon retenu est de 20 km et le minimum de voisins est 8.
Les communes rattachees a un groupe de feux recoivent ensuite le groupe
spatial majoritaire de leurs incendies.
L'execution produit **14 groupes** et **213 points de bruit**. Le groupe
spatial et le profil KMeans sont ensuite fournis comme variables au modele.

### KMeans : profils de risque

KMeans est applique aux features standardisees de l'annee de reference 2022. La standardisation est necessaire car les variables ne sont pas dans les memes unites : hectares, habitants, altitude et coordonnees.

Le nombre de groupes est compare de 2 a 7 avec l'inertie (courbe du coude) et
le score de silhouette. Le meilleur score de silhouette retient **2 groupes**
avec un score de **0,702**, tout en conservant les inerties dans
`metriques_risque.json` pour documenter le choix.

- silhouette KMeans : **0,702**.

Les groupes representent des profils de communes, pas des classes administratives definitives. Il faudra les decrire dans l'EDA du jour 4 avec leurs moyennes de feux, de surfaces et de contexte.

## 6. Modele de prediction

Le modele retenu est une Random Forest calibree avec :

- 200 arbres ;
- profondeur maximale de 12 ;
- minimum de 3 observations par feuille ;
- ponderation `balanced` pour compenser la rarete des communes incendiees ;
- calibration sigmoide pour que les probabilites affichees soient plus
	interpretables.

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

- ROC-AUC : **0,941**, mesure secondaire ;
- PR-AUC : **0,347**, contre une baseline de **0,025** ;
- score de Brier : **0,0208** ;
- rappel du top 5 % : **28,3 %** des communes positives ;
- balanced accuracy : **0,500** ;
- taux d'occurrence dans le test : **2,53 %**.

La PR-AUC est comparee a sa baseline, qui correspond au taux de communes
ayant effectivement connu un feu. L'accuracy n'est plus publiee comme mesure
principale, car elle serait trompeuse avec 2,5 % de positifs.

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
| Clustering spatial | Fait avec DBSCAN 20 km sur les feux |
| Clustering de profils | Fait avec KMeans |
| Modele de prediction | Fait avec Random Forest binaire |
| Validation temporelle et geographique | Fait sur 2023 et 6 973 communes tenues a l'ecart |
| Score par commune | Fait |
| Interface predictive Streamlit | Fait |
| Donnees meteorologiques | Non disponibles, a ajouter dans une version suivante |
