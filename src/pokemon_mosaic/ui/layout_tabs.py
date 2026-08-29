"""Les panneaux de l'étape 2, un par décision à prendre.

Chacun est autonome : il sait dire son titre, si ce qu'il contient est en état
d'être validé, et se rafraîchir. L'écran qui les héberge n'a donc rien à savoir
de leur contenu — ajouter un panneau se fait en l'écrivant ici et en l'ajoutant
à la liste, sans toucher à la navigation.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..layout import (
    PAPER_FORMATS_MM,
    card_pixel_size,
    max_useful_dpi,
    mm_to_pixels,
    paper_size_mm,
    suggest_grids,
)
from ..optimize import check_links_fit
from . import theme
from .big_spin import BigSpin
from .page_preview import MAX_PANELS, PagePreview
from .session import Session
from .wireframe import WireframeView

# Assez de propositions pour avoir le choix, assez peu pour être lues d'un coup.
SUGGESTION_COUNT = 5

# En deçà, la marge vide occupe plus de place que les cartes : la mise en page
# mérite d'être dite, même si elle reste parfaitement valide.
MIN_SHEET_COVERAGE = 0.75

# Ce que la ligne d'état gagne sur la police de l'interface.
STATUS_BOOST = 3

# Rapport d'une carte, faute de cartes chargées pour le mesurer.
FALLBACK_ASPECT = 713 / 984


def card_aspect(session: Session) -> float:
    card_set = session.card_set
    if card_set and card_set.full_size[1]:
        return card_set.full_size[0] / card_set.full_size[1]
    return FALLBACK_ASPECT


class LayoutTab(QWidget):
    """Ce que l'écran attend d'un panneau, et rien de plus."""

    # Émis quand ce qui décide de la validité a bougé : l'écran doit relire.
    state_changed = Signal()

    def title(self) -> str:
        raise NotImplementedError

    def is_valid(self) -> bool:
        """Vrai si l'on peut passer à la suite. Sans contrainte, toujours vrai."""
        return True

    def refresh(self) -> None:
        pass

    def retranslate_ui(self) -> None:
        pass


class GridTab(LayoutTab):
    """Les seules dimensions de la grille — pas un mot du format d'impression.

    Le format ne se décide qu'au panneau suivant, et le mêler ici obligeait à
    tout arbitrer d'un coup : combien de cartes par ligne, sur quelle feuille,
    à quelle finesse. On pose d'abord la forme de la mosaïque, qui ne dépend que
    du nombre de cartes retenues.
    """

    def __init__(self, session: Session, parent=None):
        super().__init__(parent)
        self._session = session
        self._updating = False
        # Vrai tant que la grille n'a pas été choisie — ni à la main, ni par une
        # proposition, ni par un préréglage. Le premier passage sur cet onglet
        # l'ajuste alors au nombre de cartes retenues, puis se désarme.
        self._auto_fit_pending = True
        # Vrai le temps d'une écriture que **nous** faisons dans la session : le
        # retour de signal qui s'ensuit n'est pas un choix venu d'ailleurs.
        self._pushing = False
        self._build()
        session.layout_changed.connect(self._on_layout_changed)
        session.selection_changed.connect(self.refresh)
        session.cards_loaded.connect(self.refresh)
        # Un nouveau jeu de cartes rouvre la question : la grille calculée pour
        # les précédentes n'a plus de raison de convenir.
        session.cards_loaded.connect(self._arm_auto_fit)

    def title(self) -> str:
        return self.tr("Dimensions de la grille")

    # --- La grille proposée au premier passage ---------------------------

    def _arm_auto_fit(self) -> None:
        self._auto_fit_pending = True

    def _on_layout_changed(self) -> None:
        """Une mise en page posée ailleurs qu'ici vaut choix explicite.

        ⚠️ Comparer les champs à la session ne suffisait pas : un préréglage qui
        rétablit la grille déjà en place ne fait bouger ni l'un ni l'autre, et
        l'ajustement l'écrasait au premier passage.
        """
        if not self._pushing:
            self._auto_fit_pending = False
        self.refresh()

    def _push(self, **changes) -> None:
        """Écrit dans la session en signalant que le changement vient d'ici."""
        self._pushing = True
        try:
            self._session.set_layout(**changes)
        finally:
            self._pushing = False

    def showEvent(self, event) -> None:
        """Le premier passage sur cet onglet propose la grille la mieux ajustée.

        Elle se calcule ici et non au chargement des cartes : le nombre retenu
        n'est arrêté qu'une fois l'étape 1 quittée, et la lancer plus tôt
        donnerait une grille pour une sélection encore en train de bouger.
        """
        super().showEvent(event)
        self._auto_fit()

    def _auto_fit(self) -> None:
        """Adopte la grille dont le nombre de cases colle au mieux à la sélection.

        ⚠️ **On écarte celles qui perdent des cartes**, même mieux classées :
        abandonner des cartes en silence juste après l'écran où l'utilisateur
        vient de les choisir une par une serait le pire des défauts possibles
        ici. Des cases vides, elles, se voient et se placent.
        """
        if not self._auto_fit_pending or not self._session.selected_count:
            return
        self._auto_fit_pending = False
        session = self._session
        paper_w, paper_h = paper_size_mm(session.paper, session.landscape)
        found = suggest_grids(
            session.selected_count, card_aspect(session),
            paper_w * session.panels / paper_h, panels=session.panels,
        )
        if not found:
            return
        fitting = [s for s in found if s.cells >= session.selected_count]
        best = fitting[0] if fitting else found[0]
        if (best.cols, best.rows) != (session.cols, session.rows):
            self._push(cols=best.cols, rows=best.rows)

    # --- Construction -----------------------------------------------------

    def _build(self) -> None:
        # Les deux dimensions sont la décision de cet onglet : elles se posent
        # en grand, côte à côte, chacune sous son intitulé.
        self._cols = BigSpin(1, 200)
        self._rows = BigSpin(1, 200)
        for champ in (self._cols, self._rows):
            champ.setFixedWidth(140)
            champ.value_changed.connect(self._on_form_changed)

        dimensions = QHBoxLayout()
        dimensions.setSpacing(14)
        dimensions.addWidget(self._cols)
        dimensions.addWidget(self._rows)
        dimensions.addStretch(1)

        self._suggestions = QListWidget()
        # Exactement la hauteur de ses cinq lignes : laissée libre, la liste
        # s'étirait sur la moitié du panneau pour n'y montrer que du vide, en
        # prenant la place de la grille, qui est ce qu'on est venu regarder.
        ligne = self._suggestions.fontMetrics().height() + 6
        self._suggestions.setFixedHeight(ligne * SUGGESTION_COUNT + 8)
        self._suggestions.itemDoubleClicked.connect(self._apply_suggestion)
        # Le titre et le mode d'emploi sur **une seule ligne** : sans cadre ni
        # marges, ils tiennent la largeur que la boîte de groupe gaspillait, et
        # la liste garde toute sa hauteur.
        self._suggestions_title = QLabel()
        titre = self._suggestions_title.font()
        titre.setBold(True)
        self._suggestions_title.setFont(titre)
        self._suggestions_hint = QLabel()
        entete = QHBoxLayout()
        entete.setContentsMargins(0, 0, 0, 0)
        entete.addWidget(self._suggestions_title)
        entete.addSpacing(12)
        entete.addWidget(self._suggestions_hint)
        entete.addStretch(1)

        self._suggestions_box = QWidget()
        propositions = QVBoxLayout(self._suggestions_box)
        propositions.setContentsMargins(0, 0, 0, 0)
        propositions.setSpacing(2)
        propositions.addLayout(entete)
        propositions.addWidget(self._suggestions)

        haut = QHBoxLayout()
        haut.setSpacing(16)
        haut.addLayout(dimensions)
        haut.addWidget(self._suggestions_box, 1)
        bandeau = QWidget()
        bandeau.setLayout(haut)
        # Le bandeau ne prend que ce qu'il lui faut : tout le reste va à la
        # grille, qui doit occuper l'essentiel du panneau.
        bandeau.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

        # La grille prend tout ce qui reste : c'est elle qu'on regarde, et c'est
        # dedans qu'on clique — ou qu'on glisse — pour poser les cases vides.
        self._wireframe = WireframeView(self._session, show_paper=False)
        self._wireframe.cell_clicked.connect(self._session.toggle_empty_cell)
        self._wireframe.cells_painted.connect(self._session.paint_empty_cells)

        self._status = QLabel()
        self._status.setWordWrap(True)
        # C'est le verdict de l'onglet : il se lit d'un coup d'œil depuis
        # l'autre bout de l'écran, et non en se penchant sur le bas du panneau.
        etat = self._status.font()
        etat.setPointSize(etat.pointSize() + STATUS_BOOST)
        self._status.setFont(etat)
        # Le décompte est écrit en gras dans les messages : sans texte enrichi,
        # les balises s'afficheraient telles quelles.
        self._status.setTextFormat(Qt.RichText)
        self._auto_place = QPushButton()
        self._auto_place.clicked.connect(self._session.auto_place_empty_cells)
        self._clear_place = QPushButton()
        self._clear_place.clicked.connect(self._session.reset_empty_cells)

        bas = QHBoxLayout()
        bas.addWidget(self._status, 1)
        bas.addWidget(self._auto_place)
        bas.addWidget(self._clear_place)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.addWidget(bandeau)
        layout.addWidget(self._wireframe, 1)
        layout.addLayout(bas)
        self.retranslate_ui()

    def retranslate_ui(self) -> None:
        self._cols.setTitle(self.tr("Colonnes"))
        self._rows.setTitle(self.tr("Lignes"))
        self._suggestions_title.setText(self.tr("Recommandations de grilles"))
        self._suggestions_hint.setText(self.tr("Double-cliquez pour appliquer"))
        self._auto_place.setText(self.tr("Placer les vides automatiquement"))
        self._auto_place.setToolTip(
            self.tr("Répartit régulièrement les cases vides qui manquent, sans "
                    "défaire celles que vous avez posées.")
        )
        self._clear_place.setText(self.tr("Tout retirer"))
        self.refresh()

    # --- Réactions --------------------------------------------------------

    def _on_form_changed(self, *_) -> None:
        if self._updating:
            return
        # La grille vient d'être choisie : l'ajustement automatique n'a plus à
        # s'en mêler, sous peine d'écraser ce choix au prochain passage.
        self._auto_fit_pending = False
        self._push(cols=self._cols.value(), rows=self._rows.value())

    def _apply_suggestion(self, item: QListWidgetItem) -> None:
        cols, rows = item.data(Qt.UserRole)
        self._auto_fit_pending = False
        self._push(cols=cols, rows=rows)

    def refresh(self) -> None:
        self._updating = True
        self._cols.setValue(self._session.cols)
        self._rows.setValue(self._session.rows)
        self._updating = False
        self._fill_suggestions()
        self._update_status()
        self._wireframe.update()
        self.state_changed.emit()

    def _fill_suggestions(self) -> None:
        self._suggestions.clear()
        session = self._session
        paper_w, paper_h = paper_size_mm(session.paper, session.landscape)
        for suggestion in suggest_grids(
            max(session.selected_count, 1), card_aspect(session),
            paper_w * session.panels / paper_h, panels=session.panels,
            limit=SUGGESTION_COUNT,
        ):
            delta = suggestion.card_delta
            if delta == 0:
                note = self.tr("pile poil")
            elif delta > 0:
                note = self.tr("%n case(s) vide(s)", "", delta)
            else:
                note = self.tr("%n carte(s) en trop", "", -delta)
            item = QListWidgetItem(
                f"{suggestion.cols} × {suggestion.rows}  —  {note}")
            item.setData(Qt.UserRole, (suggestion.cols, suggestion.rows))
            self._suggestions.addItem(item)

    # --- L'état de la grille, dit d'une couleur --------------------------

    def is_valid(self) -> bool:
        fit = self._session.grid_fit()
        return fit.surplus == 0 and self._session.missing_empty_cells() == 0

    def _update_status(self) -> None:
        """Une ligne, une couleur : rouge on ne passe pas, jaune il reste à
        faire, vert c'est prêt."""
        session = self._session
        fit = session.grid_fit()
        reste = session.missing_empty_cells()
        if fit.surplus:
            role, texte = "error", self.tr(
                "<b>%n</b> carte(s) ne tiennent pas dans la grille : agrandissez-la, "
                "ou retirez-les à l'étape précédente.", "", fit.surplus)
        elif reste:
            role, texte = "warning", self.tr(
                "Il reste <b>%n</b> case(s) vide(s) à placer : cliquez dans la "
                "grille pour choisir où.", "", reste)
        elif fit.empty_cells:
            role, texte = "ok", self.tr(
                "Les <b>%n</b> case(s) vide(s) sont placées.", "", fit.empty_cells)
        else:
            role, texte = "ok", self.tr(
                "La grille a exactement autant de cases que de cartes retenues.")
        theme.mark(self._status, role)
        self._status.setText(texte)
        self._auto_place.setEnabled(reste > 0)
        self._clear_place.setEnabled(bool(session.empty_cells()))


class PaperTab(LayoutTab):
    """Le format d'impression, montré plutôt que nommé."""

    def __init__(self, session: Session, parent=None):
        super().__init__(parent)
        self._session = session
        self._updating = False
        self._build()
        session.layout_changed.connect(self.refresh)
        # La mosaïque dessinée dessus dépend de la grille et du nombre de cartes.
        session.selection_changed.connect(self._preview.refresh)
        session.cards_loaded.connect(self._preview.refresh)

    def title(self) -> str:
        return self.tr("Format de la feuille")

    def _build(self) -> None:
        self._paper = QComboBox()
        for name in PAPER_FORMATS_MM:
            self._paper.addItem(name, name)
        self._paper.setMinimumWidth(120)
        self._paper.currentTextChanged.connect(self._on_form_changed)

        self._paper_label = QLabel()
        self._show_grid = QCheckBox()
        self._show_grid.setChecked(True)
        self._show_grid.toggled.connect(self._on_grid_toggled)

        haut = QHBoxLayout()
        haut.addWidget(self._paper_label)
        haut.addWidget(self._paper)
        haut.addSpacing(24)
        haut.addWidget(self._show_grid)
        haut.addStretch(1)

        self._hint = QLabel()
        self._hint.setWordWrap(True)
        # Dit à quelles conditions l'ajustement montré tient. Caché quand la
        # mosaïque ne l'est pas : sans elle, il n'y a rien à nuancer.
        self._grid_warning = QLabel()
        self._grid_warning.setWordWrap(True)
        theme.mark(self._grid_warning, "warning")
        # ⚠️ Ajouter une feuille depuis l'aperçu peut rendre la grille
        # indivisible : la mosaïque cesse alors d'être dessinée. Sans ce
        # message, la feuille se vidait sans qu'aucun mot ne dise pourquoi.
        self._split_error = QLabel()
        self._split_error.setWordWrap(True)
        theme.mark(self._split_error, "error")
        self._preview = PagePreview(self._session)
        # Les feuilles s'ajoutent et se retirent depuis le dessin lui-même : on
        # y voit tout de suite ce que cela change à la place occupée.
        self._preview.panels_requested.connect(self._on_panels_requested)

        layout = QVBoxLayout(self)
        layout.addLayout(haut)
        layout.addWidget(self._hint)
        layout.addWidget(self._grid_warning)
        layout.addWidget(self._split_error)
        layout.addWidget(self._preview, 1)
        self.retranslate_ui()

    def _on_panels_requested(self, panels: int) -> None:
        self._session.set_layout(panels=max(1, min(MAX_PANELS, panels)))

    def _on_grid_toggled(self, montrer: bool) -> None:
        self._preview.set_show_grid(montrer)
        self._grid_warning.setVisible(montrer)

    def retranslate_ui(self) -> None:
        self._paper_label.setText(self.tr("Format d'impression"))
        self._show_grid.setText(self.tr("Montrer la mosaïque sur la feuille"))
        self._preview.retranslate_ui()
        self._hint.setText(
            self.tr("La carte posée à gauche est à ses dimensions réelles, à la "
                    "même échelle que la feuille : c'est elle qui donne la taille. "
                    "Le « + » à droite ajoute une feuille côte à côte.")
        )
        self._grid_warning.setText(
            self.tr("Cet ajustement n'est pas définitif : l'orientation et le "
                    "nombre de posters côte à côte se règlent à l'onglet suivant, "
                    "et les dimensions de la grille restent modifiables au "
                    "premier — de quoi remplir mieux la feuille.")
        )
        self._on_grid_toggled(self._show_grid.isChecked())
        self.refresh()

    def _on_form_changed(self, *_) -> None:
        if self._updating:
            return
        self._session.set_layout(paper=self._paper.currentData())

    def is_valid(self) -> bool:
        """Une coupe ne doit jamais tomber au milieu d'une carte."""
        return not self._session.cols % self._session.panels

    def _update_split(self) -> None:
        session = self._session
        reste = session.cols % session.panels
        self._split_error.setVisible(bool(reste))
        if reste:
            self._split_error.setText(
                self.tr("%1 colonnes ne se divisent pas en %2 feuilles : la coupe "
                        "tomberait au milieu d'une carte. La mosaïque n'est pas "
                        "dessinée tant que ce n'est pas réglé — retirez une "
                        "feuille, ou changez les colonnes au premier onglet.")
                .replace("%1", str(session.cols))
                .replace("%2", str(session.panels)))

    def refresh(self) -> None:
        self._updating = True
        self._paper.setCurrentText(self._session.paper)
        self._updating = False
        # Le champ a pu refuser un format inconnu venu d'un préréglage écrit à
        # la main : on renvoie à la session ce qu'il a réellement accepté.
        if self._paper.currentText() != self._session.paper:
            self._session.set_layout(paper=self._paper.currentText())
        self._update_split()
        self._preview.refresh()
        self.state_changed.emit()


class PrintingTab(LayoutTab):
    """Tout le reste, en attendant d'être redécoupé à son tour."""

    def __init__(self, session: Session, parent=None):
        super().__init__(parent)
        self._session = session
        self._updating = False
        self._build()
        session.layout_changed.connect(self.refresh)
        session.selection_changed.connect(self.refresh)
        session.cards_loaded.connect(self.refresh)

    def title(self) -> str:
        return self.tr("Orientation et impression")

    def is_valid(self) -> bool:
        """Même refus qu'à l'onglet du format, qui règle le même nombre.

        ⚠️ Sans cela, la faute passait ou bloquait selon l'onglet où elle était
        commise : 21 colonnes portées à 2 feuilles **ici** laissaient « Suivant »
        actif, et l'on quittait l'étape avec une coupe en pleine carte.
        """
        return not self._session.cols % self._session.panels

    def _build(self) -> None:
        self._landscape = QCheckBox()
        self._dpi = QSpinBox(); self._dpi.setRange(50, 1200); self._dpi.setSingleStep(50)
        self._panels = QSpinBox(); self._panels.setRange(1, 6)
        for widget in (self._landscape, self._dpi, self._panels):
            signal = (widget.toggled if isinstance(widget, QCheckBox)
                      else widget.valueChanged)
            signal.connect(self._on_form_changed)

        self._form_box = QGroupBox()
        form = QFormLayout(self._form_box)
        self._labels = {}
        for key, widget in (("landscape", self._landscape), ("dpi", self._dpi),
                            ("panels", self._panels)):
            label = QLabel()
            self._labels[key] = label
            form.addRow(label, widget)

        self._preview_hint = QLabel(); self._preview_hint.setWordWrap(True)
        self._wireframe = WireframeView(self._session)
        self._wireframe.cell_clicked.connect(self._session.toggle_empty_cell)
        self._wireframe.cells_painted.connect(self._session.paint_empty_cells)
        self._summary = QLabel(); self._summary.setWordWrap(True)
        self._warnings = QLabel(); self._warnings.setWordWrap(True)
        theme.mark(self._warnings, "error")

        gauche = QVBoxLayout()
        gauche.addWidget(self._form_box)
        gauche.addStretch(1)
        panneau_gauche = QWidget(); panneau_gauche.setLayout(gauche)
        panneau_gauche.setFixedWidth(300)

        droite = QVBoxLayout()
        droite.addWidget(self._preview_hint)
        droite.addWidget(self._wireframe, 1)
        droite.addWidget(self._summary)
        droite.addWidget(self._warnings)
        panneau_droit = QWidget(); panneau_droit.setLayout(droite)

        layout = QHBoxLayout(self)
        layout.addWidget(panneau_gauche)
        layout.addWidget(panneau_droit, 1)
        self.retranslate_ui()

    def retranslate_ui(self) -> None:
        self._form_box.setTitle(self.tr("Impression"))
        self._labels["landscape"].setText(self.tr("Paysage"))
        self._labels["dpi"].setText(self.tr("Résolution (DPI)"))
        self._labels["panels"].setText(self.tr("Posters côte à côte"))
        self._preview_hint.setText(
            self.tr("Aperçu de la mise en page sur la feuille, sans les images. "
                    "Cliquez une case pour y placer ou retirer un vide.")
        )
        self.refresh()

    def _on_form_changed(self, *_) -> None:
        if self._updating:
            return
        self._session.set_layout(landscape=self._landscape.isChecked(),
                                 dpi=self._dpi.value(), panels=self._panels.value())

    def refresh(self) -> None:
        self._updating = True
        self._landscape.setChecked(self._session.landscape)
        self._dpi.setValue(self._session.dpi)
        self._panels.setValue(self._session.panels)
        self._updating = False
        self._push_back_clamped()
        self._update_summary()
        self._wireframe.update()
        self.state_changed.emit()

    def _push_back_clamped(self) -> None:
        """Renvoie à la session ce que les champs ont réellement accepté.

        Un préréglage écrit à la main peut porter un DPI hors bornes. Le champ
        l'écrête pour l'afficher ; sans ce retour, la session garderait la valeur
        d'origine et l'écran décrirait un poster différent de celui qui sera
        produit.
        """
        session = self._session
        accepted = {"dpi": self._dpi.value(), "panels": self._panels.value()}
        drifted = {name: value for name, value in accepted.items()
                   if getattr(session, name) != value}
        if drifted:
            session.set_layout(**drifted)

    def _update_summary(self) -> None:
        session = self._session
        paper = paper_size_mm(session.paper, session.landscape)
        warnings = []

        if session.cols % session.panels:
            self._summary.setText("")
            self._warnings.setText(
                self.tr("%1 colonnes ne se divisent pas en %2 panneaux : la coupe "
                        "tomberait au milieu d'une carte.")
                .replace("%1", str(session.cols)).replace("%2", str(session.panels))
            )
            return

        per_panel = session.cols // session.panels
        aspect = card_aspect(session)
        card_w, card_h = card_pixel_size(paper, per_panel, session.rows,
                                         aspect, session.dpi)
        total_w = card_w * session.cols
        total_h = card_h * session.rows
        self._summary.setText(
            self.tr("Cartes de %1×%2 px — image totale %3×%4 px sur %5 feuille(s) "
                    "%6 de %7×%8 mm.")
            .replace("%1", str(card_w)).replace("%2", str(card_h))
            .replace("%3", str(total_w)).replace("%4", str(total_h))
            .replace("%5", str(session.panels)).replace("%6", session.paper)
            .replace("%7", f"{paper[0]:.0f}").replace("%8", f"{paper[1]:.0f}")
        )

        # Un lien qui déborde de la grille ne se verrait sinon qu'au lancement
        # du calcul, bien après le choix de la mise en page.
        try:
            check_links_fit(session.usable_links().active,
                            session.cols, session.rows)
        except ValueError as error:
            warnings.append(str(error))

        source_width = (session.card_set.full_size[0]
                        if session.card_set and session.card_set.full_size[0] else 713)
        ceiling = max_useful_dpi(paper, per_panel, source_width)
        if session.dpi > ceiling:
            warnings.append(
                self.tr("%1 DPI dépasse le maximum utile (%2 DPI pour ce format) : "
                        "les cartes seront agrandies sans gagner en détail.")
                .replace("%1", str(session.dpi)).replace("%2", f"{ceiling:.0f}")
            )

        # ⚠️ **La part de feuille réellement couverte.** La forme des grilles est
        # bornée à trois cases d'écart : une mise en page sur plusieurs panneaux
        # côte à côte ne peut plus s'allonger pour suivre la feuille — mesuré,
        # 441 cartes en 20×23 sur deux A4 ne couvrent que 43,9 % du papier,
        # contre 96,9 % pour un 30×15. Les chiffres étaient là, mais il fallait
        # faire la division soi-même.
        sheet_px = (mm_to_pixels(paper[0], session.dpi) * session.panels
                    * mm_to_pixels(paper[1], session.dpi))
        coverage = total_w * total_h / sheet_px if sheet_px else 1.0
        if coverage < MIN_SHEET_COVERAGE:
            warnings.append(
                self.tr("La mosaïque ne couvre que %1 % de la feuille : le reste "
                        "sera une marge vide. Une grille plus allongée — plus de "
                        "colonnes que de lignes — suivrait mieux %n feuille(s) "
                        "côte à côte.", "", session.panels)
                .replace("%1", f"{coverage * 100:.0f}")
            )

        megapixels = total_w * total_h / 1e6
        if megapixels > 100:
            warnings.append(
                self.tr("Image de %1 Mpx : l'export demandera beaucoup de mémoire.")
                .replace("%1", f"{megapixels:.0f}")
            )
        self._warnings.setText("\n".join(warnings))
