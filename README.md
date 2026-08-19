# Pokémon Mosaic

Assemble ~280 cartes Pokémon en une seule mosaïque géante, en cherchant l'agencement
où les **bords des cartes voisines se ressemblent le plus en couleur** — pour que
l'ensemble se lise comme une image continue plutôt qu'un patchwork.

Le but est l'**impression d'un poster** : soit une seule grande feuille, soit
plusieurs accolées. Sortie typique : une grille 17×17 sur un A2 à 300 DPI, soit une
image de **4961 × 7016 px**.

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

### Liens entre cartes

Certaines cartes doivent rester côte à côte (Solgaleo–Lunala, Entei–Raikou). Elles
sont traitées comme des **blocs indivisibles** : un bloc ne se déplace que d'un seul
tenant, et uniquement vers une zone composée exclusivement de cartes libres. La
contrainte est donc satisfaite par construction, sans pénalité de score et sans
ralentir l'optimisation.

Un lien peut regrouper plus de deux cartes, et son **ordre est optionnel** : imposé,
la séquence est respectée à la lettre (utile quand le sens a une signification) ;
libre, l'optimiseur peut retourner le bloc et dispose de deux fois plus de placements.

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

### Recuit simulé

La descente stricte n'accepte jamais un échange qui dégrade le score, et plafonne
donc dans un minimum local. Le recuit en accepte parfois un, avec une probabilité qui
décroît au fil du calcul :

```bash
uv run pokemon-mosaic --annealing --iterations 1000000
```

| Itérations | Descente stricte | Recuit simulé |
|---|---|---|
| 50 000 | 56,3 % | **59,4 %** |
| 200 000 | 59,5 % | **64,8 %** |
| 1 000 000 | 61,0 % | **67,5 %** |

L'écart se creuse avec la durée : plus le recuit a de temps, plus il prend l'avantage.
La température se calibre toute seule à partir de l'ampleur réelle des dégradations —
le seul réglage exposé est `--acceptance`, la proportion de coups dégradants acceptés
au démarrage.

### Seuils d'arrêt et timeline

```bash
uv run pokemon-mosaic --annealing --stagnation 50000 --time-budget 30 --snapshot-every 10
```

`--target-score`, `--stagnation`, `--time-budget` arrêtent le calcul dès qu'une
condition est remplie. `--snapshot-every` enregistre l'état de la grille tous les N
**échanges retenus** — pas toutes les N tentatives, car le taux d'acceptation varie
de 0,3 % (descente stricte) à 8 % (recuit). La cadence s'adapte d'elle-même pour que
la timeline reste bornée et régulièrement répartie.

### Export poster

Avec `--paper`, la sortie devient un vrai poster : la taille des cartes se déduit du
format et du DPI, les cartes gardent leurs proportions exactes, et l'image est centrée
— la marge résiduelle absorbe l'écart de rapport entre la grille et la feuille.

```bash
uv run pokemon-mosaic --grid 17x17 --paper A2 --dpi 300 --full-resolution --format jpg
```

Découpage en plusieurs posters, avec chevauchement pour le collage et repères de
coupe. La coupe tombe toujours sur un bord de carte, donc le nombre de colonnes doit
être divisible par le nombre de panneaux :

```bash
uv run pokemon-mosaic --grid 24x12 --paper A3 --panels 2 --overlap 5 --crop-marks --format pdf
```

| Option | Défaut | Rôle |
|---|---|---|
| `--paper` | — | Format d'impression, `A0` à `A6` |
| `--landscape` | non | Feuille en paysage |
| `--dpi` | `300` | Résolution d'impression |
| `--panels` | `1` | Nombre de posters côte à côte |
| `--overlap` | `0` | Chevauchement entre panneaux, en mm |
| `--crop-marks` | non | Repères de coupe |
| `--format` | `png` | `png`, `jpg` ou `pdf` |

Le PDF porte les **dimensions physiques** de la page, ce qui lève toute ambiguïté
chez l'imprimeur. L'app prévient si le DPI demandé dépasse le maximum utile — au-delà,
les cartes sont agrandies sans gagner en détail (366 DPI en A0, 733 en A2).

Chaque panneau est rendu séparément : le poster complet n'est jamais en mémoire d'un
seul tenant, ce qui évite les 836 Mo d'un A0 en deux panneaux.

### Cases vides

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

Compter environ **4 s de chargement** des cartes, puis l'optimisation à ~127 000
itérations/s, soit 8 s pour un million. Les sorties vont dans `output/`, non versionné.

## Interface graphique

```bash
uv run pokemon-mosaic-ui
```

Assistant en trois étapes puis vue d'exécution. **Étapes 1 à 3 disponibles** ; la
vue d'exécution reste à construire.

### Étape 1 — cartes

Galerie des 280 vignettes, inclusion/exclusion par carte, par dossier ou en totalité.

Le chargement est **progressif** : les dossiers apparaissent les uns après les autres
au lieu d'attendre la fin. La première passe ne lit que les en-têtes des fichiers pour
déterminer la taille commune des vignettes — 80 ms — puis chaque extension est livrée
dès qu'elle est décodée, sur les ~3,5 s que dure le décodage complet.

Sélectionner un dossier **filtre la galerie** sur ses seules cartes ; les boutons
*Inclure* et *Exclure* agissent alors sur ce dossier. Le filtre survit à l'arrivée des
dossiers suivants.

### Étape 2 — grille et format

Format d'impression (A0 à A6, portrait ou paysage), résolution, nombre de posters
côte à côte, dimensions de grille. La taille des cartes en pixels **s'en déduit** :
le format commande.

L'**aperçu fil de fer** montre la géométrie sans les images — feuille, marges,
contours des cartes, lignes de coupe entre panneaux. Cliquer une case y place ou
retire un vide. Le nombre de vides étant fixé par la grille et la sélection, poser un
vide supplémentaire fait céder sa place au plus ancien.

Une liste propose les **grilles adaptées** au format choisi, avec l'écart de
proportions et le nombre de cartes à ajouter ou retirer. Les avertissements signalent
les cases vides, un DPI au-delà du maximum utile, ou une image trop lourde à exporter.

L'interface est **bilingue français / anglais**, avec un sélecteur en bas de fenêtre.
Les textes sont écrits en français dans le code et traduits par des fichiers Qt.
Après avoir ajouté ou modifié une chaîne :

```bash
uv run pyside6-lupdate src/pokemon_mosaic/ui/*.py -ts translations/pokemon_mosaic_en.ts
uv run pyside6-lrelease translations/pokemon_mosaic_en.ts
```

⚠️ `lupdate` n'extrait que les `tr()` portant une chaîne **littérale**. Un
`self.tr(variable)` passe inaperçu et reste non traduit — voir `MainWindow.step_title`
pour le contournement.

## Structure

```
src/pokemon_mosaic/
├── cards.py      chargement en vignettes, signatures de bord
├── links.py      liens entre cartes et bibliothèque de liens
├── layout.py     formats d'impression, ajustement, cases vides
├── grid.py       dimensionnement de la grille, rendu
├── scoring.py    matrices de distances, score global et local
├── annealing.py  recuit simulé et calibration de température
├── timeline.py   snapshots de l'exécution
├── export.py     poster, panneaux, marges, PNG / JPEG / PDF
├── optimize.py   boucle d'optimisation, contraintes, seuils d'arrêt
├── imaging.py    inspection et réduction des images produites
└── cli.py        point d'entrée

tests/            tests du cœur de calcul
experiments/      approches alternatives, conservées mais non maintenues
```

Tests et analyse statique :

```bash
uv run --extra dev pytest
uv run --extra dev ruff check src tests
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
