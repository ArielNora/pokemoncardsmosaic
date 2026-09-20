"""Mesure de la qualité d'une grille : plus le score est bas, plus les coutures sont douces.

Toutes les distances entre bords sont **précalculées une fois** dans deux matrices
N×N. Évaluer une couture devient une simple lecture de tableau : mesuré à 10 084 000
coutures/s contre 473 000 via `scipy.cdist`, soit un gain ×21 pour 1,2 Mo de mémoire
et 4 ms de précalcul. Voir SPEC.md §8.
"""

from collections.abc import Iterable, Sequence

import numpy as np

from .cards import Card

EMPTY = -1


def _pairwise_distances(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Distances entre toutes les signatures de `a` et toutes celles de `b`.

    Une signature est `(3,)`, la moyenne d'une bande, ou `(parties, 3)` avec la
    métrique améliorée. Dans ce second cas chaque partie est comparée **à celle
    qui lui correspond** sur l'autre carte, et la distance du bord est la
    moyenne des distances de ses parties : une seule partie qui jure suffit
    alors à écarter deux bords que leurs moyennes d'ensemble rapprochaient.

    ⚠️ **La moyenne, et non la somme.** Les deux donnent exactement la même
    optimisation, à un facteur constant près, mais la moyenne garde les scores
    à l'échelle de la métrique d'origine : un score de 2 000 reste un score de
    2 000 quand on coche la case, et non 20 000.

    Sur une seule partie, équivalent bit à bit à
    `scipy.spatial.distance.cdist(a, b, "euclidean")`, vérifié sur les données
    du projet. Évite d'embarquer scipy (75 Mo) pour cette seule fonction.
    """
    if a.ndim == 2:                       # (N, 3) : une partie, la métrique d'origine
        return np.sqrt(((a[:, None, :] - b[None, :, :]) ** 2).sum(axis=-1))
    # ⚠️ **Partie par partie, et non d'un bloc.** Le tableau des écarts de
    # toutes les parties pèserait 47 Mo pour 441 cartes ; en dix passes il en
    # pèse 4,7, et le total qu'on accumule, 1,6.
    total = np.zeros((a.shape[0], b.shape[0]), dtype=np.float64)
    for partie in range(a.shape[1]):
        ecart = a[:, None, partie, :] - b[None, :, partie, :]
        total += np.sqrt((ecart ** 2).sum(axis=-1))
    return total / a.shape[1]


def _signatures(cards: Sequence[Card], name: str) -> np.ndarray:
    """Les signatures d'un même bord, empilées, telles que les cartes les portent.

    ⚠️ **Toutes les cartes doivent porter le même découpage.** Mélanger des
    signatures d'une partie et de dix donnerait un tableau d'objets, et des
    distances qui ne veulent rien dire : on le refuse ici, avec le nom du bord.
    """
    signatures = [getattr(card, name) for card in cards]
    formes = {np.shape(signature) for signature in signatures}
    if len(formes) > 1:
        raise ValueError(
            f"Signatures de bord « {name} » de formes différentes : "
            f"{sorted(formes)}. Recalculez tout le jeu avec le même découpage."
        )
    return np.array(signatures, dtype=np.float64)


class EdgeDistances:
    """Table des distances entre bords de cartes, calculée une fois pour toutes.

    - `lr[i, j]` : bord droit de la carte `i` contre bord gauche de la carte `j`
    - `tb[i, j]` : bord bas de la carte `i` contre bord haut de la carte `j`

    Le découpage des bords, d'une partie ou de dix, est celui que les cartes
    portent : la table se construit après le calcul des signatures, et change
    donc avec lui.
    """

    __slots__ = ("count", "lr", "tb")

    def __init__(self, cards: Sequence[Card]):
        # Les matrices sont indexées par position, alors que la grille contient des
        # `card.index`. Les deux doivent coïncider, sinon les distances seraient
        # lues à la mauvaise ligne : en silence. C'est le seul point de passage où
        # cette confusion peut se produire : on la refuse ici.
        for position, card in enumerate(cards):
            if card.index != position:
                raise ValueError(
                    f"Numérotation discontinue : la carte en position {position} "
                    f"porte l'indice {card.index}. Construisez la sélection avec "
                    f"CardSet.subset(), qui renumérote."
                )

        right = _signatures(cards, "right")
        left = _signatures(cards, "left")
        bottom = _signatures(cards, "bottom")
        top = _signatures(cards, "top")

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
    cells: Iterable[tuple[int, int]],
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
