"""Étape 1 — choix des cartes qui composeront la mosaïque."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QFileDialog, QHBoxLayout, QLabel, QListWidget,
    QListWidgetItem, QProgressBar, QPushButton, QSplitter, QVBoxLayout, QWidget,
)

from .gallery import CardGallery
from .loader import start_loading
from .session import Session


class CardsStep(QWidget):
    """Galerie des cartes, sélection par carte ou par dossier."""

    status_message = Signal(str)

    def __init__(self, session: Session, parent=None):
        super().__init__(parent)
        self._session = session
        self._thread = None
        self._worker = None
        self._build()
        session.selection_changed.connect(self._update_counts)
        session.cards_added.connect(self._refresh_folder_counts)
        session.loading_started.connect(self._fill_folders)

    # --- Construction -----------------------------------------------------

    def _build(self) -> None:
        self._folder_label = QLabel()
        self._folders = QListWidget()
        self._folders.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self._folders.itemSelectionChanged.connect(self._apply_filter)
        self._include_folder = QPushButton()
        self._exclude_folder = QPushButton()
        self._show_all = QPushButton()
        self._include_folder.clicked.connect(lambda: self._set_folders(False))
        self._exclude_folder.clicked.connect(lambda: self._set_folders(True))
        self._show_all.clicked.connect(self._folders.clearSelection)

        left = QVBoxLayout()
        left.addWidget(self._folder_label)
        left.addWidget(self._folders, 1)
        buttons = QHBoxLayout()
        buttons.addWidget(self._include_folder)
        buttons.addWidget(self._exclude_folder)
        left.addLayout(buttons)
        left.addWidget(self._show_all)
        left_panel = QWidget()
        left_panel.setLayout(left)

        self._gallery = CardGallery(self._session)
        self._hint = QLabel()
        self._hint.setWordWrap(True)

        right = QVBoxLayout()
        right.addWidget(self._hint)
        right.addWidget(self._gallery, 1)
        right_panel = QWidget()
        right_panel.setLayout(right)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([220, 780])

        self._choose_folder = QPushButton()
        self._choose_folder.clicked.connect(self._pick_folder)
        self._count = QLabel()
        self._progress = QProgressBar()
        self._progress.hide()

        top = QHBoxLayout()
        top.addWidget(self._choose_folder)
        top.addWidget(self._count, 1)
        top.addWidget(self._progress, 1)

        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addWidget(splitter, 1)
        self.retranslate_ui()

    def retranslate_ui(self) -> None:
        self._folder_label.setText(self.tr("Dossiers"))
        self._include_folder.setText(self.tr("Inclure"))
        self._exclude_folder.setText(self.tr("Exclure"))
        self._show_all.setText(self.tr("Afficher tous les dossiers"))
        self._choose_folder.setText(self.tr("Choisir le dossier de cartes…"))
        self._hint.setText(
            self.tr("Cliquez une carte pour l'inclure ou l'exclure. "
                    "Sélectionnez un dossier pour n'afficher que ses cartes.")
        )
        self._update_counts()
        self._fill_folders()

    # --- Chargement -------------------------------------------------------

    def _pick_folder(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self, self.tr("Dossier contenant les cartes")
        )
        if directory:
            self.load(directory)

    def load(self, directory: str) -> None:
        self._progress.show()
        self._progress.setRange(0, 0)  # indéterminé le temps de lire les en-têtes
        self._choose_folder.setEnabled(False)
        self.status_message.emit(self.tr("Chargement des cartes…"))
        self._session.start_loading(directory)
        self._thread, self._worker = start_loading(
            self, directory, self._on_progress, self._on_folder_loaded,
            self._on_loaded, self._on_failed,
        )

    def _on_progress(self, done: int, total: int) -> None:
        self._progress.setRange(0, total)
        self._progress.setValue(done)

    def _on_folder_loaded(self, folder: str, cards: list) -> None:
        """Un dossier vient d'être décodé : on l'affiche sans attendre la suite."""
        self._session.append_cards(cards)

    def _on_loaded(self, card_set) -> None:
        self._progress.hide()
        self._choose_folder.setEnabled(True)
        self._session.finish_loading(card_set)
        self.status_message.emit(
            self.tr("%n carte(s) chargée(s).", "", len(card_set))
        )

    def _on_failed(self, message: str) -> None:
        self._progress.hide()
        self._choose_folder.setEnabled(True)
        self.status_message.emit(self.tr("Échec du chargement : %1").replace("%1", message))

    # --- Dossiers et compteurs -------------------------------------------

    def _fill_folders(self) -> None:
        self._folders.clear()
        self._refresh_folder_counts()

    def _refresh_folder_counts(self) -> None:
        """Ajoute les dossiers au fur et à mesure de leur arrivée.

        On n'efface pas la liste : la sélection de l'utilisateur, donc le filtre
        en cours, doit survivre à l'arrivée d'un nouveau dossier.
        """
        known = {self._folders.item(row).data(Qt.UserRole)
                 for row in range(self._folders.count())}
        for folder in self._session.folders():
            count = len(self._session.indices_in_folder(folder))
            if folder in known:
                for row in range(self._folders.count()):
                    item = self._folders.item(row)
                    if item.data(Qt.UserRole) == folder:
                        item.setText(f"{folder}  ({count})")
                        break
                continue
            item = QListWidgetItem(f"{folder}  ({count})")
            item.setData(Qt.UserRole, folder)
            self._folders.addItem(item)

    def _selected_folders(self):
        return {item.data(Qt.UserRole) for item in self._folders.selectedItems()}

    def _apply_filter(self) -> None:
        self._gallery.set_folder_filter(self._selected_folders())
        self._update_counts()

    def _set_folders(self, excluded: bool) -> None:
        indices = []
        for folder in self._selected_folders():
            indices.extend(self._session.indices_in_folder(folder))
        if indices:
            self._session.set_excluded(indices, excluded)

    def _update_counts(self) -> None:
        total = self._session.total_cards
        if not total:
            self._count.setText(self.tr("Aucune carte chargée"))
            return
        text = (self.tr("%1 cartes retenues sur %2")
                .replace("%1", str(self._session.selected_count))
                .replace("%2", str(total)))
        folders = self._selected_folders()
        if len(folders) == 1:
            # Un seul dossier : son nom est plus parlant qu'un décompte.
            text += "  —  " + self.tr("filtré sur %1").replace("%1", next(iter(folders)))
        elif folders:
            text += "  —  " + self.tr("filtré sur %n dossiers", "", len(folders))
        self._count.setText(text)
