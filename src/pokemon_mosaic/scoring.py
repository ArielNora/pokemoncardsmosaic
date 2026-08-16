"""Mesure de la qualité d'une grille : plus le score est bas, plus les coutures sont douces.

Toutes les distances entre bords sont **précalculées une fois** dans deux matrices
N×N. Évaluer une couture devient une simple lecture de tableau : mesuré à 10 084 000
coutures/s contre 473 000 via `scipy.cdist`, soit un gain ×21 pour 1,2 Mo de mémoire
et 4 ms de précalcul. Voir SPEC.md §8.
"""

from typing import Iterable, Sequence, Tuple

import numpy as np

from .cards import Card

EMPTY = -1


def _pairwise_distances(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Distances euclidiennes entre toutes les lignes de `a` et toutes celles de `b`.

    Équivalent bit à bit à `scipy.spatial.distance.cdist(a, b, "euclidean")`, vérifié
    sur les données du projet. Évite d'embarquer scipy (75 Mo) pour cette seule
    fonction.
    """
    return np.sqrt(((a[:, None, :] - b[None, :, :]) ** 2).sum(axis=-1))


class EdgeDistances:
    """Table des distances entre bords de cartes, calculée une fois pour toutes.

    - `lr[i, j]` : bord droit de la carte `i` contre bord gauche de la carte `j`
    - `tb[i, j]` : bord bas de la carte `i` contre bord haut de la carte `j`
    """

    __slots__ = ("lr", "tb", "count")

    def __init__(self, cards: Sequence[Card]):
        right = np.array([c.right for c in cards], dtype=np.float64)
        left = np.array([c.left for c in cards], dtype=np.float64)
        bottom = np.array([c.bottom for c in cards], dtype=np.float64)
        top = np.array([c.top for c in cards], dtype=np.float64)

        self.lr = _pairwise_distances(right, left)
        self.tb = _pairwise_distances(bottom, top)
        self.count = len(cards)

    @property
    def nbytes(self) -> int:
        return self.lr.nbytes + self.tb.nbytes


def grid_score(grid: np.ndarray, distances: EdgeDistances) -> float:
    """Score global de la grille, calculé d'un bloc.

    Vectorisé : toutes les coutures horizontales sont lues en une indexation, puis
    toutes les verticales. Les cases vides (`EMPTY`) ne produisent aucune couture.
    """
    total = 0.0

    left, right = grid[:, :-1], grid[:, 1:]
    keep = (left != EMPTY) & (right != EMPTY)
    if keep.any():
        total += distances.lr[left[keep], right[keep]].sum()

    top, bottom = grid[:-1, :], grid[1:, :]
    keep = (top != EMPTY) & (bottom != EMPTY)
    if keep.any():
        total += distances.tb[top[keep], bottom[keep]].sum()

    return float(total)


def local_score(
    cells: Iterable[Tuple[int, int]],
    grid: np.ndarray,
    distances: EdgeDistances,
) -> float:
    """Score des seules coutures touchant `cells`.

    C'est ce qui rend l'optimisation praticable : évaluer un échange coûte quelques
    lectures de tableau au lieu d'un parcours complet de la grille.

    Les coutures internes à `cells` ne sont comptées qu'une fois. Passer toutes les
    cases concernées par un échange en **un seul appel** est donc important : la
    couture séparant deux zones adjacentes serait sinon comptée une fois par appel,
    et pondérée deux fois dans le delta.
    """
    rows, cols = grid.shape

    # On collecte d'abord les arêtes concernées, ce qui les dédoublonne, avant de
    # les sommer. Une arête est désignée par sa case amont : (r, c) horizontale
    # relie (r, c) à (r, c+1) ; verticale relie (r, c) à (r+1, c).
    horizontal, vertical = set(), set()
    for r, c in cells:
        if c + 1 < cols:
            horizontal.add((r, c))
        if c > 0:
            horizontal.add((r, c - 1))
        if r + 1 < rows:
            vertical.add((r, c))
        if r > 0:
            vertical.add((r - 1, c))

    score = 0.0
    for r, c in horizontal:
        a, b = grid[r, c], grid[r, c + 1]
        if a != EMPTY and b != EMPTY:
            score += distances.lr[a, b]
    for r, c in vertical:
        a, b = grid[r, c], grid[r + 1, c]
        if a != EMPTY and b != EMPTY:
            score += distances.tb[a, b]

    return float(score)
