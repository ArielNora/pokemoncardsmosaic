"""Génération de mosaïques de cartes Pokémon par appariement des couleurs de bord."""

from .cards import Card, CardSet, load_cards, load_full_image
from .grid import calculate_grid_dims, render_grid, save_grid_image
from .layout import (
    GridFit,
    GridSuggestion,
    card_pixel_size,
    distribute_empty_cells,
    max_useful_dpi,
    paper_size_mm,
    suggest_grids,
)
from .links import Link, LinkLibrary, resolve_links
from .optimize import (
    OptimizationResult,
    build_initial_grid,
    generate_grid,
    optimize_grid,
)
from .scoring import EMPTY, EdgeDistances, grid_score, local_score

__version__ = "0.1.0"

__all__ = [
    "EMPTY",
    "Card",
    "CardSet",
    "EdgeDistances",
    "GridFit",
    "GridSuggestion",
    "Link",
    "LinkLibrary",
    "OptimizationResult",
    "build_initial_grid",
    "calculate_grid_dims",
    "card_pixel_size",
    "distribute_empty_cells",
    "generate_grid",
    "grid_score",
    "load_cards",
    "load_full_image",
    "local_score",
    "max_useful_dpi",
    "optimize_grid",
    "paper_size_mm",
    "render_grid",
    "resolve_links",
    "save_grid_image",
    "suggest_grids",
]
