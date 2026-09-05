"""La feuille à l'échelle, cotée, avec une vraie carte posée à côté.

« A2 » ne dit rien à personne. Un rectangle coté en centimètres le dit déjà
mieux, mais un rectangle seul n'a pas d'échelle : sur un écran, un A6 et un A0
sont le même dessin. D'où l'étalon : une carte Pokémon à ses dimensions
réelles, dans le même rapport que la feuille. C'est elle qui donne la taille,
parce que c'est le seul objet des deux que l'on ait déjà tenu en main.

La mosaïque peut se poser dessus, pour voir ce qu'elle laisse de marge.
"""

import numpy as np
from PySide6.QtCore import QPointF, QRect, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QPushButton, QWidget

from ..layout import MM_PER_INCH, REAL_CARD_MM, cards_on_panel
from . import theme
from .wireframe import (
    CARD_EDGE,
    CARD_FILL,
    EMPTY_EDGE,
    EMPTY_FILL,
    badge_rect,
    draw_badge,
    draw_cut,
)

# Place réservée aux cotes, en pixels écran : la flèche, sa tête, et le nombre
# sous elle. Trop juste, la largeur se retrouvait coupée par le bas du cadre.
GUTTER = 40
# Où la ligne de cote se pose dans cette réserve, le reste allant au nombre.
COTE = 0.45
# Longueur de la tête de flèche.
ARROW = 5
# Écart entre la feuille et la carte étalon.
GAP = 26
# Hauteur réservée à l'étiquette de l'étalon, au-dessus de lui.
LABEL_HEIGHT = 34
# Place que la cote de largeur réclame sous la feuille : la ligne, sa tête de
# flèche, et le nombre en dessous.
BOTTOM_ROOM = 42
# Le contour des cartes s'efface au-delà, faute de quoi la mosaïque devient un
# aplat de traits où l'on ne distingue plus rien.
FINE_PEN_ABOVE = 900

# Le bouton d'ajout, à droite de la feuille : sa largeur et l'écart qui l'en
# sépare. Haut comme un tiers de la feuille, pour se viser sans précision.
PLUS_WIDTH = 30
PLUS_GAP = 10
PLUS_MIN_HEIGHT = 44
# Son jumeau au-dessus de la feuille, qui ajoute une **ligne** de feuilles :
# même écart, mêmes proportions, couché.
PLUS_HEIGHT = 24
PLUS_MIN_WIDTH = 44
# Les boutons de retrait, sous chaque feuille. ⚠️ Leur hauteur **entre dans
# l'écart existant** entre la feuille et sa cote : l'agrandir éloignerait la
# cote de ce qu'elle mesure, pour loger un bouton qu'on ne regarde pas.
MINUS_SIZE = (30, 16)
# Ceux des lignes, à gauche de chaque ligne de feuilles, dans la gouttière de la
# cote de hauteur. Même règle : ils entrent dans l'écart existant.
MINUS_ROW_SIZE = (16, 30)
# Nombre maximal de feuilles côte à côte. Cinq A2 font déjà deux mètres de
# large : au-delà, ce n'est plus un poster qu'on accroche.
MAX_PANELS = 5
# Et de lignes de feuilles. Trois A2 superposés font déjà un mur.
MAX_PANEL_ROWS = 3


class PagePreview(QWidget):
    """Dessine la feuille cotée et l'étalon, tous deux à la même échelle."""

    # Nouveau nombre de feuilles côte à côte, demandé depuis l'aperçu, et
    # nouveau nombre de lignes de feuilles.
    panels_requested = Signal(int)
    panel_rows_requested = Signal(int)
    # Une case cliquée, et le trajet d'un glissement avec l'état à y poser.
    cell_clicked = Signal(int, int)
    cells_painted = Signal(list, bool)
    # Le bout de grille d'une feuille, tiré à cet endroit **de sa feuille**.
    panel_moved = Signal(int, float, float)

    def __init__(self, session, parent=None):
        super().__init__(parent)
        self._session = session
        # Décochée d'office : l'aperçu de la mosaïque est une idée de ce que ça
        # pourrait donner, pas la décision de cet onglet, qui est la taille du
        # papier. On la montre quand on la demande.
        self._show_grid = False
        # Les cases vides ne se posent que là où on les règle : ailleurs le
        # dessin est une illustration, et un clic qui creuse la mosaïque sans
        # qu'on l'ait demandé serait une surprise désagréable.
        self._paintable = False
        self._painted: list[tuple[int, int]] = []
        # L'agencement à dessiner pour de vrai, s'il y en a un.
        self._grid = None
        self._grid_cards = None
        self._tiles: dict[int, QPixmap] = {}
        self._paint_mode: bool | None = None
        # Le bout de grille en cours de déplacement, et d'où il est parti.
        self._draggable = False
        self._dragged: int | None = None
        self._drag_from = None
        self._drag_origin = (0.0, 0.0)
        self._plus = QPushButton("＋", self)
        theme.mark(self._plus, "mini")
        self._plus.clicked.connect(
            lambda: self.panels_requested.emit(self._session.panels + 1))
        self._plus_row = QPushButton("＋", self)
        theme.mark(self._plus_row, "mini")
        self._plus_row.clicked.connect(
            lambda: self.panel_rows_requested.emit(self._session.panel_rows + 1))
        self._minus: list[QPushButton] = []
        self._minus_rows: list[QPushButton] = []
        self.setMinimumHeight(260)
        self.retranslate_ui()

    def retranslate_ui(self) -> None:
        self._plus.setToolTip(self.tr("Ajouter une feuille à droite"))
        self._plus_row.setToolTip(self.tr("Ajouter une ligne de feuilles"))
        for bouton in self._minus:
            bouton.setToolTip(self.tr("Retirer une feuille"))
        for bouton in self._minus_rows:
            bouton.setToolTip(self.tr("Retirer une ligne de feuilles"))

    def refresh(self) -> None:
        """Recale les boutons **puis** repeint.

        ⚠️ Les deux ensemble, et jamais depuis `paintEvent` : y montrer ou
        déplacer un widget enfant relancerait un tour de dessin.
        """
        self.place_buttons()
        self.update()

    def set_show_grid(self, montrer: bool) -> None:
        self._show_grid = bool(montrer)
        self.update()

    def set_arrangement(self, grid, cards) -> None:
        """Pose un agencement réel à dessiner, images comprises.

        Sans lui, le dessin reste le **fil de fer** : des rectangles gris qui
        disent la place occupée. Avec, la feuille montre le poster tel qu'il
        s'imprimera, ce qui est la seule façon de juger d'une couleur de fond ou
        d'un écart entre les cartes.
        """
        self._grid = grid
        self._grid_cards = cards
        # Les vignettes converties une fois pour toutes : une conversion par
        # case et par repeint coûterait 441 fois le prix d'un tour de dessin.
        self._tiles = {}
        self.update()

    def set_paintable(self, actif: bool) -> None:
        """Autorise ou non la pose de cases vides au clic dans les pages."""
        self._paintable = bool(actif)
        self.setCursor(Qt.PointingHandCursor if actif else Qt.ArrowCursor)

    # --- Les boutons posés sur le dessin ---------------------------------

    def _sync_minus_buttons(self) -> None:
        """Un bouton de retrait par feuille, jamais quand il n'en reste qu'une.

        Ils font tous la même chose : les feuilles sont identiques, mais un
        seul bouton pour l'ensemble ne dirait pas **où** l'on retire : posé sous
        chaque colonne et à gauche de chaque ligne, il se lit comme la feuille
        qu'il enlève.
        """
        session = self._session
        self._fit_row(self._minus, 0 if session.panels <= 1 else session.panels,
                      MINUS_SIZE, self.tr("Retirer une feuille"),
                      lambda: self.panels_requested.emit(session.panels - 1))
        self._fit_row(self._minus_rows,
                      0 if session.panel_rows <= 1 else session.panel_rows,
                      MINUS_ROW_SIZE, self.tr("Retirer une ligne de feuilles"),
                      lambda: self.panel_rows_requested.emit(
                          session.panel_rows - 1))

    def _fit_row(self, boutons, voulus, taille, infobulle, action) -> None:
        while len(boutons) < voulus:
            bouton = QPushButton("－", self)
            theme.mark(bouton, "mini")
            bouton.setFixedSize(*taille)
            bouton.clicked.connect(action)
            bouton.setToolTip(infobulle)
            boutons.append(bouton)
        while len(boutons) > voulus:
            boutons.pop().deleteLater()

    def place_buttons(self) -> None:
        """Recale les boutons sur la géométrie courante du dessin."""
        self._sync_minus_buttons()
        geometrie = self.rects()
        if geometrie is None:
            for bouton in (self._plus, self._plus_row,
                           *self._minus, *self._minus_rows):
                bouton.hide()
            return
        feuille = geometrie[0]

        hauteur = max(PLUS_MIN_HEIGHT, feuille.height() / 3)
        self._plus.setGeometry(QRect(
            round(feuille.right() + PLUS_GAP),
            round(feuille.center().y() - hauteur / 2), PLUS_WIDTH, round(hauteur)))
        self._plus.setEnabled(self._session.panels < MAX_PANELS)
        self._plus.show()

        # Le jumeau du dessus ajoute une ligne. Large comme un tiers de la
        # feuille, comme l'autre est haut d'un tiers : les deux se lisent comme
        # le même geste sur deux axes.
        largeur_plus = max(PLUS_MIN_WIDTH, feuille.width() / 3)
        self._plus_row.setGeometry(QRect(
            round(feuille.center().x() - largeur_plus / 2),
            round(feuille.top() - PLUS_GAP - PLUS_HEIGHT),
            round(largeur_plus), PLUS_HEIGHT))
        self._plus_row.setEnabled(self._session.panel_rows < MAX_PANEL_ROWS)
        self._plus_row.show()

        largeur = feuille.width() / max(1, len(self._minus))
        for rang, bouton in enumerate(self._minus):
            centre = feuille.left() + largeur * (rang + 0.5)
            bouton.move(round(centre - MINUS_SIZE[0] / 2),
                        round(feuille.bottom() + 1))
            bouton.show()

        # ⚠️ **Dans la gouttière de la cote**, comme les autres entrent dans
        # l'écart sous la feuille : la cote de hauteur se trace plus à gauche,
        # et l'élargir pour loger un bouton l'éloignerait de ce qu'elle mesure.
        haut = feuille.height() / max(1, len(self._minus_rows))
        for rang, bouton in enumerate(self._minus_rows):
            centre = feuille.top() + haut * (rang + 0.5)
            bouton.move(round(feuille.left() - MINUS_ROW_SIZE[0] - 1),
                        round(centre - MINUS_ROW_SIZE[1] / 2))
            bouton.show()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.place_buttons()

    # --- Poser des cases vides, dans les pages ---------------------------

    def mousePressEvent(self, event) -> None:
        """Ouvre un geste. Ce qu'il pose est décidé par sa **première** case.

        Même grammaire que le fil de fer d'où ce geste vient : bouton gauche
        seul, et basculer case par case ferait clignoter tout ce sur quoi on
        repasse.
        """
        self._painted = []
        self._paint_mode = None
        self._dragged = None
        if event.button() != Qt.LeftButton:
            return
        point = event.position()
        if self._draggable:
            self._start_drag(point)
            return
        if not self._paintable:
            return
        cell = self.cell_at(point.x(), point.y())
        if cell is None:
            return
        self._paint_mode = cell not in set(self._session.empty_cells())
        self._painted = [cell]

    def mouseMoveEvent(self, event) -> None:
        if not (event.buttons() & Qt.LeftButton):
            return
        if self._dragged is not None:
            self._drag_to(event.position())
            return
        if self._paint_mode is None:
            return
        cell = self.cell_at(event.position().x(), event.position().y())
        if cell is None or cell in self._painted:
            return
        self._painted.append(cell)
        self.cells_painted.emit(list(self._painted), self._paint_mode)

    def mouseReleaseEvent(self, event) -> None:
        if self._paint_mode is not None and len(self._painted) == 1:
            self.cell_clicked.emit(*self._painted[0])
        self._painted = []
        self._paint_mode = None
        if self._dragged is not None:
            self._dragged = None
            self.setCursor(Qt.OpenHandCursor)

    # --- Déplacer un bout de grille dans sa feuille ----------------------

    def set_draggable(self, actif: bool) -> None:
        """Autorise ou non le déplacement d'un bout de grille à la souris."""
        self._draggable = bool(actif)
        self.setCursor(Qt.OpenHandCursor if actif else Qt.ArrowCursor)

    def _start_drag(self, point) -> None:
        """Saisit le bout de grille sous le curseur, s'il y en a un.

        ⚠️ **On saisit la grille, pas la feuille.** Cliquer dans le blanc d'une
        feuille ne doit rien attraper : on ne déplace que ce qu'on voit bouger,
        et le vide d'une feuille n'appartient à personne.
        """
        cell = self.cell_at(point.x(), point.y())
        if cell is None:
            return
        session = self._session
        index = session.panel_of(*cell)
        self._dragged = index
        self._drag_from = point
        self._drag_origin = session.panel_position_mm(index)
        self.setCursor(Qt.ClosedHandCursor)

    def _drag_to(self, point) -> None:
        """Suit la souris, en millimètres sur le papier."""
        geometrie = self.rects()
        if geometrie is None or self._dragged is None:
            return
        feuille = geometrie[0]
        surface = self._sheet_mm()
        if feuille.width() <= 0 or feuille.height() <= 0:
            return
        dx = (point.x() - self._drag_from.x()) * surface[0] / feuille.width()
        dy = (point.y() - self._drag_from.y()) * surface[1] / feuille.height()
        self.panel_moved.emit(self._dragged, self._drag_origin[0] + dx,
                              self._drag_origin[1] + dy)

    # --- Géométrie --------------------------------------------------------

    def _sheet_mm(self) -> tuple[float, float]:
        """La feuille entière, panneaux compris, dans les deux sens."""
        return self._session.sheet_mm()

    def _top_room(self) -> float:
        """Ce qu'il faut garder au-dessus de la feuille.

        L'étiquette de l'étalon, ou le bouton qui ajoute une ligne, le plus
        encombrant des deux. Sans cette réserve, le bouton se dessinait
        au-dessus du cadre et disparaissait.
        """
        return max(LABEL_HEIGHT, PLUS_GAP + PLUS_HEIGHT)

    def _side_reserve(self) -> float:
        """Tout ce qui borde la feuille horizontalement, hors étalon.

        L'écart, la gouttière de la cote de hauteur, puis à droite l'écart du
        bouton d'ajout et le bouton lui-même.
        """
        return GAP + GUTTER + PLUS_GAP + PLUS_WIDTH + 4

    def _label_width(self) -> float:
        """Largeur du texte de l'étalon, qui ne doit jamais être rogné."""
        metrics = self.fontMetrics()
        return max(metrics.horizontalAdvance(ligne)
                   for ligne in self._label_text().split("\n"))

    def _column_width(self, scale: float) -> float:
        """Place que prend l'étalon : sa carte, ou son texte s'il est plus large.

        Sur un A0 la carte ne fait plus que quelques pixels de large, et son
        étiquette débordait alors sur la feuille, le texte se lisait par-dessus
        le papier, ou disparaissait sous lui.
        """
        return max(self._label_width(), REAL_CARD_MM[0] * scale)

    def _scale(self, sheet: tuple[float, float]) -> float:
        """Pixels par millimètre, de façon que **tout** tienne côte à côte.

        ⚠️ La colonne de droite n'a pas une largeur connue d'avance : c'est la
        carte quand elle est grande, son étiquette quand la carte se réduit. On
        résout donc les deux cas et on garde le plus petit facteur, celui-là
        tient dans les deux, où le calcul en un seul passage débordait dès que
        l'étalon devenait plus étroit que son texte.
        """
        libre_x = self.width() - self._side_reserve()
        libre_y = self.height() - BOTTOM_ROOM - self._top_room()
        if sheet[0] <= 0 or sheet[1] <= 0 or libre_x <= 0 or libre_y <= 0:
            return 0.0
        etiquette = self._label_width()
        # Cas 1 : la colonne vaut l'étiquette. Cas 2 : elle vaut la carte.
        par_etiquette = (libre_x - etiquette) / sheet[0]
        par_carte = libre_x / (sheet[0] + REAL_CARD_MM[0])
        return max(0.0, min(par_etiquette, par_carte, libre_y / sheet[1]))

    def rects(self) -> tuple[QRectF, QRectF, QRectF] | None:
        """Feuille, étalon et étiquette, en pixels écran. `None` si rien ne tient.

        Calculée à part pour que le dessin et sa vérification lisent la même
        géométrie : l'étalon caché par la feuille était un défaut de placement,
        pas de tracé, et il ne se voyait qu'à l'œil.
        """
        sheet = self._sheet_mm()
        scale = self._scale(sheet)
        if scale <= 0:
            return None
        colonne = self._column_width(scale)
        # De gauche à droite : l'étalon, l'écart, la gouttière de la cote de
        # hauteur, la feuille, puis le bouton d'ajout.
        largeur_totale = (colonne + GAP + GUTTER + sheet[0] * scale
                          + PLUS_GAP + PLUS_WIDTH)
        gauche_bloc = max(2.0, (self.width() - largeur_totale) / 2)
        gauche = gauche_bloc + colonne + GAP + GUTTER
        # ⚠️ **La feuille n'est pas centrée dans le cadre entier**, mais dans ce
        # qui reste une fois l'étiquette réservée en haut et la cote en bas.
        # Centrée sur tout, la moitié de la réserve partait vers le haut où elle
        # ne sert à rien : mesuré, 37 px laissés sous la feuille pour une cote
        # qui en réclame 42, et le « 42 cm » coupé par le bord.
        libre_y = self.height() - BOTTOM_ROOM - self._top_room()
        haut = self._top_room() + max(0.0, (libre_y - sheet[1] * scale) / 2)

        feuille = QRectF(gauche, haut, sheet[0] * scale, sheet[1] * scale)
        centre_x = gauche_bloc + colonne / 2
        carte = QRectF(centre_x - REAL_CARD_MM[0] * scale / 2,
                       feuille.bottom() - REAL_CARD_MM[1] * scale,
                       REAL_CARD_MM[0] * scale, REAL_CARD_MM[1] * scale)
        etiquette = QRectF(centre_x - colonne / 2, carte.top() - LABEL_HEIGHT,
                           colonne, LABEL_HEIGHT - 4)
        return feuille, carte, etiquette

    # --- Dessin -----------------------------------------------------------

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), self.palette().window())

        geometrie = self.rects()
        if geometrie is None:
            painter.end()
            return
        feuille, carte, etiquette = geometrie

        colours = theme.colours(self.palette())
        encre = self.palette().windowText().color()
        # Avec un agencement réel, la feuille prend la couleur qui s'imprimera
        # autour de la grille : juger d'un fond sur le blanc de l'écran ne dit
        # rien de ce que donnera le papier.
        painter.setBrush(QColor(*self._session.background_colour)
                         if self._grid is not None else self.palette().base())
        painter.setPen(QPen(encre, 1.4))
        painter.drawRect(feuille)

        if self._show_grid:
            self._draw_grid(painter, feuille)

        self._draw_cuts(painter, feuille, encre)

        sheet = self._sheet_mm()
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(encre, 1))
        self._cote_horizontale(painter, feuille, sheet[0])
        self._cote_verticale(painter, feuille, sheet[1])
        self._draw_standard(painter, carte, etiquette, encre, colours)
        painter.end()

    def _draw_cuts(self, painter, feuille: QRectF, encre) -> None:
        """Les coupes entre feuilles, et le numéro de chacune.

        ⚠️ **Deux tons.** Un trait unique tiré dans la couleur du texte passait
        en blanc sur une mosaïque bleu très clair : on ne voyait plus où le
        poster se coupe, c'est-à-dire la seule chose que ce dessin a à dire de
        plus qu'une image du résultat.
        """
        session = self._session
        if session.panel_count() <= 1:
            return
        for panneau in range(1, session.panels):
            x = feuille.left() + feuille.width() * panneau / session.panels
            draw_cut(painter, QPointF(x, feuille.top()),
                     QPointF(x, feuille.bottom()))
        for ligne in range(1, session.panel_rows):
            y = feuille.top() + feuille.height() * ligne / session.panel_rows
            draw_cut(painter, QPointF(feuille.left(), y),
                     QPointF(feuille.right(), y))
        self._draw_numbers(painter, feuille, encre)

    def _draw_numbers(self, painter, feuille: QRectF, encre) -> None:
        """Le numéro de chaque feuille, celui-là même que porte son fichier.

        C'est au raboutage qu'il sert : quinze feuilles étalées sur une table
        ne disent pas d'elles-mêmes laquelle va où.
        """
        session = self._session
        largeur = feuille.width() / max(1, session.panels)
        hauteur = feuille.height() / max(1, session.panel_rows)
        for index in range(session.panel_count()):
            if not session.panel_carries_cards(index):
                continue
            ligne, colonne = divmod(index, max(1, session.panels))
            page = QRectF(feuille.left() + colonne * largeur,
                          feuille.top() + ligne * hauteur, largeur, hauteur)
            rect, sur_mosaique = badge_rect(page, self._piece_rect(index, page))
            draw_badge(painter, rect, str(index + 1), encre, sur_mosaique)

    def _piece_rect(self, index: int, page: QRectF) -> QRectF:
        """Le morceau de mosaïque que porte une feuille, à l'écran."""
        session = self._session
        geometrie = session.panel_geometry()
        ligne, colonne = divmod(index, max(1, session.panels))
        paper_w, paper_h = session.paper_mm()
        en_mm = MM_PER_INCH / session.dpi
        vers_x = page.width() / paper_w if paper_w else 0.0
        vers_y = page.height() / paper_h if paper_h else 0.0
        pose = session.panel_position_mm(index)
        combien_c = cards_on_panel(session.cols, geometrie.per_panel, colonne)
        combien_l = cards_on_panel(session.rows, geometrie.rows_per_panel, ligne)

        def etendue(combien, taille):
            return (combien * taille + max(0, combien - 1) * geometrie.gap) * en_mm

        return QRectF(page.left() + pose[0] * vers_x,
                      page.top() + pose[1] * vers_y,
                      etendue(combien_c, geometrie.card_w) * vers_x,
                      etendue(combien_l, geometrie.card_h) * vers_y)

    def grid_cells(self, feuille: QRectF) -> list[tuple[int, int, QRectF]] | None:
        """Chaque case de la mosaïque, avec son rectangle à l'écran.

        Calculée à part pour que le dessin **et** le clic lisent la même
        géométrie : les cases se posent dans les pages, s'y déplacent, et un
        placement qui ne tomberait pas sur ce qu'on voit ne servirait à rien.
        """
        session = self._session
        if session.cols <= 0 or session.rows <= 0:
            return None
        surface = self._sheet_mm()
        # ⚠️ **À la résolution de la session**, jamais à une autre : les
        # arrondis en pixels ne donnent pas le même nombre de cartes par
        # feuille, et le dessin cesserait d'être celui du poster.
        geometrie = session.panel_geometry()
        # Zéro quand la carte ne tient pas sur la feuille : le dessin doit
        # quand même sortir, la ligne d'état étant là pour le dire.
        par_feuille = max(1, geometrie.per_panel)
        par_colonne = max(1, geometrie.rows_per_panel)
        en_mm = MM_PER_INCH / session.dpi
        vers_x = feuille.width() / surface[0]
        vers_y = feuille.height() / surface[1]
        card_w = geometrie.card_w * en_mm * vers_x
        card_h = geometrie.card_h * en_mm * vers_y
        gap_x = geometrie.gap * en_mm * vers_x
        gap_y = geometrie.gap * en_mm * vers_y
        paper_w, paper_h = session.paper_mm()

        # ⚠️ **Où chaque bout de grille se pose, la session seule le sait**,
        # calé à gauche, centré en hauteur sur une seule ligne de feuilles, ou
        # là où l'utilisateur l'a tiré. Le recalculer ici en donnerait une
        # seconde version, qui finirait par diverger de celle de l'export.
        # Relevé une fois par feuille : quinze au plus, contre quarante mille
        # cases.
        places = {index: session.panel_position_mm(index)
                  for index in range(session.panel_count())}

        cases = []
        for row in range(session.rows):
            feuille_l, dans_l = divmod(row, par_colonne)
            for col in range(session.cols):
                feuille_c, dans_c = divmod(col, par_feuille)
                pose = places.get(feuille_l * session.panels + feuille_c,
                                  (0.0, 0.0))
                x = feuille.left() + (
                    (feuille_c * paper_w + pose[0]) * vers_x
                    + dans_c * (card_w + gap_x))
                y = feuille.top() + (
                    (feuille_l * paper_h + pose[1]) * vers_y
                    + dans_l * (card_h + gap_y))
                cases.append((row, col, QRectF(x, y, card_w, card_h)))
        return cases

    def cell_at(self, x: float, y: float) -> tuple[int, int] | None:
        """Case de la mosaïque sous ce point, ou None en dehors."""
        geometrie = self.rects()
        if geometrie is None:
            return None
        cases = self.grid_cells(geometrie[0])
        if cases is None:
            return None
        for row, col, rect in cases:
            if rect.contains(x, y):
                return row, col
        return None

    def _draw_grid(self, painter, feuille: QRectF) -> None:
        """La mosaïque posée sur la surface, cases vides comprises.

        ⚠️ **Les cases vides s'y voient.** Elles ne se montraient qu'au premier
        onglet, si bien que la mosaïque dessinée ici n'était pas celle qu'on
        venait de composer : on ne pouvait pas juger de la place occupée sur une
        image qui ne disait pas la vérité.
        """
        session = self._session
        cases = self.grid_cells(feuille)
        if cases is None:
            return
        if self._grid is not None:
            self._draw_arrangement(painter, feuille, cases)
            return
        vides = set(session.empty_cells())
        trait = 0 if session.cols * session.rows > FINE_PEN_ABOVE else 0.8
        # ⚠️ **Bornée à la feuille.** Une grille trop grande pour le papier
        # débordait sur tout le cadre, par-dessus les cotes et le bouton
        # d'ajout. Ce qui dépasse ne s'imprimera pas : la feuille pleine à ras
        # bord le dit, et la ligne d'état chiffre ce qui tiendrait.
        painter.save()
        painter.setClipRect(feuille)
        for row, col, rect in cases:
            creux = (row, col) in vides
            painter.setBrush(QBrush(EMPTY_FILL if creux else CARD_FILL))
            painter.setPen(QPen(EMPTY_EDGE if creux else CARD_EDGE,
                                1.2 if creux else trait))
            painter.drawRect(rect)
        painter.restore()

    def _draw_arrangement(self, painter, feuille: QRectF, cases) -> None:
        """La mosaïque avec ses images, ses trous et la couleur de ses écarts.

        ⚠️ **Les écarts se peignent sous les cartes, pas entre elles.** Un
        rectangle par intervalle multiplierait les cas de bord ; l'étendue de la
        grille peinte d'un bloc ne se voit que là où aucune carte ne la
        recouvre, c'est-à-dire exactement dans les écarts.
        """
        session = self._session
        vides = set(session.empty_cells())
        painter.save()
        painter.setClipRect(feuille)
        painter.setPen(Qt.NoPen)
        etendue = cases[0][2]
        for _row, _col, rect in cases:
            etendue = etendue.united(rect)
        painter.fillRect(etendue, QColor(*session.gap_colour))
        rows, cols = self._grid.shape
        for row, col, rect in cases:
            if row >= rows or col >= cols:
                continue
            if (row, col) in vides:
                painter.fillRect(rect, QColor(*session.empty_colour))
                continue
            tuile = self._tile(int(self._grid[row, col]))
            if tuile is None:
                painter.fillRect(rect, QColor(*session.empty_colour))
            else:
                painter.drawPixmap(rect.toRect(), tuile)
        painter.restore()

    def _tile(self, index: int) -> QPixmap | None:
        """La vignette d'une carte, convertie une seule fois."""
        if index < 0 or self._grid_cards is None:
            return None
        if index not in self._tiles:
            vignette = self._grid_cards[index].thumbnail
            data = np.ascontiguousarray(vignette)
            hauteur, largeur, _ = data.shape
            image = QImage(data.data, largeur, hauteur, 3 * largeur,
                           QImage.Format_RGB888).copy()
            self._tiles[index] = QPixmap.fromImage(image)
        return self._tiles[index]

    def _label_text(self) -> str:
        return (self.tr("carte réelle\n%1 × %2 cm")
                .replace("%1", _cm(REAL_CARD_MM[0]))
                .replace("%2", _cm(REAL_CARD_MM[1])))

    def _draw_standard(self, painter, carte: QRectF, etiquette: QRectF,
                       encre, colours) -> None:
        """L'étalon et son étiquette, dans leur colonne, à droite de la feuille.

        ⚠️ **La colonne est large du plus large des deux.** L'étiquette était
        centrée sur la seule carte : dès que celle-ci se réduisait, un A1, un
        A0, le texte débordait des deux côtés et passait sous la feuille.

        Elle est à **gauche** depuis que la droite revient au bouton d'ajout :
        les feuilles s'ajoutent de ce côté-là, et l'étalon aurait été poussé
        plus loin à chaque clic.
        """
        painter.setBrush(self.palette().alternateBase())
        painter.setPen(QPen(encre, 1.2))
        painter.drawRoundedRect(carte, 2.5, 2.5)

        painter.setPen(QPen(QColor(colours["empty_text"]), 1))
        painter.drawText(etiquette, Qt.AlignHCenter | Qt.AlignBottom,
                         self._label_text())

    def _cote_horizontale(self, painter, feuille: QRectF, mm: float) -> None:
        """La largeur, sous la feuille."""
        y = feuille.bottom() + GUTTER * COTE
        painter.drawLine(QPointF(feuille.left(), y), QPointF(feuille.right(), y))
        for x, sens in ((feuille.left(), 1), (feuille.right(), -1)):
            painter.drawLine(QPointF(x, y), QPointF(x + sens * ARROW, y - ARROW))
            painter.drawLine(QPointF(x, y), QPointF(x + sens * ARROW, y + ARROW))
        painter.drawText(QRectF(feuille.left(), y + 2, feuille.width(), 20),
                         Qt.AlignCenter, self.tr("%1 cm").replace("%1", _cm(mm)))

    def _cote_verticale(self, painter, feuille: QRectF, mm: float) -> None:
        """La hauteur, à gauche de la feuille."""
        x = feuille.left() - GUTTER * COTE
        painter.drawLine(QPointF(x, feuille.top()), QPointF(x, feuille.bottom()))
        for y, sens in ((feuille.top(), 1), (feuille.bottom(), -1)):
            painter.drawLine(QPointF(x, y), QPointF(x - ARROW, y + sens * ARROW))
            painter.drawLine(QPointF(x, y), QPointF(x + ARROW, y + sens * ARROW))
        # Le texte tourne avec la cote : couché, il resterait lisible mais
        # obligerait à chercher à quelle dimension il se rapporte.
        painter.save()
        painter.translate(x - 4, feuille.center().y())
        painter.rotate(-90)
        painter.drawText(QRectF(-feuille.height() / 2, -20, feuille.height(), 18),
                         Qt.AlignCenter, self.tr("%1 cm").replace("%1", _cm(mm)))
        painter.restore()


def _cm(mm: float) -> str:
    """Millimètres en centimètres, sans décimale inutile."""
    valeur = mm / 10
    return f"{valeur:.1f}".rstrip("0").rstrip(".").replace(".", ",")
