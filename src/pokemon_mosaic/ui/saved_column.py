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
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..scoring import EMPTY
from . import theme
from .session import MAX_SAVED

# La vignette d'une case. Assez grande pour reconnaître un agencement d'un coup
# d'œil, assez petite pour que cinq tiennent en colonne sans faire défiler.
SLOT_IMAGE = QSize(120, 120)
CLOSE_SIZE = 18
# Ce qui sépare la croix du bord de sa case.
CLOSE_MARGIN = 4
# La colonne : ce qu'elle réclame de haut, et la place qu'il faut à sa barre de
# défilement en plus de la case.
COLUMN_MIN_HEIGHT = 200
COLUMN_ROOM = 34
# La fenêtre d'un agencement hors timeline, assez grande pour le voir en entier.
DIALOG_SIZE = QSize(720, 640)


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

        # ⚠️ **La croix se pose par-dessus, elle ne prend pas de rang.** Dans
        # une ligne au-dessus de l'image, elle lui mangeait sa hauteur : la
        # mosaïque se retrouvait deux fois plus petite que sa case.
        self._close = QPushButton("✕", self)
        theme.mark(self._close, "mini")
        self._close.setFixedSize(CLOSE_SIZE, CLOSE_SIZE)
        self._close.clicked.connect(lambda: self.removed.emit(self._slot))
        self._close.setVisible(False)
        self._close.raise_()
        self._removable = removable
        # L'habillage de repos, celui que la case retrouve en perdant la main.
        self._base_role = "slot-empty"

        self._image = QLabel()
        self._image.setAlignment(Qt.AlignCenter)
        self._image.setFixedHeight(SLOT_IMAGE.height())

        pile = QVBoxLayout(self)
        pile.setContentsMargins(6, 6, 6, 6)
        pile.setSpacing(0)
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

    def resizeEvent(self, event) -> None:
        """La croix se cale dans le coin haut-droit, sur l'image."""
        super().resizeEvent(event)
        self._close.move(self.width() - CLOSE_SIZE - CLOSE_MARGIN, CLOSE_MARGIN)
        # Posée avant l'image, elle passerait dessous : les frères ajoutés
        # ensuite s'empilent au-dessus.
        self._close.raise_()

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

        # ⚠️ **Les cases défilent.** Cinq d'affilée réclament sept cents
        # pixels de haut : posées dans l'écran, elles lui imposaient cette
        # hauteur minimale, et une fenêtre plus courte étirait tout le reste
        # jusqu'à ce que l'image ne tienne plus.
        self._slots: list[SavedSlot] = []
        contenu = QWidget()
        cases = QVBoxLayout(contenu)
        cases.setContentsMargins(0, 0, 0, 0)
        cases.setSpacing(6)
        for rang in range(MAX_SAVED):
            case = SavedSlot(rang, removable)
            case.picked.connect(self._on_picked)
            case.removed.connect(self._confirm_remove)
            self._slots.append(case)
            cases.addWidget(case)
        cases.addStretch(1)

        self._scroll = QScrollArea()
        self._scroll.setWidget(contenu)
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QScrollArea.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.setMinimumHeight(COLUMN_MIN_HEIGHT)
        self._scroll.setFixedWidth(SLOT_IMAGE.width() + COLUMN_ROOM)

        pile = QVBoxLayout(self)
        pile.setContentsMargins(0, 0, 0, 0)
        pile.setSpacing(6)
        pile.addWidget(self._title)
        pile.addWidget(self._scroll, 1)

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

    def _confirm_remove(self, slot: int) -> None:
        """⚠️ **Toujours une confirmation.** La croix est à quelques pixels de
        la vignette, et ce qu'elle efface ne se retrouve pas : le cliché d'où
        vient l'agencement a pu disparaître de la timeline, et le calcul ne le
        redonnera pas à l'identique.
        """
        if self._session.saved[slot] is None:
            return
        reponse = QMessageBox.question(
            self, self.tr("Retirer cet agencement ?"),
            self.tr("La case %1 sera vidée. L'agencement ne se retrouve pas : "
                    "le calcul ne redonne pas deux fois le même.")
            .replace("%1", str(slot + 1)),
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reponse == QMessageBox.Yes:
            self._session.remove_saved(slot)

    def _on_picked(self, slot: int) -> None:
        # Une case vide n'est pas une destination : rien à montrer, et le clic
        # laisserait croire à une panne.
        if self._session.saved[slot] is not None:
            self.slot_picked.emit(slot)


# Le zoom de la fenêtre d'un agencement hors timeline, et ses bornes.
DIALOG_ZOOM_MIN, DIALOG_ZOOM_MAX, DIALOG_ZOOM_STEP = 1.0, 6.0, 1.25


class SavedDialog(QDialog):
    """Un agencement gardé que la timeline n'a plus, montré pour lui-même.

    ⚠️ **Le curseur ne saute pas.** Rejoindre un cliché disparu est impossible,
    et déplacer la timeline au plus proche montrerait autre chose que ce que la
    case promet. La fenêtre montre donc l'agencement tel qu'il a été gardé, et
    le dit en toutes lettres.
    """

    def __init__(self, saved, empty_colour, parent=None):
        super().__init__(parent)
        self._image = mosaic_image(saved.grid, saved.cards, empty_colour)
        self._zoom = DIALOG_ZOOM_MIN

        self._notice = QLabel()
        self._notice.setWordWrap(True)
        theme.mark(self._notice, "warning")
        gras = self._notice.font()
        gras.setBold(True)
        self._notice.setFont(gras)

        self._view = QLabel()
        self._view.setAlignment(Qt.AlignCenter)
        self._scroll = QScrollArea()
        self._scroll.setWidget(self._view)
        self._scroll.setWidgetResizable(False)
        self._scroll.setAlignment(Qt.AlignCenter)

        self._zoom_out = QPushButton("−")
        self._zoom_in = QPushButton("+")
        self._zoom_label = QLabel()
        for bouton in (self._zoom_out, self._zoom_in):
            bouton.setFixedWidth(32)
        self._zoom_out.clicked.connect(lambda: self._zoom_by(1 / DIALOG_ZOOM_STEP))
        self._zoom_in.clicked.connect(lambda: self._zoom_by(DIALOG_ZOOM_STEP))
        self._close = QPushButton()
        self._close.clicked.connect(self.accept)

        barre = QHBoxLayout()
        barre.addWidget(self._zoom_out)
        barre.addWidget(self._zoom_label)
        barre.addWidget(self._zoom_in)
        barre.addStretch(1)
        barre.addWidget(self._close)

        pile = QVBoxLayout(self)
        pile.addWidget(self._notice)
        pile.addWidget(self._scroll, 1)
        pile.addLayout(barre)
        self.resize(DIALOG_SIZE)
        self.retranslate_ui()

    def retranslate_ui(self) -> None:
        self.setWindowTitle(self.tr("Agencement gardé"))
        self._notice.setText(self.tr("L'agencement n'est plus dans la timeline."))
        self._close.setText(self.tr("Fermer"))
        self._redraw()

    def zoom(self) -> float:
        return self._zoom

    def _zoom_by(self, facteur: float) -> None:
        voulu = max(DIALOG_ZOOM_MIN, min(DIALOG_ZOOM_MAX, self._zoom * facteur))
        if voulu == self._zoom:
            return
        self._zoom = voulu
        self._redraw()

    def _redraw(self) -> None:
        self._zoom_label.setText(f"{self._zoom * 100:.0f} %")
        if self._image is None:
            self._view.setText(self.tr("Aucune image à montrer."))
            return
        cadre = self._scroll.viewport().size()
        ajuste = self._image.scaled(cadre, Qt.KeepAspectRatio,
                                    Qt.SmoothTransformation)
        cible = ajuste.size() * self._zoom
        pixmap = QPixmap.fromImage(
            self._image.scaled(cible, Qt.KeepAspectRatio,
                               Qt.SmoothTransformation))
        self._view.setPixmap(pixmap)
        self._view.resize(pixmap.size())

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._redraw()
