"""Génération de mosaïques de cartes Pokémon par appariement des couleurs de bord."""

from .cards import ImagePart, find_index, load_and_process_images
from .grid import calculate_grid_dims, save_grid_image
from .optimize import generate_hard_constrained_grid, optimize_groups
from .scoring import calculate_grid_mismatch_score, get_local_score_for_cells

__version__ = "0.1.0"

__all__ = [
    "ImagePart",
    "calculate_grid_dims",
    "calculate_grid_mismatch_score",
    "find_index",
    "generate_hard_constrained_grid",
    "get_local_score_for_cells",
    "load_and_process_images",
    "optimize_groups",
    "save_grid_image",
]
