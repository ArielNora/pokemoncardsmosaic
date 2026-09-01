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


# Tolérance de reconnaissance d'un format, en millimètres. L'écran saisit en
# centimètres au dixième, donc au millimètre : tout ce qui dépasse le bruit du
# flottant est une dimension réellement différente.
FORMAT_TOLERANCE_MM = 0.05


def format_name(size_mm: tuple[float, float]) -> str:
    """Le nom du format qui fait ces dimensions, ou `""` si aucun ne les fait.

    Les sept formats se distinguent d'au moins quatre millimètres : reconnaître
    à un dixième près ne peut pas confondre deux d'entre eux, et laisse passer
    l'arrondi d'une saisie en centimètres.
    """
    width, height = size_mm
    for name, (w, h) in PAPER_FORMATS_MM.items():
        if (abs(width - w) <= FORMAT_TOLERANCE_MM
                and abs(height - h) <= FORMAT_TOLERANCE_MM):
            return name
    return ""


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


# Plus grand côté qu'une grille puisse avoir. C'est la borne des champs de
# l'interface, et donc celle de tout ce qu'on propose.
MAX_GRID_SIDE = 200

# Écart maximal admis entre les deux côtés d'une grille proposée. Au-delà, la
# mosaïque devient une bande : le poster perd sa forme et l'image occupe une
# fraction dérisoire de la feuille.
MAX_SIDE_DIFFERENCE = 3


def suggest_grids(
    card_count: int,
    card_aspect: float,
    paper_aspect: float,
    max_difference: int = MAX_SIDE_DIFFERENCE,
    limit: int = 10,
) -> list[GridSuggestion]:
    """Propose des grilles pour ce nombre de cartes, classées par pertinence.

    `paper_aspect` est le rapport largeur/hauteur de la **surface entière**, feuilles
    côte à côte comprises.

    ⚠️ `panels` ne contraint plus le nombre de colonnes. Il l'obligeait à être
    divisible, pour que la coupe tombe sur un bord de carte ; plusieurs feuilles
    ne sont désormais qu'une façon d'avoir plus de place, et la coupe tombe où
    elle tombe — c'est du papier qu'on raboute.

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


@dataclass(frozen=True)
class GridGeometry:
    """Tout ce qu'il faut pour poser une grille sur des feuilles, en pixels.

    `per_panel` est le nombre de cartes que porte **une** feuille en largeur,
    `rows_per_panel` en hauteur : ce sont eux qui garantissent qu'une coupe tombe
    entre deux cartes, chaque feuille repartant de son propre bord — celui de
    gauche pour les colonnes, celui du haut pour les lignes.
    """

    per_panel: int
    card_w: int
    card_h: int
    gap: int
    rows_per_panel: int = 1

    @property
    def pitch(self) -> tuple[int, int]:
        """De combien on avance d'une carte à la suivante, écart compris."""
        return self.card_w + self.gap, self.card_h + self.gap

    def span(self, count: int) -> int:
        """Largeur occupée par `count` cartes en ligne, écarts intérieurs compris."""
        return count * self.card_w + max(0, count - 1) * self.gap


def cards_across(paper_w_px: int, card_w: int, gap: int) -> int:
    """Combien de cartes tiennent en largeur sur une feuille, écarts compris."""
    if card_w <= 0:
        return 0
    return max(0, (paper_w_px + gap) // (card_w + gap))


def cards_down(paper_h_px: int, card_h: int, gap: int) -> int:
    """Combien de cartes tiennent en hauteur sur une feuille, écarts compris.

    La même arithmétique que `cards_across` sur l'autre axe. Nommée à part parce
    que les points d'appel se lisent mal autrement : une feuille se remplit dans
    les deux sens dès qu'il y a plusieurs **lignes** de feuilles.
    """
    return cards_across(paper_h_px, card_h, gap)


def grid_geometry(
    paper: tuple[float, float],
    panels: int,
    cols: int,
    rows: int,
    card_aspect: float,
    dpi: int = DEFAULT_DPI,
    card_width_mm: float | None = None,
    gap_mm: float = 0.0,
    panel_rows: int = 1,
) -> GridGeometry:
    """La géométrie d'une grille sur `panels` × `panel_rows` feuilles.

    `card_width_mm` à `None` demande la **plus grande** carte qui fasse tenir la
    grille : c'est le réglage automatique, tant que l'utilisateur n'a pas choisi
    de taille. Une valeur la fige, et c'est alors à la grille de s'y adapter —
    l'écran le dit et propose de la corriger.

    ⚠️ **C'est la carte qui se plie à la feuille, pas l'inverse.** Exiger que le
    nombre de colonnes se divise par le nombre de feuilles interdisait des
    grilles parfaitement bonnes — 21 colonnes sur 2 feuilles — pour une raison
    qui n'était pas la leur. On pose plutôt un nombre **entier** de cartes par
    feuille : la coupe tombe alors sur un bord de carte par construction.
    """
    paper_w_px = mm_to_pixels(paper[0], dpi)
    paper_h_px = mm_to_pixels(paper[1], dpi)
    if panels < 1 or cols < 1 or rows < 1 or card_aspect <= 0:
        raise ValueError("Mise en page vide : ni colonne, ni ligne, ni feuille.")
    gap = max(0, mm_to_pixels(max(0.0, gap_mm), dpi))

    panel_rows = max(1, panel_rows)

    if card_width_mm is not None:
        card_w = max(1, mm_to_pixels(card_width_mm, dpi))
        card_h = max(1, math.floor(card_w / card_aspect))
        # ⚠️ **Zéro quand rien ne tient**, et surtout pas un plancher à un : une
        # carte plus large que la feuille en logeait « une », et `grid_fits`
        # répondait que la grille tenait pour une grille d'une colonne. Ce sont
        # les points d'appel qui se gardent d'une division par zéro.
        return GridGeometry(cards_across(paper_w_px, card_w, gap),
                            card_w, card_h, gap,
                            cards_down(paper_h_px, card_h, gap))

    # Automatique : le plus **petit** nombre de cartes par feuille qui convienne,
    # donc la carte la plus grande. Il lui faut de quoi loger toutes les colonnes
    # sur les feuilles disponibles, et une hauteur qui tienne sur la feuille.
    per_panel = max(1, math.ceil(cols / panels))
    while per_panel <= paper_w_px:
        card_w = max(1, (paper_w_px - (per_panel - 1) * gap) // per_panel)
        card_h = math.floor(card_w / card_aspect)
        # ⚠️ **La hauteur se répartit sur les lignes de feuilles**, comme la
        # largeur sur les colonnes : ce n'est plus « tout tient sur une
        # feuille », mais « ce qui tient sur une feuille, multiplié par le
        # nombre de lignes, suffit ».
        par_feuille = cards_down(paper_h_px, card_h, gap) if card_h >= 1 else 0
        if card_h >= 1 and par_feuille * panel_rows >= rows:
            return GridGeometry(per_panel, card_w, max(1, card_h), gap,
                                par_feuille)
        # Trop haute pour la feuille : une carte de plus par feuille, donc des
        # cartes plus petites.
        per_panel += 1
    # Grille absurdement dense : on rend la plus petite carte possible plutôt
    # que de lever, l'écran ayant déjà de quoi la dire trop fine.
    return GridGeometry(cards_across(paper_w_px, 1, gap), 1, 1, gap,
                        cards_down(paper_h_px, 1, gap))


def grid_fits(
    panels: int,
    cols: int,
    rows: int,
    geometry: GridGeometry,
    panel_rows: int = 1,
) -> bool:
    """La grille tient-elle sur les feuilles, à cette géométrie ?

    Dans les deux sens : les colonnes se répartissent sur les feuilles côte à
    côte, les lignes sur les feuilles superposées. Ni le papier ni la finesse
    n'y entrent — la géométrie porte déjà ce qu'une feuille loge.
    """
    return (geometry.per_panel * panels >= cols
            and geometry.rows_per_panel * max(1, panel_rows) >= rows)


def best_grid_shapes(
    panels: int,
    card_count: int,
    current_cells: int,
    geometry: GridGeometry,
    limit: int = 6,
    panel_rows: int = 1,
) -> list[tuple[int, int]]:
    """Les grilles qui tiennent, classées par intérêt, à géométrie figée.

    Classement, dans cet ordre : d'abord celles qui **placent le plus de
    cartes** — une grille qui en laisse dehors est un poster amputé —, puis
    celles dont le nombre de cases s'écarte le moins de la grille actuelle, en
    trop comme en moins. On ne cherche donc pas la plus grande grille possible,
    mais la plus proche de ce que l'utilisateur avait en tête.

    Ni le papier ni la finesse n'y entrent : la géométrie porte déjà ce qu'une
    feuille loge dans les deux sens.
    """
    # ⚠️ **Plafonné.** Sans borne, une carte d'un millimètre sur cinq A0 à
    # 1200 DPI donne des centaines de milliers de candidats à trier sur le fil
    # de l'interface — mesuré, 4,3 secondes de fenêtre figée. Les champs de
    # grille s'arrêtent de toute façon à `MAX_GRID_SIDE` : au-delà, rien n'est
    # applicable.
    max_cols = min(MAX_GRID_SIDE, geometry.per_panel * panels)
    max_rows = min(MAX_GRID_SIDE, geometry.rows_per_panel * max(1, panel_rows))
    if max_cols < 1 or max_rows < 1:
        return []

    candidates = []
    for cols in range(1, int(max_cols) + 1):
        for rows in range(1, int(max_rows) + 1):
            cells = cols * rows
            candidates.append((-min(cells, card_count), abs(cells - current_cells),
                               abs(cols - rows), cols, rows))
    candidates.sort()
    return [(cols, rows) for *_, cols, rows in candidates[:limit]]


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
