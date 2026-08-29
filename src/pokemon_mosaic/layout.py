"""Mise en page : ajustement de la grille au format d'impression et cases vides.

C'est la logique de l'étape 2 de l'application, écrite sans dépendance à l'interface
pour être testable seule. Voir SPEC.md §4.
"""

import math
from dataclasses import dataclass

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

# Dimensions d'une carte Pokémon que l'on tient en main, en millimètres. Elle ne
# sert à rien au calcul : c'est un étalon, posé à côté de la feuille pour que
# « A2 » veuille dire quelque chose sans avoir à sortir un mètre.
REAL_CARD_MM = (63.0, 88.0)


def paper_size_mm(name: str, landscape: bool = False) -> tuple[float, float]:
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


# Écart maximal admis entre les deux côtés d'une grille proposée. Au-delà, la
# mosaïque devient une bande : le poster perd sa forme et l'image occupe une
# fraction dérisoire de la feuille.
MAX_SIDE_DIFFERENCE = 3


def suggest_grids(
    card_count: int,
    card_aspect: float,
    paper_aspect: float,
    panels: int = 1,
    max_difference: int = MAX_SIDE_DIFFERENCE,
    limit: int = 10,
) -> list[GridSuggestion]:
    """Propose des grilles pour ce nombre de cartes, classées par pertinence.

    `paper_aspect` est le rapport largeur/hauteur de la **feuille entière** ; avec
    `panels > 1`, la grille est répartie sur plusieurs feuilles côte à côte et le
    nombre de colonnes est contraint à être divisible par `panels`, pour que la coupe
    tombe toujours sur un bord de carte.

    Classement : d'abord les grilles dont le nombre de cases est proche du nombre de
    cartes, puis celles qui ajustent le mieux le format.

    ⚠️ **Le format n'est plus un filtre, seulement un départage.** Il l'était, à
    5 % près, et cela ne laissait passer que des grilles **carrées** : une carte
    fait 0,725 de rapport, une feuille A 0,707, si bien que la grille idéale a
    toujours autant de lignes que de colonnes à 2,5 % près. Vingt cartes n'ont
    alors aucune grille de vingt cases — 4×5 s'écarte de 18 % du format et
    tombait —, et l'on proposait 4×4 en abandonnant quatre cartes, ou 5×5 en
    laissant cinq trous. Même chose sur 133 cartes : 11×12 en loge 132, contre
    144 pour le meilleur carré.

    Ce qui borne la forme est désormais `max_difference`, l'écart entre les deux
    côtés : au-delà la mosaïque devient une bande et l'image n'occupe plus
    qu'un ruban de la feuille, en deçà elle reste un poster. L'écart au format
    reste calculé, affiché, et sert à trancher entre deux grilles d'égal intérêt.
    """
    if card_count <= 0 or card_aspect <= 0 or paper_aspect <= 0:
        return []

    # Assez de lignes pour dépasser la grille carrée, l'écart maximal en plus :
    # au-delà, toute grille est plus grande que le jeu de cartes et s'en éloigne.
    ceiling = math.isqrt(card_count) + max_difference + 1
    found: list[GridSuggestion] = []
    for rows in range(1, ceiling + 1):
        for cols in range(max(1, rows - max_difference), rows + max_difference + 1):
            if cols % panels:
                continue
            error = abs((cols * card_aspect / rows) - paper_aspect) / paper_aspect
            found.append(
                GridSuggestion(cols, rows, error, cols * rows - card_count)
            )

    found.sort(key=lambda s: (abs(s.card_delta), s.aspect_error))
    return found[:limit]


# Nombre d'or. Ses multiples fractionnaires ne retombent jamais sur un motif
# périodique, ce qui est exactement ce qu'on veut pour disperser des points.
GOLDEN_RATIO = 0.618033988749895


def distribute_empty_cells(
    shape: tuple[int, int], count: int
) -> list[tuple[int, int]]:
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


def _first_free_cell(taken, row: int, col: int, rows: int, cols: int) -> tuple[int, int]:
    """Trouve une case libre à partir de (row, col), en balayant vers la droite."""
    for offset in range(rows * cols):
        r = (row + offset // cols) % rows
        c = (col + offset) % cols
        if (r, c) not in taken:
            return (r, c)
    raise ValueError("Aucune case libre disponible.")


def card_pixel_size(
    paper: tuple[float, float],
    cols: int,
    rows: int,
    card_aspect: float,
    dpi: int = DEFAULT_DPI,
) -> tuple[int, int]:
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

    # `floor` et non `round` : arrondir vers le haut ferait dépasser la largeur
    # totale (cols × card_w) de celle de la feuille, la marge deviendrait négative
    # et le poster serait rogné — jusqu'à cols/2 pixels de chaque côté. On préfère
    # au plus un pixel de blanc supplémentaire.
    card_w = math.floor(card_w)
    return (max(1, card_w), max(1, math.floor(card_w / card_aspect)))


def max_useful_dpi(
    paper: tuple[float, float], cols: int, source_card_width_px: int
) -> float:
    """DPI au-delà duquel on interpole sans ajouter de détail.

    Les cartes sources ont une résolution finie : imprimer plus fin qu'elle revient à
    agrandir du vide. L'application avertit l'utilisateur quand il franchit ce seuil.
    """
    if cols <= 0 or source_card_width_px <= 0:
        return float("inf")
    card_width_mm = paper[0] / cols
    return source_card_width_px / (card_width_mm / MM_PER_INCH)
