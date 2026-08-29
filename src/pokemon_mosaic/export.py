"""Export du poster : pleine résolution, découpage en panneaux, PNG / JPEG / PDF.

Le format d'impression commande : la taille des cartes en pixels se déduit du format
et du DPI, jamais l'inverse. Les cartes gardent leurs proportions exactes et l'image
est centrée, la marge résiduelle absorbant l'écart de rapport entre la grille et la
feuille (2,47 % pour une grille carrée). Ni déformation ni rognage. Voir SPEC.md §4.

Le rendu se fait **fenêtre par fenêtre** : chaque panneau n'assemble que les cartes
qui l'intersectent, et le poster complet n'est jamais en mémoire d'un seul tenant.
Un A0 en deux panneaux ferait sinon 836 Mo.
"""

import contextlib
import os
from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np
from PIL import Image, ImageDraw

from .cards import CardSet, load_full_image
from .layout import DEFAULT_DPI, card_pixel_size, max_useful_dpi, mm_to_pixels, paper_size_mm
from .scoring import EMPTY

WHITE = (255, 255, 255)
SUPPORTED_EXTENSIONS = (".png", ".jpg", ".jpeg", ".pdf")
CROP_MARK_MM = 5.0
CROP_MARK_WIDTH_PX = 3


class ExportCancelled(Exception):
    """L'export a été interrompu à la demande. Les fichiers déjà écrits sont
    effacés : un poster à moitié rendu ressemble à un poster fini."""


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
    """Calcule la mise en page et rassemble les avertissements à montrer.

    ⚠️ **Plusieurs feuilles, c'est une seule surface.** Le calcul découpait
    auparavant la grille par feuille et exigeait que les colonnes s'y divisent,
    pour que la coupe tombe toujours sur un bord de carte. Cette contrainte est
    abandonnée : des feuilles côte à côte ne sont qu'une façon d'avoir **plus de
    place**, la carte se dimensionne sur la surface entière, et la coupe tombe
    où elle tombe — c'est du papier qu'on raboute, pas une mosaïque qu'on
    partage. Le chevauchement et les repères de coupe existent précisément pour
    ça.
    """
    rows, cols = grid.shape
    card_aspect = cards.full_size[0] / cards.full_size[1]
    paper_w_mm, paper_h_mm = settings.paper_mm
    surface_mm = (paper_w_mm * settings.panels, paper_h_mm)
    card_px = card_pixel_size(surface_mm, cols, rows, card_aspect, settings.dpi)

    paper_w, paper_h = settings.paper_px
    # ⚠️ **La grille est calée à gauche**, non centrée : la place en trop est ce
    # qu'apporte la feuille suivante, et elle doit se voir d'un bloc, du côté où
    # l'on ajoutera la prochaine. Répartie de part et d'autre, elle donnait deux
    # demi-marges qui ne disaient rien. La marge verticale, elle, ne dépend
    # d'aucune feuille et reste centrée.
    margin_x = 0
    margin_y = (paper_h - rows * card_px[1]) // 2

    warnings: list[str] = []
    ceiling = max_useful_dpi(surface_mm, cols, cards.full_size[0])
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
    check_cancelled: Callable[[], bool] | None = None,
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
        # Une ligne de 17 cartes pleine résolution prend le temps de lire 17
        # fichiers : c'est la granularité la plus fine où l'arrêt reste franc.
        if check_cancelled is not None and check_cancelled():
            raise ExportCancelled()
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


def render_panel(
    grid: np.ndarray,
    cards: CardSet,
    plan: PosterPlan,
    panel: int,
    full_resolution: bool = True,
    check_cancelled: Callable[[], bool] | None = None,
) -> Image.Image:
    """Rend un seul panneau, repères de coupe compris."""
    _, paper_h = plan.settings.paper_px
    x0, x1 = plan.panel_bounds(panel)
    image = _render_window(grid, cards, plan, (x0, 0, x1, paper_h),
                           full_resolution, check_cancelled)
    if plan.settings.crop_marks:
        _draw_crop_marks(image, plan, panel)
    return image


def render_panels(
    grid: np.ndarray,
    cards: CardSet,
    settings: PosterSettings,
    full_resolution: bool = True,
) -> list[Image.Image]:
    """Produit une image par panneau. Les garde toutes en mémoire : préférer
    `export_poster`, qui écrit chaque panneau avant de rendre le suivant."""
    plan = plan_poster(grid, cards, settings)
    return [render_panel(grid, cards, plan, panel, full_resolution)
            for panel in range(settings.panels)]


def panel_paths(path: str, panels: int) -> list[str]:
    """Chemins des fichiers que produirait un export vers `path`.

    Sert aussi à prévenir l'utilisateur de ce qui va être écrasé : avec plusieurs
    panneaux, choisir « poster.png » écrit en réalité « poster_1of2.png » et
    « poster_2of2.png », qu'aucun sélecteur de fichier ne signale.
    """
    base, extension = os.path.splitext(path)
    extension = extension.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Format non géré : {extension} (attendu .png, .jpg ou .pdf)")
    if panels == 1:
        return [f"{base}{extension}"]
    return [f"{base}_{panel}of{panels}{extension}"
            for panel in range(1, panels + 1)]


def export_poster(
    grid: np.ndarray,
    cards: CardSet,
    settings: PosterSettings,
    path: str,
    full_resolution: bool = True,
    on_progress: Callable[[int, int, str], None] | None = None,
    check_cancelled: Callable[[], bool] | None = None,
) -> list[str]:
    """Écrit le poster. Renvoie la liste des fichiers produits.

    Le format se déduit de l'extension : `.png`, `.jpg`/`.jpeg`, `.pdf`. Le PDF porte
    les dimensions physiques et le DPI, ce qui lève toute ambiguïté chez l'imprimeur.
    Avec plusieurs panneaux, un suffixe `_1of2` est ajouté à chaque fichier.

    Chaque panneau est rendu **puis écrit** avant que le suivant ne commence : garder
    les deux moitiés d'un A0 en mémoire ferait 836 Mo pour rien.
    """
    targets = panel_paths(path, settings.panels)

    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)

    plan = plan_poster(grid, cards, settings)
    for warning in plan.warnings:
        print(f"  ⚠️  {warning}")

    written: list[str] = []
    try:
        for panel, target in enumerate(targets):
            if on_progress is not None:
                on_progress(panel, settings.panels, target)
            image = render_panel(grid, cards, plan, panel,
                                 full_resolution, check_cancelled)
            _save(image, target, settings)
            written.append(target)
            print(f"Enregistré : {target} ({image.width}x{image.height} px)")
    except ExportCancelled:
        # Un fichier partiel est pire qu'aucun fichier : rien ne le distingue
        # d'un poster terminé au moment de l'envoyer à l'imprimeur.
        for target in written:
            with contextlib.suppress(OSError):
                os.remove(target)
        raise

    if on_progress is not None:
        on_progress(settings.panels, settings.panels, "")
    return written


def _save(image: Image.Image, target: str, settings: PosterSettings) -> None:
    extension = os.path.splitext(target)[1].lower()
    if extension == ".pdf":
        image.save(target, "PDF", resolution=float(settings.dpi))
    elif extension in (".jpg", ".jpeg"):
        image.save(target, quality=settings.jpeg_quality, dpi=(settings.dpi,) * 2)
    else:
        image.save(target, dpi=(settings.dpi,) * 2)
