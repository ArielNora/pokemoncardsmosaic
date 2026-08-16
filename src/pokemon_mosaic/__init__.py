"""Génération de mosaïques de cartes Pokémon par appariement des couleurs de bord."""

from .cards import Card, CardSet, load_cards, load_full_image
from .grid import calculate_grid_dims, render_grid, save_grid_image
from .optimize import build_initial_grid, generate_grid, optimize_grid
from .scoring import EMPTY, EdgeDistances, grid_score, local_score

__version__ = "0.1.0"

__all__ = [
    "EMPTY",
    "Card",
    "CardSet",
    "EdgeDistances",
    "build_initial_grid",
    "calculate_grid_dims",
    "generate_grid",
    "grid_score",
    "load_cards",
    "load_full_image",
    "local_score",
    "optimize_grid",
    "render_grid",
    "save_grid_image",
]
