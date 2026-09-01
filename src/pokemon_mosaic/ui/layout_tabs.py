"""Les panneaux de l'étape 2, un par décision à prendre.

Chacun est autonome : il sait dire son titre, si ce qu'il contient est en état
d'être validé, et se rafraîchir. L'écran qui les héberge n'a donc rien à savoir
de leur contenu — ajouter un panneau se fait en l'écrivant ici et en l'ajoutant
à la liste, sans toucher à la navigation.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
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
    mm_to_pixels,
    suggest_grids,
)
from ..optimize import check_links_fit
from . import theme
from .big_spin import BigChoice, BigFloatSpin, BigSpin
from .page_preview import MAX_PANEL_ROWS, MAX_PANELS, PagePreview
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

    # Le nombre de feuilles se règle depuis le dessin, et les quatre panneaux
    # montrent le même dessin : le geste appartient donc à la classe commune.
    def _on_panels_requested(self, panels: int) -> None:
        self._session.set_layout(panels=max(1, min(MAX_PANELS, panels)))

    def _on_panel_rows_requested(self, rows: int) -> None:
        self._session.set_layout(panel_rows=max(1, min(MAX_PANEL_ROWS, rows)))

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
        largeur, hauteur = session.sheet_mm()
        found = suggest_grids(
            session.selected_count, card_aspect(session), largeur / hauteur,
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
        self._preview.panels_requested.connect(self._on_panels_requested)
        self._preview.panel_rows_requested.connect(self._on_panel_rows_requested)
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
        largeur, hauteur = session.sheet_mm()
        for suggestion in suggest_grids(
            max(session.selected_count, 1), card_aspect(session),
            largeur / hauteur, limit=SUGGESTION_COUNT,
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
        # ⚠️ **Trois champs pour une seule feuille.** Le format nommé est une
        # commodité, pas la définition : la feuille se décrit par ses deux
        # côtés, et un nom n'existe que pour sept d'entre elles. Les deux
        # dimensions sont donc modifiables, et le nom suit ce qu'elles disent —
        # rien à quoi il corresponde, et le champ montre une croix.
        self._paper = BigChoice(list(PAPER_FORMATS_MM))
        self._paper.value_changed.connect(self._on_format_chosen)
        # En centimètres : c'est ce qu'on lit sur une rame de papier, et le
        # millimètre demanderait quatre chiffres pour dire la même chose.
        self._width = BigFloatSpin(1.0, 200.0, step=0.5)
        self._height = BigFloatSpin(1.0, 200.0, step=0.5)
        for champ in (self._width, self._height):
            champ.value_changed.connect(self._on_size_changed)
        for champ in (self._paper, self._width, self._height):
            champ.setFixedWidth(140)

        # L'orientation décrit la feuille : elle appartient à cet onglet, pas au
        # suivant, où elle n'avait rien à voir avec la finesse d'impression.
        self._landscape = QCheckBox()
        self._landscape.toggled.connect(self._on_landscape_toggled)
        # ⚠️ **La finesse n'est plus ici.** Elle ne décide de rien qui se voie
        # sur cet écran — tout s'y mesure en millimètres — et la demander au
        # début obligeait à trancher une question d'impression avant d'avoir
        # posé la mosaïque. Elle se choisit à l'export, devant le fichier
        # qu'elle pèse.

        champs = QHBoxLayout()
        champs.setSpacing(14)
        champs.addWidget(self._paper)
        champs.addWidget(self._width)
        champs.addWidget(self._height)
        champs.addStretch(1)

        self._sheet_title = QLabel()
        titre = self._sheet_title.font()
        titre.setBold(True)
        titre.setPointSize(titre.pointSize() + 1)
        self._sheet_title.setFont(titre)

        gauche = QVBoxLayout()
        gauche.setSpacing(6)
        gauche.addWidget(self._sheet_title)
        gauche.addLayout(champs)
        gauche.addWidget(self._landscape)

        self._hint = QLabel()
        self._hint.setWordWrap(True)
        self._hint.setAlignment(Qt.AlignTop)

        haut = QHBoxLayout()
        haut.setSpacing(24)
        haut.addLayout(gauche)
        haut.addWidget(self._hint, 1)
        bandeau = QWidget()
        bandeau.setLayout(haut)
        bandeau.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

        # ⚠️ **La mosaïque ne se dessine pas ici.** Cet onglet ne décide que du
        # papier, et une grille posée dessus se lisait comme un aperçu du
        # résultat alors qu'elle n'était réglée nulle part encore : on la
        # regardait pour juger une mise en page que les onglets suivants
        # allaient refaire. La feuille, l'étalon et les boutons suffisent à
        # dire ce que cet onglet décide.
        self._preview = PagePreview(self._session)
        self._preview.set_show_grid(False)
        # Les feuilles s'ajoutent et se retirent depuis le dessin lui-même : on
        # y voit tout de suite ce que cela change à la place occupée.
        self._preview.panels_requested.connect(self._on_panels_requested)
        self._preview.panel_rows_requested.connect(self._on_panel_rows_requested)

        self._summary = QLabel(); self._summary.setWordWrap(True)
        self._warnings = QLabel(); self._warnings.setWordWrap(True)
        theme.mark(self._warnings, "warning")

        layout = QVBoxLayout(self)
        layout.addWidget(bandeau)
        layout.addWidget(self._preview, 1)
        layout.addWidget(self._summary)
        layout.addWidget(self._warnings)
        self.retranslate_ui()

    def retranslate_ui(self) -> None:
        self._sheet_title.setText(self.tr("Format de la feuille"))
        self._paper.setTitle(self.tr("Format"))
        self._width.setTitle(self.tr("Largeur (cm)"))
        self._height.setTitle(self.tr("Hauteur (cm)"))
        self._landscape.setText(self.tr("Paysage"))
        self._preview.retranslate_ui()
        self._hint.setText(
            self.tr("Choisissez le format de la feuille, et appuyez sur les "
                    "boutons + ou − pour ajouter ou enlever des feuilles.")
        )
        self.refresh()

    # --- Réactions --------------------------------------------------------

    def _on_format_chosen(self, name: str) -> None:
        if not self._updating:
            self._session.set_layout(paper=name)

    def _on_landscape_toggled(self, landscape: bool) -> None:
        if not self._updating:
            self._session.set_layout(landscape=landscape)

    def _on_size_changed(self, *_) -> None:
        """Les deux champs disent la feuille **telle qu'elle s'imprime**.

        C'est donc l'orientation qu'on défait avant de ranger : la session tient
        toujours la feuille en portrait, et « A4 paysage » doit rester un A4.
        """
        if self._updating:
            return
        width = self._width.value() * 10
        height = self._height.value() * 10
        if self._session.landscape:
            width, height = height, width
        self._session.set_layout(paper_size_mm=(width, height))

    def refresh(self) -> None:
        session = self._session
        width, height = session.paper_mm()
        self._updating = True
        self._paper.setValue(session.paper)
        self._width.setValue(width / 10)
        self._height.setValue(height / 10)
        self._landscape.setChecked(session.landscape)
        self._updating = False
        self._update_summary()
        self._preview.refresh()
        self.state_changed.emit()

    def _update_summary(self) -> None:
        session = self._session
        paper = session.paper_mm()
        warnings = []

        # ⚠️ **Le résumé ne parle que du papier.** Il annonçait la taille des
        # cartes et de la mosaïque : ni l'une ni l'autre ne se règle ici, ni ne
        # se voit depuis que la grille n'y est plus dessinée, et un format hors
        # catalogue laissait un trou là où le nom devait aller. Ce que cet
        # onglet décide, c'est une surface — c'est elle qu'il chiffre.
        largeur, hauteur = session.sheet_mm()
        self._summary.setText(
            self.tr("%n feuille(s) de %1 × %2 cm — surface totale de %3 × %4 cm.",
                    "", session.panel_count())
            .replace("%1", f"{paper[0] / 10:.1f}")
            .replace("%2", f"{paper[1] / 10:.1f}")
            .replace("%3", f"{largeur / 10:.1f}")
            .replace("%4", f"{hauteur / 10:.1f}")
        )

        # La mosaïque n'est pas dessinée ici, mais c'est bien cette surface
        # qu'elle couvrira : le blanc qui reste se compte en feuilles achetées.
        aspect = card_aspect(session)
        geometrie = grid_geometry(
            paper, session.panels, session.cols, session.rows, aspect,
            session.dpi, session.card_width_mm, session.card_gap_mm,
            session.panel_rows)
        total_w = geometrie.span(session.cols)
        total_h = (geometrie.card_h * session.rows
                   + max(0, session.rows - 1) * geometrie.gap)

        # Un lien qui déborde de la grille ne se verrait sinon qu'au lancement
        # du calcul, bien après le choix de la mise en page.
        try:
            check_links_fit(session.usable_links().active,
                            session.cols, session.rows)
        except ValueError as error:
            warnings.append(str(error))

        # ⚠️ **La part de papier réellement couverte, dite sans la juger.** Le
        # message conseillait d'allonger la grille pour mieux remplir : depuis
        # qu'ajouter une feuille veut dire « avoir plus de place », ce blanc est
        # l'état normal, et l'onglet précédent l'annonce comme tel. Deux écrans
        # disaient le contraire du même blanc, et le conseil poussait à défaire
        # ce que le « + » venait de faire. On donne le chiffre, et ce qu'il
        # coûte à l'impression — la décision reste à l'utilisateur.
        sheet_px = (mm_to_pixels(largeur, session.dpi)
                    * mm_to_pixels(hauteur, session.dpi))
        coverage = total_w * total_h / sheet_px if sheet_px else 1.0
        if coverage < MIN_SHEET_COVERAGE:
            warnings.append(
                self.tr("La mosaïque couvre %1 % du papier : le reste sortira "
                        "blanc de l'imprimante. C'est normal si vous avez ajouté "
                        "des feuilles pour avoir de la place ; sinon, une grille "
                        "plus large ou moins de feuilles la rempliraient mieux.")
                .replace("%1", f"{coverage * 100:.0f}")
            )

        # Le poids de l'image en mégapixels est parti avec la finesse : il se
        # dit à l'export, où elle se choisit, et avec le chiffre de mémoire.
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
        # ⚠️ **Les mêmes champs que les dimensions de la grille.** Ce sont deux
        # réglages du même ordre — ce qu'on met dans la case, après la taille de
        # la grille —, et deux `QDoubleSpinBox` de vingt pixels les faisaient
        # passer pour des détails d'un formulaire.
        self._width = BigFloatSpin(1.0, 2000.0, step=1.0)
        self._width.value_changed.connect(self._on_form_changed)
        self._gap = BigFloatSpin(0.0, 100.0, step=0.5)
        self._gap.value_changed.connect(self._on_form_changed)
        for champ in (self._width, self._gap):
            champ.setFixedWidth(150)

        # ⚠️ L'automatique est un **état**, pas une valeur : décoché, le champ
        # montre ce que le calcul a trouvé sans que ce soit un choix.
        self._auto = QCheckBox()
        self._auto.setChecked(True)
        self._auto.toggled.connect(self._on_auto_toggled)

        # Le bouton se lit comme une valeur possible du champ qu'il remplit :
        # sa place est dessous, pas à l'autre bout de la ligne.
        self._real_card = QPushButton()
        self._real_card.clicked.connect(self._use_real_card)

        largeur = QVBoxLayout()
        largeur.setSpacing(4)
        largeur.addWidget(self._width)
        largeur.addWidget(self._real_card)
        largeur.addWidget(self._auto, 0, Qt.AlignHCenter)

        ecart = QVBoxLayout()
        ecart.setSpacing(4)
        ecart.addWidget(self._gap)
        ecart.addStretch(1)

        reglages = QHBoxLayout()
        reglages.setSpacing(14)
        reglages.addLayout(largeur)
        reglages.addLayout(ecart)

        # Les formes qui tiendraient, en haut avec les réglages qu'elles
        # corrigent : en bas, la liste poussait la grille hors de l'écran au
        # moment précis où l'on voulait la regarder changer.
        self._show_shapes = QPushButton()
        self._show_shapes.clicked.connect(self._fill_shapes)
        self._shapes_hint = QLabel()
        self._shapes = QListWidget()
        ligne = self._shapes.fontMetrics().height() + 6
        self._shapes.setFixedHeight(ligne * SHAPE_COUNT + 8)
        self._shapes.itemDoubleClicked.connect(self._apply_shape)
        # Vide, elle laissait un rectangle noir sur un quart du panneau. Une
        # fois ouverte, en revanche, elle **reste** : elle se refermait dès que
        # la grille tenait, c'est-à-dire juste après le double-clic, et comparer
        # deux propositions demandait de la rouvrir entre chacune.
        self._shapes.hide()

        entete = QHBoxLayout()
        entete.setContentsMargins(0, 0, 0, 0)
        entete.addWidget(self._show_shapes)
        entete.addSpacing(12)
        entete.addWidget(self._shapes_hint)
        entete.addStretch(1)

        self._shapes_box = QWidget()
        formes = QVBoxLayout(self._shapes_box)
        formes.setContentsMargins(0, 0, 0, 0)
        formes.setSpacing(2)
        formes.addLayout(entete)
        formes.addWidget(self._shapes)

        haut = QHBoxLayout()
        haut.setSpacing(16)
        haut.addLayout(reglages)
        haut.addWidget(self._shapes_box, 1)
        bandeau = QWidget()
        bandeau.setLayout(haut)
        bandeau.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

        self._preview = PagePreview(self._session)
        self._preview.set_show_grid(True)
        self._preview.panels_requested.connect(self._on_panels_requested)
        self._preview.panel_rows_requested.connect(self._on_panel_rows_requested)

        self._status = QLabel()
        self._status.setWordWrap(True)
        self._status.setTextFormat(Qt.RichText)
        etat = self._status.font()
        etat.setPointSize(etat.pointSize() + STATUS_BOOST)
        self._status.setFont(etat)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.addWidget(bandeau)
        layout.addWidget(self._preview, 1)
        layout.addWidget(self._status)
        self.retranslate_ui()

    def retranslate_ui(self) -> None:
        self._width.setTitle(self.tr("Largeur d'une carte (mm)"))
        self._gap.setTitle(self.tr("Écart entre cartes (mm)"))
        self._auto.setText(self.tr("automatique"))
        self._auto.setToolTip(
            self.tr("La plus grande taille qui fasse tenir la grille, recalculée "
                    "à chaque changement.")
        )
        self._real_card.setText(self.tr("Taille d'une vraie carte"))
        self._real_card.setToolTip(
            self.tr("Fixe la largeur à %1 mm, celle d'une carte qu'on tient en "
                    "main. Ne touche à rien d'autre.").replace(
                        "%1", f"{REAL_CARD_MM[0]:.0f}")
        )
        self._show_shapes.setText(self.tr("Grilles qui tiendraient"))
        self._shapes_hint.setText(self.tr("Double-cliquez pour appliquer"))
        self._preview.retranslate_ui()
        self.refresh()

    # --- Réactions --------------------------------------------------------

    def _geometry(self):
        session = self._session
        return grid_geometry(
            session.paper_mm(), session.panels,
            session.cols, session.rows, card_aspect(session), session.dpi,
            session.card_width_mm, session.card_gap_mm, session.panel_rows)

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
            session.panels, session.selected_count,
            session.cols * session.rows, self._geometry(), limit=SHAPE_COUNT,
            panel_rows=session.panel_rows,
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
        # Aucune forme ne tient parfois — une carte de 2 000 mm sur un A5 — et
        # la liste vide était alors un rectangle noir sans explication.
        trouve = self._shapes.count() > 0
        self._shapes.setVisible(trouve)
        self._shapes_hint.setText(
            self.tr("Double-cliquez pour appliquer") if trouve
            else self.tr("Aucune grille ne tiendrait à cette taille de carte.")
        )

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
        return grid_fits(session.panels, session.cols, session.rows,
                         self._geometry(), session.panel_rows)

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
                "elle en logerait <b>%4 × %5</b>.", "", session.panel_count())
            texte = (texte.replace("%1", f"{largeur:.1f}")
                     .replace("%2", str(session.cols))
                     .replace("%3", str(session.rows))
                     .replace("%4", str(geometrie.per_panel * session.panels))
                     .replace("%5", str(geometrie.rows_per_panel
                                        * session.panel_rows)))
        theme.mark(self._status, role)
        self._status.setText(texte)


class PlacementTab(LayoutTab):
    """Où chaque bout de grille se pose dans sa feuille.

    ⚠️ **Un bout de grille ne quitte pas sa feuille.** Le poster se coupe entre
    deux cartes, jamais au milieu d'une : laisser glisser la mosaïque d'une
    feuille à l'autre remettrait cette règle en jeu à chaque geste. Chaque
    feuille porte donc son morceau, et le déplace pour son compte.
    """

    def __init__(self, session: Session, parent=None):
        super().__init__(parent)
        self._session = session
        self._build()
        session.layout_changed.connect(self.refresh)
        session.selection_changed.connect(self.refresh)
        session.cards_loaded.connect(self.refresh)

    def title(self) -> str:
        return self.tr("Emplacement de la grille")

    def _build(self) -> None:
        self._hint = QLabel()
        self._hint.setWordWrap(True)
        self._reset = QPushButton()
        self._reset.clicked.connect(self._put_back)

        haut = QHBoxLayout()
        haut.addWidget(self._hint, 1)
        haut.addWidget(self._reset)
        bandeau = QWidget()
        bandeau.setLayout(haut)
        bandeau.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

        self._preview = PagePreview(self._session)
        self._preview.set_show_grid(True)
        self._preview.set_draggable(True)
        self._preview.panels_requested.connect(self._on_panels_requested)
        self._preview.panel_rows_requested.connect(self._on_panel_rows_requested)
        self._preview.panel_moved.connect(self._session.move_panel)

        self._status = QLabel()
        self._status.setWordWrap(True)
        self._status.setTextFormat(Qt.RichText)
        etat = self._status.font()
        etat.setPointSize(etat.pointSize() + STATUS_BOOST)
        self._status.setFont(etat)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.addWidget(bandeau)
        layout.addWidget(self._preview, 1)
        layout.addWidget(self._status)
        self.retranslate_ui()

    def retranslate_ui(self) -> None:
        self._hint.setText(
            self.tr("Cliquez dans la mosaïque et tirez pour la déplacer. Chaque "
                    "feuille porte son morceau et le déplace pour son compte : "
                    "un morceau ne passe jamais sur la feuille voisine, sans "
                    "quoi une coupe tomberait en pleine carte.")
        )
        self._reset.setText(self.tr("Remettre en place"))
        self._reset.setToolTip(
            self.tr("Ramène tous les morceaux à leur emplacement par défaut : "
                    "calés à gauche, centrés en hauteur.")
        )
        self._preview.retranslate_ui()
        self.refresh()

    def _put_back(self) -> None:
        if self._session.panel_offsets:
            self._session.set_layout(panel_offsets={})

    def refresh(self) -> None:
        deplaces = len(self._session.panel_offsets)
        if deplaces:
            role, texte = "ok", self.tr(
                "<b>%n</b> feuille(s) déplacée(s) à la main.", "", deplaces)
        else:
            role, texte = "ok", self.tr(
                "Les morceaux sont à leur emplacement par défaut.")
        theme.mark(self._status, role)
        self._status.setText(texte)
        self._reset.setEnabled(bool(deplaces))
        self._preview.refresh()
        self.state_changed.emit()
