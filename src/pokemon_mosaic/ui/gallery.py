"""Modèle et vue de la galerie de cartes."""


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
    """Expose les cartes de la session, filtrées par dossier.

    `_visible` fait le lien entre les lignes affichées et les indices de cartes :
    filtrer ne change jamais l'indice d'une carte, seulement ce qu'on en montre.
    """

    def __init__(self, session: Session):
        super().__init__()
        self._session = session
        self._pixmaps = {}
        self._folders = None          # None = tous les dossiers
        self._visible: list[int] = []
        session.loading_started.connect(self._reset)
        session.cards_added.connect(self._on_cards_added)
        session.selection_changed.connect(self._refresh_all)
        # Une session peut déjà contenir des cartes : sans cela, un modèle créé
        # après le chargement afficherait une galerie vide.
        self._rebuild()

    # --- Filtrage ---------------------------------------------------------

    def set_folder_filter(self, folders: set[str] | None) -> None:
        """Restreint l'affichage à ces dossiers ; None les montre tous."""
        self._folders = folders or None
        self._rebuild()

    def _passes(self, card_index: int) -> bool:
        if self._folders is None:
            return True
        return self._session.folder_of(card_index) in self._folders

    def _rebuild(self) -> None:
        self.beginResetModel()
        self._visible = [
            card.index for card in (self._session.card_set or [])
            if self._passes(card.index)
        ]
        self.endResetModel()

    # --- Arrivée des cartes ----------------------------------------------

    def _reset(self) -> None:
        self.beginResetModel()
        self._pixmaps.clear()
        self._visible = []
        self.endResetModel()

    def _on_cards_added(self, indices) -> None:
        """Insère à la fin, sans réinitialiser : le défilement et la sélection
        de l'utilisateur survivent à l'arrivée d'un nouveau dossier."""
        accepted = [i for i in indices if self._passes(i)]
        if not accepted:
            return
        start = len(self._visible)
        self.beginInsertRows(QModelIndex(), start, start + len(accepted) - 1)
        self._visible.extend(accepted)
        self.endInsertRows()

    def _refresh_all(self) -> None:
        if self.rowCount():
            top, bottom = self.index(0), self.index(self.rowCount() - 1)
            self.dataChanged.emit(top, bottom, [Qt.DecorationRole, Qt.ToolTipRole])

    # --- Données ----------------------------------------------------------

    def card_index_at(self, row: int) -> int | None:
        return self._visible[row] if 0 <= row < len(self._visible) else None

    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self._visible)

    def data(self, index: QModelIndex, role=Qt.DisplayRole):
        if not index.isValid() or not self._session.card_set:
            return None
        card = self._session.card_set[self._visible[index.row()]]

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

    def set_folder_filter(self, folders) -> None:
        self.model().set_folder_filter(folders)

    def _on_clicked(self, index: QModelIndex) -> None:
        model = self.model()
        selected = self.selectionModel().selectedIndexes()
        # Un clic sur une sélection multiple bascule tout le lot, ce qui évite de
        # devoir cliquer les cartes une par une après un rectangle de sélection.
        rows = [i.row() for i in selected] if len(selected) > 1 else [index.row()]
        cards = [model.card_index_at(row) for row in rows]
        cards = [c for c in cards if c is not None]
        clicked = model.card_index_at(index.row())
        if clicked is None:
            return
        self._session.set_excluded(cards, not self._session.is_excluded(clicked))
