"""Construction et optimisation de la grille, avec groupes de cartes indissociables."""

import random
from typing import Dict, List, Sequence

import numpy as np

from .cards import ImagePart
from .grid import calculate_grid_dims
from .scoring import calculate_grid_mismatch_score, get_local_score_for_cells


def optimize_groups(
    grid_indices: np.ndarray,
    image_parts: Sequence[ImagePart],
    img_to_group: Dict[int, List[int]],
    iterations: int = 50000,
) -> np.ndarray:
    """Descente par échanges aléatoires (hill climbing strict).

    À chaque tour : on tire une case au hasard, on identifie l'objet qui s'y
    trouve (une carte seule, ou le bloc entier auquel elle appartient), on tente
    de le déplacer vers une zone tirée au hasard, et on annule si le score local
    ne s'améliore pas. Aucun coup perdant n'est jamais accepté.

    Les groupes durs sont préservés par construction : un bloc ne se déplace que
    d'un seul tenant, et uniquement vers une zone composée exclusivement de
    cartes libres — ce qui évite d'avoir à gérer des blocs qui s'entrechoquent.
    """
    rows, cols = grid_indices.shape
    print(f"Optimisation ({iterations} itérations)...")
    changes = 0

    for i in range(iterations):
        # 1. Objet source
        r1, c1 = random.randint(0, rows - 1), random.randint(0, cols - 1)
        idx1 = grid_indices[r1, c1]
        if idx1 == -1:
            continue

        if idx1 in img_to_group:
            group_a = img_to_group[idx1]
            # Le bloc est posé horizontalement et dans l'ordre : on remonte à sa
            # tête par simple décalage plutôt qu'en balayant la ligne.
            head_c = c1 - group_a.index(idx1)
            if head_c < 0 or head_c + len(group_a) > cols:
                continue
            coords_a = [(r1, head_c + k) for k in range(len(group_a))]
            if any(grid_indices[rr, cc] != group_a[k] for k, (rr, cc) in enumerate(coords_a)):
                continue
        else:
            group_a = [idx1]
            coords_a = [(r1, c1)]

        # 2. Zone cible, de même largeur que l'objet source
        r2, c2 = random.randint(0, rows - 1), random.randint(0, cols - 1)
        if (r2, c2) in coords_a:
            continue
        if c2 + len(group_a) > cols:
            continue

        coords_b = [(r2, c2 + k) for k in range(len(group_a))]
        if any(cell in coords_a for cell in coords_b):
            continue

        # La cible ne doit contenir que des cartes libres : on ne casse pas un
        # autre bloc pour faire de la place.
        indices_b = []
        for rr, cc in coords_b:
            t_idx = grid_indices[rr, cc]
            if t_idx == -1 or t_idx in img_to_group:
                break
            indices_b.append(t_idx)
        else:
            score_before = get_local_score_for_cells(coords_a, grid_indices, image_parts) + \
                           get_local_score_for_cells(coords_b, grid_indices, image_parts)

            for k, (rr, cc) in enumerate(coords_b):
                grid_indices[rr, cc] = group_a[k]
            for k, (rr, cc) in enumerate(coords_a):
                grid_indices[rr, cc] = indices_b[k]

            score_after = get_local_score_for_cells(coords_a, grid_indices, image_parts) + \
                          get_local_score_for_cells(coords_b, grid_indices, image_parts)

            if score_after >= score_before:
                for k, (rr, cc) in enumerate(coords_a):
                    grid_indices[rr, cc] = group_a[k]
                for k, (rr, cc) in enumerate(coords_b):
                    grid_indices[rr, cc] = indices_b[k]
            else:
                changes += 1

        if i % 10000 == 0 and i > 0:
            print(f"  Itération {i} : {changes} échanges retenus...")

    print(f"Optimisation terminée. {changes} échanges.")
    return grid_indices


def generate_hard_constrained_grid(
    image_parts: Sequence[ImagePart],
    hard_groups: Sequence[Sequence[int]] = (),
    iterations: int = 500000,
) -> np.ndarray:
    """Construit la grille : pose les blocs, remplit le reste, puis optimise.

    `hard_groups` liste des groupes de cartes à garder côte à côte
    horizontalement, dans l'ordre donné (ex. [[solgaleo, lunala]]).
    """
    if not image_parts:
        return np.array([])

    print(f"Grille pour {len(image_parts)} cartes et {len(hard_groups)} groupe(s) imposé(s).")
    grid_cols, grid_rows = calculate_grid_dims(len(image_parts))
    print(f"--- Grille : {grid_cols}x{grid_rows} ---")

    img_to_group: Dict[int, List[int]] = {}
    for grp in hard_groups:
        for idx in grp:
            img_to_group[idx] = list(grp)

    used_indices = set()
    grid_indices = np.full((grid_rows, grid_cols), -1, dtype=int)

    # 1. Les blocs d'abord, posés à la suite en partant du coin haut-gauche
    print("Placement des groupes imposés...")
    current_r, current_c = 0, 0
    for grp in hard_groups:
        while current_r < grid_rows:
            if current_c + len(grp) <= grid_cols:
                for k, img_idx in enumerate(grp):
                    grid_indices[current_r, current_c + k] = img_idx
                    used_indices.add(img_idx)
                current_c += len(grp)
                break
            current_r += 1
            current_c = 0

    # 2. Les cartes libres remplissent le reste, dans un ordre aléatoire
    print("Remplissage des cartes libres...")
    available = [p.original_index for p in image_parts if p.original_index not in used_indices]
    random.shuffle(available)
    for r in range(grid_rows):
        for c in range(grid_cols):
            if grid_indices[r, c] == -1 and available:
                grid_indices[r, c] = available.pop()

    print(f"Score initial : {calculate_grid_mismatch_score(grid_indices, image_parts):.2f}")
    grid_indices = optimize_groups(grid_indices, image_parts, img_to_group, iterations=iterations)
    print(f"Score final   : {calculate_grid_mismatch_score(grid_indices, image_parts):.2f}")

    return grid_indices
