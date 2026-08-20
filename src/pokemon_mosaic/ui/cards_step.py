"""Étape 1 — choix des cartes qui composeront la mosaïque."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from .gallery import CardGallery
from .links_panel import LinksPanel
from .loader import start_loading
from .session import Session

# L'annulation étant vérifiée à chaque fichier, l'arrêt prend quelques
# millisecondes ; ce délai n'est qu'un filet.
SHUTDOWN_TIMEOUT_MS = 5000


class CardsStep(QWidget):
    """Galerie des cartes, sélection par carte ou par dossier."""

    status_message = Signal(str)

    def __init__(self, session: Session, parent=None):
        super().__init__(parent)
        self._session = session
        self._thread = None
        self._worker = None
        # Vrai tant qu'aucun lot n'est arrivé du chargement en cours : la session
        # ne sera vidée qu'à ce moment-là.
        self._awaiting_first_batch = False
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

        folders_layout = QVBoxLayout()
        folders_layout.setContentsMargins(0, 0, 0, 0)
        folders_layout.addWidget(self._folder_label)
        folders_layout.addWidget(self._folders, 1)
        buttons = QHBoxLayout()
        buttons.addWidget(self._include_folder)
        buttons.addWidget(self._exclude_folder)
        folders_layout.addLayout(buttons)
        folders_layout.addWidget(self._show_all)
        folders_panel = QWidget()
        folders_panel.setLayout(folders_layout)

        # Liens et dossiers partagent la colonne de gauche : un séparateur mobile
        # plutôt qu'un partage fixe, les deux listes n'ayant pas la même longueur
        # d'un jeu de cartes à l'autre.
        self._links = LinksPanel(self._session)
        left_panel = QSplitter(Qt.Vertical)
        left_panel.addWidget(folders_panel)
        left_panel.addWidget(self._links)
        left_panel.setStretchFactor(0, 1)
        left_panel.setSizes([420, 300])

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
        splitter.setSizes([300, 700])

        self._choose_folder = QPushButton()
        self._choose_folder.clicked.connect(self._pick_folder)
        # Actions globales, volontairement séparées des boutons du panneau de
        # gauche qui, eux, ne portent que sur les dossiers sélectionnés.
        self._include_all = QPushButton()
        self._exclude_all = QPushButton()
        self._include_all.clicked.connect(lambda: self._set_all(False))
        self._exclude_all.clicked.connect(lambda: self._set_all(True))
        self._count = QLabel()
        self._progress = QProgressBar()
        self._progress.hide()

        top = QHBoxLayout()
        top.addWidget(self._choose_folder)
        top.addWidget(self._include_all)
        top.addWidget(self._exclude_all)
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
        self._include_all.setText(self.tr("Tout inclure"))
        self._exclude_all.setText(self.tr("Tout exclure"))
        self._hint.setText(
            self.tr("Cliquez une carte pour l'inclure ou l'exclure. "
                    "Sélectionnez un dossier pour n'afficher que ses cartes.")
        )
        self._links.retranslate_ui()
        self._update_counts()
        # Pas de _fill_folders() ici : les noms de dossiers sont des chemins, pas
        # des textes traduits. Le rappeler viderait la liste et détruirait la
        # sélection, donc le filtre en cours, pour rien.

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
        # On ne vide surtout pas la session ici : `start_loading` efface les cartes,
        # la sélection ET les liens. Si le dossier se révélait inexploitable, tout
        # ce travail serait perdu alors que le message dirait seulement « échec du
        # chargement ». On attend le premier lot pour basculer.
        self._awaiting_first_batch = True
        self._pending_directory = directory
        self._thread, self._worker = start_loading(
            self, directory, self._on_progress, self._on_folder_loaded,
            self._on_loaded, self._on_failed,
            strip_size=self._session.strip_size,
        )

    def _on_progress(self, done: int, total: int) -> None:
        self._progress.setRange(0, total)
        self._progress.setValue(done)

    def _on_folder_loaded(self, folder: str, cards: list) -> None:
        """Un dossier vient d'être décodé : on l'affiche sans attendre la suite.

        C'est ici, et pas avant, que l'ancienne session est remplacée : à ce stade
        le nouveau chargement est acquis.
        """
        if self._awaiting_first_batch:
            self._session.start_loading(self._pending_directory)
            self._awaiting_first_batch = False
        self._session.append_cards(cards)

    def _on_loaded(self, card_set) -> None:
        self._progress.hide()
        self._choose_folder.setEnabled(True)
        self._awaiting_first_batch = False
        self._session.finish_loading(card_set)
        # Les liens fournis d'office ne peuvent être posés qu'une fois les cartes
        # connues : ils sont décrits par chemin, pas par indice.
        self._session.apply_default_links()
        self.status_message.emit(
            self.tr("%n carte(s) chargée(s).", "", len(card_set))
        )

    def _on_failed(self, message: str) -> None:
        self._progress.hide()
        self._choose_folder.setEnabled(True)
        # Rien n'a été vidé : la sélection et les liens précédents sont intacts.
        self._awaiting_first_batch = False
        self.status_message.emit(
            self.tr("Échec du chargement : %1").replace("%1", message)
        )

    def shutdown(self) -> None:
        """Interrompt proprement un chargement en cours.

        Appelée à la fermeture de la fenêtre : détruire un QThread encore actif
        fait abandonner le processus par Qt.
        """
        if self._worker is not None:
            self._worker.cancel()

        stopped = True
        if self._thread is not None and self._thread.isRunning():
            self._thread.quit()
            stopped = self._thread.wait(SHUTDOWN_TIMEOUT_MS)

        if not stopped:
            # Lâcher la référence d'un fil encore actif rouvrirait le crash que
            # cette méthode existe pour éviter. On la garde et on le signale.
            print("Le chargement ne s'est pas arrêté dans le délai imparti.")
            return
        self._thread = self._worker = None

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

    def _set_all(self, excluded: bool) -> None:
        """Agit sur toutes les cartes chargées, indépendamment du filtre affiché."""
        if self._session.card_set:
            self._session.set_excluded(
                [card.index for card in self._session.card_set], excluded
            )

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
