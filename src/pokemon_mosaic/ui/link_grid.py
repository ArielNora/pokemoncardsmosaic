"""L'éditeur de rectangle d'un lien : la grille de cases, et sa palette.

Un lien est un rectangle plein d'au plus trois cases de côté. On le compose en
posant les cartes à leur place plutôt qu'en ordonnant une liste : sur un 3×3,
lire « la septième » ne dit rien, alors que voir la case le dit tout de suite.

La grille grandit par ses bords. Un « + » au-dessus ajoute une rangée, un « + »
à droite ajoute une colonne, et un « − » apparaît en regard de chaque rangée et
de chaque colonne dès qu'il y en a plus d'une, on ne peut jamais supprimer la
dernière, ni dépasser trois.
"""

import numpy as np
from PySide6.QtCore import QMimeData, QSize, Qt, Signal
from PySide6.QtGui import QDrag, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ..links import MAX_SIDE
from . import theme
from .gallery import numpy_to_pixmap

# Type de contenu propre au projet plutôt que du texte brut : une chaîne venue
# d'ailleurs : un nom de fichier lâché depuis le Finder, serait sinon prise
# pour un indice de carte.
CARD_MIME = "application/x-pokemon-mosaic-card"

# Assez grand pour reconnaître une illustration, assez petit pour qu'un 3×3
# tienne à côté de la palette sans forcer le dialogue à occuper l'écran.
#
# **Une seule taille pour les deux côtés** : une carte glissée depuis la palette
# doit avoir exactement l'aspect qu'elle aura dans le rectangle, sans quoi on la
# voit rapetisser en la déposant et l'on doute d'avoir pris la bonne.
CELL_WIDTH = 78
CELL_HEIGHT = int(CELL_WIDTH * 1024 / 734)


def card_mime(index: int) -> QMimeData:
    """Le paquet transporté par un glisser, décrivant une carte par son indice."""
    payload = QMimeData()
    payload.setData(CARD_MIME, str(index).encode())
    return payload


def card_from_mime(payload: QMimeData) -> int | None:
    """Indice de carte porté par un glisser, ou None si ce n'en est pas un."""
    if not payload.hasFormat(CARD_MIME):
        return None
    try:
        return int(bytes(payload.data(CARD_MIME)).decode())
    except ValueError:
        return None


class CardPalette(QListWidget):
    """Les cartes disponibles, d'où l'on tire pour remplir la grille.

    Une **grille de vignettes**, sans nom écrit : sur quatre cent quarante et une
    cartes, une liste d'une carte par ligne oblige à faire défiler sans fin, et
    le nom occupe la place de ce qu'on cherche vraiment, l'illustration. Le nom
    revient en infobulle, au survol prolongé.

    `QListWidget` sait déjà glisser, mais son format natif décrit une ligne de
    modèle et non une carte. On pose le nôtre pour que la case sache exactement
    ce qu'elle reçoit.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setViewMode(QListWidget.IconMode)
        self.setIconSize(QSize(CELL_WIDTH, CELL_HEIGHT))
        # La cellule dépasse un peu la vignette : sans cette marge, Qt rogne les
        # bords et les cartes se touchent.
        self.setGridSize(QSize(CELL_WIDTH + 12, CELL_HEIGHT + 12))
        self.setResizeMode(QListWidget.Adjust)   # recalcule les colonnes au redimensionnement
        self.setWrapping(True)
        self.setSpacing(2)
        # `Static` et `DragOnly` : on tire **vers la grille**, jamais pour
        # réordonner la palette, qui n'a pas d'ordre propre.
        self.setMovement(QListWidget.Static)
        self.setDragDropMode(QListWidget.DragOnly)
        self.setDragEnabled(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

    def mimeData(self, items):
        if not items:
            return QMimeData()
        return card_mime(items[0].data(Qt.UserRole))


class CardCell(QFrame):
    """Une case du rectangle : vide, ou portant une carte.

    Accepte le dépôt d'une carte, et se vide au double-clic. Pas de croix dans
    le coin : sur des vignettes déjà petites, un bouton par-dessus mangerait
    l'illustration qu'on cherche justement à reconnaître.
    """

    dropped = Signal(int, int, int)      # ligne, colonne, indice de carte
    cleared = Signal(int, int)

    def __init__(self, row: int, col: int, parent=None):
        super().__init__(parent)
        self._row, self._col = row, col
        self._card: int | None = None
        # Origine du geste en cours, pour distinguer un clic d'un glissement.
        self._press = None
        self.setAcceptDrops(True)
        self.setFrameShape(QFrame.StyledPanel)
        self.setFixedSize(CELL_WIDTH, CELL_HEIGHT)
        self._image = QLabel(self)
        self._image.setAlignment(Qt.AlignCenter)
        self._image.setGeometry(1, 1, CELL_WIDTH - 2, CELL_HEIGHT - 2)
        self._image.setWordWrap(True)
        # Et non `_paint()` seul : une case doit porter son texte d'attente dès
        # sa construction. Sans cela elle reste blanche jusqu'au premier
        # `set_card`, ce qui la fait paraître différente d'une case vidée.
        self.set_card(None, None)

    # --- Contenu ----------------------------------------------------------

    @property
    def card(self) -> int | None:
        return self._card

    def set_card(self, index: int | None, thumbnail: np.ndarray | None) -> None:
        self._card = index
        if index is None or thumbnail is None:
            self._image.setPixmap(QPixmap())
            self._image.setText(self.tr("carte"))
        else:
            self._image.setText("")
            self._image.setPixmap(numpy_to_pixmap(thumbnail).scaled(
                CELL_WIDTH - 2, CELL_HEIGHT - 2,
                Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self._paint()

    def _paint(self) -> None:
        # Une case vide se distingue d'un coup d'œil : c'est ce qui manque pour
        # pouvoir valider, et l'utilisateur doit les repérer sans les compter.
        # Les couleurs viennent du thème, qui les décline en clair et en sombre.
        theme.mark(self, "cell" if self._card is not None else "cell-empty")

    # --- Glisser-déposer --------------------------------------------------

    def dragEnterEvent(self, event):
        if card_from_mime(event.mimeData()) is None:
            event.ignore()
            return
        event.acceptProposedAction()

    dragMoveEvent = dragEnterEvent

    def dropEvent(self, event):
        index = card_from_mime(event.mimeData())
        if index is None:
            event.ignore()
            return
        event.acceptProposedAction()
        self.dropped.emit(self._row, self._col, index)

    def mouseDoubleClickEvent(self, event):
        if self._card is not None:
            self.cleared.emit(self._row, self._col)

    def mousePressEvent(self, event):
        """Retient d'où part le geste, pour mesurer s'il devient un glissement.

        ⚠️ **L'événement est accepté**, et non laissé filer vers le parent.
        `QWidget::mousePressEvent` l'ignore par défaut : la case ne capturerait
        alors pas la souris, et les mouvements suivants iraient au parent, le
        glissement d'une case vers une autre ne partirait jamais depuis une vraie
        souris. Les tests ne le voyaient pas : `QTest.mouseMove` livre
        l'événement au widget visé, court-circuitant la capture.
        """
        if event.button() == Qt.LeftButton and self._card is not None:
            self._press = event.position().toPoint()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """Une carte déjà posée se déplace vers une autre case.

        Sans cela, corriger une inversion demanderait de vider les deux cases
        puis de retourner chercher les cartes dans la palette.

        ⚠️ **Au-delà du seuil de Qt seulement.** Démarrer à tout mouvement
        arrachait la carte dès deux pixels de tremblement, et `drag.exec()`
        ouvre une boucle imbriquée qui avale la suite du geste : le double-clic
        n'arrivait jamais, et la case ne se vidait pas. Comme c'est le seul
        moyen de la vider, le geste échouait une fois sur deux sans raison
        visible.
        """
        if self._card is None or not (event.buttons() & Qt.LeftButton):
            return
        if self._press is None:
            return
        parcouru = (event.position().toPoint() - self._press).manhattanLength()
        if parcouru < QApplication.startDragDistance():
            return
        drag = QDrag(self)
        drag.setMimeData(card_mime(self._card))
        if self._image.pixmap() and not self._image.pixmap().isNull():
            drag.setPixmap(self._image.pixmap())
        drag.exec(Qt.MoveAction)


class LinkGrid(QWidget):
    """Le rectangle en cours de composition, et ses boutons de redimensionnement."""

    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        # Contenu logique, indexé [ligne][colonne]. La disposition Qt en est
        # reconstruite ; l'inverse : lire les widgets pour connaître l'état,
        # rendrait toute modification dépendante de l'ordre de destruction.
        self._cards: list[list[int | None]] = [[None]]
        self._thumbnails: dict[int, np.ndarray] = {}
        self._grid = QGridLayout(self)
        self._grid.setSpacing(4)
        self._cells: dict[tuple[int, int], CardCell] = {}
        self._rebuild()

    # --- État -------------------------------------------------------------

    def set_thumbnails(self, thumbnails: dict[int, np.ndarray]) -> None:
        self._thumbnails = thumbnails
        self._rebuild()

    @property
    def rows(self) -> int:
        return len(self._cards)

    @property
    def cols(self) -> int:
        return len(self._cards[0])

    @property
    def shape(self) -> tuple[int, int]:
        """La forme, en (colonnes, lignes) : la convention de tout le projet."""
        return (self.cols, self.rows)

    def cards(self) -> list[int | None]:
        """Le contenu en ordre de lecture, tel que `Link` l'attend."""
        return [card for row in self._cards for card in row]

    def placed_cards(self) -> set[int]:
        return {card for card in self.cards() if card is not None}

    @property
    def complete(self) -> bool:
        return all(card is not None for card in self.cards())

    def empty_count(self) -> int:
        return sum(1 for card in self.cards() if card is None)

    def load(self, cards: tuple[int, ...], shape: tuple[int, int]) -> None:
        """Repose un lien existant dans la grille."""
        cols, rows = shape
        self._cards = [list(cards[r * cols:(r + 1) * cols]) for r in range(rows)]
        self._rebuild()
        self.changed.emit()

    # --- Modifications ----------------------------------------------------

    def place(self, row: int, col: int, index: int) -> None:
        """Pose une carte, en la retirant de la case qu'elle occupait déjà.

        Une carte ne peut figurer qu'une fois dans un lien : sans ce retrait,
        déplacer une carte la laisserait des deux côtés, et `Link` refuserait le
        résultat par une exception au moment de valider.
        """
        for r, ligne in enumerate(self._cards):
            for c, carte in enumerate(ligne):
                if carte == index:
                    self._cards[r][c] = None
        self._cards[row][col] = index
        self._refresh_cells()
        self.changed.emit()

    def clear_cell(self, row: int, col: int) -> None:
        self._cards[row][col] = None
        self._refresh_cells()
        self.changed.emit()

    def add_row(self) -> None:
        if self.rows >= MAX_SIDE:
            return
        self._cards.append([None] * self.cols)
        self._rebuild()
        self.changed.emit()

    def add_col(self) -> None:
        if self.cols >= MAX_SIDE:
            return
        for ligne in self._cards:
            ligne.append(None)
        self._rebuild()
        self.changed.emit()

    def remove_row(self, row: int) -> None:
        """Supprime une rangée. Ses cartes repartent dans la palette."""
        if self.rows <= 1:
            return
        del self._cards[row]
        self._rebuild()
        self.changed.emit()

    def remove_col(self, col: int) -> None:
        if self.cols <= 1:
            return
        for ligne in self._cards:
            del ligne[col]
        self._rebuild()
        self.changed.emit()

    # --- Disposition ------------------------------------------------------

    def _clear_layout(self) -> None:
        while self._grid.count():
            item = self._grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

    def _rebuild(self) -> None:
        """Reconstruit la disposition entière.

        Reconstruire plutôt que rapiécer : la grille compte au plus seize
        éléments, et un ajout ou un retrait déplace les boutons « − » de toutes
        les rangées suivantes. Rapiécer coûterait plus de code qu'il n'en économise.
        """
        self._clear_layout()
        self._cells.clear()

        # Rangée 0 : ajouter une ligne, centré au-dessus des cases.
        if self.rows < MAX_SIDE:
            self._add_row_button = QPushButton("＋")
            self._add_row_button.setToolTip(self.tr("Ajouter une ligne"))
            self._add_row_button.setFixedWidth(40)
            self._add_row_button.clicked.connect(self.add_row)
            self._grid.addWidget(self._add_row_button, 0, 1, 1, self.cols,
                                 Qt.AlignCenter)

        for r in range(self.rows):
            # Colonne 0 : retirer cette rangée. Jamais la dernière.
            if self.rows > 1:
                moins = QPushButton("－")
                moins.setToolTip(self.tr("Supprimer cette ligne"))
                moins.setFixedSize(26, 26)
                moins.clicked.connect(lambda _=False, row=r: self.remove_row(row))
                self._grid.addWidget(moins, r + 1, 0, Qt.AlignCenter)

            for c in range(self.cols):
                cell = CardCell(r, c)
                cell.dropped.connect(self.place)
                cell.cleared.connect(self.clear_cell)
                self._cells[(r, c)] = cell
                self._grid.addWidget(cell, r + 1, c + 1)

        # Dernière colonne : ajouter une colonne, centré à droite des cases.
        if self.cols < MAX_SIDE:
            self._add_col_button = QPushButton("＋")
            self._add_col_button.setToolTip(self.tr("Ajouter une colonne"))
            self._add_col_button.setFixedHeight(40)
            self._add_col_button.clicked.connect(self.add_col)
            self._grid.addWidget(self._add_col_button, 1, self.cols + 1,
                                 self.rows, 1, Qt.AlignCenter)

        # Dernière rangée : retirer une colonne. Jamais la dernière.
        if self.cols > 1:
            for c in range(self.cols):
                moins = QPushButton("－")
                moins.setToolTip(self.tr("Supprimer cette colonne"))
                moins.setFixedSize(26, 26)
                moins.clicked.connect(lambda _=False, col=c: self.remove_col(col))
                self._grid.addWidget(moins, self.rows + 1, c + 1, Qt.AlignCenter)

        self._refresh_cells()

    def _refresh_cells(self) -> None:
        for (r, c), cell in self._cells.items():
            index = self._cards[r][c]
            cell.set_card(index, self._thumbnails.get(index)
                          if index is not None else None)


class GridPanel(QWidget):
    """La grille, avec le titre et le rappel de ce qui manque."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.grid = LinkGrid()
        self.title = QLabel()
        self.hint = QLabel()
        self.hint.setWordWrap(True)
        self.hint.setAlignment(Qt.AlignCenter)
        layout = QVBoxLayout(self)
        layout.addWidget(self.title)
        layout.addStretch(1)
        layout.addWidget(self.grid, 0, Qt.AlignCenter)
        layout.addSpacing(12)
        # Le rappel accompagne la grille au lieu d'être plaqué en bas : épinglé
        # au pied du panneau, il se retrouvait à cinq cents pixels des cases
        # qu'il commente, séparé par un vide.
        layout.addWidget(self.hint)
        layout.addStretch(1)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
