# Les illustrations

Ce que le projet attend d'une image de carte, et comment elles circulent.

## Format

**734 × 1024, WebP qualité 80, illustration seule** — sans cadre, sans bandeau
de nom, sans texte d'attaque. C'est la texture que le jeu compose à l'affichage,
et c'est elle qui porte les couleurs de bord dont l'algorithme se sert.

Le format n'est pas indicatif : il sert de **filtre**. Une image qui n'y est pas
est soit une autre illustration, soit un agrandissement, et dans les deux cas
elle n'a pas sa place telle quelle. `artwork.process()` ramène au format,
applique un rognage si on lui en déclare un, et encode.

⚠️ **Le rognage est déclaré en pixels du format cible**, donc l'image est mise à
l'échelle *avant* d'être rognée. Une source en 717 × 1000 à qui l'on retire
30 px du haut tomberait sinon 2,4 % à côté sans que rien ne le signale.

## Pourquoi la qualité 80

Mesuré sur les 441 illustrations : **56,5 Mo** au total contre **541 Mo** pour
les mêmes images sans perte. L'écart médian sur la moyenne RGB d'un bord — la
seule grandeur dont l'algorithme se sert — vaut **0,45 niveau sur 255**, sous
l'erreur des vignettes à 25 %, déjà acceptée.

Le WebP avec perte impose un sous-échantillonnage 4:2:0 de la chrominance. La
luminance survit très bien, la chrominance beaucoup moins, ce qui explique les
écarts numériques importants qu'on observe sur les aplats colorés sans que l'œil
les voie.

## D'où elles viennent

**D'un dossier local, et de nulle part ailleurs.** Le projet ne va chercher
aucune image sur un site : il n'y a ni catalogue distant, ni adresse d'origine,
ni récupération automatique. Les illustrations sont déposées à la main dans
`data/pokemoncards/<extension>/`, par le mainteneur, comme il l'entend.

## Comment elles circulent

Le **miroir** est un dépôt GitHub dédié et public dont la *release* porte une
archive par extension, plus le catalogue `cards.json`. C'est la seule provenance
que connaissent la ligne de commande et l'application.

```
data/pokemoncards/  ──build_manifest.py──▶  cards.json
        │                                       │
        └───────publish_release.py──────────────┘
                          │
                          ▼
              miroir GitHub (release cards-v4)
                          │
                fetch_cards.py / bouton de l'étape 1
                          ▼
                 dossier de cartes de l'utilisateur
```

Les octets d'un miroir sont **identiques pour tout le monde** : un réencodage
local, lui, dépend de la version de libwebp installée et produirait des
empreintes différentes d'une machine à l'autre.

Chaque archive est vérifiée par empreinte, puis chaque image à l'intérieur. Le
découpage par extension permet de ne retélécharger que ce qui a changé.

## Ajouter des cartes

1. déposer les illustrations dans `data/pokemoncards/<extension>/`, nommées
   `<extension>-<numéro>-<nom>.webp` ;
2. `uv run python scripts/build_manifest.py` — le catalogue est mis à jour et
   les champs qu'un fichier ne porte pas (rareté, noms) sont nommés ;
3. les compléter dans `cards.json` ;
4. `uv run python scripts/publish_release.py`.

Les utilisateurs voient les nouvelles cartes au bouton « Mettre à jour le
catalogue » : l'application relit `cards.json` depuis la *release* et ne
télécharge que les extensions incomplètes.

## Point de droit

Ces illustrations appartiennent à leurs ayants droit. Les héberger est une
rediffusion, et le miroir vit pour cette raison dans un dépôt **dédié**, sans
code ni historique : un signalement viserait ce dépôt-là, qui se reconstruit en
trente secondes depuis `data/pokemoncards/`, et le dépôt de code n'est pas
atteint.
