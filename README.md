# Pokémon Mosaic

Assemble ~280 cartes Pokémon en une seule mosaïque géante, en cherchant l'agencement
où les **bords des cartes voisines se ressemblent le plus en couleur** — pour que
l'ensemble se lise comme une image continue plutôt qu'un patchwork.

Sortie typique : une grille 20×14, soit une image de **14260 × 13776 px**, plus un
aperçu réduit exploitable.

## Comment ça marche

1. **Vignettes** — chaque carte est chargée directement en vignette réduite (25 %,
   soit 178 × 246), toutes ramenées à la taille de la plus petite carte trouvée. Les
   images pleine résolution ne sont relues du disque qu'à l'export.
2. **Signature** — chaque carte est résumée à 4 vecteurs RGB : la couleur moyenne
   d'une bande de 10 % en haut, en bas, à gauche et à droite. 12 nombres par carte.
3. **Distances précalculées** — deux matrices N×N contiennent toutes les distances
   possibles entre bords (droite↔gauche et bas↔haut). Évaluer une couture devient une
   lecture de tableau.
4. **Score** — le coût d'une grille est la somme, sur chaque couture, de la distance
   entre le bord droit d'une carte et le bord gauche de sa voisine (idem
   verticalement). Plus bas = plus lisse.
5. **Optimisation** — descente stricte (*hill climbing*) : on tire deux zones au
   hasard, on échange, on ne garde que si le score local s'améliore. Seules les
   coutures touchées sont recalculées.

### Pourquoi travailler sur des vignettes

Les signatures ne sont que des moyennes de larges bandes, et réduire une image *est*
déjà un moyennage. L'erreur introduite est inférieure à **0,3 niveau de couleur sur
255**, pour des gains considérables :

| | Pleine résolution | Vignettes 25 % |
|---|---|---|
| Mémoire pour 280 cartes | 562 Mo | **35 Mo** |
| Chargement | ~30 s | **3,7 s** |
| Optimisation | 24 000 it/s | **127 000 it/s** |
| Rendu d'un aperçu | — | **5 ms** |

### Groupes imposés

Certaines cartes doivent rester côte à côte (Solgaleo–Lunala, Entei–Raikou). Elles
sont traitées comme des **blocs indivisibles** : un bloc ne se déplace que d'un seul
tenant, et uniquement vers une zone composée exclusivement de cartes libres. La
contrainte est donc satisfaite par construction, sans pénalité de score et sans
ralentir l'optimisation.

## Installation

Nécessite Python 3.13 et [uv](https://docs.astral.sh/uv/).

```bash
uv sync
```

Le socle est volontairement minimal — **numpy et Pillow seulement**, soit 47 Mo. Pour
relancer les scripts de `experiments/`, qui dépendent encore d'opencv, scipy et
scikit-learn :

```bash
uv sync --extra experiments
```

## Données

**Les cartes ne sont pas versionnées** (~350 Mo de PNG). Place-les toi-même dans :

```
data/pokemoncards/
├── serie_A/
│   ├── 0_promo/
│   ├── 1_puissance_genetique/
│   └── ...
└── serie_B/
    ├── 0_promo/
    └── ...
```

Un fichier PNG par carte, nommé d'après le Pokémon (`lucario.png`). Le dossier est
parcouru récursivement : l'organisation en séries/extensions est pour ta lisibilité,
le code ne s'en sert pas.

> Stocker ces images de façon partageable entre plusieurs machines reste à faire —
> voir [TODO.md](TODO.md).

## Utilisation

```bash
uv run pokemon-mosaic
```

Options utiles :

```bash
uv run pokemon-mosaic --iterations 50000 --preview-percent 25
```

| Option | Défaut | Rôle |
|---|---|---|
| `--data-dir` | `data/pokemoncards` | Dossier racine des cartes |
| `--output-dir` | `output/` | Où écrire la mosaïque |
| `--iterations` | `1000000` | Itérations d'optimisation |
| `--strip-size` | `0.1` | Épaisseur des bandes de bord (fraction) |
| `--grid` | auto | Grille explicite, ex. `17x17` |
| `--free-order` | non | Autoriser l'optimiseur à retourner les cartes liées |
| `--full-resolution` | non | Exporter en pleine résolution |
| `--preview-percent` | `15` | Taille de l'aperçu réduit |

Avec `--grid`, les cases excédentaires deviennent des **cases vides figées**,
réparties régulièrement et jamais déplacées par l'optimisation. L'app annonce alors
combien de cartes ajouter pour remplir exactement la grille :

```bash
uv run pokemon-mosaic --grid 17x17
```
```
280 cartes pour 289 cases (17×17) : il restera 9 cases vides.
Ajoutez 9 cartes pour remplir la grille.
```

Compter environ **30 s de chargement** des cartes, puis le temps d'optimisation
(~3000 itérations/s). Les sorties vont dans `output/`, non versionné.

## Structure

```
src/pokemon_mosaic/
├── cards.py      chargement en vignettes, signatures de bord
├── links.py      liens entre cartes et bibliothèque de liens
├── layout.py     formats d'impression, ajustement, cases vides
├── grid.py       dimensionnement de la grille, rendu
├── scoring.py    matrices de distances, score global et local
├── optimize.py   hill climbing, blocs imposés, cases figées
├── imaging.py    inspection et réduction des images produites
└── cli.py        point d'entrée

tests/            tests du cœur de calcul
experiments/      approches alternatives, conservées mais non maintenues
```

Tests :

```bash
uv run --extra dev pytest
```

### experiments/

Trois pistes antérieures, gardées pour référence. Aucune n'est sur le chemin
principal, aucune ne s'exécute à l'import.

- **`greedy_edge_matching.py`** — remplissage case par case en prenant à chaque fois
  la meilleure carte restante. Rapide mais myope : les dernières cases héritent des
  rebuts. C'est ce défaut qui a motivé l'optimisation par échanges.
- **`soft_adjacency_penalty.py`** — l'adjacence forcée par pénalité de score
  (`distance × 5000`) plutôt que par blocs. Oblige à recalculer le score global à
  chaque itération : trop lent, abandonné.
- **`tsne_assignment.py`** — approche entièrement différente : t-SNE sur les pixels
  bruts puis affectation optimale par algorithme hongrois. Regroupe par ressemblance
  globale au lieu de lisser les coutures. Jamais branché sur un point d'entrée.

## Limitations connues

Documentées dans le code, non corrigées à ce stade — voir [TODO.md](TODO.md).

- **La forme de la grille dépend de la factorisation du nombre de cartes.** 280 donne
  20×14, mais 281 est premier et donnerait une bande 281×1 de 200 000 px de large.
  C'est la seule raison pour laquelle une carte est exclue par défaut. L'application
  à venir rendra la grille explicite et autorisera les cases vides, ce qui supprime
  le problème.
- **La transparence est ignorée.** La majorité des cartes sont en RGBA et certaines
  ont de la vraie transparence, écartée sans composition sur un fond.

Deux limitations précédentes ont disparu avec la refonte du cœur : les indices ne
peuvent plus se désynchroniser (ils sont attribués à l'insertion), et la couture
partagée entre deux zones échangées n'est plus comptée deux fois (les deux zones sont
évaluées en un seul appel).
