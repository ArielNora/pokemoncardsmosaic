"""La feuille à l'échelle, cotée, avec une vraie carte posée à côté.

« A2 » ne dit rien à personne. Un rectangle coté en centimètres le dit déjà
mieux, mais un rectangle seul n'a pas d'échelle : sur un écran, un A6 et un A0
sont le même dessin. D'où l'étalon — une carte Pokémon à ses dimensions
réelles, dans le même rapport que la feuille. C'est elle qui donne la taille,
parce que c'est le seul objet des deux que l'on ait déjà tenu en main.
"""

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget

from ..layout import REAL_CARD_MM, paper_size_mm
from . import theme

# Place réservée aux cotes, en pixels écran : la flèche, sa tête, et le nombre
# sous elle. Trop juste, la largeur se retrouvait coupée par le bas du cadre.
GUTTER = 40
# Où la ligne de cote se pose dans cette réserve, le reste allant au nombre.
COTE = 0.45
# Longueur de la tête de flèche.
ARROW = 5
# Écart entre la feuille et la carte étalon.
GAP = 26


class PagePreview(QWidget):
    """Dessine la feuille cotée et l'étalon, tous deux à la même échelle."""

    def __init__(self, session, parent=None):
        super().__init__(parent)
        self._session = session
        self.setMinimumHeight(260)

    # --- Géométrie --------------------------------------------------------

    def _sheet_mm(self) -> tuple[float, float]:
        """La feuille entière, panneaux compris."""
        session = self._session
        width, height = paper_size_mm(session.paper, session.landscape)
        return width * session.panels, height

    def _scale(self, sheet: tuple[float, float]) -> float:
        """Pixels par millimètre, de façon que tout tienne — étalon compris.

        La carte étalon entre dans le calcul : sur un A6, elle fait plus de la
        moitié de la largeur de la feuille, et l'oublier la ferait sortir du
        cadre au lieu de dire ce qu'elle est venue dire.
        """
        largeur = sheet[0] + GAP / 2 + REAL_CARD_MM[0]
        hauteur = max(sheet[1], REAL_CARD_MM[1])
        libre_x = self.width() - 2 * GUTTER - GAP
        libre_y = self.height() - 2 * GUTTER
        if largeur <= 0 or hauteur <= 0 or libre_x <= 0 or libre_y <= 0:
            return 0.0
        return min(libre_x / largeur, libre_y / hauteur)

    # --- Dessin -----------------------------------------------------------

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), self.palette().window())

        sheet = self._sheet_mm()
        scale = self._scale(sheet)
        if scale <= 0:
            painter.end()
            return

        colours = theme.colours(self.palette())
        encre = self.palette().windowText().color()

        largeur_totale = (sheet[0] + GAP / 2 + REAL_CARD_MM[0]) * scale + GAP
        gauche = max(GUTTER, (self.width() - largeur_totale) / 2)
        haut = (self.height() - sheet[1] * scale) / 2

        feuille = QRectF(gauche, haut, sheet[0] * scale, sheet[1] * scale)
        painter.setBrush(self.palette().base())
        painter.setPen(QPen(encre, 1.4))
        painter.drawRect(feuille)

        # Les coupes entre panneaux : la feuille dessinée est leur somme.
        if self._session.panels > 1:
            painter.setPen(QPen(encre, 1, Qt.DashLine))
            for panneau in range(1, self._session.panels):
                x = feuille.left() + feuille.width() * panneau / self._session.panels
                painter.drawLine(QPointF(x, feuille.top()),
                                 QPointF(x, feuille.bottom()))

        painter.setPen(QPen(encre, 1))
        self._cote_horizontale(painter, feuille, sheet[0])
        self._cote_verticale(painter, feuille, sheet[1])

        # L'étalon, à droite, aligné sur le bas de la feuille : posés sur la même
        # ligne, les deux objets se comparent d'un coup d'œil.
        carte = QRectF(feuille.right() + GAP,
                       feuille.bottom() - REAL_CARD_MM[1] * scale,
                       REAL_CARD_MM[0] * scale, REAL_CARD_MM[1] * scale)
        painter.setBrush(self.palette().alternateBase())
        painter.setPen(QPen(encre, 1.2))
        painter.drawRoundedRect(carte, 2.5, 2.5)

        painter.setPen(QPen(QColor(colours["empty_text"]), 1))
        etiquette = QRectF(carte.left() - GAP / 2, carte.top() - 34,
                           carte.width() + GAP, 30)
        painter.drawText(etiquette, Qt.AlignHCenter | Qt.AlignBottom,
                         self.tr("carte réelle\n%1 × %2 cm")
                         .replace("%1", _cm(REAL_CARD_MM[0]))
                         .replace("%2", _cm(REAL_CARD_MM[1])))
        painter.end()

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
