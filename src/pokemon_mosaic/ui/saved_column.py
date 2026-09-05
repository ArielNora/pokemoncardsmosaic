"""La colonne des agencements mis de côté, à droite de l'écran.

Cinq cases numérotées, les mêmes à l'exécution et à l'export : c'est le passage
d'une étape à l'autre. On met de côté ce qu'on aime pendant que le calcul
tourne, et on retrouve exactement ces cases pour habiller puis écrire le poster.

⚠️ **Une case garde son rang.** Vider la deuxième ne fait pas remonter la
troisième : une colonne qui se réordonne sous la souris ferait cliquer sur autre
chose que ce qu'on visait.
"""

import numpy as np
from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..scoring import EMPTY
from . import theme
from .session import MAX_SAVED

# La vignette d'une case. Assez grande pour reconnaître un agencement d'un coup
# d'œil, assez petite pour que cinq tiennent en colonne sans faire défiler.
SLOT_IMAGE = QSize(120, 84)
CLOSE_SIZE = 18


def mosaic_image(grid: np.ndarray, cards, empty_colour) -> QImage | None:
    """Assemble une mosaïque à partir des vignettes déjà en mémoire.

    Le seul endroit qui sache le faire : l'exécution, les cases mises de côté et
    l'export en ont tous besoin, et trois assemblages auraient fini par montrer
    trois choses différentes.
    """
    if cards is None or not len(cards):
        return None
    tile_h, tile_w = cards[0].thumbnail.shape[:2]
    rows, cols = grid.shape
    canvas = np.full((rows * tile_h, cols * tile_w, 3), empty_colour, dtype=np.uint8)
    for row in range(rows):
        for col in range(cols):
            index = int(grid[row, col])
            if index == EMPTY:
                continue
            canvas[row * tile_h:(row + 1) * tile_h,
                   col * tile_w:(col + 1) * tile_w] = cards[index].thumbnail

    canvas = np.ascontiguousarray(canvas)
    height, width, _ = canvas.shape
    return QImage(canvas.data, width, height, 3 * width,
                  QImage.Format_RGB888).copy()


class SavedSlot(QFrame):
    """Une case : la mosaïque en petit, et la croix qui la vide."""

    picked = Signal(int)
    removed = Signal(int)

    def __init__(self, slot: int, removable: bool, parent=None):
        super().__init__(parent)
        self._slot = slot
        self.setFixedWidth(SLOT_IMAGE.width() + 16)

        self._close = QPushButton("✕")
        theme.mark(self._close, "mini")
        self._close.setFixedSize(CLOSE_SIZE, CLOSE_SIZE)
        self._close.clicked.connect(lambda: self.removed.emit(self._slot))
        self._close.setVisible(False)
        self._removable = removable
        # L'habillage de repos, celui que la case retrouve en perdant la main.
        self._base_role = "slot-empty"

        entete = QHBoxLayout()
        entete.setContentsMargins(0, 0, 0, 0)
        entete.addStretch(1)
        entete.addWidget(self._close)

        self._image = QLabel()
        self._image.setAlignment(Qt.AlignCenter)
        self._image.setFixedSize(SLOT_IMAGE)

        pile = QVBoxLayout(self)
        pile.setContentsMargins(6, 4, 6, 6)
        pile.setSpacing(2)
        pile.addLayout(entete)
        pile.addWidget(self._image)

    def show_saved(self, saved, empty_colour) -> None:
        """Pose l'agencement de la case, ou la vide."""
        self._close.setVisible(self._removable and saved is not None)
        if saved is None:
            self._image.setPixmap(QPixmap())
            self._image.setText(self.tr("vide"))
            self._base_role = "slot-empty"
            theme.mark(self, self._base_role)
            return
        image = mosaic_image(saved.grid, saved.cards, empty_colour)
        if image is not None:
            self._image.setText("")
            self._image.setPixmap(QPixmap.fromImage(image.scaled(
                SLOT_IMAGE, Qt.KeepAspectRatio, Qt.SmoothTransformation)))
        self._base_role = "slot"
        theme.mark(self, self._base_role)

    def set_current(self, current: bool) -> None:
        theme.mark(self, "slot-current" if current else self._base_role)

    def mousePressEvent(self, event) -> None:
        """Toute la case est cliquable : viser la vignette seule serait un jeu
        d'adresse, et la croix a déjà son propre clic."""
        super().mousePressEvent(event)
        if event.button() == Qt.LeftButton:
            self.picked.emit(self._slot)


class SavedColumn(QWidget):
    """Les cinq cases, plus leur intitulé.

    `removable` : la croix n'a de sens que là où l'on met de côté. À l'export,
    retirer sous ses propres pieds l'agencement affiché n'apporte rien.
    """

    slot_picked = Signal(int)

    def __init__(self, session, removable: bool = True, parent=None):
        super().__init__(parent)
        self._session = session
        self._current: int | None = None

        self._title = QLabel()
        police = self._title.font()
        police.setBold(True)
        self._title.setFont(police)

        self._slots: list[SavedSlot] = []
        pile = QVBoxLayout(self)
        pile.setContentsMargins(0, 0, 0, 0)
        pile.setSpacing(6)
        pile.addWidget(self._title)
        for rang in range(MAX_SAVED):
            case = SavedSlot(rang, removable)
            case.picked.connect(self._on_picked)
            case.removed.connect(self._session.remove_saved)
            self._slots.append(case)
            pile.addWidget(case)
        pile.addStretch(1)

        session.saved_changed.connect(self.refresh)
        self.retranslate_ui()

    def retranslate_ui(self) -> None:
        self._title.setText(self.tr("Agencements gardés"))
        self.refresh()

    def refresh(self) -> None:
        for rang, case in enumerate(self._slots):
            case.show_saved(self._session.saved[rang], self._session.empty_colour)
        self._mark_current()

    def current(self) -> int | None:
        return self._current

    def set_current(self, slot: int | None) -> None:
        """Marque la case affichée. `None` n'en marque aucune."""
        self._current = slot
        self._mark_current()

    def _mark_current(self) -> None:
        for rang, case in enumerate(self._slots):
            case.set_current(rang == self._current)

    def _on_picked(self, slot: int) -> None:
        # Une case vide n'est pas une destination : rien à montrer, et le clic
        # laisserait croire à une panne.
        if self._session.saved[slot] is not None:
            self.slot_picked.emit(slot)
