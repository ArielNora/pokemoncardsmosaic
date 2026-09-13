"""Le menu des agencements gardés : tout ce qui est enregistré, en un endroit.

Chaque agencement s'y voit en petit, avec une **croix rouge** sur les cartes que
le catalogue n'a pas, et la liste des cartes qu'il emploie, les manquantes
nommées. De là, on l'ouvre dans une case pour l'exporter, on l'envoie en JSON,
on en importe un, on le renomme ou on le jette.

⚠️ **Un agencement à qui il manque une carte ne s'ouvre pas.** Amputé, ce n'est
plus celui qu'on a partagé : la fenêtre le montre et dit ce qui manque, mais
elle ne le laisse pas passer à l'export.
"""

import os

import numpy as np
from PySide6.QtCore import QObject, QSize, Qt, QThreadPool, Signal, Slot
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..arrangements import (
    Arrangement,
    delete_arrangement,
    list_arrangements,
    read_arrangement,
    rename_arrangement,
    save_arrangement,
    unique_name,
    write_arrangement,
)
from ..scoring import EMPTY
from . import theme
from .session import MAX_SAVED, NoFreeSlot, Session
from .spinner import Spinner

DIALOG_SIZE = QSize(1000, 660)
# L'aperçu d'un agencement dans la fenêtre. Assez grand pour reconnaître une
# mosaïque et voir où sont les trous.
PREVIEW = QSize(360, 460)
# La croix des cartes absentes, dessinée par-dessus la case qu'elles occupaient.
MISSING_FILL = QColor(120, 30, 30)
MISSING_CROSS = QColor(255, 90, 90)
# Ce qu'on accorde à l'aperçu en cours pour s'arrêter quand la fenêtre se ferme.
# Il s'abandonne à la rangée suivante : quelques millisecondes en pratique.
SHUTDOWN_TIMEOUT_MS = 5000


def arrangement_tiles(arrangement: Arrangement, session: Session) -> list:
    """Les vignettes de l'agencement, rang par rang, `None` pour une absente.

    ⚠️ **Résolues dans le fil de l'interface.** La table des chemins de la
    session se refait quand un lot de cartes arrive, et un lot arrive dans ce
    fil-là : le calcul de fond ne reçoit donc que des vignettes déjà trouvées.
    """
    cartes = session.card_set
    tuiles = []
    for chemin in arrangement.cards:
        index = session.index_of_path(chemin)
        tuiles.append(None if index is None else cartes[index].thumbnail)
    return tuiles


def compose_arrangement(grid, tiles, tile_shape, empty_colour, fit=None,
                        cancelled=lambda: False) -> QImage | None:
    """Assemble la mosaïque, croix rouge là où une vignette manque.

    Sans rien lire de la session : c'est ce qui permet de la calculer hors du
    fil de l'interface. `fit` rend l'image déjà réduite ; `cancelled`, relu à
    chaque rangée, abandonne un aperçu que plus personne n'attend.
    """
    tile_h, tile_w = tile_shape
    rows, cols = len(grid), len(grid[0])
    canvas = np.full((rows * tile_h, cols * tile_w, 3), empty_colour, np.uint8)
    manquantes = []
    for row, ligne in enumerate(grid):
        if cancelled():
            return None
        for col, case in enumerate(ligne):
            if case == EMPTY:
                continue
            vignette = tiles[case]
            if vignette is None:
                manquantes.append((row, col))
                continue
            canvas[row * tile_h:(row + 1) * tile_h,
                   col * tile_w:(col + 1) * tile_w] = vignette

    canvas = np.ascontiguousarray(canvas)
    hauteur, largeur, _ = canvas.shape
    image = QImage(canvas.data, largeur, hauteur, 3 * largeur,
                   QImage.Format_RGB888).copy()
    if manquantes:
        peintre = QPainter(image)
        peintre.setPen(QPen(MISSING_CROSS, max(1, tile_w // 8)))
        for row, col in manquantes:
            x, y = col * tile_w, row * tile_h
            peintre.fillRect(x, y, tile_w, tile_h, MISSING_FILL)
            peintre.drawLine(x, y, x + tile_w, y + tile_h)
            peintre.drawLine(x + tile_w, y, x, y + tile_h)
        peintre.end()
    if fit is not None:
        image = image.scaled(fit, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    return image


def arrangement_image(arrangement: Arrangement, session: Session,
                      empty_colour) -> QImage | None:
    """La mosaïque d'un agencement, croix rouge là où une carte manque.

    Dessinée depuis le catalogue de celui qui regarde, et non depuis des images
    enregistrées : un agencement ne transporte pas les cartes, il les nomme.
    """
    if not arrangement.grid:
        return None
    cartes = session.card_set
    if cartes is None or not len(cartes):
        return None
    return compose_arrangement(arrangement.grid,
                               arrangement_tiles(arrangement, session),
                               cartes[0].thumbnail.shape[:2], empty_colour)


class _PreviewCourier(QObject):
    """Porte l'aperçu du fil de fond jusqu'à la fenêtre.

    ⚠️ **Un objet à part, et non la fenêtre.** Le calcul peut finir après elle :
    émettre sur une fenêtre détruite planterait, alors qu'un messager dont le
    destinataire a disparu se tait, Qt ayant défait la connexion.
    """

    ready = Signal(int, QImage)


class _PreviewState:
    """Le jeton de l'aperçu attendu, relu par le fil de fond à chaque rangée."""

    def __init__(self):
        self.token = 0
        self.stopped = False


class ArrangementsDialog(QDialog):
    """La bibliothèque : la liste à gauche, l'agencement choisi à droite."""

    def __init__(self, session: Session, directory: str, parent=None,
                 start: bool = False):
        super().__init__(parent)
        self._session = session
        self._directory = directory
        # ⚠️ **Deux usages de la même fenêtre.** Ouverte sous les cases, elle
        # range un agencement dans une case sans rien toucher d'autre. Ouverte
        # depuis la barre du haut, aux deux premières étapes, elle en **part** :
        # cartes, grille, habillage et case, voir `Session.apply_arrangement`.
        self._start = start
        # Le nom de l'agencement dont on est parti, vide sinon : la fenêtre
        # principale le dit une fois celle-ci refermée.
        self.applied = ""
        self._arrangements: list[Arrangement] = []
        # ⚠️ **Un seul aperçu à la fois, et le dernier demandé.** Parcourir la
        # liste au clavier lance une demande par ligne : en parallèle, autant de
        # mosaïques de 62 Mo en mémoire. La réserve de fils appartient à la
        # fenêtre, qui l'attend en disparaissant : Qt abandonne le processus si
        # l'on détruit un fil en plein calcul.
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(1)
        self._preview = _PreviewState()
        self._courier = _PreviewCourier()
        self._courier.ready.connect(self._on_preview)
        self._build()
        self.reload()
        session.cards_loaded.connect(self._on_cards_loaded)

    # --- Construction -----------------------------------------------------

    def _build(self) -> None:
        self._list = QListWidget()
        self._list.currentRowChanged.connect(lambda _: self._show_current())
        self._list.setMinimumWidth(280)

        self._title = QLabel()
        gras = self._title.font()
        gras.setBold(True)
        self._title.setFont(gras)
        self._title.setWordWrap(True)
        self._image = QLabel()
        self._image.setAlignment(Qt.AlignCenter)
        self._image.setFixedSize(PREVIEW)
        # L'animation se pose par-dessus l'aperçu, au centre : elle dit que
        # l'image arrive à l'endroit même où elle arrivera.
        self._spinner = Spinner(self._image)
        self._spinner.move((PREVIEW.width() - self._spinner.width()) // 2,
                           (PREVIEW.height() - self._spinner.height()) // 2)
        self._spinner.hide()
        self._missing = QLabel()
        self._missing.setWordWrap(True)
        theme.mark(self._missing, "warning")
        alerte = self._missing.font()
        alerte.setBold(True)
        self._missing.setFont(alerte)
        # La liste des cartes employées, les absentes en tête et signalées.
        self._cards = QListWidget()

        droite = QVBoxLayout()
        droite.addWidget(self._title)
        droite.addWidget(self._missing)
        haut = QHBoxLayout()
        haut.addWidget(self._image)
        haut.addWidget(self._cards, 1)
        droite.addLayout(haut, 1)

        self._open = QPushButton()
        self._open.clicked.connect(self._open_current)
        self._export = QPushButton()
        self._export.clicked.connect(self._export_current)
        self._import = QPushButton()
        self._import.clicked.connect(self._import_file)
        self._rename = QPushButton()
        self._rename.clicked.connect(self._rename_current)
        self._delete = QPushButton()
        self._delete.clicked.connect(self._delete_current)
        self._close = QPushButton()
        self._close.clicked.connect(self.accept)

        boutons = QHBoxLayout()
        for bouton in (self._open, self._export, self._import, self._rename,
                       self._delete):
            boutons.addWidget(bouton)
        boutons.addStretch(1)
        boutons.addWidget(self._close)

        panneau = QWidget()
        panneau.setLayout(droite)
        milieu = QHBoxLayout()
        milieu.addWidget(self._list)
        milieu.addWidget(panneau, 1)

        pile = QVBoxLayout(self)
        pile.addLayout(milieu, 1)
        pile.addLayout(boutons)
        self.resize(DIALOG_SIZE)
        self.retranslate_ui()

    def retranslate_ui(self) -> None:
        self.setWindowTitle(self.tr("Agencements enregistrés"))
        self._open.setText(self.tr("Partir de cet agencement") if self._start
                           else self.tr("Mettre dans une case"))
        self._export.setText(self.tr("Exporter en JSON…"))
        self._import.setText(self.tr("Importer un JSON…"))
        self._rename.setText(self.tr("Renommer…"))
        self._delete.setText(self.tr("Supprimer…"))
        self._close.setText(self.tr("Fermer"))
        self._show_current()

    # --- La liste ---------------------------------------------------------

    def reload(self, select: str | None = None) -> None:
        """Relit la bibliothèque et garde l'agencement demandé sélectionné."""
        self._arrangements = list_arrangements(self._directory)
        self._list.clear()
        for arrangement in self._arrangements:
            manquantes = len(self._session.missing_cards(arrangement))
            texte = arrangement.name
            # Sans catalogue, le compte vaudrait toutes les cartes de chaque
            # agencement : il ne dirait rien, le message du panneau le remplace.
            if manquantes and self._catalogue_loaded():
                texte += "\n" + self.tr("%n carte(s) manquante(s)", "", manquantes)
            self._list.addItem(QListWidgetItem(texte))
        if self._arrangements:
            rangs = [rang for rang, un in enumerate(self._arrangements)
                     if un.name == select]
            self._list.setCurrentRow(rangs[0] if rangs else 0)
        else:
            # ⚠️ **La ligne choisie se montre par son signal**, qui part dès
            # qu'on la pose sur une liste tout juste vidée. L'appeler en plus
            # lançait un second aperçu, le premier partant pour rien. Seule une
            # liste restée vide ne change pas de ligne, et doit se dire à la main.
            self._show_current()

    def _catalogue_loaded(self) -> bool:
        """Des cartes sont-elles chargées ? Premier démarrage ou chargement en
        cours, un agencement ne peut pas encore s'ouvrir.

        ⚠️ **Tout le chargement, pas son premier lot.** Le jeu n'est pas vide
        dès le premier dossier arrivé, mais la suite arrive encore : partir
        d'un agencement à ce moment-là était défait par les lots suivants.
        """
        cartes = self._session.card_set
        return (cartes is not None and len(cartes) > 0
                and not self._session.loading)

    def _on_cards_loaded(self) -> None:
        """La fenêtre restée ouverte pendant le chargement se met à jour : les
        compteurs de cartes manquantes et l'ouverture en dépendent."""
        courant = self.current()
        self.reload(select=courant.name if courant is not None else None)

    def current(self) -> Arrangement | None:
        rang = self._list.currentRow()
        if 0 <= rang < len(self._arrangements):
            return self._arrangements[rang]
        return None

    def _show_current(self) -> None:
        arrangement = self.current()
        for bouton in (self._export, self._rename, self._delete):
            bouton.setEnabled(arrangement is not None)
        if arrangement is None:
            self._title.setText(self.tr("Aucun agencement enregistré."))
            self._missing.setText("")
            self._request_preview(None)
            self._cards.clear()
            self._open.setEnabled(False)
            return

        manquantes = self._session.missing_cards(arrangement)
        colonnes, lignes = arrangement.shape
        self._title.setText(
            self.tr("%1 : %2 × %3 cartes, score %4")
            .replace("%1", arrangement.name)
            .replace("%2", str(colonnes)).replace("%3", str(lignes))
            .replace("%4", f"{arrangement.score:.1f}")
        )
        # ⚠️ **Amputé, ce n'est plus l'agencement qu'on a partagé.** On le
        # montre, on dit ce qui manque, et on ne le laisse pas passer.
        self._open.setEnabled(not manquantes and self._catalogue_loaded())
        if not self._catalogue_loaded():
            # ⚠️ **Sans cartes chargées, rien n'est « manquant ».** Toutes le
            # seraient, et le message laissait croire à un catalogue incomplet
            # alors qu'il suffit de charger les cartes. La liste reste
            # parcourable ; seule l'ouverture attend.
            self._missing.setText(
                self.tr("Chargez d'abord les cartes : un agencement ne s'ouvre "
                        "qu'avec elles."))
        else:
            self._missing.setText(
                "" if not manquantes else
                self.tr("%n carte(s) de cet agencement manquent au catalogue : "
                        "il ne peut pas être ouvert.", "", len(manquantes))
            )
        self._cards.clear()
        absentes = set(manquantes)
        for chemin in sorted(arrangement.cards, key=lambda c: (c not in absentes, c)):
            item = QListWidgetItem(
                ("✕ " if chemin in absentes else "") + chemin)
            if chemin in absentes:
                item.setForeground(QColor(theme.colours(self.palette())["error"]))
            self._cards.addItem(item)
        # ⚠️ **La sélection n'attend pas l'image.** Tout ce qui précède est déjà
        # à l'écran ; l'aperçu, plusieurs dixièmes de seconde sur 441 cartes,
        # se calcule en fond.
        self._request_preview(arrangement)

    # --- L'aperçu ---------------------------------------------------------

    def _request_preview(self, arrangement: Arrangement | None) -> None:
        """Demande l'aperçu en fond, et fait tourner l'attente en son centre.

        ⚠️ **L'ancienne image s'efface tout de suite.** Laissée le temps du
        calcul, elle se lirait sous le titre du nouvel agencement.
        """
        self._preview.token += 1
        # Les demandes pas encore commencées sont périmées ; celle qui tourne
        # le verra à sa prochaine rangée.
        self._pool.clear()
        self._image.setPixmap(QPixmap())
        cartes = self._session.card_set
        if (arrangement is None or not arrangement.grid
                or cartes is None or not len(cartes)):
            self._spinner.hide()
            return

        jeton, etat, messager = self._preview.token, self._preview, self._courier
        grille = arrangement.grid
        tuiles = arrangement_tiles(arrangement, self._session)
        forme = cartes[0].thumbnail.shape[:2]
        couleur = self._session.empty_colour

        def perime() -> bool:
            return etat.stopped or etat.token != jeton

        def calcul() -> None:
            # Rien ici ne touche la fenêtre : elle peut disparaître pendant.
            try:
                image = compose_arrangement(grille, tuiles, forme, couleur,
                                            fit=PREVIEW, cancelled=perime)
            except Exception:  # noqa: BLE001 - l'attente ne doit pas tourner à vide
                # Volontairement large : une exception perdue dans un fil de
                # fond laisserait l'animation tourner pour toujours.
                image = QImage()
            if image is not None and not perime():
                messager.ready.emit(jeton, image)

        self._spinner.show()
        self._pool.start(calcul)

    @Slot(int, QImage)
    def _on_preview(self, token: int, image: QImage) -> None:
        """⚠️ **Le jeton se revérifie à l'arrivée.** Le calcul a pu émettre juste
        avant qu'on change de ligne : son image arrive après la nouvelle
        demande, et se poserait sous le mauvais titre, l'attente éteinte."""
        if token != self._preview.token:
            return
        self._image.setPixmap(QPixmap.fromImage(image))
        self._spinner.hide()

    def done(self, result: int) -> None:
        """Referme la fenêtre une fois l'aperçu en cours abandonné."""
        self._preview.stopped = True
        self._pool.clear()
        self._pool.waitForDone(SHUTDOWN_TIMEOUT_MS)
        super().done(result)

    # --- Les gestes -------------------------------------------------------

    def _open_current(self) -> None:
        """Range l'agencement choisi dans une case, prêt pour l'export."""
        arrangement = self.current()
        if arrangement is None:
            return
        if self._start:
            self._start_from(arrangement)
            return
        try:
            garde = self._session.saved_from_arrangement(arrangement)
        except ValueError as erreur:
            QMessageBox.warning(self, self.tr("Agencement incomplet"),
                                str(erreur))
            return
        rang = self._session.save_grid(garde.grid, garde.cards,
                                       garde.iteration, garde.score)
        if rang is None:
            QMessageBox.information(
                self, self.tr("Aucune case libre"),
                self.tr("Les %n case(s) sont prises : videz-en une pour "
                        "ouvrir celui-ci.", "", MAX_SAVED))
            return
        # ⚠️ **L'habillage vient avec l'agencement** : un agencement partagé
        # doit redonner le même poster. Il est commun aux quatre cases, et
        # remplace donc celui qui était en place. Posé seulement une fois la
        # case obtenue : un refus ne doit rien changer.
        ignores = self._session.apply_presentation(arrangement.presentation)
        if ignores:
            # Les noms du fichier et non des libellés : c'est dans le fichier
            # qu'on les corrige.
            QMessageBox.warning(
                self, self.tr("Habillage incomplet"),
                self.tr("%n réglage(s) de l'habillage étaient illisibles et n'ont "
                        "pas été repris : %1.", "", len(ignores))
                .replace("%1", ", ".join(ignores)))
        self.accept()

    def _start_from(self, arrangement: Arrangement) -> None:
        """Part de l'agencement : cartes, grille, habillage et case.

        Refusé sans rien toucher quand les quatre cases sont prises, décidé par
        l'utilisateur. Ce que la reprise a dû écarter, liens qui ne tiennent
        pas dans la grille ou réglages illisibles, est dit dans un seul avis.
        """
        try:
            depart = self._session.apply_arrangement(arrangement)
        except NoFreeSlot:
            QMessageBox.information(
                self, self.tr("Aucune case libre"),
                self.tr("Les %n case(s) sont prises : videz-en une pour partir "
                        "de celui-ci.", "", MAX_SAVED))
            return
        except ValueError as erreur:
            QMessageBox.warning(self, self.tr("Agencement incomplet"),
                                str(erreur))
            return
        avis = []
        if depart.disabled_links:
            noms = ", ".join(lien.name for lien in depart.disabled_links
                             if lien.name)
            texte = self.tr("%n lien(s) ne tenaient pas dans cet agencement et "
                            "ont été désactivés.", "", len(depart.disabled_links))
            avis.append(texte + (f" ({noms})" if noms else ""))
        if depart.ignored:
            avis.append(
                self.tr("%n réglage(s) de l'habillage étaient illisibles et "
                        "n'ont pas été repris : %1.", "", len(depart.ignored))
                .replace("%1", ", ".join(depart.ignored)))
        if avis:
            QMessageBox.warning(self, self.tr("Agencement repris"),
                                "\n\n".join(avis))
        self.applied = arrangement.name
        self.accept()

    def _export_current(self) -> None:
        arrangement = self.current()
        if arrangement is None:
            return
        chemin, _ = QFileDialog.getSaveFileName(
            self, self.tr("Exporter l'agencement"),
            os.path.join(os.path.expanduser("~"), f"{arrangement.name}.json"),
            self.tr("Agencement (*.json)"))
        if not chemin:
            return
        try:
            write_arrangement(chemin, arrangement)
        except OSError as erreur:
            QMessageBox.warning(self, self.tr("Écriture impossible"), str(erreur))

    def _import_file(self) -> None:
        """Lit un JSON venu d'ailleurs et le range dans la bibliothèque.

        Le nom est rendu unique : deux personnes nomment volontiers leur essai
        de la même façon, et l'import écraserait le sien sans le dire.
        """
        chemin, _ = QFileDialog.getOpenFileName(
            self, self.tr("Importer un agencement"),
            os.path.expanduser("~"), self.tr("Agencement (*.json)"))
        if not chemin:
            return
        try:
            arrangement = read_arrangement(chemin)
        except (OSError, ValueError) as erreur:
            QMessageBox.warning(self, self.tr("Fichier illisible"), str(erreur))
            return
        nom = unique_name(self._directory, arrangement.name or os.path.basename(chemin))
        try:
            save_arrangement(self._directory, Arrangement(
                name=nom, cards=arrangement.cards, grid=arrangement.grid,
                presentation=arrangement.presentation, score=arrangement.score,
                saved_at=arrangement.saved_at))
        except OSError as erreur:
            QMessageBox.warning(self, self.tr("Écriture impossible"), str(erreur))
            return
        self.reload(select=nom)

    def _rename_current(self) -> None:
        arrangement = self.current()
        if arrangement is None:
            return
        nom, valide = QInputDialog.getText(
            self, self.tr("Renommer l'agencement"), self.tr("Nom"),
            text=arrangement.name)
        nom = nom.strip()
        if not valide or not nom or nom == arrangement.name:
            return
        # ⚠️ **Le nom rendu, et non le nom tapé.** Pris par un autre, il reçoit
        # un suffixe : sélectionner le nom tapé désignait l'autre agencement, et
        # « Supprimer » l'aurait visé.
        nouveau = unique_name(self._directory, nom, ignore=arrangement.name)
        try:
            rename_arrangement(self._directory, arrangement.name, nouveau)
        except OSError as erreur:
            QMessageBox.warning(self, self.tr("Renommage impossible"), str(erreur))
            return
        self.reload(select=nouveau)

    def _delete_current(self) -> None:
        arrangement = self.current()
        if arrangement is None:
            return
        reponse = QMessageBox.question(
            self, self.tr("Supprimer cet agencement ?"),
            self.tr("« %1 » sera effacé de la bibliothèque. Le calcul ne "
                    "redonne pas deux fois le même.")
            .replace("%1", arrangement.name),
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reponse == QMessageBox.Yes:
            try:
                delete_arrangement(self._directory, arrangement.name)
            except OSError as erreur:
                QMessageBox.warning(self, self.tr("Suppression impossible"),
                                    str(erreur))
                return
            self.reload()
