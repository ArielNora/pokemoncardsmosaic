# Consignes de travail

## Avant chaque commit

1. **`/code-review` en effort `medium`** sur le diff de travail, corrections
   appliquées **avant** de figer le commit.
   Réviser après coup oblige à un `--amend` ou à un commit de rattrapage qui
   encombre l'historique.
2. `ruff` et `pytest` passent — le hook `pre-commit` le refuse sinon.

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
- **Vérifier le rendu, pas seulement les tests.** Plusieurs défauts réels
  (dossiers homonymes fusionnés, cases vides alignées en colonne, formulaire
  désynchronisé) n'ont été vus qu'en regardant une capture d'écran ou les chiffres
  d'une exécution réelle, sur une suite de tests au vert.

## Documents

- `SPEC.md` — définition du projet et journal des décisions. À tenir à jour.
- `TODO.md` — évolutions reportées après la v1.
