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

### 4bis. Variables temporelles a horizon court (ajout du 18/09)

Les variables ci-dessus sont annuelles : une ligne par commune et par annee. Elles
repondent a « cette commune brulera-t-elle dans l'annee ? ». Le professeur a
demande plus fin : pouvoir interroger une date precise, par exemple
Aix-en-Provence le 15 juin 2025. Un second jeu de variables a donc ete
construit, a la **journee**.

#### Le probleme de volume, et comment il est resolu

Une ligne par commune et par jour, c'est 34 863 x 365 x 19 = **242 millions de
lignes**. Impossible a traiter en pandas sur une machine de bureau.

La methode retenue est l'**echantillonnage negatif**, standard sur les
evenements rares :

1. on conserve **tous** les couples (commune, date) suivis d'un feu dans
   l'horizon considere : aucun positif n'est perdu ;
2. on tire au hasard cinq negatifs par positif ;
3. on **corrige la probabilite** predite pour revenir au taux reel, en
   multipliant la cote par la fraction de negatifs conservee.

Resultat : **1 498 374 lignes** au lieu de 27 018 825 couples possibles sur la
grille, soit 5,5 % de l'espace, pour 4,66 % des negatifs conserves. Sans la
correction du prior, les probabilites affichees seraient environ vingt fois trop
elevees.

L'entrainement se fait sur une grille hebdomadaire — deux dates distantes de
trois jours donnent des variables quasi identiques — mais le modele, une fois
entraine, s'applique a **n'importe quelle date** : les variables sont
recalculees a la volee pour la date demandee.

#### Les 22 variables

| Famille | Variables | Fenetre |
|---|---|---|
| Activite recente de la commune | `feux_7j`, `feux_30j`, `feux_90j`, `feux_365j`, `surface_30j_ha`, `surface_365j_ha`, `jours_depuis_dernier_feu` | arretee la **veille** de la date evaluee |
| Saisonnalite | `feux_meme_mois_5a`, `jour_annee_sin`, `jour_annee_cos`, `mois` | jour de l'annee, encode en cyclique |
| Voisinage 20 km | `feux_voisinage_30j`, `feux_voisinage_5a` | feux des communes situees a moins de 20 km, commune exclue |
| Historique long | `nb_feux_5a`, `nb_feux_10a`, `surface_10a_ha` | repris du panel annuel |
| Contexte fixe | `latitude`, `longitude`, `population`, `densite`, `altitude_moy`, `superficie_km2` | — |

#### Pourquoi le voisinage remplace le cluster spatial

`cluster_spatial` et `cluster_risque` sont **volontairement absents** de ce jeu.
DBSCAN est calcule sur l'ensemble des feux 2006-2024, periode de test comprise :
l'utiliser ici reviendrait a donner au modele une information qu'il ne peut pas
avoir au moment de la prediction. Mesure faite sur l'horizon 30 jours :

| Jeu de variables | PR-AUC | Precision top 5 % | Rappel top 5 % |
|---|---|---|---|
| avec les clusters (fuite) | 0,4873 | 54,2 % | 34,1 % |
| sans les clusters | 0,4803 | 54,4 % | 34,2 % |
| **avec le voisinage 20 km** | **0,4861** | **55,6 %** | **35,0 %** |

Le voisinage, calcule strictement sur le passe, recupere la quasi-totalite de la
performance **et** ameliore la precision. C'est la traduction honnete de l'idee
de « continuum de risque » : un feu ne s'arrete pas a la limite communale.

#### Resultats par horizon

Entrainement 2010-2022, test janvier 2023 - novembre 2024.

| Horizon | PR-AUC | Gain sur le hasard | Precision top 5 % | Rappel top 5 % |
|---|---|---|---|---|
| 10 jours | 0,216 | x 7,5 | 22,4 % | 39,1 % |
| 30 jours | 0,485 | x 6,1 | 55,4 % | 34,9 % |
| 60 jours | 0,764 | x 5,3 | 90,3 % | 31,1 % |

Variables les plus importantes a 30 jours : `jours_depuis_dernier_feu` (40,5 %),
`feux_voisinage_30j` (15,0 %), `nb_feux_10a` (10,8 %), `feux_voisinage_5a`
(6,7 %), `surface_10a_ha` (5,2 %), `mois` (4,5 %).

Exemple de lecture, Aix-en-Provence :

| Date interrogee | 10 jours | 30 jours | 60 jours |
|---|---|---|---|
| 20 janvier 2025 | 7,8 % | 14,7 % | 58,7 % |
| 15 juin 2025 | 20,8 % | 42,1 % | 92,3 % |
| 10 aout 2025 | 26,5 % | 43,4 % | 81,4 % |

La saisonnalite ressort nettement : a horizon egal, le risque est deux a trois
fois plus eleve en juin qu'en janvier.

Fichiers : `models/pipeline/features_horizon.py`,
`models/train_test/train_horizons.py`.
Commande : `make train-horizons`.
Page de l'application : **11 · Prediction datee**.

---

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

**Limite connue** : aucune commune n'atteint ce dernier niveau, la probabilite
maximale sur toute la France etant de 30,5 %. L'application affiche donc
desormais des niveaux par **deciles** et non par seuils fixes.

Ces seuils sont des seuils de lecture pour l'interface, pas des seuils reglementaires.

### 6bis. Comparaison des modeles (ajout du 18/09)

Le professeur a demande « Random Forest ou XGBoost ? ». Sans point de
comparaison chiffre, retenir la Random Forest n'est pas un choix mais une
preference. Les trois candidats ont donc ete entraines sur **exactement le meme
decoupage**, avec les memes variables et la meme calibration sigmoide (cv=3).

Entrainement 2011-2022 (418 356 lignes), test 2023 (34 863 lignes, 2,53 % de
positifs).

| Modele | PR-AUC | Gain sur le hasard | ROC-AUC | Brier | Precision top 5 % | Rappel top 5 % | Entrainement |
|---|---|---|---|---|---|---|---|
| Regression logistique | 0,222 | x 8,8 | 0,921 | 0,0237 | 25,4 % | 50,2 % | 3 s |
| Random Forest | 0,328 | x 12,9 | 0,937 | 0,0210 | 27,7 % | 54,8 % | 62 s |
| **XGBoost** | **0,331** | **x 13,1** | 0,935 | 0,0211 | **28,5 %** | **56,3 %** | **13 s** |

Lecture :

- la **regression logistique** sert de plancher. Elle montre ce qu'on obtient
  sans interaction entre variables. Les modeles a arbres apportent **+48 %** de
  PR-AUC : la relation entre historique et risque n'est donc pas lineaire ;
- **XGBoost et Random Forest sont a egalite** sur la PR-AUC (0,331 contre
  0,328, un ecart de 1 %). XGBoost prend un leger avantage sur le rappel au top
  5 % (56,3 % contre 54,8 %) ;
- l'argument decisif est ailleurs : XGBoost s'entraine **cinq fois plus vite**
  (13 s contre 62 s). A performance equivalente, un modele qui se reentraine
  cinq fois plus vite se reentraine cinq fois plus souvent ;
- la **calibration** est comparable (Brier 0,021 pour les deux), donc les
  probabilites des deux modeles sont egalement exploitables.

Conclusion retenue : **XGBoost pour les modeles a horizon court** (ou la vitesse
compte, le jeu faisant 1,5 million de lignes), **Random Forest conservee pour le
modele annuel** deja en production, les deux etant statistiquement equivalents.

Fichier : `models/train_test/comparaison_modeles.py`.
Commande : `make comparer-modeles`.
Page de l'application : **10 · Comparaison**.

---

## 7. Validation

Le test est temporel : le modele apprend sur 2011-2022 et est evalue sur 2023. Les metriques produites lors de l'execution sont :

- ROC-AUC : **0,941**, mesure secondaire ;
- PR-AUC : **0,347**, contre une baseline de **0,025** ;
- score de Brier : **0,0208** ;
- precision du top 5 % : **28,3 %** (494 communes brulees sur 1 744 designees) ;
- rappel du top 5 % : **56,0 %** (494 communes attrapees sur 882 qui ont brule) ;
  precision et rappel ont le meme numerateur mais pas le meme denominateur :
  les confondre divise le chiffre annonce par deux ;
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
- le voisinage est desormais une variable numerique (`feux_voisinage_30j` et
  `feux_voisinage_5a`, rayon 20 km) dans les modeles a horizon ; le modele
  annuel, lui, n'utilise encore que l'appartenance au groupe DBSCAN ;
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
| Variables temporelles 10 / 30 / 60 jours | Fait, voir section 4bis |
| Prediction a une date precise | Fait, page 11 de l'application |
| Comparaison Random Forest / XGBoost | Fait, voir section 6bis |
| Baseline regression logistique | Fait, voir section 6bis |
| Densite de voisinage (rayon 20 km) | Fait, variables `feux_voisinage_*` |
| Clustering temporel | Non fait |
| Rapport methodologique | Non fait |
