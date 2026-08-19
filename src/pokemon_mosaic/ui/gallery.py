"""Modèle et vue de la galerie de cartes."""

from typing import Optional

import numpy as np
from PySide6.QtCore import QAbstractListModel, QModelIndex, QSize, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPixmap
from PySide6.QtWidgets import QListView

from .session import Session

THUMB_WIDTH = 84
EXCLUDED_OPACITY = 0.25


def numpy_to_pixmap(array: np.ndarray) -> QPixmap:
    """Convertit une vignette RGB en QPixmap.

    `QImage` ne copie pas le tampon qu'on lui passe : sans `.copy()`, l'image
    pointerait sur une mémoire numpy susceptible d'être libérée.
    """
    array = np.ascontiguousarray(array)
    height, width, _ = array.shape
    image = QImage(array.data, width, height, 3 * width, QImage.Format_RGB888)
    return QPixmap.fromImage(image.copy())


class CardGalleryModel(QAbstractListModel):
    """Expose les cartes de la session, avec leur état inclus / exclu."""

    def __init__(self, session: Session):
        super().__init__()
        self._session = session
        self._pixmaps = {}
        session.cards_loaded.connect(self._reset)
        session.selection_changed.connect(self._refresh_all)

    def _reset(self) -> None:
        self.beginResetModel()
        self._pixmaps.clear()
        self.endResetModel()

    def _refresh_all(self) -> None:
        if self.rowCount():
            top, bottom = self.index(0), self.index(self.rowCount() - 1)
            self.dataChanged.emit(top, bottom, [Qt.DecorationRole, Qt.ToolTipRole])

    def rowCount(self, parent=QModelIndex()) -> int:
        return self._session.total_cards

    def data(self, index: QModelIndex, role=Qt.DisplayRole):
        if not index.isValid() or not self._session.card_set:
            return None
        card = self._session.card_set[index.row()]

        if role == Qt.DecorationRole:
            return self._pixmap_for(card.index)
        if role == Qt.ToolTipRole:
            state = "exclue" if self._session.is_excluded(card.index) else "incluse"
            return f"{card.name}\n{self._session.folder_of(card.index)}\n({state})"
        if role == Qt.UserRole:
            return card.index
        return None

    def _pixmap_for(self, card_index: int) -> QPixmap:
        excluded = self._session.is_excluded(card_index)
        key = (card_index, excluded)
        if key in self._pixmaps:
            return self._pixmaps[key]

        card = self._session.card_set[card_index]
        pixmap = numpy_to_pixmap(card.thumbnail).scaledToWidth(
            THUMB_WIDTH, Qt.SmoothTransformation
        )
        if excluded:
            # Une carte exclue reste lisible mais nettement effacée : on doit
            # pouvoir la retrouver pour la réinclure.
            faded = QPixmap(pixmap.size())
            faded.fill(QColor(0, 0, 0, 0))
            painter = QPainter(faded)
            painter.setOpacity(EXCLUDED_OPACITY)
            painter.drawPixmap(0, 0, pixmap)
            painter.end()
            pixmap = faded

        self._pixmaps[key] = pixmap
        return pixmap


class CardGallery(QListView):
    """Grille de vignettes ; un clic bascule l'inclusion d'une carte."""

    def __init__(self, session: Session, parent=None):
        super().__init__(parent)
        self._session = session
        self.setModel(CardGalleryModel(session))
        self.setViewMode(QListView.IconMode)
        self.setResizeMode(QListView.Adjust)
        self.setMovement(QListView.Static)
        self.setUniformItemSizes(True)
        self.setSelectionMode(QListView.ExtendedSelection)
        self.setSpacing(3)
        self.setIconSize(QSize(THUMB_WIDTH, int(THUMB_WIDTH * 984 / 713)))
        self.clicked.connect(self._on_clicked)

    def _on_clicked(self, index: QModelIndex) -> None:
        selected = self.selectionModel().selectedIndexes()
        # Un clic sur une sélection multiple bascule tout le lot, ce qui évite de
        # devoir cliquer les cartes une par une après un rectangle de sélection.
        rows = [i.row() for i in selected] if len(selected) > 1 else [index.row()]
        excluded = not self._session.is_excluded(index.row())
        self._session.set_excluded(rows, excluded)
