# Changer de branche sans rien casser

Memo court. A garder ouvert le jour ou tu dois aller voir une autre branche
(celle de Pierre, une branche de test, `main`...) et revenir travailler ici.

---

## 1. Le probleme en une phrase

**Git versionne le code, pas les donnees.**

Le `.gitignore` du projet exclut volontairement :

```
data/processed/run/
data/raw/
models/run/
*.joblib
*.csv (les gros)
```

Consequence directe : quand tu changes de branche, Git remplace tes fichiers
Python, tes notebooks, tes `docs/`... mais il **ne sait pas** que
`model_risque.joblib` existe. Ces fichiers sont "non suivis" (*untracked*).

Selon ce que fait l'outil (ligne de commande, GitHub Desktop, un `stash`, un
`clean`), ces fichiers non suivis peuvent :

- rester en place (cas normal, tout va bien) ;
- ou disparaitre (cas du `git clean`, ou d'un stash mal remis).

Et c'est exactement ce qui t'est arrive : au retour, Streamlit affichait
"comparaison_modeles.json introuvable". Le code etait bon, les **artefacts**
avaient saute.

> Il y a un deuxieme piege, plus sournois : `data/processed/latest_run.json`
> pointe vers un dossier de run precis. Si le dossier disparait mais pas le
> JSON, Streamlit cherche un run qui n'existe plus. Le script gere ce cas.

---

## 2. Avant de quitter la branche

Deux commandes, dans cet ordre, depuis la racine du projet :

```powershell
git status
python verifier_etat.py --sauvegarder
```

`git status` : tu dois voir **soit** "nothing to commit, working tree clean",
**soit** la liste de tes modifications. Si tu as des modifications non
commitees, commit-les avant de bouger. C'est la regle la plus simple et la
plus sure : **on ne change pas de branche avec du travail non commite.**

`--sauvegarder` : le script zippe les artefacts (modeles, scores, SHAP,
comparaisons, horizons) dans `sauvegardes/artefacts_<date>.zip`. Environ 6 Mo.
Il affiche a la fin le nom exact du zip : **note-le**, ou laisse la fenetre
ouverte.

Ensuite seulement : tu changes de branche.

---

## 3. Au retour sur ta branche

Trois commandes :

```powershell
git branch --show-current
python verifier_etat.py
streamlit run api/streamlit/app.py
```

`git branch --show-current` : verifie que tu es bien sur **ta** branche. C'est
bete, mais 90 % des "mon code a disparu" sont en realite "je ne suis pas sur
la bonne branche".

`python verifier_etat.py` : le diagnostic. Il liste les 22 artefacts, dit pour
chacun s'il est **OK** ou **MANQUANT**, sa taille, et quelles pages Streamlit
en dependent. Trois issues possibles :

| Ce qu'il affiche | Ce que tu fais |
|---|---|
| `Tout est en place.` | Tu lances Streamlit, c'est fini. |
| Une liste de MANQUANT | Tu restaures (etape 4) ou tu regeneres (etape 5). |
| `Aucun run exploitable` | Le run entier a saute : restaure, ou regenere tout. |

---

## 4. Restaurer (rapide : 10 secondes)

```powershell
python verifier_etat.py --restaurer artefacts_2026-09-18_10-48-17.zip
```

(le nom du zip que le script t'avait donne a l'etape 2)

Le script remet chaque fichier a sa place, puis relance automatiquement le
diagnostic pour te montrer le resultat. Tu dois voir "Tout est en place."

C'est **toujours** la voie a preferer. Regenerer, c'est plus d'une heure de
calcul pour obtenir exactement les memes fichiers.

---

## 5. Regenerer (long : 1 h a 1 h 30)

Si tu n'as pas de sauvegarde. Le diagnostic te donne les commandes dans le bon
ordre ; les voici en entier, avec leur duree :

```powershell
python -m models.pipeline.build_dataset         # ~15 min
python -m models.train_test.train_model         # ~10 min
python -m models.train_test.cross_validation    # ~25 min
python -m models.train_test.comparaison_modeles # ~2 min
python -m models.train_test.train_horizons      # ~20 min
python explainability/compute_shap.py           # ~5 min
```

L'ordre compte : `train_model` a besoin du dataset produit par
`build_dataset`, et `compute_shap` a besoin du modele produit par
`train_model`. Tu peux aussi tout enchainer avec `make ml-complet` si tu as
`make` installe ; sinon ces six lignes font la meme chose.

Le diagnostic n'affiche que les commandes **reellement necessaires** : s'il ne
manque que `shap_values.npy`, il ne te dira pas de relancer l'entrainement.

Attention : une regeneration complete cree un **nouveau** dossier de run
(nouvelle date). C'est normal. `latest_run.json` est mis a jour tout seul, et
les chiffres peuvent bouger a la 3e decimale (les forets aleatoires ne sont
pas exactement reproductibles d'une machine a l'autre).

---

## 6. Le cas GitHub Desktop : "Overwrite stash?"

Celui que tu as eu. Traduction : GitHub Desktop ne garde **qu'un seul stash
par branche**. Il en existe deja un sur la branche ou tu reviens, et il te
demande s'il peut l'ecraser avec le nouveau.

- Si le stash existant contient du travail dont tu te fiches : **Overwrite**.
- Si tu ne sais pas ce qu'il contient : **Cancel**, puis va voir avec
  `git stash list` et `git stash show -p stash@{0}` avant de decider.

La vraie parade est en amont : **commit avant de changer de branche** (etape
2). Pas de travail en cours, pas de stash, pas de dialogue.

---

## 7. Version ultra-courte

**Avant de partir**

```powershell
git status                              # tout doit etre commite
python verifier_etat.py --sauvegarder   # note le nom du zip
```

**Au retour**

```powershell
git branch --show-current               # suis-je au bon endroit ?
python verifier_etat.py                 # que manque-t-il ?
python verifier_etat.py --restaurer <zip>   # si ca manque
streamlit run api/streamlit/app.py
```

---

## 8. Pourquoi on ne met pas simplement les artefacts dans Git

Question legitime, et la reponse fait partie des choses a savoir dire a la
soutenance.

`features_risque.csv` pese 157 Mo. GitHub refuse les fichiers de plus de
100 Mo et rale des 50 Mo. Un modele `.joblib` pese 113 Mo. Surtout, ces
fichiers sont **binaires** : Git ne sait pas stocker seulement la difference
entre deux versions, il stocke une copie complete a chaque commit. Dix
entrainements et le depot fait plusieurs gigaoctets, pour toujours — un
fichier commite ne disparait jamais vraiment de l'historique.

La regle de metier est donc : **le depot contient de quoi reproduire les
artefacts, pas les artefacts**. C'est le role du `makefile` et des scripts de
pipeline. La sauvegarde zip locale est le complement pragmatique : elle evite
de payer une heure de calcul pour retrouver quelque chose qu'on avait deja.

Pour aller plus loin (hors perimetre du projet) : DVC ou Git LFS versionnent
les gros fichiers en les stockant ailleurs que dans le depot Git.
