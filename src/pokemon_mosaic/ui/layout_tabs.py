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
    QDoubleSpinBox,
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
    MM_PER_INCH,
    PAPER_FORMATS_MM,
    REAL_CARD_MM,
    best_grid_shapes,
    grid_fits,
    grid_geometry,
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

# Assez de propositions pour avoir le choix, assez peu pour être lues d'un coup.
SUGGESTION_COUNT = 5
# Les formes de grille qui tiendraient, quand la taille de carte est figée.
SHAPE_COUNT = 6

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


class GridSizeTab(LayoutTab):
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
        return self.tr("Taille et cases vides")

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
            paper_w * session.panels / paper_h,
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

        # ⚠️ **La mosaïque se regarde dans les pages**, comme sur tous les
        # onglets de la famille : une grille sans papier ne disait pas si elle y
        # tenait. C'est donc dedans qu'on clique — ou qu'on glisse — pour poser
        # les cases vides.
        self._preview = PagePreview(self._session)
        self._preview.set_show_grid(True)
        self._preview.set_paintable(True)
        self._preview.panels_requested.connect(
            lambda n: self._session.set_layout(panels=max(1, min(MAX_PANELS, n))))
        self._preview.cell_clicked.connect(self._session.toggle_empty_cell)
        self._preview.cells_painted.connect(self._session.paint_empty_cells)

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
        layout.addWidget(self._preview, 1)
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
        self._preview.refresh()
        self.state_changed.emit()

    def _fill_suggestions(self) -> None:
        self._suggestions.clear()
        session = self._session
        paper_w, paper_h = paper_size_mm(session.paper, session.landscape)
        for suggestion in suggest_grids(
            max(session.selected_count, 1), card_aspect(session),
            paper_w * session.panels / paper_h, limit=SUGGESTION_COUNT,
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
        return self.tr("Pages")

    def _build(self) -> None:
        self._paper = QComboBox()
        for name in PAPER_FORMATS_MM:
            self._paper.addItem(name, name)
        self._paper.setMinimumWidth(120)
        self._paper.currentTextChanged.connect(self._on_form_changed)

        self._paper_label = QLabel()
        # L'orientation décrit la feuille : elle appartient à cet onglet, pas au
        # suivant, où elle n'avait rien à voir avec la finesse d'impression.
        self._landscape = QCheckBox()
        self._landscape.toggled.connect(self._on_form_changed)
        # La finesse décrit les pages à imprimer : elle est ici, avec elles, et
        # non sur un onglet à part où elle n'avait aucun voisin.
        self._dpi = QSpinBox()
        self._dpi.setRange(50, 1200)
        self._dpi.setSingleStep(50)
        self._dpi.valueChanged.connect(self._on_form_changed)
        self._dpi_label = QLabel()

        haut = QHBoxLayout()
        haut.addWidget(self._paper_label)
        haut.addWidget(self._paper)
        haut.addSpacing(20)
        haut.addWidget(self._landscape)
        haut.addSpacing(20)
        haut.addWidget(self._dpi_label)
        haut.addWidget(self._dpi)
        haut.addStretch(1)

        self._hint = QLabel()
        self._hint.setWordWrap(True)
        # La mosaïque est toujours dessinée : la bascule et son message n'ont
        # plus lieu d'être, la famille d'onglets suivante la montrant partout.
        self._preview = PagePreview(self._session)
        self._preview.set_show_grid(True)
        # Les feuilles s'ajoutent et se retirent depuis le dessin lui-même : on
        # y voit tout de suite ce que cela change à la place occupée.
        self._preview.panels_requested.connect(self._on_panels_requested)

        self._summary = QLabel(); self._summary.setWordWrap(True)
        self._warnings = QLabel(); self._warnings.setWordWrap(True)
        theme.mark(self._warnings, "warning")

        layout = QVBoxLayout(self)
        layout.addLayout(haut)
        layout.addWidget(self._hint)
        layout.addWidget(self._preview, 1)
        layout.addWidget(self._summary)
        layout.addWidget(self._warnings)
        self.retranslate_ui()

    def _on_panels_requested(self, panels: int) -> None:
        self._session.set_layout(panels=max(1, min(MAX_PANELS, panels)))

    def retranslate_ui(self) -> None:
        self._paper_label.setText(self.tr("Format d'impression"))
        self._landscape.setText(self.tr("Paysage"))
        self._dpi_label.setText(self.tr("Finesse (DPI)"))
        self._preview.retranslate_ui()
        self._hint.setText(
            self.tr("Cet onglet choisit le papier : son format, son orientation, "
                    "et combien de feuilles côte à côte. La carte posée à gauche "
                    "est à ses dimensions réelles et donne l'échelle ; le « + » à "
                    "droite ajoute une feuille, donc de la place. La mosaïque "
                    "dessinée n'est qu'une idée de ce que ça donnerait : les "
                    "onglets « Grille » la régleront précisément.")
        )
        self.refresh()

    def _on_form_changed(self, *_) -> None:
        if self._updating:
            return
        self._session.set_layout(paper=self._paper.currentData(),
                                 landscape=self._landscape.isChecked(),
                                 dpi=self._dpi.value())

    def refresh(self) -> None:
        self._updating = True
        self._paper.setCurrentText(self._session.paper)
        self._landscape.setChecked(self._session.landscape)
        self._dpi.setValue(self._session.dpi)
        self._updating = False
        # Les champs ont pu refuser un format inconnu ou un DPI hors bornes,
        # venus d'un préréglage écrit à la main : on renvoie à la session ce
        # qu'ils ont réellement accepté.
        drifted = {}
        if self._paper.currentText() != self._session.paper:
            drifted["paper"] = self._paper.currentText()
        if self._dpi.value() != self._session.dpi:
            drifted["dpi"] = self._dpi.value()
        if drifted:
            self._session.set_layout(**drifted)
        self._update_summary()
        self._preview.refresh()
        self.state_changed.emit()

    def _update_summary(self) -> None:
        session = self._session
        paper = paper_size_mm(session.paper, session.landscape)
        warnings = []

        # ⚠️ **Un nombre entier de cartes par feuille**, pour qu'une coupe tombe
        # toujours entre deux cartes. C'est la carte qui se plie à la feuille.
        aspect = card_aspect(session)
        geometrie = grid_geometry(
            paper, session.panels, session.cols, session.rows, aspect,
            session.dpi, session.card_width_mm, session.card_gap_mm)
        per_panel, card_w, card_h = (geometrie.per_panel, geometrie.card_w,
                                     geometrie.card_h)
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

        # ⚠️ **La part de papier réellement couverte, dite sans la juger.** Le
        # message conseillait d'allonger la grille pour mieux remplir : depuis
        # qu'ajouter une feuille veut dire « avoir plus de place », ce blanc est
        # l'état normal, et l'onglet précédent l'annonce comme tel. Deux écrans
        # disaient le contraire du même blanc, et le conseil poussait à défaire
        # ce que le « + » venait de faire. On donne le chiffre, et ce qu'il
        # coûte à l'impression — la décision reste à l'utilisateur.
        sheet_px = (mm_to_pixels(paper[0], session.dpi) * session.panels
                    * mm_to_pixels(paper[1], session.dpi))
        coverage = total_w * total_h / sheet_px if sheet_px else 1.0
        if coverage < MIN_SHEET_COVERAGE:
            warnings.append(
                self.tr("La mosaïque couvre %1 % du papier : le reste sortira "
                        "blanc de l'imprimante. C'est normal si vous avez ajouté "
                        "des feuilles pour avoir de la place ; sinon, une grille "
                        "plus large ou moins de feuilles la rempliraient mieux.")
                .replace("%1", f"{coverage * 100:.0f}")
            )

        megapixels = total_w * total_h / 1e6
        if megapixels > 100:
            warnings.append(
                self.tr("Image de %1 Mpx : l'export demandera beaucoup de mémoire.")
                .replace("%1", f"{megapixels:.0f}")
            )
        self._warnings.setText("\n".join(warnings))


class CardSizeTab(LayoutTab):
    """La taille des cartes et l'écart qui les sépare.

    Tant que l'utilisateur n'y touche pas, la taille reste **automatique** : la
    plus grande qui fasse tenir la grille, recalculée à chaque changement. Dès
    qu'il la fixe, le rapport s'inverse — c'est à la grille de s'y adapter, et
    l'écran le dit avec de quoi la corriger.
    """

    def __init__(self, session: Session, parent=None):
        super().__init__(parent)
        self._session = session
        self._updating = False
        self._build()
        session.layout_changed.connect(self.refresh)
        session.selection_changed.connect(self.refresh)
        session.cards_loaded.connect(self.refresh)

    def title(self) -> str:
        return self.tr("Taille des cartes et écarts")

    # --- Construction -----------------------------------------------------

    def _build(self) -> None:
        self._width = QDoubleSpinBox()
        self._width.setRange(1.0, 2000.0)
        self._width.setDecimals(1)
        self._width.setSingleStep(1.0)
        self._width.setSuffix(" mm")
        self._width.setMinimumWidth(110)
        self._width.valueChanged.connect(self._on_form_changed)

        # ⚠️ L'automatique est un **état**, pas une valeur : décoché, le champ
        # montre ce que le calcul a trouvé sans que ce soit un choix.
        self._auto = QCheckBox()
        self._auto.setChecked(True)
        self._auto.toggled.connect(self._on_auto_toggled)

        self._gap = QDoubleSpinBox()
        self._gap.setRange(0.0, 100.0)
        self._gap.setDecimals(1)
        self._gap.setSingleStep(0.5)
        self._gap.setSuffix(" mm")
        self._gap.setMinimumWidth(100)
        self._gap.valueChanged.connect(self._on_form_changed)

        self._width_label = QLabel()
        self._gap_label = QLabel()
        self._real_card = QPushButton()
        self._real_card.clicked.connect(self._use_real_card)

        haut = QHBoxLayout()
        haut.addWidget(self._width_label)
        haut.addWidget(self._width)
        haut.addWidget(self._auto)
        haut.addSpacing(20)
        haut.addWidget(self._gap_label)
        haut.addWidget(self._gap)
        haut.addSpacing(20)
        haut.addWidget(self._real_card)
        haut.addStretch(1)

        self._preview = PagePreview(self._session)
        self._preview.set_show_grid(True)
        self._preview.panels_requested.connect(
            lambda n: self._session.set_layout(panels=max(1, min(MAX_PANELS, n))))

        self._status = QLabel()
        self._status.setWordWrap(True)
        self._status.setTextFormat(Qt.RichText)
        etat = self._status.font()
        etat.setPointSize(etat.pointSize() + STATUS_BOOST)
        self._status.setFont(etat)

        # Les formes qui tiennent, sur demande : la liste ne s'ouvre que quand
        # la grille déborde, seul moment où elle a quelque chose à proposer.
        self._show_shapes = QPushButton()
        self._show_shapes.clicked.connect(self._fill_shapes)
        self._shapes = QListWidget()
        ligne = self._shapes.fontMetrics().height() + 6
        self._shapes.setFixedHeight(ligne * SHAPE_COUNT + 8)
        self._shapes.itemDoubleClicked.connect(self._apply_shape)
        self._shapes_hint = QLabel()
        self._shapes.hide()
        self._shapes_hint.hide()

        bas = QHBoxLayout()
        bas.addWidget(self._status, 1)
        bas.addWidget(self._show_shapes)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.addLayout(haut)
        layout.addWidget(self._preview, 1)
        layout.addWidget(self._shapes_hint)
        layout.addWidget(self._shapes)
        layout.addLayout(bas)
        self.retranslate_ui()

    def retranslate_ui(self) -> None:
        self._width_label.setText(self.tr("Largeur d'une carte"))
        self._auto.setText(self.tr("automatique"))
        self._auto.setToolTip(
            self.tr("La plus grande taille qui fasse tenir la grille, recalculée "
                    "à chaque changement.")
        )
        self._gap_label.setText(self.tr("Écart entre cartes"))
        self._real_card.setText(self.tr("Taille d'une vraie carte"))
        self._real_card.setToolTip(
            self.tr("Fixe la largeur à %1 mm, celle d'une carte qu'on tient en "
                    "main. Ne touche à rien d'autre.").replace(
                        "%1", f"{REAL_CARD_MM[0]:.0f}")
        )
        self._show_shapes.setText(self.tr("Grilles qui tiendraient"))
        self._shapes_hint.setText(
            self.tr("Double-cliquez pour appliquer. Classées par nombre de cartes "
                    "placées, puis par écart à la grille actuelle.")
        )
        self._preview.retranslate_ui()
        self.refresh()

    # --- Réactions --------------------------------------------------------

    def _geometry(self):
        session = self._session
        return grid_geometry(
            paper_size_mm(session.paper, session.landscape), session.panels,
            session.cols, session.rows, card_aspect(session), session.dpi,
            session.card_width_mm, session.card_gap_mm)

    def _on_auto_toggled(self, auto: bool) -> None:
        if self._updating:
            return
        # En repassant en automatique, on oublie la valeur choisie ; en la
        # quittant, on part de ce que le calcul montrait, seul point de départ
        # qui ne fasse pas sauter le dessin.
        self._session.set_layout(
            card_width_mm=None if auto else self._current_width_mm())

    def _current_width_mm(self) -> float:
        geometrie = self._geometry()
        return geometrie.card_w / self._session.dpi * MM_PER_INCH

    def _on_form_changed(self, *_) -> None:
        if self._updating:
            return
        changes = {"card_gap_mm": self._gap.value()}
        if not self._auto.isChecked():
            changes["card_width_mm"] = self._width.value()
        self._session.set_layout(**changes)

    def _use_real_card(self) -> None:
        self._session.set_layout(card_width_mm=float(REAL_CARD_MM[0]))

    def _apply_shape(self, item: QListWidgetItem) -> None:
        cols, rows = item.data(Qt.UserRole)
        self._session.set_layout(cols=cols, rows=rows)

    def _fill_shapes(self) -> None:
        session = self._session
        self._shapes.clear()
        for cols, rows in best_grid_shapes(
            paper_size_mm(session.paper, session.landscape), session.panels,
            session.selected_count, session.cols * session.rows,
            self._geometry(), session.dpi, limit=SHAPE_COUNT,
        ):
            delta = cols * rows - session.selected_count
            if delta == 0:
                note = self.tr("pile poil")
            elif delta > 0:
                note = self.tr("%n case(s) vide(s)", "", delta)
            else:
                note = self.tr("%n carte(s) en trop", "", -delta)
            item = QListWidgetItem(f"{cols} × {rows}  —  {note}")
            item.setData(Qt.UserRole, (cols, rows))
            self._shapes.addItem(item)
        montrer = self._shapes.count() > 0
        self._shapes.setVisible(montrer)
        self._shapes_hint.setVisible(montrer)

    def refresh(self) -> None:
        session = self._session
        auto = session.card_width_mm is None
        self._updating = True
        self._auto.setChecked(auto)
        self._width.setEnabled(not auto)
        self._width.setValue(self._current_width_mm())
        self._gap.setValue(session.card_gap_mm)
        self._updating = False
        self._update_status()
        self._preview.refresh()
        self.state_changed.emit()

    # --- Ce que ça donne, dit d'une couleur -------------------------------

    def is_valid(self) -> bool:
        session = self._session
        return grid_fits(paper_size_mm(session.paper, session.landscape),
                         session.panels, session.cols, session.rows,
                         self._geometry(), session.dpi)

    def _update_status(self) -> None:
        session = self._session
        geometrie = self._geometry()
        tient = self.is_valid()
        largeur = geometrie.card_w / session.dpi * MM_PER_INCH
        hauteur = geometrie.card_h / session.dpi * MM_PER_INCH
        if tient:
            role = "ok"
            texte = self.tr(
                "Cartes de <b>%1 × %2 mm</b>, %3 par feuille. La grille tient.")
            texte = (texte.replace("%1", f"{largeur:.1f}")
                     .replace("%2", f"{hauteur:.1f}")
                     .replace("%3", str(geometrie.per_panel)))
        else:
            role = "error"
            texte = self.tr(
                "À <b>%1 mm</b>, la grille %2 × %3 ne tient pas sur %n feuille(s) : "
                "elle en logerait <b>%4 × %5</b>.", "", session.panels)
            texte = (texte.replace("%1", f"{largeur:.1f}")
                     .replace("%2", str(session.cols))
                     .replace("%3", str(session.rows))
                     .replace("%4", str(geometrie.per_panel * session.panels))
                     .replace("%5", str(self._max_rows(geometrie))))
        theme.mark(self._status, role)
        self._status.setText(texte)
        self._show_shapes.setEnabled(not tient)
        if tient:
            self._shapes.hide()
            self._shapes_hint.hide()

    def _max_rows(self, geometrie) -> int:
        session = self._session
        paper_h = mm_to_pixels(
            paper_size_mm(session.paper, session.landscape)[1], session.dpi)
        pas = geometrie.card_h + geometrie.gap
        return max(0, (paper_h + geometrie.gap) // pas) if pas else 0


class PlacementTab(LayoutTab):
    """Où la grille se pose dans les pages. À écrire.

    Laissé en place plutôt qu'omis : l'onglet existe dans le parcours, et le
    voir vide dit mieux ce qui viendra qu'une absence qu'on prendrait pour un
    oubli.
    """

    def __init__(self, session: Session, parent=None):
        super().__init__(parent)
        self._session = session
        self._build()
        session.layout_changed.connect(self.refresh)

    def title(self) -> str:
        return self.tr("Emplacement de la grille")

    def _build(self) -> None:
        self._hint = QLabel()
        self._hint.setWordWrap(True)
        self._preview = PagePreview(self._session)
        self._preview.set_show_grid(True)
        self._preview.panels_requested.connect(
            lambda n: self._session.set_layout(panels=max(1, min(MAX_PANELS, n))))
        self._todo = QLabel()
        self._todo.setWordWrap(True)
        theme.mark(self._todo, "warning")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.addWidget(self._hint)
        layout.addWidget(self._preview, 1)
        layout.addWidget(self._todo)
        self.retranslate_ui()

    def retranslate_ui(self) -> None:
        self._hint.setText(
            self.tr("La mosaïque est pour l'instant calée contre le bord gauche, "
                    "et centrée verticalement.")
        )
        self._todo.setText(
            self.tr("À venir : un bouton pour la centrer au mieux sur les "
                    "feuilles, et la possibilité de la déplacer en la faisant "
                    "glisser.")
        )
        self._preview.retranslate_ui()
        self.refresh()

    def refresh(self) -> None:
        self._preview.refresh()
        self.state_changed.emit()
