"""Mise en page : ajustement de la grille au format d'impression et cases vides.

C'est la logique de l'étape 2 de l'application, écrite sans dépendance à l'interface
pour être testable seule. Voir SPEC.md §4.
"""

import math
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

# Formats ISO 216, en millimètres, portrait.
PAPER_FORMATS_MM = {
    "A6": (105, 148),
    "A5": (148, 210),
    "A4": (210, 297),
    "A3": (297, 420),
    "A2": (420, 594),
    "A1": (594, 841),
    "A0": (841, 1189),
}

DEFAULT_DPI = 300
MM_PER_INCH = 25.4


def paper_size_mm(name: str, landscape: bool = False) -> Tuple[float, float]:
    """Dimensions d'un format, en millimètres."""
    try:
        width, height = PAPER_FORMATS_MM[name.upper()]
    except KeyError:
        raise ValueError(
            f"Format inconnu : {name}. Connus : {', '.join(PAPER_FORMATS_MM)}"
        ) from None
    return (height, width) if landscape else (width, height)


def mm_to_pixels(mm: float, dpi: int = DEFAULT_DPI) -> int:
    return round(mm / MM_PER_INCH * dpi)


@dataclass(frozen=True)
class GridFit:
    """Comment un nombre de cartes se loge dans une grille donnée.

    `empty_cells` est le nombre de cases à laisser vides ; `surplus` le nombre de
    cartes en trop si elles ne tiennent pas toutes.
    """

    cols: int
    rows: int
    card_count: int

    @property
    def cells(self) -> int:
        return self.cols * self.rows

    @property
    def empty_cells(self) -> int:
        return max(0, self.cells - self.card_count)

    @property
    def surplus(self) -> int:
        return max(0, self.card_count - self.cells)

    @property
    def fits_exactly(self) -> bool:
        return self.card_count == self.cells

    def message(self) -> str:
        """Avertissement chiffré, tel qu'affiché à l'utilisateur."""
        if self.fits_exactly:
            return f"Les {self.card_count} cartes remplissent exactement la grille {self.cols}×{self.rows}."
        if self.surplus:
            return (
                f"{self.card_count} cartes pour {self.cells} cases "
                f"({self.cols}×{self.rows}) : retirez {self.surplus} carte"
                f"{'s' if self.surplus > 1 else ''}, ou agrandissez la grille."
            )
        return (
            f"{self.card_count} cartes pour {self.cells} cases "
            f"({self.cols}×{self.rows}) : il restera {self.empty_cells} case"
            f"{'s' if self.empty_cells > 1 else ''} vide"
            f"{'s' if self.empty_cells > 1 else ''}. "
            f"Ajoutez {self.empty_cells} carte{'s' if self.empty_cells > 1 else ''} "
            f"pour remplir la grille."
        )


@dataclass(frozen=True)
class GridSuggestion:
    """Une grille candidate pour un format donné."""

    cols: int
    rows: int
    aspect_error: float
    card_delta: int

    @property
    def cells(self) -> int:
        return self.cols * self.rows


def suggest_grids(
    card_count: int,
    card_aspect: float,
    paper_aspect: float,
    panels: int = 1,
    tolerance: float = 0.05,
    limit: int = 8,
) -> List[GridSuggestion]:
    """Propose des grilles proches du format visé, classées par pertinence.

    `paper_aspect` est le rapport largeur/hauteur de la **feuille entière** ; avec
    `panels > 1`, la grille est répartie sur plusieurs feuilles côte à côte et le
    nombre de colonnes est contraint à être divisible par `panels`, pour que la coupe
    tombe toujours sur un bord de carte.

    Classement : d'abord les grilles dont le nombre de cases est proche du nombre de
    cartes, puis celles qui ajustent le mieux le format.
    """
    if card_count <= 0 or card_aspect <= 0 or paper_aspect <= 0:
        return []

    found: List[GridSuggestion] = []
    for rows in range(1, card_count * 2):
        # cols tel que (cols * card_aspect) / rows ~= paper_aspect
        ideal = paper_aspect * rows / card_aspect
        for cols in {math.floor(ideal), math.ceil(ideal)}:
            if cols < panels or cols % panels:
                continue
            error = abs((cols * card_aspect / rows) - paper_aspect) / paper_aspect
            if error > tolerance:
                continue
            found.append(
                GridSuggestion(cols, rows, error, cols * rows - card_count)
            )

    found.sort(key=lambda s: (abs(s.card_delta), s.aspect_error))
    seen, unique = set(), []
    for suggestion in found:
        key = (suggestion.cols, suggestion.rows)
        if key not in seen:
            seen.add(key)
            unique.append(suggestion)
    return unique[:limit]


# Nombre d'or. Ses multiples fractionnaires ne retombent jamais sur un motif
# périodique, ce qui est exactement ce qu'on veut pour disperser des points.
GOLDEN_RATIO = 0.618033988749895


def distribute_empty_cells(
    shape: Tuple[int, int], count: int
) -> List[Tuple[int, int]]:
    """Répartit `count` cases vides sur une grille (rows, cols).

    C'est le placement par défaut : l'utilisateur peut ensuite déplacer chaque case
    à la main, mais n'y est jamais obligé.

    Disperser un indice à plat ne suffit pas : la colonne se déduit alors du reste
    modulo le nombre de colonnes, et ce repliement réintroduit des alignements. Un
    pas constant est le pire cas (288 cases et 8 trous donnent un pas de 36 = 24 + 12,
    donc deux colonnes seulement), mais le nombre d'or aliase aussi sur une grille
    17×17, où 289 = 17².

    On choisit donc **ligne et colonne séparément** : les lignes régulièrement
    espacées, les colonnes par une suite au nombre d'or, dont les multiples
    fractionnaires ne forment jamais de motif périodique.
    """
    rows, cols = shape
    total = rows * cols
    if count <= 0:
        return []
    if count > total:
        raise ValueError(f"{count} cases vides demandées pour seulement {total} cases.")

    taken = set()
    for k in range(count):
        row = min(rows - 1, k * rows // count)
        col = int(((k * GOLDEN_RATIO) % 1.0) * cols)
        taken.add(_first_free_cell(taken, row, col, rows, cols))

    return sorted(taken)


def _first_free_cell(taken, row: int, col: int, rows: int, cols: int) -> Tuple[int, int]:
    """Trouve une case libre à partir de (row, col), en balayant vers la droite."""
    for offset in range(rows * cols):
        r = (row + offset // cols) % rows
        c = (col + offset) % cols
        if (r, c) not in taken:
            return (r, c)
    raise ValueError("Aucune case libre disponible.")


def card_pixel_size(
    paper: Tuple[float, float],
    cols: int,
    rows: int,
    card_aspect: float,
    dpi: int = DEFAULT_DPI,
) -> Tuple[int, int]:
    """Taille d'une carte en pixels pour remplir la feuille, proportions conservées.

    Le format d'impression commande : on remplit la dimension la plus contraignante et
    on laisse une marge sur l'autre, sans jamais déformer ni rogner. Voir SPEC.md §4.
    """
    paper_w_px = mm_to_pixels(paper[0], dpi)
    paper_h_px = mm_to_pixels(paper[1], dpi)

    # Deux candidats : remplir la largeur, ou remplir la hauteur.
    by_width = paper_w_px / cols
    by_height = paper_h_px / rows * card_aspect
    card_w = min(by_width, by_height)
    return (max(1, round(card_w)), max(1, round(card_w / card_aspect)))


def max_useful_dpi(
    paper: Tuple[float, float], cols: int, source_card_width_px: int
) -> float:
    """DPI au-delà duquel on interpole sans ajouter de détail.

    Les cartes sources ont une résolution finie : imprimer plus fin qu'elle revient à
    agrandir du vide. L'application avertit l'utilisateur quand il franchit ce seuil.
    """
    if cols <= 0 or source_card_width_px <= 0:
        return float("inf")
    card_width_mm = paper[0] / cols
    return source_card_width_px / (card_width_mm / MM_PER_INCH)
