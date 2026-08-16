"""Dimensionnement de la grille et rendu de la mosaïque finale."""

import math
import os
from typing import List, Sequence, Tuple

import cv2
import numpy as np

from .cards import ImagePart


def calculate_grid_dims(n: int) -> Tuple[int, int]:
    """Renvoie (colonnes, lignes) : la paire de facteurs de `n` la plus proche du carré.

    Garantit zéro case vide et zéro carte perdue — mais la forme dépend
    entièrement de la factorisation de `n`, ce qui la rend très instable :

        279 cartes ->  31 x 9
        280 cartes ->  20 x 14
        281 cartes -> 281 x 1   (281 est premier)

    C'est la raison d'être de la `remove_list` du pipeline : retirer une carte
    pour retomber sur un nombre bien factorisable. À revoir (voir TODO.md).
    """
    if n <= 0:
        return (0, 0)
    for i in range(int(math.isqrt(n)), 0, -1):
        if n % i == 0:
            return (n // i, i)
    return (n, 1)


def save_grid_image(grid: np.ndarray, parts: Sequence[ImagePart], path: str) -> None:
    """Assemble les tuiles selon `grid` et écrit l'image résultante."""
    if not parts:
        return

    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)

    rows, cols = grid.shape
    th, tw, _ = parts[0].full_image.shape
    canvas = np.zeros((rows * th, cols * tw, 3), dtype=np.uint8)

    for r in range(rows):
        for c in range(cols):
            idx = grid[r, c]
            if idx != -1:
                canvas[r * th : (r + 1) * th, c * tw : (c + 1) * tw] = parts[idx].full_image

    if not cv2.imwrite(path, canvas):
        raise IOError(f"Échec de l'écriture de {path}")
    print(f"Enregistré : {path} ({canvas.shape[1]}x{canvas.shape[0]} px)")
