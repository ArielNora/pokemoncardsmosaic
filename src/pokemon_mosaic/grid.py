"""Dimensionnement de la grille et rendu de la mosaïque."""

import math
import os

import numpy as np
from PIL import Image

from .cards import CardSet, load_full_image
from .scoring import EMPTY

WHITE = (255, 255, 255)


def calculate_grid_dims(n: int) -> tuple[int, int]:
    """Renvoie (colonnes, lignes) : la paire de facteurs de `n` la plus proche du carré.

    Garantit zéro case vide et zéro carte perdue — mais la forme dépend entièrement
    de la factorisation de `n`, ce qui la rend très instable :

        279 cartes ->  31 x 9
        280 cartes ->  20 x 14
        281 cartes -> 281 x 1   (281 est premier)

    Conservé pour le pipeline en ligne de commande. L'application rendra la grille
    explicite et autorisera les cases vides, ce qui supprime le problème.
    """
    if n <= 0:
        return (0, 0)
    for i in range(math.isqrt(n), 0, -1):
        if n % i == 0:
            return (n // i, i)
    return (n, 1)


def render_grid(
    grid: np.ndarray,
    cards: CardSet,
    full_resolution: bool = False,
    empty_colour: tuple[int, int, int] = WHITE,
) -> Image.Image:
    """Assemble les cartes selon `grid` et renvoie l'image.

    Par défaut, l'assemblage se fait à partir des vignettes déjà en mémoire, ce qui
    prend quelques millisecondes — c'est ce qui permet le défilement fluide de la
    timeline. Avec `full_resolution`, chaque carte est relue depuis le disque à sa
    taille d'origine : bien plus lent, réservé à l'export.
    """
    rows, cols = grid.shape
    tile_w, tile_h = cards.full_size if full_resolution else cards.thumb_size

    canvas = Image.new("RGB", (cols * tile_w, rows * tile_h), empty_colour)

    for r in range(rows):
        for c in range(cols):
            idx = int(grid[r, c])
            if idx == EMPTY:
                continue
            card = cards[idx]
            tile = (
                Image.fromarray(load_full_image(card, (tile_w, tile_h)))
                if full_resolution
                else Image.fromarray(card.thumbnail)
            )
            canvas.paste(tile, (c * tile_w, r * tile_h))

    return canvas


def save_grid_image(
    grid: np.ndarray,
    cards: CardSet,
    path: str,
    full_resolution: bool = False,
    empty_colour: tuple[int, int, int] = WHITE,
) -> None:
    """Rend la grille et l'écrit sur le disque."""
    if not len(cards):
        return

    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)

    image = render_grid(grid, cards, full_resolution, empty_colour)
    image.save(path)
    print(f"Enregistré : {path} ({image.width}x{image.height} px)")
