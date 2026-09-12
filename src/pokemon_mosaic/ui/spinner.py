"""Une animation d'attente, pour ce qui se calcule en fond."""

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QPainter, QPen
from PySide6.QtWidgets import QWidget

# Le diamètre, l'épaisseur du trait, et la part du cercle qui est dessinée.
SPINNER_SIZE = 36
SPINNER_WIDTH = 4
SPINNER_ARC = 270
# Un pas toutes les 16 ms, soixante images par seconde, et le tour en une seconde.
SPINNER_TICK_MS = 16
SPINNER_STEP = 6


class Spinner(QWidget):
    """Un arc qui tourne.

    ⚠️ **La minuterie ne tourne qu'affichée.** Cachée, elle réveillerait le
    processeur soixante fois par seconde pour dessiner ce que personne ne voit.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(SPINNER_SIZE, SPINNER_SIZE)
        # Posée par-dessus une image, elle ne doit pas lui voler un clic.
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._angle = 0
        self._timer = QTimer(self)
        self._timer.setInterval(SPINNER_TICK_MS)
        self._timer.timeout.connect(self._advance)

    def angle(self) -> int:
        return self._angle

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._timer.start()

    def hideEvent(self, event) -> None:
        super().hideEvent(event)
        self._timer.stop()

    def _advance(self) -> None:
        self._angle = (self._angle + SPINNER_STEP) % 360
        self.update()

    def paintEvent(self, event) -> None:
        peintre = QPainter(self)
        peintre.setRenderHint(QPainter.Antialiasing)
        stylo = QPen(self.palette().highlight().color(), SPINNER_WIDTH)
        stylo.setCapStyle(Qt.RoundCap)
        peintre.setPen(stylo)
        marge = SPINNER_WIDTH / 2
        cadre = QRectF(self.rect()).adjusted(marge, marge, -marge, -marge)
        # Qt compte en seizièmes de degré, et en sens inverse des aiguilles.
        peintre.drawArc(cadre, -self._angle * 16, SPINNER_ARC * 16)
        peintre.end()
