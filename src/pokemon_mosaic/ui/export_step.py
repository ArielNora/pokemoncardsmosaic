"""Étape 4 : l'export, où l'on habille un agencement gardé avant de l'écrire.

Le calcul est fini, la grille est arrêtée : **sa forme ne se discute plus**.
Ce qui reste ouvert est tout ce qui n'y touche pas, l'écart entre les cartes,
le nombre de feuilles, les couleurs de ce qui n'est pas une carte, la finesse
d'impression. Trois onglets, un par famille de décisions, et la colonne des
cinq agencements gardés à droite : on habille celui qu'on regarde, et on
l'exporte quand il va.

⚠️ **Ni les colonnes ni les lignes ne s'y règlent.** Les changer défferait
l'agencement que l'algorithme vient de trouver : les cartes ne seraient plus à
leur place, et le score n'aurait plus de sens.
"""

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QColorDialog,
    QHBoxLayout,
    QLabel,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..layout import MM_PER_INCH, max_useful_dpi
from . import theme
from .big_spin import BigFloatSpin
from .export_dialog import ExportDialog
from .exporter import start_export
from .layout_step import (
    SUB_TAB_HEIGHT,
    TAB_BOOST,
    TAB_WIDTH,
    TabDelegate,
    TabList,
)
from .page_preview import PagePreview
from .saved_column import SavedColumn
from .session import Session

# L'état neutre des onglets d'ici : ils ne se valident pas, on y passe et on y
# revient. Le cadre reste, la couleur ne dit rien de plus qu'« onglet ».
NEUTRAL = "neutral"
# Le zoom de l'aperçu, en pas et en bornes. À 1, la feuille tient dans le cadre.
ZOOM_MIN, ZOOM_MAX, ZOOM_STEP = 1.0, 6.0, 0.5
# Taille de la pastille de couleur d'un bouton.
SWATCH = QSize(28, 18)


def swatch(colour) -> str:
    """La feuille de style d'un bouton qui montre sa couleur."""
    return (f"background: rgb({colour[0]}, {colour[1]}, {colour[2]});"
            " border: 1px solid palette(mid); border-radius: 3px;")


class ExportTab(QWidget):
    """Un onglet de l'étape, avec son intitulé."""

    def __init__(self, session: Session, parent=None):
        super().__init__(parent)
        self._session = session
        self._updating = False

    def title(self) -> str:
        raise NotImplementedError

    def refresh(self) -> None:
        pass


class PresentationTab(ExportTab):
    """Ce qui se règle encore sans toucher à la forme de la grille."""

    def __init__(self, session: Session, parent=None):
        super().__init__(session, parent)
        self._gap = BigFloatSpin(0.0, 50.0, step=0.5)
        self._gap.value_changed.connect(self._on_gap)
        self._width = BigFloatSpin(1.0, 200.0, step=0.5)
        self._width.value_changed.connect(self._on_width)
        self._auto_width = QPushButton()
        self._auto_width.clicked.connect(self._on_auto_width)
        self._centre = QPushButton()
        self._centre.clicked.connect(self._session.center_panels)

        self._note = QLabel()
        self._note.setWordWrap(True)

        champs = QHBoxLayout()
        champs.setSpacing(24)
        champs.addWidget(self._width, 0, Qt.AlignTop)
        champs.addWidget(self._gap, 0, Qt.AlignTop)
        boutons = QVBoxLayout()
        boutons.addWidget(self._auto_width)
        boutons.addWidget(self._centre)
        boutons.addStretch(1)
        champs.addLayout(boutons)
        champs.addStretch(1)

        pile = QVBoxLayout(self)
        pile.setContentsMargins(8, 6, 8, 6)
        pile.addWidget(self._note)
        pile.addLayout(champs)
        pile.addStretch(1)
        self.retranslate_ui()

    def title(self) -> str:
        return self.tr("Présentation")

    def retranslate_ui(self) -> None:
        self._width.setTitle(self.tr("Largeur d'une carte (mm)"))
        self._gap.setTitle(self.tr("Écart entre les cartes (mm)"))
        self._auto_width.setText(self.tr("Au plus grand"))
        self._centre.setText(self.tr("Centrer sur les feuilles"))
        self._note.setText(self.tr(
            "La forme de la grille est arrêtée : la changer déferait "
            "l'agencement trouvé. Tout ce qui n'y touche pas reste ouvert, "
            "l'écart entre les cartes, leur taille, et le nombre de feuilles, "
            "que l'aperçu ajoute par ses « + »."))
        self.refresh()

    def refresh(self) -> None:
        self._updating = True
        session = self._session
        self._gap.setValue(session.card_gap_mm)
        largeur = session.card_width_mm
        if largeur is None:
            # ⚠️ **La géométrie compte en pixels.** Posée telle quelle dans un
            # champ en millimètres, la largeur automatique s'affichait à 200,
            # c'est-à-dire écrêtée au maximum du champ.
            largeur = (session.panel_geometry().card_w
                       * MM_PER_INCH / session.dpi)
        self._width.setValue(largeur)
        self._updating = False

    def _on_gap(self, valeur: float) -> None:
        if not self._updating:
            self._session.set_layout(card_gap_mm=valeur)

    def _on_width(self, valeur: float) -> None:
        if not self._updating:
            self._session.set_layout(card_width_mm=valeur)

    def _on_auto_width(self) -> None:
        """Rend la largeur au calcul : la plus grande qui fasse tenir la grille."""
        self._session.set_layout(card_width_mm=None)


class ColoursTab(ExportTab):
    """Les couleurs de tout ce qui n'est pas une carte."""

    ROLES = ("background_colour", "gap_colour", "empty_colour")

    def __init__(self, session: Session, parent=None):
        super().__init__(session, parent)
        self._labels: dict[str, QLabel] = {}
        self._buttons: dict[str, QPushButton] = {}
        self._note = QLabel()
        self._note.setWordWrap(True)

        pile = QVBoxLayout(self)
        pile.setContentsMargins(8, 6, 8, 6)
        pile.addWidget(self._note)
        for role in self.ROLES:
            intitule = QLabel()
            bouton = QPushButton()
            bouton.setFixedSize(SWATCH)
            bouton.clicked.connect(lambda _=False, r=role: self._pick(r))
            self._labels[role] = intitule
            self._buttons[role] = bouton
            ligne = QHBoxLayout()
            ligne.setSpacing(10)
            ligne.addWidget(bouton)
            ligne.addWidget(intitule)
            ligne.addStretch(1)
            pile.addLayout(ligne)
        pile.addStretch(1)
        self.retranslate_ui()

    def title(self) -> str:
        return self.tr("Couleurs des vides")

    def retranslate_ui(self) -> None:
        self._note.setText(self.tr(
            "Ces couleurs ne changent rien au calcul : une case vide est un "
            "bord pour l'algorithme, qui ne compare jamais ses voisines à "
            "travers elle. Elles ne se voient qu'à l'impression."))
        self._labels["background_colour"].setText(self.tr("Autour de la grille"))
        self._labels["gap_colour"].setText(self.tr("Entre les cartes"))
        self._labels["empty_colour"].setText(self.tr("Cases vides"))
        self.refresh()

    def refresh(self) -> None:
        for role, bouton in self._buttons.items():
            bouton.setStyleSheet(swatch(getattr(self._session, role)))

    def _pick(self, role: str) -> None:
        actuelle = QColor(*getattr(self._session, role))
        choisie = QColorDialog.getColor(actuelle, self, self._labels[role].text())
        if choisie.isValid():
            # La session prévient tout le monde, cet onglet compris : un
            # second chemin ferait deux repeints pour un clic.
            self._session.set_algorithm(
                **{role: (choisie.red(), choisie.green(), choisie.blue())})


class ResolutionTab(ExportTab):
    """La finesse d'impression, et de quoi regarder le détail de près."""

    zoom_changed = Signal(float)

    def __init__(self, session: Session, parent=None):
        super().__init__(session, parent)
        self._zoom = ZOOM_MIN
        self._dpi = QSpinBox()
        self._dpi.setRange(50, 1200)
        self._dpi.setSingleStep(50)
        self._dpi.valueChanged.connect(self._on_dpi)
        self._dpi_label = QLabel()
        self._note = QLabel()
        self._note.setWordWrap(True)
        self._pixels = QLabel()
        self._pixels.setWordWrap(True)

        self._zoom_out = QPushButton("−")
        self._zoom_in = QPushButton("+")
        self._zoom_label = QLabel()
        for bouton in (self._zoom_out, self._zoom_in):
            bouton.setFixedWidth(32)
        self._zoom_out.clicked.connect(lambda: self._zoom_by(-ZOOM_STEP))
        self._zoom_in.clicked.connect(lambda: self._zoom_by(ZOOM_STEP))
        self._zoom_fit = QPushButton()
        self._zoom_fit.clicked.connect(lambda: self._set_zoom(ZOOM_MIN))

        finesse = QHBoxLayout()
        finesse.setSpacing(10)
        finesse.addWidget(self._dpi_label)
        finesse.addWidget(self._dpi)
        finesse.addStretch(1)

        loupe = QHBoxLayout()
        loupe.setSpacing(6)
        loupe.addWidget(self._zoom_out)
        loupe.addWidget(self._zoom_label)
        loupe.addWidget(self._zoom_in)
        loupe.addWidget(self._zoom_fit)
        loupe.addStretch(1)

        pile = QVBoxLayout(self)
        pile.setContentsMargins(8, 6, 8, 6)
        pile.addWidget(self._note)
        pile.addLayout(finesse)
        pile.addWidget(self._pixels)
        pile.addLayout(loupe)
        pile.addStretch(1)
        self.retranslate_ui()

    def title(self) -> str:
        return self.tr("Résolution")

    def retranslate_ui(self) -> None:
        self._dpi_label.setText(self.tr("Finesse (DPI)"))
        self._zoom_fit.setText(self.tr("Ajuster"))
        self._note.setText(self.tr(
            "La finesse commande le poids du fichier et le détail visible sur "
            "le papier. Au-delà du maximum utile, les cartes sont agrandies "
            "sans gagner un pixel de détail."))
        self.refresh()

    def refresh(self) -> None:
        self._updating = True
        session = self._session
        self._dpi.setValue(session.dpi)
        self._updating = False
        self._zoom_label.setText(f"{self._zoom * 100:.0f} %")
        largeur, hauteur = session.paper_mm()
        pixels_l = round(largeur / 25.4 * session.dpi)
        pixels_h = round(hauteur / 25.4 * session.dpi)
        texte = (self.tr("Chaque feuille fera %1 × %2 pixels.")
                 .replace("%1", str(pixels_l)).replace("%2", str(pixels_h)))
        cartes = session.card_set
        if cartes is not None and len(cartes):
            utile = max_useful_dpi(session.paper_mm(), session.cols,
                                   cartes.full_size[0])
            if session.dpi > utile:
                texte += " " + (self.tr("Au-delà de %1 DPI, l'impression "
                                        "agrandit sans ajouter de détail.")
                                .replace("%1", f"{utile:.0f}"))
        self._pixels.setText(texte)

    def zoom(self) -> float:
        return self._zoom

    def _on_dpi(self, valeur: int) -> None:
        if not self._updating:
            self._session.set_layout(dpi=valeur)

    def _zoom_by(self, pas: float) -> None:
        self._set_zoom(self._zoom + pas)

    def _set_zoom(self, valeur: float) -> None:
        valeur = max(ZOOM_MIN, min(ZOOM_MAX, valeur))
        if valeur == self._zoom:
            return
        self._zoom = valeur
        self._zoom_label.setText(f"{self._zoom * 100:.0f} %")
        self.zoom_changed.emit(self._zoom)


class ExportStep(QWidget):
    """L'écran d'export : les onglets, l'aperçu, et les agencements gardés."""

    status_message = Signal(str)

    def __init__(self, session: Session, parent=None):
        super().__init__(parent)
        self._session = session
        self._export_thread = None
        self._export_worker = None
        self._slot: int | None = None
        self._build()
        session.saved_changed.connect(self._on_saved_changed)
        session.layout_changed.connect(self._on_layout_changed)
        # Les couleurs voyagent avec les réglages d'algorithme : l'aperçu, les
        # pastilles des boutons et les vignettes de la colonne en dépendent.
        session.algorithm_changed.connect(self._on_layout_changed)
        session.algorithm_changed.connect(self._saved.refresh)

    # --- Construction -----------------------------------------------------

    def _build(self) -> None:
        self._tabs = [PresentationTab(self._session),
                      ColoursTab(self._session),
                      ResolutionTab(self._session)]
        self._list = TabList()
        self._list.setItemDelegate(TabDelegate(self._list))
        self._list.setFixedWidth(TAB_WIDTH)
        self._list.setWordWrap(True)
        theme.mark(self._list, "tabs")
        self._list.setSpacing(0)
        self._list.setSelectionMode(QAbstractItemView.SingleSelection)

        self._pages = QStackedWidget()
        for onglet in self._tabs:
            item = QListWidgetItem("")
            item.setSizeHint(QSize(TAB_WIDTH - 8, SUB_TAB_HEIGHT))
            police = self.font()
            police.setPointSize(police.pointSize() + TAB_BOOST)
            police.setBold(True)
            item.setFont(police)
            # ⚠️ **Un état neutre, et non « prêt ».** Ces onglets ne se valident
            # pas : une coche verte promettrait une étape franchie là où l'on
            # ne fait qu'ajuster.
            item.setData(Qt.UserRole + 2, NEUTRAL)
            self._list.addItem(item)
            self._pages.addWidget(onglet)
        self._list.currentRowChanged.connect(self._pages.setCurrentIndex)
        self._list.setCurrentRow(0)
        self._tabs[2].zoom_changed.connect(self._apply_zoom)

        # L'aperçu montre le poster tel qu'il s'imprimera, agencement compris.
        self._preview = PagePreview(self._session)
        self._preview.set_show_grid(True)
        self._preview.panels_requested.connect(
            lambda combien: self._session.set_layout(panels=combien))
        self._preview.panel_rows_requested.connect(
            lambda combien: self._session.set_layout(panel_rows=combien))
        self._preview.set_draggable(True)
        self._preview.panel_moved.connect(self._session.move_panel)
        # ⚠️ **Une zone défilante pour le zoom.** L'aperçu se dessine à la
        # taille qu'on lui donne : l'agrandir dans un cadre fixe le rognerait,
        # et il n'y aurait aucun moyen d'atteindre le bas de la feuille.
        self._scroll = QScrollArea()
        self._scroll.setWidget(self._preview)
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QScrollArea.NoFrame)

        self._saved = SavedColumn(self._session, removable=False)
        self._saved.slot_picked.connect(self.show_slot)

        self._export = QPushButton()
        self._export.clicked.connect(self._open_export)
        self._summary = QLabel()
        barre = QHBoxLayout()
        barre.addWidget(self._export)
        barre.addStretch(1)
        barre.addWidget(self._summary)

        centre = QVBoxLayout()
        centre.addWidget(self._pages)
        centre.addWidget(self._scroll, 1)
        centre.addLayout(barre)

        layout = QHBoxLayout(self)
        layout.addWidget(self._list)
        layout.addLayout(centre, 1)
        layout.addWidget(self._saved)
        self.retranslate_ui()

    def retranslate_ui(self) -> None:
        for rang, onglet in enumerate(self._tabs):
            onglet.retranslate_ui()
            self._list.item(rang).setText(onglet.title())
        self._export.setText(self.tr("Exporter cet agencement…"))
        self._saved.retranslate_ui()
        self._refresh_preview()

    # --- L'agencement affiché ---------------------------------------------

    def show_slot(self, slot: int) -> None:
        """Montre l'agencement d'une case, et la marque comme courante."""
        saved = self._session.saved[slot]
        if saved is None:
            return
        self._slot = slot
        self._saved.set_current(slot)
        self._preview.set_arrangement(saved.grid, saved.cards)
        self._update_summary()

    def enter(self) -> None:
        """Appelé en arrivant sur l'étape : ouvre la première case gardée.

        ⚠️ **Toujours une case ouverte.** Un écran d'export sans agencement
        n'aurait rien à habiller, et la colonne n'est pas un menu qu'on doit
        penser à ouvrir.
        """
        if self._slot is None or self._session.saved[self._slot] is None:
            premier = self._session.first_saved()
            if premier is not None:
                self.show_slot(premier)
        self._refresh_preview()

    def current_saved(self):
        if self._slot is None:
            return None
        return self._session.saved[self._slot]

    # --- Réactions --------------------------------------------------------

    def _on_saved_changed(self) -> None:
        if self._slot is not None and self._session.saved[self._slot] is None:
            self._slot = None
        self.enter()

    def _on_layout_changed(self) -> None:
        for onglet in self._tabs:
            onglet.refresh()
        self._refresh_preview()

    def _refresh_preview(self) -> None:
        self._preview.refresh()
        self._update_summary()

    def _apply_zoom(self, zoom: float) -> None:
        """Le zoom agrandit le dessin ; la zone défilante fait le reste."""
        base = self._scroll.viewport().size()
        self._preview.setMinimumSize(int(base.width() * zoom),
                                     int(base.height() * zoom))
        self._preview.refresh()

    def _update_summary(self) -> None:
        saved = self.current_saved()
        if saved is None:
            self._summary.setText(self.tr("Aucun agencement gardé."))
            self._export.setEnabled(False)
            return
        self._export.setEnabled(self._export_thread is None)
        self._summary.setText(
            self.tr("Agencement %1 sur %2, score %3")
             .replace("%1", str((self._slot or 0) + 1))
             .replace("%2", str(self._session.saved_count()))
             .replace("%3", f"{saved.score:.1f}")
        )

    # --- Écriture ---------------------------------------------------------

    def _open_export(self) -> None:
        saved = self.current_saved()
        if saved is None or self._export_thread is not None:
            return
        dialog = ExportDialog(self._session, saved.grid, saved.cards, parent=self)
        try:
            if not dialog.exec():
                return
            settings, path = dialog.settings(), dialog.path()
            full_resolution = dialog.full_resolution()
        finally:
            dialog.deleteLater()
        self._start_export(saved, settings, path, full_resolution)

    def _start_export(self, saved, settings, path, full_resolution) -> None:
        self._export.setEnabled(False)
        self._export_thread, self._export_worker = start_export(
            self, saved.grid, saved.cards, settings, path, full_resolution,
            progress=self._on_export_progress,
            exported=self._on_export_finished,
            cancelled=self._on_export_cancelled,
            failed=self._on_export_failed,
        )

    def _on_export_progress(self, fait: int, total: int, fichier: str) -> None:
        self.status_message.emit(
            self.tr("Écriture %1 / %2").replace("%1", str(fait))
            .replace("%2", str(total)))

    def _on_export_cancelled(self) -> None:
        self._export_thread = self._export_worker = None
        self._update_summary()
        self.status_message.emit(self.tr("Export interrompu."))

    def _on_export_finished(self, paths) -> None:
        self._export_thread = self._export_worker = None
        self._update_summary()
        self.status_message.emit(
            self.tr("%n fichier(s) écrit(s).", "", len(paths)))

    def _on_export_failed(self, message: str) -> None:
        self._export_thread = self._export_worker = None
        self._update_summary()
        self.status_message.emit(message)

    def shutdown(self) -> bool:
        """Rend faux si un export tourne encore : la fenêtre ne doit pas partir
        avec un fil qui écrit."""
        return self._export_thread is None
