"""Génération de mosaïques de cartes Pokémon par appariement des couleurs de bord."""

from .annealing import Annealing
from .cards import Card, CardSet, load_cards, load_full_image
from .control import RunControl
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
from .links import DEFAULT_LINKS, Link, LinkLibrary, resolve_links
from .optimize import (
    OptimizationResult,
    StopConditions,
    StopReason,
    build_initial_grid,
    check_links_fit,
    generate_grid,
    optimize_grid,
    select_cards,
)
from .scoring import EMPTY, EdgeDistances, grid_score, local_score
from .timeline import Snapshot, Timeline

__version__ = "0.1.0"

__all__ = [
    "DEFAULT_LINKS",
    "EMPTY",
    "Annealing",
    "Card",
    "CardSet",
    "EdgeDistances",
    "GridFit",
    "GridSuggestion",
    "Link",
    "LinkLibrary",
    "OptimizationResult",
    "RunControl",
    "Snapshot",
    "StopConditions",
    "StopReason",
    "Timeline",
    "build_initial_grid",
    "calculate_grid_dims",
    "card_pixel_size",
    "check_links_fit",
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
    "select_cards",
    "suggest_grids",
]
