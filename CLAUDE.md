# Consignes de travail

## Avant chaque commit

1. **`/code-review` en effort `medium`** sur le diff de travail, corrections
   appliquées **avant** de figer le commit.
   Réviser après coup oblige à un `--amend` ou à un commit de rattrapage qui
   encombre l'historique.
   Un commit petit peut reporter sa revue au suivant, **jamais au-delà de deux
   commits**. Et lancer la revue veut dire l'invoquer réellement : relire son
   propre diff et passer `ruff` n'est pas une revue.
2. `ruff` et `pytest` passent — le hook `pre-commit` le refuse sinon.

## Lancer les tests

**Fichier par fichier**, pas en un bloc — la machine de l'utilisateur est juste
en mémoire :

```bash
scripts/run_tests.sh
```

Un processus par fichier de tests, code de sortie 1 si l'un échoue. C'est ce que
lance le hook `pre-commit`. En un seul processus, la QApplication partagée, les
widgets, les vignettes et les images d'export s'accumulent : **177 Mo de pic d'un
bloc contre 142 Mo fichier par fichier**, pour deux secondes de plus.

Pour un fichier seul, `uv run pytest tests/test_x.py` reste le bon geste.

⚠️ **Ne pas gonfler les fixtures.** Des vignettes de 178×246 dans une fenêtre de
900×600, pour tester le zoom, coûtaient 83 Mo à elles seules ; des vignettes de
60×166 dans une fenêtre de 420×320 démontrent la même chose. Quand un test exige
que l'image dépasse le cadre, **rétrécir le cadre plutôt que grossir l'image**.

Le hook s'active une fois par clone :

```bash
git config core.hooksPath .githooks
```

## Granularité des commits

**Un commit par intention, pas par session de travail.** Les premiers commits du
projet font 300 à 1100 lignes et mélangent plusieurs sujets : c'est trop pour être
relu ou bissecté utilement.

## Revue complète

Aux grandes étapes (fin de l'interface, avant l'empaquetage), l'utilisateur lance
lui-même une revue complète du code. Ses constats sont à **vérifier un par un** —
une revue peut se tromper. Reproduire avant de corriger, puis verrouiller par un
test de non-régression.

## Pièges connus du projet

- **Indices de cartes.** `card.index` doit toujours égaler la position dans la
  liste : les matrices de distances sont indexées par position. Pour ne travailler
  que sur une partie des cartes, utiliser `select_cards()`, qui renumérote les
  cartes **et** traduit les liens. `CardSet.subset()` seul laisse les liens
  pointer sur d'autres cartes, sans erreur ni signe visible.
- **Traduction.** `lupdate` n'extrait que les `tr()` portant une chaîne littérale.
  `self.tr(variable)` reste non traduit sans que rien ne le signale. Après toute
  modification de texte :

  ```bash
  uv run pyside6-lupdate src/pokemon_mosaic/ui/*.py -ts translations/pokemon_mosaic_en.ts
  uv run pyside6-lrelease translations/pokemon_mosaic_en.ts
  ```
- **Le cœur n'est pas couvert de bout en bout partout.** Une régression de
  signature dans `load_cards` est passée à travers 231 tests, parce que les tests
  d'interface construisent leurs `CardSet` à la main. Après toute modification de
  `cards.py`, lancer un chargement réel.
- **Vérifier le rendu, pas seulement les tests.** Plusieurs défauts réels
  (dossiers homonymes fusionnés, cases vides alignées en colonne, formulaire
  désynchronisé) n'ont été vus qu'en regardant une capture d'écran ou les chiffres
  d'une exécution réelle, sur une suite de tests au vert.

## Documents

- `SPEC.md` — définition du projet et journal des décisions. À tenir à jour.
- `TODO.md` — évolutions reportées après la v1.
