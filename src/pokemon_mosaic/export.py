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
from .layout import (
    DEFAULT_DPI,
    grid_geometry,
    max_useful_dpi,
    mm_to_pixels,
    paper_size_mm,
)
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
    # Dimensions de la feuille en portrait, quand elles ne sont pas celles d'un
    # format nommé. `None` s'en remet à `paper`, ce que fait la ligne de
    # commande, qui ne connaît que des noms.
    paper_size_mm: tuple[float, float] | None = None
    landscape: bool = False
    dpi: int = DEFAULT_DPI
    # Feuilles côte à côte, et lignes de feuilles superposées. Le poster est
    # leur somme : `panels` × `panel_rows` fichiers à imprimer et à rabouter.
    panels: int = 1
    panel_rows: int = 1
    # Largeur d'une carte sur le papier ; `None` demande la plus grande qui
    # fasse tenir la grille. L'écart les sépare, en millimètres.
    card_width_mm: float | None = None
    card_gap_mm: float = 0.0
    overlap_mm: float = 0.0
    crop_marks: bool = False
    background: tuple[int, int, int] = WHITE
    empty_colour: tuple[int, int, int] = WHITE
    jpeg_quality: int = 95

    def __post_init__(self):
        if self.panels < 1 or self.panel_rows < 1:
            raise ValueError("Il faut au moins un panneau.")
        if self.overlap_mm < 0:
            raise ValueError("Le chevauchement ne peut pas être négatif.")

    @property
    def paper_mm(self) -> tuple[float, float]:
        if self.paper_size_mm is None:
            return paper_size_mm(self.paper, self.landscape)
        width, height = self.paper_size_mm
        return (height, width) if self.landscape else (width, height)

    @property
    def paper_px(self) -> tuple[int, int]:
        w, h = self.paper_mm
        return mm_to_pixels(w, self.dpi), mm_to_pixels(h, self.dpi)

    @property
    def overlap_px(self) -> int:
        return mm_to_pixels(self.overlap_mm, self.dpi)

    @property
    def panel_count(self) -> int:
        """Le nombre de feuilles à imprimer, toutes lignes confondues."""
        return self.panels * self.panel_rows


@dataclass
class PosterPlan:
    """Le calcul de mise en page, séparé du rendu pour être vérifiable seul."""

    settings: PosterSettings
    cols: int
    rows: int
    card_px: tuple[int, int]
    margin_px: tuple[int, int]
    cards_per_panel: int = 1
    gap_px: int = 0
    rows_per_panel: int = 1
    warnings: list[str] = field(default_factory=list)

    def column_x(self, col: int) -> int:
        """Abscisse du bord gauche d'une colonne dans l'image du poster.

        ⚠️ **Chaque feuille repart de son propre bord.** Les cartes ne se suivent
        pas d'une feuille à l'autre en ignorant la coupe : elles recommencent à
        gauche de la suivante. C'est ce qui garantit qu'une coupe tombe toujours
        **entre** deux cartes, et jamais sur une. Le reste de feuille — moins
        d'une carte, quelques dixièmes de millimètre — sort blanc et disparaît
        au raboutage, les repères de coupe étant là pour le rogner.
        """
        par_feuille = max(1, self.cards_per_panel)
        return ((col // par_feuille) * self.settings.paper_px[0]
                + (col % par_feuille) * (self.card_px[0] + self.gap_px))

    def row_y(self, row: int) -> int:
        """Ordonnée du bord haut d'une ligne, même règle que `column_x`.

        Une coupe horizontale ne coupe pas plus une carte qu'une coupe
        verticale : chaque ligne de feuilles repart de son **bord haut**.
        """
        par_feuille = max(1, self.rows_per_panel)
        return ((row // par_feuille) * self.settings.paper_px[1]
                + (row % par_feuille) * (self.card_px[1] + self.gap_px))

    @property
    def total_px(self) -> tuple[int, int]:
        paper_w, paper_h = self.settings.paper_px
        return paper_w * self.settings.panels, paper_h * self.settings.panel_rows

    def panel_at(self, index: int) -> tuple[int, int]:
        """Ligne et colonne de la `index`-ième feuille, lues de gauche à droite."""
        return divmod(index, self.settings.panels)

    def panel_bounds(self, panel: int) -> tuple[int, int, int, int]:
        """Fenêtre d'un panneau dans l'image du poster, chevauchement compris."""
        paper_w, paper_h = self.settings.paper_px
        overlap = self.settings.overlap_px
        ligne, colonne = self.panel_at(panel)
        x0 = colonne * paper_w - (overlap if colonne > 0 else 0)
        x1 = (colonne + 1) * paper_w + (
            overlap if colonne < self.settings.panels - 1 else 0)
        y0 = ligne * paper_h - (overlap if ligne > 0 else 0)
        y1 = (ligne + 1) * paper_h + (
            overlap if ligne < self.settings.panel_rows - 1 else 0)
        return x0, y0, x1, y1


def plan_poster(
    grid: np.ndarray, cards: CardSet, settings: PosterSettings
) -> PosterPlan:
    """Calcule la mise en page et rassemble les avertissements à montrer.

    ⚠️ **Plusieurs feuilles, c'est de la place en plus** — et la coupe tombe
    toujours **entre deux cartes**. On exigeait pour cela que le nombre de
    colonnes se divise par le nombre de feuilles, ce qui interdisait des grilles
    parfaitement bonnes pour une raison qui n'était pas la leur. C'est désormais
    la **carte** qui se plie à la feuille : `panel_card_size` en pose un nombre
    entier par feuille, et la grille peut alors déborder sur la suivante sans
    qu'aucune carte ne soit coupée en deux.
    """
    rows, cols = grid.shape
    card_aspect = cards.full_size[0] / cards.full_size[1]
    geometry = grid_geometry(
        settings.paper_mm, settings.panels, cols, rows, card_aspect, settings.dpi,
        settings.card_width_mm, settings.card_gap_mm, settings.panel_rows,
    )
    per_panel, card_px = geometry.per_panel, (geometry.card_w, geometry.card_h)

    paper_w, paper_h = settings.paper_px
    # ⚠️ **La grille est calée à gauche**, non centrée : la place en trop est ce
    # qu'apporte la feuille suivante, et elle doit se voir d'un bloc, du côté où
    # l'on ajoutera la prochaine. Répartie de part et d'autre, elle donnait deux
    # demi-marges qui ne disaient rien.
    margin_x = 0
    hauteur = rows * card_px[1] + max(0, rows - 1) * geometry.gap
    # ⚠️ **Une seule ligne de feuilles : on centre.** Rien ne se coupe en
    # hauteur, et la marge ne dépend alors d'aucune feuille. Dès qu'il y en a
    # plusieurs, la marge passe à zéro : décalée, elle pousserait la dernière
    # ligne de chaque feuille au-delà de son bord bas, et la coupe tomberait en
    # pleine carte — la seule chose que l'on ne s'autorise jamais.
    margin_y = (paper_h - hauteur) // 2 if settings.panel_rows == 1 else 0

    warnings: list[str] = []
    ceiling = max_useful_dpi(settings.paper_mm, per_panel, cards.full_size[0])
    if settings.dpi > ceiling:
        warnings.append(
            f"{settings.dpi} DPI dépasse le maximum utile ({ceiling:.0f} DPI pour ce "
            f"format) : les cartes seront agrandies sans gagner en détail."
        )
    megapixels = paper_w * paper_h * settings.panel_count / 1e6
    if megapixels > 100:
        warnings.append(
            f"Image de {megapixels:.0f} Mpx : prévoir ~{megapixels * 3 / 1024:.1f} Go "
            f"de mémoire pendant l'export."
        )

    if (per_panel * settings.panels < cols
            or geometry.rows_per_panel * settings.panel_rows < rows):
        warnings.append(
            f"La grille {cols}×{rows} déborde de {settings.panel_count} feuille(s) "
            f"à cette taille de carte : le poster serait tronqué."
        )
    return PosterPlan(settings, cols, rows, card_px, (margin_x, margin_y),
                      per_panel, geometry.gap, geometry.rows_per_panel, warnings)


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

    # Les colonnes ne sont plus à pas constant — chaque feuille repart de son
    # bord —, donc on relève celles qui touchent la fenêtre plutôt que de les
    # déduire d'une division. Deux cents colonnes au plus : le balayage ne pèse
    # rien à côté de la lecture des images.
    touchees = [c for c in range(plan.cols)
                if margin_x + plan.column_x(c) < x1
                and margin_x + plan.column_x(c) + card_w > x0]
    # Les lignes non plus ne sont plus à pas constant, chaque ligne de feuilles
    # repartant de son bord haut : on les relève comme les colonnes.
    lignes = [r for r in range(plan.rows)
              if margin_y + plan.row_y(r) < y1
              and margin_y + plan.row_y(r) + card_h > y0]

    for r in lignes:
        # Une ligne de 17 cartes pleine résolution prend le temps de lire 17
        # fichiers : c'est la granularité la plus fine où l'arrêt reste franc.
        if check_cancelled is not None and check_cancelled():
            raise ExportCancelled()
        for c in touchees:
            left = margin_x + plan.column_x(c) - x0
            top = margin_y + plan.row_y(r) - y0
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
    """Trace de discrets repères de coupe aux angles de la zone à conserver.

    Le chevauchement déborde désormais des quatre côtés quand les feuilles sont
    en plusieurs lignes : les repères suivent, sans quoi ils auraient marqué le
    bord de l'image et non celui du papier à conserver.
    """
    settings = plan.settings
    overlap = settings.overlap_px
    paper_w, paper_h = settings.paper_px
    ligne, colonne = plan.panel_at(panel)
    left = overlap if colonne > 0 else 0
    right = left + paper_w
    top = overlap if ligne > 0 else 0
    bottom = top + paper_h
    length = mm_to_pixels(CROP_MARK_MM, settings.dpi)
    draw = ImageDraw.Draw(image)

    for x in (left, right - 1):
        for y in (top, bottom - 1):
            end = y + length if y == top else y - length
            draw.line([(x, y), (x, end)], fill=(0, 0, 0), width=CROP_MARK_WIDTH_PX)
    for y in (top, bottom - 1):
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
    x0, y0, x1, y1 = plan.panel_bounds(panel)
    image = _render_window(grid, cards, plan, (x0, y0, x1, y1),
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
            for panel in range(settings.panel_count)]


def panel_paths(path: str, panels: int, panel_rows: int = 1) -> list[str]:
    """Chemins des fichiers que produirait un export vers `path`.

    Sert aussi à prévenir l'utilisateur de ce qui va être écrasé : avec plusieurs
    panneaux, choisir « poster.png » écrit en réalité « poster_1of2.png » et
    « poster_2of2.png », qu'aucun sélecteur de fichier ne signale.

    Sur plusieurs lignes de feuilles, un numéro seul ne dirait plus où coller
    quoi : le nom porte alors la ligne et la colonne — « poster_l2c3sur2x3.png ».
    """
    base, extension = os.path.splitext(path)
    extension = extension.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Format non géré : {extension} (attendu .png, .jpg ou .pdf)")
    if panels == 1 and panel_rows == 1:
        return [f"{base}{extension}"]
    if panel_rows == 1:
        return [f"{base}_{panel}of{panels}{extension}"
                for panel in range(1, panels + 1)]
    return [f"{base}_l{ligne}c{colonne}sur{panel_rows}x{panels}{extension}"
            for ligne in range(1, panel_rows + 1)
            for colonne in range(1, panels + 1)]


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
    targets = panel_paths(path, settings.panels, settings.panel_rows)

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
                on_progress(panel, settings.panel_count, target)
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
        on_progress(settings.panel_count, settings.panel_count, "")
    return written


def _save(image: Image.Image, target: str, settings: PosterSettings) -> None:
    extension = os.path.splitext(target)[1].lower()
    if extension == ".pdf":
        image.save(target, "PDF", resolution=float(settings.dpi))
    elif extension in (".jpg", ".jpeg"):
        image.save(target, quality=settings.jpeg_quality, dpi=(settings.dpi,) * 2)
    else:
        image.save(target, dpi=(settings.dpi,) * 2)
