"""Étape 1 — choix des cartes qui composeront la mosaïque."""

import os

from PySide6.QtCore import QEvent, QStandardPaths, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..paths import APP_NAME
from . import theme
from .downloader import start_download
from .gallery import CardGallery
from .links_panel import LinksPanel
from .loader import start_loading
from .session import Session

# L'annulation étant vérifiée à chaque fichier, l'arrêt prend quelques
# millisecondes ; ce délai n'est qu'un filet.
SHUTDOWN_TIMEOUT_MS = 5000
# Un téléchargement s'arrête entre deux archives, pas au milieu de l'une : le
# délai doit couvrir la fin de l'archive en cours.
DOWNLOAD_SHUTDOWN_MS = 15000


def proposed_cards_dir() -> str:
    """Où proposer de déposer les cartes.

    `QStandardPaths` sait localiser « Images » dans la langue et l'arborescence
    de l'utilisateur, sur les trois systèmes — inutile d'écrire une règle par
    plateforme. Un dossier visible et sauvegardé, plutôt qu'un recoin de données
    applicatives que personne ne va voir.
    """
    base = QStandardPaths.writableLocation(QStandardPaths.PicturesLocation)
    return os.path.join(base or os.path.expanduser("~"), APP_NAME, "cartes")


class CardsStep(QWidget):
    """Galerie des cartes, sélection par carte ou par dossier."""

    status_message = Signal(str)

    # Émis quand le dossier de cartes change : la fenêtre le mémorise.
    folder_changed = Signal(str)

    def __init__(self, session: Session, parent=None):
        super().__init__(parent)
        self._session = session
        self._thread = None
        self._worker = None
        self._download_thread = None
        self._download_worker = None
        # Dossier visé par le téléchargement en cours, à charger une fois qu'il
        # est fini. Distinct de `session.data_dir`, qui ne bascule qu'au premier
        # lot réellement lu.
        self._download_dir = None
        # Vrai tant qu'aucun lot n'est arrivé du chargement en cours : la session
        # ne sera vidée qu'à ce moment-là.
        self._awaiting_first_batch = False
        self._build()
        session.selection_changed.connect(self._update_counts)
        session.cards_added.connect(self._refresh_folder_counts)
        session.loading_started.connect(self._fill_folders)
        # Un nouveau jeu de cartes s'ouvre en entier : garder la recherche
        # précédente montrerait une galerie presque vide sans dire pourquoi.
        session.loading_started.connect(self._search.clear)
        session.cards_added.connect(self._update_state)
        session.cards_added.connect(self._update_bulk_labels)
        self._update_state()

    # --- Construction -----------------------------------------------------

    def _build(self) -> None:
        # Les lignes déjà posées, par série et par dossier : l'arbre se remplit
        # au fur et à mesure du chargement, sans être reconstruit.
        self._series_items: dict[str, QTreeWidgetItem] = {}
        self._folder_items: dict[str, QTreeWidgetItem] = {}
        self._folder_label = QLabel()
        # ⚠️ **Un arbre, et non plus une liste.** Les extensions se rangent par
        # série — « A1 », « A1a » et la promo A sont la série A —, et c'est
        # ainsi qu'on les cherche : par série d'abord, extension ensuite. Vingt
        # dossiers à plat obligeaient à lire chaque nom pour savoir où l'on en
        # était. Sélectionner une série vise toutes ses extensions.
        self._folders = QTreeWidget()
        self._folders.setHeaderHidden(True)
        self._folders.setSelectionMode(QAbstractItemView.ExtendedSelection)
        # Au pixel et non par ligne entière : au trackpad, le mode par élément
        # saute une extension au moindre geste au lieu de la découvrir.
        self._folders.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        # ⚠️ **Marge de défilement automatique nulle.** Qt en réserve seize
        # pixels *à l'intérieur* de la vue : cliquer l'extension à demi coupée du
        # bas tombe forcément dedans, et tant que le bouton reste enfoncé la
        # liste dévale jusqu'en bas — mesuré, 210 crans sur 242. À zéro, la bande
        # sensible passe hors de la vue : le clic ne déclenche plus rien, et
        # glisser *sous* la liste pour prolonger une sélection continue de faire
        # défiler. Couper `setAutoScroll` supprimerait aussi ce second geste.
        self._folders.setAutoScrollMargin(0)
        self._folders.itemSelectionChanged.connect(self._apply_filter)
        self._folders.itemSelectionChanged.connect(self._update_folder_buttons)
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
        self._left_panel = QSplitter(Qt.Vertical)
        self._left_panel.addWidget(folders_panel)
        self._left_panel.addWidget(self._links)
        self._left_panel.setStretchFactor(0, 1)
        self._left_panel.setSizes([420, 300])
        left_panel = self._left_panel

        self._gallery = CardGallery(self._session)
        self._hint = QLabel()
        self._hint.setWordWrap(True)

        # La recherche vit au-dessus de la galerie, et non dans la barre du haut :
        # elle ne commande qu'elle. Le bouton d'effacement intégré évite d'avoir
        # à sélectionner le texte pour revenir à la galerie entière.
        self._search = QLineEdit()
        self._search.setClearButtonEnabled(True)
        theme.mark(self._search, "search")
        self._search.textChanged.connect(self._apply_filter)

        # Tant qu'aucune carte n'est chargée, la galerie n'a rien à montrer et
        # les boutons du haut n'ont rien sur quoi agir. On met à sa place les
        # deux seules actions qui aient un sens, au centre, plutôt qu'une grande
        # zone vide et une barre d'outils inerte.
        self._empty_title = QLabel()
        self._empty_title.setAlignment(Qt.AlignCenter)
        police = self._empty_title.font()
        police.setPointSize(police.pointSize() + 4)
        police.setBold(True)
        self._empty_title.setFont(police)
        self._empty_hint = QLabel()
        self._empty_hint.setAlignment(Qt.AlignCenter)
        self._empty_hint.setWordWrap(True)
        self._download = QPushButton()
        self._download.clicked.connect(self._pick_download_folder)
        self._locate = QPushButton()
        self._locate.clicked.connect(self._pick_folder)
        for bouton in (self._download, self._locate):
            bouton.setMinimumWidth(320)
            bouton.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        vide = QVBoxLayout()
        vide.addStretch(1)
        vide.addWidget(self._empty_title)
        vide.addWidget(self._empty_hint)
        vide.addSpacing(24)
        vide.addWidget(self._download, 0, Qt.AlignCenter)
        vide.addWidget(self._locate, 0, Qt.AlignCenter)
        vide.addStretch(1)
        self._empty_page = QWidget()
        self._empty_page.setLayout(vide)

        # Ils portent sur **ce que la galerie montre**, filtres compris : c'est
        # ce que leur position dessus laisse entendre, et le seul geste de masse
        # à portée quand une recherche a réduit l'affichage. Le libellé le dit
        # dès qu'un filtre est actif, pour qu'on ne les lise pas comme globaux.
        self._include_all = QPushButton()
        self._exclude_all = QPushButton()
        self._invert = QPushButton()
        self._include_all.clicked.connect(lambda: self._set_all(False))
        self._exclude_all.clicked.connect(lambda: self._set_all(True))
        self._invert.clicked.connect(self._invert_selection)

        # Ils agissent sur la galerie : ils se posent **dessus**, en bas à
        # droite, plutôt que dans la barre du haut d'où ils commandaient de loin
        # une zone qu'ils ne touchaient pas.
        self._bulk = QWidget(self._gallery)
        theme.mark(self._bulk, "floating-bar")
        bulk_row = QHBoxLayout(self._bulk)
        bulk_row.setContentsMargins(6, 5, 6, 5)
        bulk_row.setSpacing(6)
        bulk_row.addWidget(self._include_all)
        bulk_row.addWidget(self._exclude_all)
        bulk_row.addWidget(self._invert)
        self._gallery.installEventFilter(self)

        self._pages = QStackedWidget()
        self._pages.addWidget(self._empty_page)   # 0
        self._pages.addWidget(self._gallery)      # 1

        # Sous la liste des cartes, pleine largeur, et non dans une boîte de
        # dialogue : ce n'est pas une erreur qui arrête quoi que ce soit, c'est
        # un état du jeu de cartes qu'il faut pouvoir relire en travaillant.
        # La colonne de gauche a été essayée d'abord : le texte y était écrasé
        # entre deux listes et coupé en plein mot.
        self._warnings = QLabel()
        self._warnings.setWordWrap(True)
        self._warnings.setTextFormat(Qt.PlainText)
        theme.mark(self._warnings, "banner")
        self._warnings.hide()

        right = QVBoxLayout()
        right.addWidget(self._hint)
        right.addWidget(self._search)
        right.addWidget(self._pages, 1)
        right.addWidget(self._warnings)
        right_panel = QWidget()
        right_panel.setLayout(right)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([300, 700])

        self._choose_folder = QPushButton()
        self._choose_folder.clicked.connect(self._pick_folder)
        self._update_catalogue = QPushButton()
        self._update_catalogue.clicked.connect(self._start_update)
        self._cancel = QPushButton()
        self._cancel.clicked.connect(self._cancel_download)
        self._cancel.hide()
        self._count = QLabel()
        self._progress = QProgressBar()
        self._progress.hide()

        top = QHBoxLayout()
        top.addWidget(self._choose_folder)
        top.addWidget(self._update_catalogue)
        top.addWidget(self._count, 1)
        top.addWidget(self._progress, 1)
        top.addWidget(self._cancel)

        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addWidget(splitter, 1)
        self.retranslate_ui()

    def retranslate_ui(self) -> None:
        self._folder_label.setText(self.tr("Dossiers"))
        self._include_folder.setText(self.tr("Inclure l'extension"))
        self._exclude_folder.setText(self.tr("Exclure l'extension"))
        self._show_all.setText(self.tr("Afficher tous les dossiers"))
        self._choose_folder.setText(self.tr("Choisir le dossier de cartes…"))
        self._update_catalogue.setText(self.tr("Mettre à jour le catalogue"))
        self._update_catalogue.setToolTip(
            self.tr("Relit la liste des cartes publiée et récupère celles qui "
                    "manquent au dossier."))
        self._cancel.setText(self.tr("Annuler"))
        self._empty_title.setText(self.tr("Aucune carte chargée"))
        self._empty_hint.setText(
            self.tr("Les illustrations ne sont pas fournies avec l'application. "
                    "Téléchargez-les, ou désignez un dossier qui les contient "
                    "déjà."))
        self._download.setText(self.tr("Télécharger les cartes…"))
        self._locate.setText(self.tr("J'ai déjà les cartes : choisir le dossier…"))
        self._update_bulk_labels()
        self._hint.setText(
            self.tr("Cliquez une carte pour l'inclure ou l'exclure. "
                    "Sélectionnez un dossier pour n'afficher que ses cartes.")
        )
        self._search.setPlaceholderText(self.tr("Rechercher une carte par nom…"))
        self._links.retranslate_ui()
        self._update_counts()
        # Pas de _fill_folders() ici : les noms de dossiers sont des chemins, pas
        # des textes traduits. Le rappeler viderait la liste et détruirait la
        # sélection, donc le filtre en cours, pour rien.

    # Marge entre les boutons posés sur la galerie et ses bords. La barre de
    # défilement est contournée par sa largeur réelle : la supposer absente les
    # ferait passer dessous dès que la galerie déborde.
    BULK_MARGIN = 8

    def eventFilter(self, watched, event):
        """Replace les boutons posés sur la galerie à chaque redimensionnement.

        Un widget enfant ne suit aucune disposition : sans cela, il resterait au
        coin haut-gauche et sortirait du cadre à la première fenêtre agrandie.
        """
        if watched is self._gallery and event.type() in (
                QEvent.Resize, QEvent.Show):
            self._place_bulk_buttons()
        return super().eventFilter(watched, event)

    def _place_bulk_buttons(self) -> None:
        barre = self._gallery.verticalScrollBar()
        largeur_barre = barre.width() if barre.isVisible() else 0
        taille = self._bulk.sizeHint()
        self._bulk.setGeometry(
            self._gallery.width() - taille.width() - largeur_barre
            - self.BULK_MARGIN,
            self._gallery.height() - taille.height() - self.BULK_MARGIN,
            taille.width(), taille.height())
        self._bulk.raise_()

    # --- État de l'écran --------------------------------------------------

    def _update_state(self) -> None:
        """Montre la galerie ou l'état vide, et n'active que ce qui a un sens.

        Appelée à chaque arrivée de cartes et non seulement en fin de chargement :
        la galerie se remplit par lots, et rester sur l'écran vide jusqu'au
        dernier donnerait l'impression que rien ne se passe.
        """
        garni = self._session.total_cards > 0
        self._pages.setCurrentIndex(1 if garni else 0)
        # Deux listes vides sur trois cents pixels ne disent rien et détournent
        # l'œil des deux seules actions possibles. On les retire tant qu'elles
        # n'ont rien à montrer.
        self._left_panel.setVisible(garni)
        for bouton in (self._include_all, self._exclude_all, self._invert,
                       self._show_all):
            bouton.setEnabled(garni)
        self._bulk.setVisible(garni)
        self._update_folder_buttons()
        self._hint.setVisible(garni)
        self._search.setVisible(garni)
        # La mise à jour vise un dossier : sans dossier connu, elle n'a pas de
        # cible. Le bouton de l'état vide, lui, en demande un.
        self._update_catalogue.setEnabled(bool(self._session.data_dir))
        self._update_catalogue.setVisible(garni)

    def _show_warnings(self, card_set) -> None:
        """Dit ce que le chargement a trouvé d'anormal, et pourquoi ça compte."""
        if not getattr(card_set, "has_warnings", False):
            self._warnings.hide()
            return
        lignes = []
        if card_set.odd_sizes:
            attendu = f"{card_set.full_size[0]}×{card_set.full_size[1]}"
            montres = card_set.odd_sizes[:5]
            detail = ", ".join(f"{w}×{h} ({n})"
                               for (w, h), n in
                               ((e.size, e.count) for e in montres))
            # La liste est tronquée mais le total les compte tous : sans cette
            # mention, les chiffres se contredisent et l'utilisateur ne peut pas
            # savoir s'il manque des lignes ou si le total est faux.
            reste = len(card_set.odd_sizes) - len(montres)
            if reste:
                detail += self.tr(", et %n autre(s) format(s)", "", reste)
            total = sum(e.count for e in card_set.odd_sizes)
            lignes.append(
                self.tr("%1 carte(s) ne sont pas au format %2 : %3. Elles seront "
                        "étirées à ce format, ce qui déforme l'illustration et "
                        "fausse les couleurs de bord dont l'assemblage se sert.")
                .replace("%1", str(total)).replace("%2", attendu)
                .replace("%3", detail))
        if card_set.unreadable:
            lignes.append(
                self.tr("%1 fichier(s) illisibles, ignorés : %2")
                .replace("%1", str(len(card_set.unreadable)))
                .replace("%2", ", ".join(card_set.unreadable[:3])))
        self._warnings.setText("⚠️ " + "\n\n⚠️ ".join(lignes))
        self._warnings.show()

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

    # --- Téléchargement ---------------------------------------------------

    def _pick_download_folder(self) -> None:
        """Demande où déposer les cartes, puis lance la récupération.

        Le dossier proposé est créé avant d'ouvrir le dialogue : celui-ci ne sait
        pas se placer dans un dossier qui n'existe pas, et retomberait sur le
        dernier emplacement visité — ce qui ferait perdre la proposition.
        """
        propose = proposed_cards_dir()
        try:
            os.makedirs(propose, exist_ok=True)
        except OSError:
            propose = os.path.expanduser("~")
        directory = QFileDialog.getExistingDirectory(
            self, self.tr("Où déposer les cartes"), propose)
        if directory:
            self._start_download(directory)

    def _start_update(self) -> None:
        """Complète le dossier déjà en place depuis le catalogue publié."""
        if self._session.data_dir:
            self._start_download(self._session.data_dir)

    def _start_download(self, directory: str) -> None:
        if self._download_thread is not None:
            return
        self._download_dir = directory
        self._progress.show()
        self._progress.setRange(0, 0)  # indéterminé le temps de lire le catalogue
        self._cancel.show()
        for bouton in (self._choose_folder, self._download, self._locate,
                       self._update_catalogue):
            bouton.setEnabled(False)
        self.status_message.emit(self.tr("Lecture du catalogue…"))
        self._download_thread, self._download_worker = start_download(
            self, directory, self._on_download_progress, self._on_surveyed,
            self._on_downloaded, self._on_download_failed,
            self._on_download_cancelled)

    def _cancel_download(self) -> None:
        if self._download_worker is not None:
            self._download_worker.cancel()
            self._cancel.setEnabled(False)
            self.status_message.emit(self.tr("Arrêt demandé…"))

    def _on_surveyed(self, cartes: int, octets: int) -> None:
        if not cartes:
            self.status_message.emit(self.tr("Le dossier est déjà complet."))
            return
        self._progress.setRange(0, octets)
        self._progress.setValue(0)
        self.status_message.emit(
            self.tr("%1 carte(s) à récupérer, %2 Mo…")
            .replace("%1", str(cartes))
            .replace("%2", f"{octets / 1e6:.0f}"))

    def _on_download_progress(self, faits: int, total: int, jeu: str) -> None:
        self._progress.setRange(0, total)
        self._progress.setValue(faits)
        self.status_message.emit(
            self.tr("Téléchargement : %1").replace("%1", jeu))

    def _end_download(self) -> None:
        self._progress.hide()
        self._cancel.hide()
        self._cancel.setEnabled(True)
        for bouton in (self._choose_folder, self._download, self._locate):
            bouton.setEnabled(True)
        self._download_thread = self._download_worker = None
        self._update_state()

    def _on_downloaded(self, ecrites: int, failures: list) -> None:
        dossier = self._download_dir
        self._end_download()
        if failures:
            # Les échecs sont dits, mais on charge quand même ce qui est arrivé :
            # un dossier partiel reste utilisable, et le refuser en bloc pour une
            # extension manquante serait disproportionné.
            quoi, pourquoi = failures[0]
            self.status_message.emit(
                self.tr("%1 échec(s), dont %2 : %3")
                .replace("%1", str(len(failures)))
                .replace("%2", quoi).replace("%3", pourquoi))
        elif ecrites:
            self.status_message.emit(
                self.tr("%n carte(s) récupérée(s).", "", ecrites))
        if dossier:
            self.load(dossier)

    def _on_download_cancelled(self, ecrites: int) -> None:
        dossier = self._download_dir
        self._end_download()
        self.status_message.emit(
            self.tr("Téléchargement interrompu — %n carte(s) récupérée(s).",
                    "", ecrites))
        # Ce qui est arrivé est bon : chaque image a été vérifiée avant écriture.
        # Le dossier est simplement incomplet, et une relance le complètera.
        if dossier and ecrites:
            self.load(dossier)

    def _on_download_failed(self, message: str) -> None:
        self._end_download()
        self.status_message.emit(
            self.tr("Téléchargement impossible : %1").replace("%1", message))

    # --- Suites du chargement ---------------------------------------------

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
        self._show_warnings(card_set)
        self._update_state()
        if self._session.data_dir:
            self.folder_changed.emit(self._session.data_dir)
        self.status_message.emit(
            self.tr("%n carte(s) chargée(s).", "", len(card_set))
        )

    def _on_failed(self, message: str) -> None:
        self._progress.hide()
        self._choose_folder.setEnabled(True)
        # Rien n'a été vidé : la sélection et les liens précédents sont intacts.
        self._awaiting_first_batch = False
        self._update_state()
        self.status_message.emit(
            self.tr("Échec du chargement : %1").replace("%1", message)
        )

    def shutdown(self) -> bool:
        """Interrompt le chargement. Rend faux s'il ne s'est pas arrêté.

        Appelée à la fermeture de la fenêtre : détruire un QThread encore actif
        fait abandonner le processus par Qt.
        """
        # Les deux fils sont prévenus **avant** d'attendre l'un ou l'autre :
        # les arrêter l'un après l'autre ferait attendre le second en entier
        # alors qu'il aurait pu s'arrêter pendant l'attente du premier.
        for worker in (self._worker, self._download_worker):
            if worker is not None:
                worker.cancel()

        stopped = True
        for thread, delai in ((self._thread, SHUTDOWN_TIMEOUT_MS),
                              (self._download_thread, DOWNLOAD_SHUTDOWN_MS)):
            if thread is not None and thread.isRunning():
                thread.quit()
                stopped = thread.wait(delai) and stopped

        if not stopped:
            # Lâcher la référence d'un fil encore actif rouvrirait le crash que
            # cette méthode existe pour éviter. On la garde et on le signale.
            # `status_message` et non `print` : depuis un paquet `.app`, la
            # sortie standard ne va nulle part que l'utilisateur puisse lire.
            self.status_message.emit(
                self.tr("Arrêt en cours : le chargement ne répond pas encore.")
            )
            return False
        self._thread = self._worker = None
        self._download_thread = self._download_worker = None
        return True

    # --- Dossiers et compteurs -------------------------------------------

    def _fill_folders(self) -> None:
        self._folders.clear()
        self._series_items = {}
        self._folder_items = {}
        self._refresh_folder_counts()

    def _refresh_folder_counts(self) -> None:
        """Ajoute les dossiers au fur et à mesure de leur arrivée.

        On n'efface pas l'arbre : la sélection de l'utilisateur, donc le filtre
        en cours, doit survivre à l'arrivée d'un nouveau dossier.
        """
        for serie, dossiers in self._session.folders_by_series():
            parent = self._series_item(serie)
            total = 0
            for folder in dossiers:
                count = len(self._session.indices_in_folder(folder))
                total += count
                self._folder_item(folder, parent).setText(
                    0, f"{folder}  ({count})")
            if parent is not None:
                parent.setText(0, self.tr("Série %1  (%2)")
                               .replace("%1", serie).replace("%2", str(total)))

    def _series_item(self, serie: str):
        """La ligne d'une série, créée à sa première extension.

        `None` pour les dossiers sans série : un dossier choisi à la main ne
        suit aucune convention de nommage, et se pose donc à la racine.
        """
        if not serie:
            return None
        if serie not in self._series_items:
            # ⚠️ **Insérée à sa place, non ajoutée à la fin.** Les dossiers
            # arrivent dans l'ordre où le système les rend — `os.walk` ne trie
            # pas les répertoires —, si bien qu'une série découverte plus tard
            # se serait posée sous une série qui lui succède. Les séries
            # occupent ainsi toujours les premiers rangs, dans l'ordre, et les
            # dossiers sans série restent à la suite.
            rang = sum(1 for autre in self._series_items if autre < serie)
            item = QTreeWidgetItem()
            self._folders.insertTopLevelItem(rang, item)
            police = item.font(0)
            police.setBold(True)
            item.setFont(0, police)
            item.setExpanded(True)
            self._series_items[serie] = item
        return self._series_items[serie]

    def _folder_item(self, folder: str, parent):
        if folder not in self._folder_items:
            item = (QTreeWidgetItem(parent) if parent is not None
                    else QTreeWidgetItem(self._folders))
            item.setData(0, Qt.UserRole, folder)
            self._folder_items[folder] = item
        return self._folder_items[folder]

    def _invert_selection(self) -> None:
        """Les cartes affichées changent de camp, chacune la sienne."""
        cartes = self._gallery.visible_cards()
        if cartes:
            self._session.invert_excluded(cartes)

    def _set_all(self, excluded: bool) -> None:
        """Agit sur les cartes affichées — filtre par extension et recherche compris.

        Elles portaient auparavant sur tout le jeu chargé. Sans recherche c'était
        sans danger : les boutons « Inclure l'extension » couvraient le besoin
        ciblé. Avec elle, chercher « dracaufeu » puis cliquer « Tout exclure »
        effaçait la sélection entière — mesuré, 40 cartes exclues au lieu de 10.
        """
        cartes = self._gallery.visible_cards()
        if cartes:
            self._session.set_excluded(cartes, excluded)

    def _update_folder_buttons(self) -> None:
        """« Inclure l'extension » n'a de cible que si l'on en a désigné une.

        Actifs sans sélection, ils ne faisaient rien : le clic partait dans le
        vide et l'utilisateur croyait à une panne."""
        vise = bool(self._session.total_cards and self._selected_folders())
        self._include_folder.setEnabled(vise)
        self._exclude_folder.setEnabled(vise)

    def _selected_folders(self):
        """Les dossiers visés, une série valant toutes ses extensions."""
        dossiers = set()
        for item in self._folders.selectedItems():
            propre = item.data(0, Qt.UserRole)
            if propre:
                dossiers.add(propre)
            for rang in range(item.childCount()):
                enfant = item.child(rang).data(0, Qt.UserRole)
                if enfant:
                    dossiers.add(enfant)
        return dossiers

    def _filtering(self) -> bool:
        return bool(self._selected_folders() or self._search.text().strip())

    def _update_bulk_labels(self) -> None:
        """Nomme la cible des boutons de masse quand elle n'est plus tout le jeu.

        « Tout exclure » au-dessus de dix résultats de recherche se lit comme
        « ces dix-là ». Le libellé chiffré retire l'ambiguïté dans les deux sens.
        """
        if self._filtering():
            combien = self._gallery.visible_count()
            self._include_all.setText(
                self.tr("Inclure les %n affichée(s)", "", combien))
            self._exclude_all.setText(
                self.tr("Exclure les %n affichée(s)", "", combien))
        else:
            self._include_all.setText(self.tr("Tout inclure"))
            self._exclude_all.setText(self.tr("Tout exclure"))
        # « Inverser » garde un libellé court : il partage la portée de ses deux
        # voisins, que leur propre libellé annonce déjà, et trois intitulés
        # chiffrés feraient déborder la barre du cadre de la galerie.
        self._invert.setText(self.tr("Inverser"))
        self._invert.setToolTip(
            self.tr("Les cartes affichées changent de camp : les incluses "
                    "sortent, les exclues rentrent.")
            if self._filtering() else
            self.tr("Toutes les cartes changent de camp : les incluses "
                    "sortent, les exclues rentrent.")
        )
        # Le libellé change de longueur : la barre flottante doit se replacer,
        # sinon elle déborde du bord droit de la galerie ou s'en décolle.
        self._bulk.adjustSize()
        self._place_bulk_buttons()

    def _apply_filter(self) -> None:
        self._gallery.set_folder_filter(self._selected_folders())
        self._gallery.set_name_filter(self._search.text().strip())
        self._update_bulk_labels()
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
        # Une recherche qui ne rend rien doit se lire dans le compteur : une
        # galerie vide sans explication passe pour un chargement raté.
        if self._search.text().strip():
            text += "  —  " + self.tr("%n carte(s) trouvée(s)", "",
                                      self._gallery.visible_count())
        self._count.setText(text)
