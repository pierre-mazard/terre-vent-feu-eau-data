# Jour 2 - Consolidation, qualite et EDA

## Objectif

Le jour 2 sert a passer d'une base chargee a une base exploitable pour l'analyse et la modelisation. Le travail realise combine trois niveaux :

1. verifier que les donnees chargees sont coherentes ;
2. decrire les tendances temporelles, geographiques et metier ;
3. transformer ces constats en decisions pour le clustering du jour 4.

## Ce qui etait deja disponible

Le pipeline du jour 1 avait deja produit les tables `ref_communes`, `stg_bdiff`, `fires` et la vue `v_fires_geo`. Les 52 fichiers annuels BDIFF, de 1973 a 2024, sont presents dans `data/raw`.

Le script `data/ingestion_pipeline/qualite.py` execute six controles SQL. La derniere execution a donne 6/6 controles passes :

- 0 doublon sur la cle metier ;
- 99,31 % de feux geocodes, au-dessus du seuil de 97 % ;
- periode 1973-2024 respectee ;
- aucune surface negative ;
- aucune surface de foret superieure a la surface parcourue ;
- 140246 cles distinctes dans le staging et 140246 lignes dans `fires`.

## EDA realisee

Le notebook `analysis/eda_jour2.ipynb` contient l'analyse suivante.

### 1. Chargement

Les donnees sont lues depuis PostgreSQL, avec une jointure gauche entre `fires` et `ref_communes`. Ce choix est important : la vue `v_fires_geo` est une jointure interne et ferait disparaitre les 0,69 % de feux non geocodes. Les dates sont converties en dates pandas et une variable `saison` est creee.

### 2. Profilage de qualite

Le notebook calcule, pour chaque colonne, le nombre de valeurs manquantes et le taux de nullite. Les valeurs manquantes ne sont pas remplacees sans justification : pour `nature` et `type_peuplement`, l'absence d'information est une caracteristique de la source a documenter.

### 3. Analyse annuelle

Le notebook calcule par annee :

- le nombre de feux ;
- la surface totale parcourue ;
- la surface mediane ;
- la surface moyenne.

Deux courbes sont produites : le volume annuel et la surface annuelle avec une moyenne glissante sur cinq ans.

La moyenne glissante est retenue au lieu de STL. STL n'est pas obligatoire dans le sujet et ajoute une decomposition plus difficile a expliquer. La moyenne glissante suffit ici pour faire apparaitre une tendance sans donner une precision artificielle a des donnees affectees par des ruptures de couverture.

### 4. Saisonnalite

Les feux et les surfaces sont regroupes par mois. Deux graphiques montrent les mois les plus representes et les mois qui concentrent le plus de surface brulee. Ces variables pourront alimenter les features cycliques du modele : mois, jour julien, sinus et cosinus saisonniers.

### 5. Causes et vegetation

Les feux sont regroupes par `nature`. La valeur absente est affichee comme `Non renseignee` au lieu d'etre supprimee. Les surfaces sont aussi agregees par type de vegetation.

La rupture de structure de 2023 est conservee dans l'interpretation : seules les surfaces parcourue et foret sont comparables sur toute la periode. Les autres colonnes de vegetation doivent etre comparees par sous-periode.

### 6. Geographie

Le notebook produit un classement par departement et une carte de dispersion des feux geocodes. La taille des points est liee a la surface parcourue et la couleur a l'annee. Les feux sans coordonnees restent presents dans les statistiques nationales, mais ne peuvent pas apparaitre sur la carte.

Le controle geographique a revele 139280 coordonnees presentes, dont 137929 plausibles pour la France metropolitaine et 1351 hors des bornes metropolitaines. Ces lignes ne sont pas supprimees de la base : elles sont seulement exclues de la carte metropolitaine pour eviter une visualisation fausse.

## Decisions methodologiques

### Pourquoi ne pas faire STL maintenant ?

STL est possible, mais pas necessaire pour franchir le jour 2. Elle suppose une serie temporelle regulierement definie et son interpretation serait fragilisee par :

- la couverture geographique differente avant et apres 2006 ;
- la rupture de formulaire et de vegetation en 2023 ;
- l'absence de donnees meteorologiques ;
- l'annee 2024 potentiellement incomplete.

La tendance glissante et la saisonnalite mensuelle sont plus transparentes pour la soutenance. STL pourra devenir une analyse complementaire, pas une condition de reussite du jour 2.

### Variables candidates pour le jour 4

- nombre de feux par commune sur 5, 10 et 20 ans ;
- surface totale et mediane ;
- surface forestiere ;
- distribution mensuelle et saisonniere ;
- densite de feux dans un voisinage spatial ;
- population, densite, altitude et superficie communale ;
- proportion de feux recents et intensite historique.

Le score produit devra etre presente comme un score historique relatif, et non comme une probabilite causale ou une prevision operationnelle, tant que les donnees meteorologiques ne sont pas integrees.

## Limites a presenter

- les annees 1973-2005 ne representent pas toute la France ;
- les donnees du departement 64 sont incompletes en 2010-2011 ;
- 2024 peut etre incomplet pour certains departements ;
- les causes et types de peuplement sont souvent absents ;
- les colonnes de vegetation changent en 2023 ;
- 0,69 % des feux ne sont pas geocodes ;
- l'analyse historique ne contient pas encore la meteo, le vent ou la secheresse.

## Etat du jour 2

Le matin du jour 2 est couvert par la consolidation SQL, le pipeline relancable et les six controles d'integrite. L'apres-midi est couvert par le notebook EDA : profilage, temporel, saisonnalite, causes, vegetation et geographie. Les cellules de chargement, d'analyse et de controle geographique ont ete executees avec succes contre PostgreSQL.

Les tests pytest et les controles qualite plus fins restent des travaux de validation a programmer apres l'EDA. Ils ne bloquent pas le passage au choix des features et du clustering, mais devront etre ajoutes avant le rendu final.

## Execution

Depuis la racine du projet :

```powershell
streamlit run api/streamlit/app.py
```

Pour l'EDA, ouvrir `analysis/eda_jour2.ipynb`, selectionner l'interpreteur Python du projet, puis executer les cellules dans l'ordre.
