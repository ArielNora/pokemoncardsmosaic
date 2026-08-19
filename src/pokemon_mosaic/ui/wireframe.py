"""Aperçu fil de fer de la mise en page.

Montre la disposition et les proportions du résultat — feuille, marges, contours
des cartes, coupes entre panneaux — **sans les images**, comme demandé : on juge
ici de la géométrie, pas du contenu.
"""

from typing import Optional, Tuple

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget

from ..layout import card_pixel_size

PAPER = QColor(252, 252, 252)
PAPER_EDGE = QColor(120, 120, 120)
CARD_EDGE = QColor(150, 165, 190)
CARD_FILL = QColor(225, 233, 245)
EMPTY_FILL = QColor(255, 255, 255)
EMPTY_EDGE = QColor(210, 120, 120)
CUT_LINE = QColor(200, 90, 90)
MARGIN_FILL = QColor(240, 240, 240)


class WireframeView(QWidget):
    """Dessine la mise en page à l'échelle et convertit les clics en cases."""

    cell_clicked = Signal(int, int)

    def __init__(self, session, parent=None):
        super().__init__(parent)
        self._session = session
        self._geometry: Optional[Tuple[float, float, float, float]] = None
        self.setMinimumSize(320, 380)
        self.setCursor(Qt.PointingHandCursor)

    # --- Géométrie --------------------------------------------------------

    def _layout(self):
        """Renvoie (échelle, origine feuille, taille feuille, taille carte) en pixels
        écran, ou None si la mise en page n'a pas de sens."""
        session = self._session
        if session.cols <= 0 or session.rows <= 0:
            return None
        if session.cols % session.panels:
            return None

        card_aspect = 713 / 984
        if session.card_set and session.card_set.full_size[1]:
            width, height = session.card_set.full_size
            card_aspect = width / height

        paper_w, paper_h = _paper_mm(session)
        total_w = paper_w * session.panels
        card_w_px, card_h_px = card_pixel_size(
            (paper_w, paper_h), session.cols // session.panels, session.rows,
            card_aspect, dpi=72,
        )
        # Tout est ramené en millimètres pour le dessin, puis mis à l'échelle.
        card_w = card_w_px / 72 * 25.4
        card_h = card_h_px / 72 * 25.4

        margin = 12
        scale = min((self.width() - 2 * margin) / total_w,
                    (self.height() - 2 * margin) / paper_h)
        if scale <= 0:
            return None

        origin_x = (self.width() - total_w * scale) / 2
        origin_y = (self.height() - paper_h * scale) / 2
        return scale, (origin_x, origin_y), (total_w, paper_h), (card_w, card_h)

    def _grid_origin(self, geometry):
        """Coin haut-gauche de la grille : l'image est centrée sur la feuille."""
        scale, (ox, oy), (total_w, paper_h), (card_w, card_h) = geometry
        session = self._session
        grid_w = card_w * session.cols
        grid_h = card_h * session.rows
        return ox + (total_w - grid_w) * scale / 2, oy + (paper_h - grid_h) * scale / 2

    # --- Dessin -----------------------------------------------------------

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), self.palette().window())

        geometry = self._layout()
        self._geometry = geometry
        if geometry is None:
            return

        scale, (ox, oy), (total_w, paper_h), (card_w, card_h) = geometry
        session = self._session

        # La feuille, marges comprises.
        painter.setBrush(QBrush(MARGIN_FILL))
        painter.setPen(QPen(PAPER_EDGE, 1))
        painter.drawRect(QRectF(ox, oy, total_w * scale, paper_h * scale))

        gx, gy = self._grid_origin(geometry)
        painter.setBrush(QBrush(PAPER))
        painter.setPen(Qt.NoPen)
        painter.drawRect(QRectF(gx, gy, card_w * session.cols * scale,
                                card_h * session.rows * scale))

        empty = set(session.empty_cells())
        # Au-delà d'un certain nombre de cases, les contours se confondent : on
        # allège le trait pour que la grille reste lisible.
        pen_width = 1 if session.cols * session.rows <= 900 else 0
        for row in range(session.rows):
            for col in range(session.cols):
                rect = QRectF(gx + col * card_w * scale, gy + row * card_h * scale,
                              card_w * scale, card_h * scale)
                is_empty = (row, col) in empty
                painter.setBrush(QBrush(EMPTY_FILL if is_empty else CARD_FILL))
                painter.setPen(QPen(EMPTY_EDGE if is_empty else CARD_EDGE,
                                    1.5 if is_empty else pen_width))
                painter.drawRect(rect)

        # Coupes entre panneaux : elles tombent toujours sur un bord de carte.
        if session.panels > 1:
            painter.setPen(QPen(CUT_LINE, 2, Qt.DashLine))
            for panel in range(1, session.panels):
                x = ox + (total_w / session.panels) * panel * scale
                painter.drawLine(x, oy, x, oy + paper_h * scale)
        painter.end()

    # --- Interaction ------------------------------------------------------

    def mousePressEvent(self, event) -> None:
        cell = self.cell_at(event.position().x(), event.position().y())
        if cell is not None:
            self.cell_clicked.emit(*cell)

    def cell_at(self, x: float, y: float):
        """Case de la grille sous ce point de l'écran, ou None en dehors."""
        if self._geometry is None:
            return None
        scale, _, _, (card_w, card_h) = self._geometry
        gx, gy = self._grid_origin(self._geometry)
        # `int()` tronque vers zéro : un clic juste à gauche de la grille
        # donnerait la colonne 0 au lieu d'être rejeté. On écarte d'abord.
        if x < gx or y < gy:
            return None
        col = int((x - gx) / (card_w * scale))
        row = int((y - gy) / (card_h * scale))
        if 0 <= row < self._session.rows and 0 <= col < self._session.cols:
            return row, col
        return None


def _paper_mm(session):
    from ..layout import paper_size_mm

    return paper_size_mm(session.paper, session.landscape)
