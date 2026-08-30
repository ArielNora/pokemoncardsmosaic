"""La feuille à l'échelle, cotée, avec une vraie carte posée à côté.

« A2 » ne dit rien à personne. Un rectangle coté en centimètres le dit déjà
mieux, mais un rectangle seul n'a pas d'échelle : sur un écran, un A6 et un A0
sont le même dessin. D'où l'étalon — une carte Pokémon à ses dimensions
réelles, dans le même rapport que la feuille. C'est elle qui donne la taille,
parce que c'est le seul objet des deux que l'on ait déjà tenu en main.

La mosaïque peut se poser dessus, pour voir ce qu'elle laisse de marge.
"""

from PySide6.QtCore import QPointF, QRect, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QPainter, QPen
from PySide6.QtWidgets import QPushButton, QWidget

from ..layout import MM_PER_INCH, REAL_CARD_MM, grid_geometry
from . import theme
from .wireframe import CARD_EDGE, CARD_FILL, EMPTY_EDGE, EMPTY_FILL

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
# Les boutons de retrait, sous chaque feuille. ⚠️ Leur hauteur **entre dans
# l'écart existant** entre la feuille et sa cote : l'agrandir éloignerait la
# cote de ce qu'elle mesure, pour loger un bouton qu'on ne regarde pas.
MINUS_SIZE = (30, 16)
# Nombre maximal de feuilles côte à côte. Cinq A2 font déjà deux mètres de
# large : au-delà, ce n'est plus un poster qu'on accroche.
MAX_PANELS = 5


class PagePreview(QWidget):
    """Dessine la feuille cotée et l'étalon, tous deux à la même échelle."""

    # Nouveau nombre de feuilles côte à côte, demandé depuis l'aperçu.
    panels_requested = Signal(int)
    # Une case cliquée, et le trajet d'un glissement avec l'état à y poser.
    cell_clicked = Signal(int, int)
    cells_painted = Signal(list, bool)

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
        self._paint_mode: bool | None = None
        self._plus = QPushButton("＋", self)
        theme.mark(self._plus, "mini")
        self._plus.clicked.connect(
            lambda: self.panels_requested.emit(self._session.panels + 1))
        self._minus: list[QPushButton] = []
        self.setMinimumHeight(260)
        self.retranslate_ui()

    def retranslate_ui(self) -> None:
        self._plus.setToolTip(self.tr("Ajouter une feuille à droite"))
        for bouton in self._minus:
            bouton.setToolTip(self.tr("Retirer une feuille"))

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

    def set_paintable(self, actif: bool) -> None:
        """Autorise ou non la pose de cases vides au clic dans les pages."""
        self._paintable = bool(actif)
        self.setCursor(Qt.PointingHandCursor if actif else Qt.ArrowCursor)

    # --- Les boutons posés sur le dessin ---------------------------------

    def _sync_minus_buttons(self) -> None:
        """Un bouton de retrait par feuille, jamais quand il n'en reste qu'une.

        Ils font tous la même chose — les feuilles sont identiques —, mais un
        seul bouton pour l'ensemble ne dirait pas **où** l'on retire : posé sous
        chacune, il se lit comme la colonne qu'il enlève.
        """
        voulus = 0 if self._session.panels <= 1 else self._session.panels
        while len(self._minus) < voulus:
            bouton = QPushButton("－", self)
            theme.mark(bouton, "mini")
            bouton.setFixedSize(*MINUS_SIZE)
            bouton.clicked.connect(
                lambda: self.panels_requested.emit(self._session.panels - 1))
            bouton.setToolTip(self.tr("Retirer une feuille"))
            self._minus.append(bouton)
        while len(self._minus) > voulus:
            self._minus.pop().deleteLater()

    def place_buttons(self) -> None:
        """Recale les boutons sur la géométrie courante du dessin."""
        self._sync_minus_buttons()
        geometrie = self.rects()
        if geometrie is None:
            self._plus.hide()
            for bouton in self._minus:
                bouton.hide()
            return
        feuille = geometrie[0]

        hauteur = max(PLUS_MIN_HEIGHT, feuille.height() / 3)
        self._plus.setGeometry(QRect(
            round(feuille.right() + PLUS_GAP),
            round(feuille.center().y() - hauteur / 2), PLUS_WIDTH, round(hauteur)))
        self._plus.setEnabled(self._session.panels < MAX_PANELS)
        self._plus.show()

        largeur = feuille.width() / max(1, len(self._minus))
        for rang, bouton in enumerate(self._minus):
            centre = feuille.left() + largeur * (rang + 0.5)
            bouton.move(round(centre - MINUS_SIZE[0] / 2),
                        round(feuille.bottom() + 1))
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
        if not self._paintable or event.button() != Qt.LeftButton:
            return
        cell = self.cell_at(event.position().x(), event.position().y())
        if cell is None:
            return
        self._paint_mode = cell not in set(self._session.empty_cells())
        self._painted = [cell]

    def mouseMoveEvent(self, event) -> None:
        if self._paint_mode is None or not (event.buttons() & Qt.LeftButton):
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

    # --- Géométrie --------------------------------------------------------

    def _sheet_mm(self) -> tuple[float, float]:
        """La feuille entière, panneaux compris."""
        session = self._session
        width, height = session.paper_mm()
        return width * session.panels, height

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
        étiquette débordait alors sur la feuille — le texte se lisait par-dessus
        le papier, ou disparaissait sous lui.
        """
        return max(self._label_width(), REAL_CARD_MM[0] * scale)

    def _scale(self, sheet: tuple[float, float]) -> float:
        """Pixels par millimètre, de façon que **tout** tienne côte à côte.

        ⚠️ La colonne de droite n'a pas une largeur connue d'avance : c'est la
        carte quand elle est grande, son étiquette quand la carte se réduit. On
        résout donc les deux cas et on garde le plus petit facteur — celui-là
        tient dans les deux, où le calcul en un seul passage débordait dès que
        l'étalon devenait plus étroit que son texte.
        """
        libre_x = self.width() - self._side_reserve()
        libre_y = self.height() - BOTTOM_ROOM - LABEL_HEIGHT
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
        libre_y = self.height() - BOTTOM_ROOM - LABEL_HEIGHT
        haut = LABEL_HEIGHT + max(0.0, (libre_y - sheet[1] * scale) / 2)

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
        painter.setBrush(self.palette().base())
        painter.setPen(QPen(encre, 1.4))
        painter.drawRect(feuille)

        if self._show_grid:
            self._draw_grid(painter, feuille)

        # Les coupes entre panneaux : la feuille dessinée est leur somme.
        if self._session.panels > 1:
            painter.setPen(QPen(encre, 1, Qt.DashLine))
            for panneau in range(1, self._session.panels):
                x = feuille.left() + feuille.width() * panneau / self._session.panels
                painter.drawLine(QPointF(x, feuille.top()),
                                 QPointF(x, feuille.bottom()))

        sheet = self._sheet_mm()
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(encre, 1))
        self._cote_horizontale(painter, feuille, sheet[0])
        self._cote_verticale(painter, feuille, sheet[1])
        self._draw_standard(painter, carte, etiquette, encre, colours)
        painter.end()

    def grid_cells(self, feuille: QRectF) -> list[tuple[int, int, QRectF]] | None:
        """Chaque case de la mosaïque, avec son rectangle à l'écran.

        Calculée à part pour que le dessin **et** le clic lisent la même
        géométrie : les cases se posent désormais dans les pages, et un
        placement qui ne tomberait pas sur ce qu'on voit ne servirait à rien.
        """
        session = self._session
        if session.cols <= 0 or session.rows <= 0:
            return None
        surface = self._sheet_mm()
        aspect = _card_aspect(session)
        # ⚠️ **Un nombre entier de cartes par feuille**, pour qu'une coupe tombe
        # toujours entre deux cartes. **À la résolution de la session**, jamais à
        # une autre : les arrondis en pixels ne donnent pas le même nombre de
        # cartes par feuille, et le dessin cesserait d'être celui du poster.
        geometrie = grid_geometry(
            session.paper_mm(), session.panels,
            session.cols, session.rows, aspect, session.dpi,
            session.card_width_mm, session.card_gap_mm)
        par_feuille = geometrie.per_panel
        px_vers_x = MM_PER_INCH / session.dpi * feuille.width() / surface[0]
        px_vers_y = MM_PER_INCH / session.dpi * feuille.height() / surface[1]
        card_w = geometrie.card_w * px_vers_x
        card_h = geometrie.card_h * px_vers_y
        gap_x, gap_y = geometrie.gap * px_vers_x, geometrie.gap * px_vers_y
        feuille_w = feuille.width() / max(1, session.panels)

        # ⚠️ **Calée à gauche.** La place en trop est ce qu'apporte la feuille
        # suivante : elle doit se voir d'un bloc, du côté où l'on ajoutera la
        # prochaine, et non coupée en deux demi-marges.
        gx = feuille.left()
        gy = feuille.top() + (feuille.height() - card_h * session.rows
                              - max(0, session.rows - 1) * gap_y) / 2
        cases = []
        for row in range(session.rows):
            for col in range(session.cols):
                # ⚠️ Chaque feuille repart de son bord, comme à l'export.
                x = ((col // par_feuille) * feuille_w
                     + (col % par_feuille) * (card_w + gap_x))
                cases.append((row, col, QRectF(gx + x, gy + row * (card_h + gap_y),
                                               card_w, card_h)))
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

    def _label_text(self) -> str:
        return (self.tr("carte réelle\n%1 × %2 cm")
                .replace("%1", _cm(REAL_CARD_MM[0]))
                .replace("%2", _cm(REAL_CARD_MM[1])))

    def _draw_standard(self, painter, carte: QRectF, etiquette: QRectF,
                       encre, colours) -> None:
        """L'étalon et son étiquette, dans leur colonne, à droite de la feuille.

        ⚠️ **La colonne est large du plus large des deux.** L'étiquette était
        centrée sur la seule carte : dès que celle-ci se réduisait — un A1, un
        A0 —, le texte débordait des deux côtés et passait sous la feuille.

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


def _card_aspect(session) -> float:
    card_set = session.card_set
    if card_set and card_set.full_size[1]:
        return card_set.full_size[0] / card_set.full_size[1]
    return 713 / 984


def _cm(mm: float) -> str:
    """Millimètres en centimètres, sans décimale inutile."""
    valeur = mm / 10
    return f"{valeur:.1f}".rstrip("0").rstrip(".").replace(".", ",")
