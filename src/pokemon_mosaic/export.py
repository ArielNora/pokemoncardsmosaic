"""Export du poster : pleine résolution, découpage en panneaux, PNG / JPEG / PDF.

Le format d'impression commande : la taille des cartes en pixels se déduit du format
et du DPI, jamais l'inverse. Les cartes gardent leurs proportions exactes et l'image
est centrée, la marge résiduelle absorbant l'écart de rapport entre la grille et la
feuille (2,47 % pour une grille carrée). Ni déformation ni rognage. Voir SPEC.md §4.

Le rendu se fait **fenêtre par fenêtre** : chaque panneau n'assemble que les cartes
qui l'intersectent, et le poster complet n'est jamais en mémoire d'un seul tenant.
Un A0 en deux panneaux ferait sinon 836 Mo.
"""

import os
from dataclasses import dataclass, field

import numpy as np
from PIL import Image, ImageDraw

from .cards import CardSet, load_full_image
from .layout import DEFAULT_DPI, card_pixel_size, max_useful_dpi, mm_to_pixels, paper_size_mm
from .scoring import EMPTY

WHITE = (255, 255, 255)
CROP_MARK_MM = 5.0
CROP_MARK_WIDTH_PX = 3


@dataclass
class PosterSettings:
    """Tout ce qui décrit le poster à produire."""

    paper: str = "A2"
    landscape: bool = False
    dpi: int = DEFAULT_DPI
    panels: int = 1
    overlap_mm: float = 0.0
    crop_marks: bool = False
    background: tuple[int, int, int] = WHITE
    empty_colour: tuple[int, int, int] = WHITE
    jpeg_quality: int = 95

    def __post_init__(self):
        if self.panels < 1:
            raise ValueError("Il faut au moins un panneau.")
        if self.overlap_mm < 0:
            raise ValueError("Le chevauchement ne peut pas être négatif.")

    @property
    def paper_mm(self) -> tuple[float, float]:
        return paper_size_mm(self.paper, self.landscape)

    @property
    def paper_px(self) -> tuple[int, int]:
        w, h = self.paper_mm
        return mm_to_pixels(w, self.dpi), mm_to_pixels(h, self.dpi)

    @property
    def overlap_px(self) -> int:
        return mm_to_pixels(self.overlap_mm, self.dpi)


@dataclass
class PosterPlan:
    """Le calcul de mise en page, séparé du rendu pour être vérifiable seul."""

    settings: PosterSettings
    cols: int
    rows: int
    card_px: tuple[int, int]
    margin_px: tuple[int, int]
    warnings: list[str] = field(default_factory=list)

    @property
    def cols_per_panel(self) -> int:
        return self.cols // self.settings.panels

    @property
    def total_px(self) -> tuple[int, int]:
        paper_w, paper_h = self.settings.paper_px
        return paper_w * self.settings.panels, paper_h

    def panel_bounds(self, panel: int) -> tuple[int, int]:
        """Fenêtre horizontale d'un panneau, chevauchement compris."""
        paper_w = self.settings.paper_px[0]
        overlap = self.settings.overlap_px
        x0 = panel * paper_w - (overlap if panel > 0 else 0)
        x1 = (panel + 1) * paper_w + (overlap if panel < self.settings.panels - 1 else 0)
        return x0, x1


def plan_poster(
    grid: np.ndarray, cards: CardSet, settings: PosterSettings
) -> PosterPlan:
    """Calcule la mise en page et rassemble les avertissements à montrer."""
    rows, cols = grid.shape
    if cols % settings.panels:
        raise ValueError(
            f"{cols} colonnes ne se divisent pas en {settings.panels} panneaux : la "
            f"coupe tomberait au milieu d'une carte."
        )

    card_aspect = cards.full_size[0] / cards.full_size[1]
    cols_per_panel = cols // settings.panels
    card_px = card_pixel_size(
        settings.paper_mm, cols_per_panel, rows, card_aspect, settings.dpi
    )

    paper_w, paper_h = settings.paper_px
    margin_x = (paper_w * settings.panels - cols * card_px[0]) // 2
    margin_y = (paper_h - rows * card_px[1]) // 2

    warnings: list[str] = []
    ceiling = max_useful_dpi(settings.paper_mm, cols_per_panel, cards.full_size[0])
    if settings.dpi > ceiling:
        warnings.append(
            f"{settings.dpi} DPI dépasse le maximum utile ({ceiling:.0f} DPI pour ce "
            f"format) : les cartes seront agrandies sans gagner en détail."
        )
    megapixels = paper_w * paper_h * settings.panels / 1e6
    if megapixels > 100:
        warnings.append(
            f"Image de {megapixels:.0f} Mpx : prévoir ~{megapixels * 3 / 1024:.1f} Go "
            f"de mémoire pendant l'export."
        )

    return PosterPlan(settings, cols, rows, card_px, (margin_x, margin_y), warnings)


def _render_window(
    grid: np.ndarray,
    cards: CardSet,
    plan: PosterPlan,
    window: tuple[int, int, int, int],
    full_resolution: bool,
) -> Image.Image:
    """Assemble la portion du poster contenue dans `window` (x0, y0, x1, y1).

    Seules les cartes qui intersectent la fenêtre sont chargées. Pillow découpe
    lui-même ce qui dépasse, donc coller à des coordonnées négatives est sans danger.
    """
    x0, y0, x1, y1 = window
    card_w, card_h = plan.card_px
    margin_x, margin_y = plan.margin_px
    canvas = Image.new("RGB", (x1 - x0, y1 - y0), plan.settings.background)
    draw = ImageDraw.Draw(canvas)

    first_col = max(0, (x0 - margin_x) // card_w)
    last_col = min(plan.cols - 1, (x1 - margin_x) // card_w)
    first_row = max(0, (y0 - margin_y) // card_h)
    last_row = min(plan.rows - 1, (y1 - margin_y) // card_h)

    for r in range(first_row, last_row + 1):
        for c in range(first_col, last_col + 1):
            left = margin_x + c * card_w - x0
            top = margin_y + r * card_h - y0
            index = int(grid[r, c])
            if index == EMPTY:
                draw.rectangle(
                    [left, top, left + card_w - 1, top + card_h - 1],
                    fill=plan.settings.empty_colour,
                )
                continue
            card = cards[index]
            if full_resolution:
                tile = Image.fromarray(load_full_image(card, (card_w, card_h)))
            else:
                tile = Image.fromarray(card.thumbnail).resize(
                    (card_w, card_h), Image.Resampling.LANCZOS
                )
            canvas.paste(tile, (left, top))

    return canvas


def _draw_crop_marks(image: Image.Image, plan: PosterPlan, panel: int) -> None:
    """Trace de discrets repères de coupe aux angles de la zone à conserver."""
    settings = plan.settings
    overlap = settings.overlap_px
    paper_w, paper_h = settings.paper_px
    left = overlap if panel > 0 else 0
    right = left + paper_w
    length = mm_to_pixels(CROP_MARK_MM, settings.dpi)
    draw = ImageDraw.Draw(image)

    for x in (left, right - 1):
        for y in (0, paper_h - 1):
            end = y + length if y == 0 else y - length
            draw.line([(x, y), (x, end)], fill=(0, 0, 0), width=CROP_MARK_WIDTH_PX)
    for y in (0, paper_h - 1):
        for x in (left, right - 1):
            end = x + length if x == left else x - length
            draw.line([(x, y), (end, y)], fill=(0, 0, 0), width=CROP_MARK_WIDTH_PX)


def render_panels(
    grid: np.ndarray,
    cards: CardSet,
    settings: PosterSettings,
    full_resolution: bool = True,
) -> list[Image.Image]:
    """Produit une image par panneau, jamais le poster entier en mémoire."""
    plan = plan_poster(grid, cards, settings)
    _, paper_h = settings.paper_px

    panels = []
    for panel in range(settings.panels):
        x0, x1 = plan.panel_bounds(panel)
        image = _render_window(grid, cards, plan, (x0, 0, x1, paper_h), full_resolution)
        if settings.crop_marks:
            _draw_crop_marks(image, plan, panel)
        panels.append(image)
    return panels


def export_poster(
    grid: np.ndarray,
    cards: CardSet,
    settings: PosterSettings,
    path: str,
    full_resolution: bool = True,
) -> list[str]:
    """Écrit le poster. Renvoie la liste des fichiers produits.

    Le format se déduit de l'extension : `.png`, `.jpg`/`.jpeg`, `.pdf`. Le PDF porte
    les dimensions physiques et le DPI, ce qui lève toute ambiguïté chez l'imprimeur.
    Avec plusieurs panneaux, un suffixe `_1of2` est ajouté à chaque fichier.
    """
    base, extension = os.path.splitext(path)
    extension = extension.lower()
    if extension not in (".png", ".jpg", ".jpeg", ".pdf"):
        raise ValueError(f"Format non géré : {extension} (attendu .png, .jpg ou .pdf)")

    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)

    plan = plan_poster(grid, cards, settings)
    for warning in plan.warnings:
        print(f"  ⚠️  {warning}")

    images = render_panels(grid, cards, settings, full_resolution)
    written = []
    for panel, image in enumerate(images, start=1):
        suffix = f"_{panel}of{settings.panels}" if settings.panels > 1 else ""
        target = f"{base}{suffix}{extension}"
        if extension == ".pdf":
            image.save(target, "PDF", resolution=float(settings.dpi))
        elif extension in (".jpg", ".jpeg"):
            image.save(target, quality=settings.jpeg_quality, dpi=(settings.dpi,) * 2)
        else:
            image.save(target, dpi=(settings.dpi,) * 2)
        written.append(target)
        print(f"Enregistré : {target} ({image.width}x{image.height} px)")
    return written
