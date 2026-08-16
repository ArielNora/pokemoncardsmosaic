"""Construction et optimisation de la grille, avec groupes de cartes indissociables."""

import random
from typing import Dict, List, Optional, Sequence

import numpy as np

from .cards import CardSet
from .grid import calculate_grid_dims
from .scoring import EMPTY, EdgeDistances, grid_score, local_score


def optimize_grid(
    grid: np.ndarray,
    distances: EdgeDistances,
    img_to_group: Optional[Dict[int, List[int]]] = None,
    iterations: int = 50000,
    rng: Optional[random.Random] = None,
) -> int:
    """Descente par échanges aléatoires (hill climbing strict).

    `grid` est modifiée sur place ; la fonction renvoie le **nombre d'échanges
    retenus**. C'est cette grandeur, et non le nombre de tentatives, qui cadencera
    les snapshots de la timeline (voir SPEC.md §5).

    À chaque tour : on tire une case au hasard, on identifie l'objet qui s'y trouve
    (une carte seule, ou le bloc entier auquel elle appartient), on tente de le
    déplacer vers une zone tirée au hasard, et on annule si le score local ne
    s'améliore pas. Aucun coup perdant n'est jamais accepté.

    Les groupes sont préservés par construction : un bloc ne se déplace que d'un seul
    tenant, et uniquement vers une zone composée exclusivement de cartes libres.

    Les cases vides (`EMPTY`) sont figées : elles ne sont jamais choisies comme source
    et jamais recouvertes.
    """
    img_to_group = img_to_group or {}
    rng = rng or random
    rows, cols = grid.shape
    changes = 0

    for _ in range(iterations):
        # 1. Objet source
        r1, c1 = rng.randrange(rows), rng.randrange(cols)
        idx1 = grid[r1, c1]
        if idx1 == EMPTY:
            continue

        if idx1 in img_to_group:
            group = img_to_group[idx1]
            # Le bloc est posé horizontalement et dans l'ordre : on remonte à sa tête
            # par simple décalage plutôt qu'en balayant la ligne.
            head_c = c1 - group.index(idx1)
            if head_c < 0 or head_c + len(group) > cols:
                continue
            source = [(r1, head_c + k) for k in range(len(group))]
            if any(grid[r, c] != group[k] for k, (r, c) in enumerate(source)):
                continue
        else:
            group = [int(idx1)]
            source = [(r1, c1)]

        # 2. Zone cible, de même largeur que l'objet source
        r2, c2 = rng.randrange(rows), rng.randrange(cols)
        if c2 + len(group) > cols:
            continue
        target = [(r2, c2 + k) for k in range(len(group))]
        if any(cell in source for cell in target):
            continue

        # La cible ne doit contenir que des cartes libres : on ne casse pas un autre
        # bloc, et on ne recouvre pas une case vide figée.
        occupants = []
        for r, c in target:
            value = grid[r, c]
            if value == EMPTY or value in img_to_group:
                break
            occupants.append(int(value))
        else:
            # Un seul appel couvrant les deux zones : la couture qui les sépare,
            # lorsqu'elles sont adjacentes, n'est ainsi comptée qu'une fois.
            cells = source + target
            before = local_score(cells, grid, distances)

            for k, (r, c) in enumerate(target):
                grid[r, c] = group[k]
            for k, (r, c) in enumerate(source):
                grid[r, c] = occupants[k]

            if local_score(cells, grid, distances) >= before:
                for k, (r, c) in enumerate(source):
                    grid[r, c] = group[k]
                for k, (r, c) in enumerate(target):
                    grid[r, c] = occupants[k]
            else:
                changes += 1

    return changes


def build_initial_grid(
    cards: CardSet,
    shape: Optional[tuple] = None,
    hard_groups: Sequence[Sequence[int]] = (),
    rng: Optional[random.Random] = None,
) -> np.ndarray:
    """Pose les blocs imposés, puis remplit le reste avec les cartes libres."""
    rng = rng or random
    grid_cols, grid_rows = shape or calculate_grid_dims(len(cards))
    grid = np.full((grid_rows, grid_cols), EMPTY, dtype=int)

    used = set()
    r, c = 0, 0
    for group in hard_groups:
        while r < grid_rows:
            if c + len(group) <= grid_cols:
                for k, idx in enumerate(group):
                    grid[r, c + k] = idx
                    used.add(idx)
                c += len(group)
                break
            r, c = r + 1, 0

    available = [card.index for card in cards if card.index not in used]
    rng.shuffle(available)
    for r in range(grid_rows):
        for c in range(grid_cols):
            if grid[r, c] == EMPTY and available:
                grid[r, c] = available.pop()

    return grid


def generate_grid(
    cards: CardSet,
    hard_groups: Sequence[Sequence[int]] = (),
    iterations: int = 500000,
    shape: Optional[tuple] = None,
    rng: Optional[random.Random] = None,
) -> np.ndarray:
    """Construit la grille, l'optimise, et rend compte de la progression."""
    if not len(cards):
        return np.array([])

    distances = EdgeDistances(cards.cards)
    print(f"Matrices de distances : {distances.nbytes / 1024 / 1024:.1f} Mo")

    grid = build_initial_grid(cards, shape, hard_groups, rng)
    print(f"--- Grille : {grid.shape[1]}x{grid.shape[0]} ---")
    print(f"Score initial : {grid_score(grid, distances):.2f}")

    changes = optimize_grid(grid, distances, _group_map(hard_groups), iterations, rng)

    print(f"Échanges retenus : {changes}")
    print(f"Score final   : {grid_score(grid, distances):.2f}")
    return grid


def _group_map(hard_groups: Sequence[Sequence[int]]) -> Dict[int, List[int]]:
    mapping: Dict[int, List[int]] = {}
    for group in hard_groups:
        for idx in group:
            mapping[idx] = list(group)
    return mapping
