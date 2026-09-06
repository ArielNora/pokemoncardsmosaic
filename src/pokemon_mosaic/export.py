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

from . import chameleon
from .cards import CardSet, load_full_image
from .layout import (
    DEFAULT_DPI,
    MM_PER_INCH,
    cards_on_panel,
    clamp_offset_mm,
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
    # Où l'utilisateur a posé le bout de grille de chaque feuille, en
    # millimètres depuis le coin haut-gauche de **sa** feuille. Absente, la
    # feuille garde le placement par défaut : calée à gauche, centrée en
    # hauteur quand il n'y a qu'une ligne de feuilles.
    panel_offsets: dict[int, tuple[float, float]] = field(default_factory=dict)
    # Largeur d'une carte sur le papier ; `None` demande la plus grande qui
    # fasse tenir la grille. L'écart les sépare, en millimètres.
    card_width_mm: float | None = None
    card_gap_mm: float = 0.0
    overlap_mm: float = 0.0
    crop_marks: bool = False
    # Ce qui entoure la grille sur la feuille.
    background: tuple[int, int, int] = WHITE
    # Ce qui sépare deux cartes. Distinct du fond : l'écart se voit **dans** la
    # mosaïque, et le teinter ne dit pas la même chose que teinter la marge
    # autour d'elle. `None` s'en remet au fond, ce que fait la ligne de
    # commande, qui ne connaît qu'une couleur.
    gap_colour: tuple[int, int, int] | None = None
    empty_colour: tuple[int, int, int] = WHITE
    # Le mode caméléon : les écarts, et la bordure, prennent la couleur de ce
    # qui les borde plutôt qu'un aplat. Voir `chameleon.py`.
    chameleon_gaps: bool = False
    chameleon_border: bool = False
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
    # Position du bout de grille de chaque feuille, en pixels depuis son coin
    # haut-gauche. Toujours bornée : voir `plan_poster`.
    offsets_px: dict[int, tuple[int, int]] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def panel_of(self, row: int, col: int) -> int:
        """Numéro de la feuille qui porte cette case, lue de gauche à droite."""
        return ((row // max(1, self.rows_per_panel)) * self.settings.panels
                + col // max(1, self.cards_per_panel))

    def card_origin(self, row: int, col: int) -> tuple[int, int]:
        """Coin haut-gauche d'une case dans l'image du poster.

        ⚠️ **Chaque feuille repart de son propre bord.** Les cartes ne se suivent
        pas d'une feuille à l'autre en ignorant la coupe : elles recommencent au
        coin de la suivante. C'est ce qui garantit qu'une coupe tombe toujours
        **entre** deux cartes, et jamais sur une. Le reste de feuille : moins
        d'une carte, quelques dixièmes de millimètre, sort blanc et disparaît
        au raboutage, les repères de coupe étant là pour le rogner.

        ⚠️ **Un seul endroit calcule cette position.** Elle en avait deux : une
        par axe, et le déplacement à la main dépend des deux à la fois : le
        bout de grille d'une feuille se déplace dans **sa** feuille, donc son
        décalage se lit à l'intersection d'une ligne et d'une colonne.
        """
        par_col = max(1, self.cards_per_panel)
        par_lig = max(1, self.rows_per_panel)
        paper_w, paper_h = self.settings.paper_px
        feuille_c, dans_c = divmod(col, par_col)
        feuille_l, dans_l = divmod(row, par_lig)
        dx, dy = self.offsets_px.get(self.panel_of(row, col),
                                     (self.margin_px[0], self.margin_px[1]))
        return (feuille_c * paper_w + dx + dans_c * (self.card_px[0] + self.gap_px),
                feuille_l * paper_h + dy + dans_l * (self.card_px[1] + self.gap_px))

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

    ⚠️ **Plusieurs feuilles, c'est de la place en plus**, et la coupe tombe
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
    # ⚠️ **Une seule ligne de feuilles : on centre.** Rien ne se coupe en
    # hauteur, et la marge ne dépend alors d'aucune feuille. Dès qu'il y en a
    # plusieurs, la marge passe à zéro : décalée, elle pousserait la dernière
    # ligne de chaque feuille au-delà de son bord bas, et la coupe tomberait en
    # pleine carte : la seule chose que l'on ne s'autorise jamais.
    #
    # ⚠️ **Ce que porte la feuille, pas ce que porte la grille.** Les deux se
    # confondent tant que tout tient ; quand la grille déborde, compter toutes
    # les lignes donnait une marge **négative**, là où l'écran, qui compte ce
    # que la feuille loge, en donnait une positive. Deux dessins du même poster.
    sur_la_feuille = _span(cards_on_panel(rows, geometry.rows_per_panel, 0),
                           card_px[1], geometry.gap)
    margin_y = (max(0, (paper_h - sur_la_feuille) // 2)
                if settings.panel_rows == 1 else 0)

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
    # ⚠️ **Les déplacements sont re-bornés ici.** L'écran les borne déjà, mais
    # un préréglage écrit à la main pousserait sinon un bout de grille hors de
    # sa feuille, et la coupe tomberait en pleine carte.
    offsets = {}
    for index, offset in settings.panel_offsets.items():
        ligne, colonne = divmod(int(index), settings.panels)
        if not (0 <= colonne < settings.panels
                and 0 <= ligne < settings.panel_rows):
            continue
        libre = (
            paper_w - _span(cards_on_panel(cols, per_panel, colonne),
                            card_px[0], geometry.gap),
            paper_h - _span(cards_on_panel(rows, geometry.rows_per_panel, ligne),
                            card_px[1], geometry.gap),
        )
        borne = clamp_offset_mm(tuple(offset), (libre[0] / settings.dpi * MM_PER_INCH,
                                                libre[1] / settings.dpi * MM_PER_INCH))
        offsets[int(index)] = (mm_to_pixels(borne[0], settings.dpi),
                               mm_to_pixels(borne[1], settings.dpi))

    return PosterPlan(settings, cols, rows, card_px, (margin_x, margin_y),
                      per_panel, geometry.gap, geometry.rows_per_panel,
                      offsets, warnings)


def _span(count: int, size: int, gap: int) -> int:
    """Place occupée par `count` cartes à la file, écarts intérieurs compris."""
    return max(0, count * size + max(0, count - 1) * gap)


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
    canvas = Image.new("RGB", (x1 - x0, y1 - y0), plan.settings.background)
    draw = ImageDraw.Draw(canvas)
    _fill_gaps(draw, plan, window)

    # ⚠️ **Aucune case ne se déduit d'une division.** Chaque feuille repart de
    # son coin, et son bout de grille a pu être déplacé à la main : la position
    # d'une case dépend de sa ligne **et** de sa colonne. On demande donc à
    # `card_origin` et on garde ce qui touche la fenêtre. Quarante mille cases
    # au plus, quelques additions chacune : rien à côté de la lecture des
    # images.
    for r in range(plan.rows):
        # Une ligne de 17 cartes pleine résolution prend le temps de lire 17
        # fichiers : c'est la granularité la plus fine où l'arrêt reste franc.
        if check_cancelled is not None and check_cancelled():
            raise ExportCancelled()
        for c in range(plan.cols):
            origine = plan.card_origin(r, c)
            if not (origine[0] < x1 and origine[0] + card_w > x0
                    and origine[1] < y1 and origine[1] + card_h > y0):
                continue
            left = origine[0] - x0
            top = origine[1] - y0
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

    # ⚠️ **Après les cartes, et non avant.** Le caméléon lit les pixels de bord
    # que les cartes viennent de poser : peint avant, il n'aurait rien à lire.
    _paint_chameleon(canvas, grid, plan, window)
    return canvas


def _fill_gaps(draw, plan: PosterPlan, window) -> None:
    """Teinte l'espace entre les cartes, sous les cartes elles-mêmes.

    ⚠️ **La couleur des écarts n'est pas celle du fond.** Peindre l'étendue de
    la mosaïque avant d'y coller les cartes ne laisse voir cette couleur que
    dans les écarts, exactement là où elle doit se voir ; le reste de la
    feuille garde le fond. Sans cela, il n'y avait qu'une couleur pour les deux
    et l'écart ne se réglait pas séparément.
    """
    couleur = plan.settings.gap_colour
    if couleur is None or couleur == plan.settings.background:
        return
    boite = _mosaic_box(plan, window)
    if boite is None:
        return
    gauche, haut, droite, bas = boite
    draw.rectangle([gauche, haut, droite - 1, bas - 1], fill=couleur)


def _line(canvas: Image.Image, x: int, y: int, count: int,
          vertical: bool) -> np.ndarray | None:
    """Une ligne de pixels lue dans l'image, ou `None` si elle en sort.

    Une carte qui déborde de la fenêtre a son bord dehors : l'écart qui la
    longe se peindra sans elle plutôt qu'avec du blanc lu hors cadre.
    """
    largeur, hauteur = canvas.size
    if x < 0 or y < 0 or count <= 0:
        return None
    if vertical and (x >= largeur or y + count > hauteur):
        return None
    if not vertical and (y >= hauteur or x + count > largeur):
        return None
    boite = ((x, y, x + 1, y + count) if vertical
             else (x, y, x + count, y + 1))
    bande = np.asarray(canvas.crop(boite), dtype=np.uint8)
    return bande[:, 0, :] if vertical else bande[0, :, :]


def _paste(canvas: Image.Image, bloc: np.ndarray, x: int, y: int) -> None:
    if bloc.size:
        canvas.paste(Image.fromarray(bloc), (x, y))


def _paint_chameleon(canvas: Image.Image, grid: np.ndarray, plan: PosterPlan,
                     window) -> None:
    """Peint les écarts, les croisées et la bordure d'après les cartes voisines.

    Tout se lit dans l'image déjà composée : un écart n'a besoin que des deux
    lignes de pixels qui le bordent, une croisée que de ses quatre coins. C'est
    ce qui permet de traiter la pleine résolution sans copier le poster.
    """
    settings = plan.settings
    if not (settings.chameleon_gaps or settings.chameleon_border):
        return
    gap = plan.gap_px
    x0, y0, _, _ = window
    card_w, card_h = plan.card_px

    def coin(r: int, c: int, droite: bool, bas: bool):
        """Le pixel d'angle d'une case, lu dans l'image."""
        ox, oy = plan.card_origin(r, c)
        x = ox - x0 + (card_w - 1 if droite else 0)
        y = oy - y0 + (card_h - 1 if bas else 0)
        ligne = _line(canvas, x, y, 1, vertical=True)
        return None if ligne is None else ligne[0]

    if settings.chameleon_gaps and gap > 0:
        for r in range(plan.rows):
            for c in range(plan.cols):
                _paint_gaps_of(canvas, plan, window, r, c)
        for r in range(plan.rows - 1):
            for c in range(plan.cols - 1):
                # ⚠️ Une croisée n'existe qu'**à l'intérieur d'une feuille** :
                # d'une feuille à l'autre, les deux cases ne se touchent pas et
                # le carré qui les sépare est du papier, pas un écart.
                if (plan.panel_of(r, c) != plan.panel_of(r + 1, c + 1)
                        or plan.panel_of(r, c) != plan.panel_of(r, c + 1)):
                    continue
                coins = (coin(r, c, True, True), coin(r, c + 1, False, True),
                         coin(r + 1, c, True, False),
                         coin(r + 1, c + 1, False, False))
                if any(pixel is None for pixel in coins):
                    continue
                ox, oy = plan.card_origin(r, c)
                _paste(canvas, chameleon.crossing(*coins, gap, gap),
                       ox - x0 + card_w, oy - y0 + card_h)

    if settings.chameleon_border and gap > 0:
        _paint_border(canvas, plan, window)


def _paint_gaps_of(canvas: Image.Image, plan: PosterPlan, window,
                   r: int, c: int) -> None:
    """Les deux écarts qui suivent une case : celui de droite, celui du bas."""
    x0, y0, _, _ = window
    card_w, card_h = plan.card_px
    gap = plan.gap_px
    ox, oy = plan.card_origin(r, c)

    if c + 1 < plan.cols and plan.panel_of(r, c) == plan.panel_of(r, c + 1):
        gauche = _line(canvas, ox - x0 + card_w - 1, oy - y0, card_h, True)
        voisin = plan.card_origin(r, c + 1)
        droite = _line(canvas, voisin[0] - x0, voisin[1] - y0, card_h, True)
        if gauche is not None and droite is not None:
            _paste(canvas, chameleon.gradient_between(gauche, droite, gap, True),
                   ox - x0 + card_w, oy - y0)

    if r + 1 < plan.rows and plan.panel_of(r, c) == plan.panel_of(r + 1, c):
        haut = _line(canvas, ox - x0, oy - y0 + card_h - 1, card_w, False)
        voisin = plan.card_origin(r + 1, c)
        bas = _line(canvas, voisin[0] - x0, voisin[1] - y0, card_w, False)
        if haut is not None and bas is not None:
            _paste(canvas, chameleon.gradient_between(haut, bas, gap, False),
                   ox - x0, oy - y0 + card_h)


def _paint_border(canvas: Image.Image, plan: PosterPlan, window) -> None:
    """La bande qui cerne la mosaïque, du bord des cartes vers le fond.

    Large comme l'écart : la mosaïque paraît cernée du même liseré que ce qui
    la traverse, et le reste de la marge garde le fond.

    ⚠️ **Le bord se lit d'un seul tenant, et non carte par carte.** Une bande
    par carte laissait un trou au-dessus de chaque écart : la mosaïque était
    cernée d'un liseré à créneaux. Lue sur toute la largeur du morceau, la
    ligne de bord porte déjà la couleur des écarts, qui viennent d'être peints.

    Les quatre coins se mélangent en bilinéaire, du pixel d'angle vers le fond :
    laissés au fond, ils faisaient quatre encoches sombres.
    """
    boite = _mosaic_box(plan, window)
    if boite is None:
        return
    gauche, haut, droite, bas = boite
    gap = plan.gap_px
    fond = plan.settings.background
    largeur, hauteur = droite - gauche, bas - haut

    ligne_haut = _line(canvas, gauche, haut, largeur, False)
    ligne_bas = _line(canvas, gauche, bas - 1, largeur, False)
    ligne_gauche = _line(canvas, gauche, haut, hauteur, True)
    ligne_droite = _line(canvas, droite - 1, haut, hauteur, True)

    if ligne_haut is not None:
        _paste(canvas, chameleon.border_band(ligne_haut, fond, gap, False, False),
               gauche, haut - gap)
    if ligne_bas is not None:
        _paste(canvas, chameleon.border_band(ligne_bas, fond, gap, False, True),
               gauche, bas)
    if ligne_gauche is not None:
        _paste(canvas, chameleon.border_band(ligne_gauche, fond, gap, True, False),
               gauche - gap, haut)
    if ligne_droite is not None:
        _paste(canvas, chameleon.border_band(ligne_droite, fond, gap, True, True),
               droite, haut)

    for x, y, dedans in ((gauche - gap, haut - gap, 3), (droite, haut - gap, 2),
                         (gauche - gap, bas, 1), (droite, bas, 0)):
        angle = _line(canvas,
                      gauche if dedans in (1, 3) else droite - 1,
                      haut if dedans in (2, 3) else bas - 1, 1, True)
        if angle is None:
            continue
        coins = [fond, fond, fond, fond]
        coins[dedans] = angle[0]
        _paste(canvas, chameleon.crossing(*coins, gap, gap), x, y)


def _mosaic_box(plan: PosterPlan, window) -> tuple[int, int, int, int] | None:
    """L'étendue de la mosaïque dans cette fenêtre, en coordonnées d'image."""
    x0, y0, x1, y1 = window
    card_w, card_h = plan.card_px
    gauche = haut = droite = bas = None
    for r in range(plan.rows):
        for c in range(plan.cols):
            ox, oy = plan.card_origin(r, c)
            if not (ox < x1 and ox + card_w > x0 and oy < y1 and oy + card_h > y0):
                continue
            gauche = ox if gauche is None else min(gauche, ox)
            haut = oy if haut is None else min(haut, oy)
            droite = ox + card_w if droite is None else max(droite, ox + card_w)
            bas = oy + card_h if bas is None else max(bas, oy + card_h)
    if gauche is None:
        return None
    return (gauche - x0, haut - y0, droite - x0, bas - y0)


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
    quoi : le nom porte alors la ligne et la colonne, « poster_l2c3sur2x3.png ».
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
