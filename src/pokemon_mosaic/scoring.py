"""Mesure de la qualité d'une grille : plus le score est bas, plus les coutures sont douces."""

from typing import List, Sequence, Tuple

import numpy as np
from scipy.spatial.distance import cdist

from .cards import ImagePart


def _edge_distance(a: np.ndarray, b: np.ndarray) -> float:
    """Distance euclidienne entre deux signatures de bord (BGR)."""
    return cdist([a], [b], "euclidean")[0][0]


def calculate_grid_mismatch_score(
    grid_indices: np.ndarray, image_parts: Sequence[ImagePart]
) -> float:
    """Score global : somme des écarts de couleur sur toutes les coutures de la grille."""
    total = 0.0
    rows, cols = grid_indices.shape

    # Coutures horizontales : bord droit de la case gauche vs bord gauche de la case droite
    for r in range(rows):
        for c in range(cols - 1):
            idx_l, idx_r = grid_indices[r, c], grid_indices[r, c + 1]
            if idx_l == -1 or idx_r == -1:
                continue
            total += _edge_distance(image_parts[idx_l].right, image_parts[idx_r].left)

    # Coutures verticales
    for c in range(cols):
        for r in range(rows - 1):
            idx_t, idx_b = grid_indices[r, c], grid_indices[r + 1, c]
            if idx_t == -1 or idx_b == -1:
                continue
            total += _edge_distance(image_parts[idx_t].bottom, image_parts[idx_b].top)

    return total


def get_local_score_for_cells(
    cells: Sequence[Tuple[int, int]],
    grid_indices: np.ndarray,
    image_parts: Sequence[ImagePart],
) -> float:
    """Score des seules coutures touchant `cells`.

    C'est ce qui rend l'optimisation praticable : évaluer un échange coûte
    quelques distances au lieu d'un parcours complet de la grille.

    Note : si deux zones adjacentes sont évaluées par deux appels distincts, la
    couture qui les sépare est comptée une fois par appel, donc pondérée ×2 dans
    le delta. Biais connu, non corrigé.
    """
    rows, cols = grid_indices.shape
    score = 0.0
    processed_edges = set()

    for r, c in cells:
        idx = grid_indices[r, c]
        if idx == -1:
            continue
        curr = image_parts[idx]

        # Un voisin dans `cells` donne une couture interne, sinon une couture
        # externe : les deux comptent. `processed_edges` évite de compter deux
        # fois une couture interne, vue depuis chacune de ses deux cases.
        neighbours = (
            (r, c + 1, c < cols - 1, "right"),
            (r, c - 1, c > 0, "left"),
            (r + 1, c, r < rows - 1, "bottom"),
            (r - 1, c, r > 0, "top"),
        )

        for nr, nc, in_bounds, side in neighbours:
            if not in_bounds:
                continue
            n_idx = grid_indices[nr, nc]
            if n_idx == -1:
                continue
            edge_sig = tuple(sorted(((r, c), (nr, nc))))
            if edge_sig in processed_edges:
                continue
            neighbour = image_parts[n_idx]
            if side == "right":
                score += _edge_distance(curr.right, neighbour.left)
            elif side == "left":
                score += _edge_distance(neighbour.right, curr.left)
            elif side == "bottom":
                score += _edge_distance(curr.bottom, neighbour.top)
            else:
                score += _edge_distance(neighbour.bottom, curr.top)
            processed_edges.add(edge_sig)

    return score
