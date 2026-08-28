"""Étape 2 — format d'impression, grille et cases vides."""

from PySide6.QtCore import Qt
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
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..layout import (
    PAPER_FORMATS_MM,
    card_pixel_size,
    max_useful_dpi,
    paper_size_mm,
    suggest_grids,
)
from ..optimize import check_links_fit
from . import theme
from .session import Session
from .wireframe import WireframeView


class LayoutStep(QWidget):
    """Réglages de mise en page, avec aperçu fil de fer en direct."""

    def __init__(self, session: Session, parent=None):
        super().__init__(parent)
        self._session = session
        self._updating = False
        self._build()
        session.layout_changed.connect(self._refresh)
        session.selection_changed.connect(self._refresh)
        session.cards_loaded.connect(self._refresh)

    # --- Construction -----------------------------------------------------

    def _build(self) -> None:
        self._paper = QComboBox()
        for name in PAPER_FORMATS_MM:
            self._paper.addItem(name, name)
        self._paper.setCurrentText(self._session.paper)
        self._landscape = QCheckBox()
        self._dpi = QSpinBox(); self._dpi.setRange(50, 1200); self._dpi.setSingleStep(50)
        self._dpi.setValue(self._session.dpi)
        self._panels = QSpinBox(); self._panels.setRange(1, 6)
        self._panels.setValue(self._session.panels)
        self._cols = QSpinBox(); self._cols.setRange(1, 200)
        self._cols.setValue(self._session.cols)
        self._rows = QSpinBox(); self._rows.setRange(1, 200)
        self._rows.setValue(self._session.rows)

        for widget in (self._paper, self._landscape, self._dpi, self._panels,
                       self._cols, self._rows):
            signal = (widget.currentTextChanged if isinstance(widget, QComboBox)
                      else widget.toggled if isinstance(widget, QCheckBox)
                      else widget.valueChanged)
            signal.connect(self._on_form_changed)

        self._form_box = QGroupBox()
        form = QFormLayout(self._form_box)
        self._labels = {}
        for key, widget in (("paper", self._paper), ("landscape", self._landscape),
                            ("dpi", self._dpi), ("panels", self._panels),
                            ("cols", self._cols), ("rows", self._rows)):
            label = QLabel()
            self._labels[key] = label
            form.addRow(label, widget)

        self._suggestions_box = QGroupBox()
        self._suggestions = QListWidget()
        self._suggestions.itemDoubleClicked.connect(self._apply_suggestion)
        self._suggestions_hint = QLabel()
        self._suggestions_hint.setWordWrap(True)
        suggestions_layout = QVBoxLayout(self._suggestions_box)
        suggestions_layout.addWidget(self._suggestions_hint)
        suggestions_layout.addWidget(self._suggestions)

        self._reset_empty = QPushButton()
        self._reset_empty.clicked.connect(self._session.reset_empty_cells)

        left = QVBoxLayout()
        left.addWidget(self._form_box)
        left.addWidget(self._suggestions_box, 1)
        left.addWidget(self._reset_empty)
        left_panel = QWidget(); left_panel.setLayout(left)
        left_panel.setFixedWidth(330)

        self._wireframe = WireframeView(self._session)
        self._wireframe.cell_clicked.connect(self._session.toggle_empty_cell)
        self._preview_hint = QLabel(); self._preview_hint.setWordWrap(True)
        self._summary = QLabel(); self._summary.setWordWrap(True)
        self._warnings = QLabel(); self._warnings.setWordWrap(True)
        theme.mark(self._warnings, "error")

        right = QVBoxLayout()
        right.addWidget(self._preview_hint)
        right.addWidget(self._wireframe, 1)
        right.addWidget(self._summary)
        right.addWidget(self._warnings)
        right_panel = QWidget(); right_panel.setLayout(right)

        layout = QHBoxLayout(self)
        layout.addWidget(left_panel)
        layout.addWidget(right_panel, 1)
        self.retranslate_ui()

    def retranslate_ui(self) -> None:
        self._form_box.setTitle(self.tr("Format et grille"))
        self._labels["paper"].setText(self.tr("Format d'impression"))
        self._labels["landscape"].setText(self.tr("Paysage"))
        self._labels["dpi"].setText(self.tr("Résolution (DPI)"))
        self._labels["panels"].setText(self.tr("Posters côte à côte"))
        self._labels["cols"].setText(self.tr("Colonnes"))
        self._labels["rows"].setText(self.tr("Lignes"))
        self._suggestions_box.setTitle(self.tr("Grilles adaptées à ce format"))
        self._suggestions_hint.setText(
            self.tr("Double-cliquez pour appliquer. L'écart indique de combien la "
                    "grille s'éloigne des proportions de la feuille.")
        )
        self._reset_empty.setText(self.tr("Replacer les cases vides automatiquement"))
        self._preview_hint.setText(
            self.tr("Aperçu de la mise en page, sans les images. "
                    "Cliquez une case pour y placer ou retirer un vide.")
        )
        self._refresh()

    # --- Réactions --------------------------------------------------------

    def _on_form_changed(self, *_) -> None:
        if self._updating:
            return
        self._session.set_layout(
            paper=self._paper.currentData(), landscape=self._landscape.isChecked(),
            dpi=self._dpi.value(), panels=self._panels.value(),
            cols=self._cols.value(), rows=self._rows.value(),
        )

    def _apply_suggestion(self, item: QListWidgetItem) -> None:
        cols, rows = item.data(Qt.UserRole)
        self._updating = True
        self._cols.setValue(cols)
        self._rows.setValue(rows)
        self._updating = False
        self._on_form_changed()

    def _sync_form(self) -> None:
        """Recopie la session dans les champs.

        Indispensable dès que la mise en page peut changer ailleurs que dans ce
        formulaire — chargement d'un préréglage, par exemple. Sans cela, les champs
        affichent une configuration qui n'est plus celle utilisée.
        """
        self._updating = True
        session = self._session
        self._paper.setCurrentText(session.paper)
        self._landscape.setChecked(session.landscape)
        self._dpi.setValue(session.dpi)
        self._panels.setValue(session.panels)
        self._cols.setValue(session.cols)
        self._rows.setValue(session.rows)
        self._updating = False
        self._push_back_clamped()

    def _push_back_clamped(self) -> None:
        """Renvoie à la session ce que les champs ont réellement accepté.

        Un préréglage écrit à la main peut porter un DPI hors bornes ou un format
        de papier inconnu. Le champ l'écrête, ou l'ignore pour une liste
        déroulante ; sans ce retour, la session garderait la valeur d'origine et
        le formulaire décrirait un poster différent de celui qui sera produit —
        un format inconnu faisant même échouer l'export.
        """
        session = self._session
        accepted = {
            "paper": self._paper.currentText(),
            "dpi": self._dpi.value(),
            "panels": self._panels.value(),
            "cols": self._cols.value(),
            "rows": self._rows.value(),
        }
        drifted = {name: value for name, value in accepted.items()
                   if getattr(session, name) != value}
        if drifted:
            session.set_layout(**drifted)

    def _refresh(self) -> None:
        self._sync_form()
        self._fill_suggestions()
        self._update_summary()
        self._wireframe.update()

    def _card_aspect(self) -> float:
        card_set = self._session.card_set
        if card_set and card_set.full_size[1]:
            return card_set.full_size[0] / card_set.full_size[1]
        return 713 / 984

    def _fill_suggestions(self) -> None:
        self._suggestions.clear()
        session = self._session
        paper_w, paper_h = paper_size_mm(session.paper, session.landscape)
        found = suggest_grids(
            max(session.selected_count, 1), self._card_aspect(),
            paper_w * session.panels / paper_h, panels=session.panels,
        )
        for suggestion in found:
            delta = suggestion.card_delta
            if delta == 0:
                note = self.tr("pile poil")
            elif delta > 0:
                note = self.tr("+%n carte(s) à ajouter", "", delta)
            else:
                note = self.tr("%n carte(s) en trop", "", -delta)
            item = QListWidgetItem(
                f"{suggestion.cols}×{suggestion.rows}  "
                f"({suggestion.cells})  —  {suggestion.aspect_error * 100:.1f} %  —  {note}"
            )
            item.setData(Qt.UserRole, (suggestion.cols, suggestion.rows))
            self._suggestions.addItem(item)

    def _update_summary(self) -> None:
        session = self._session
        paper = paper_size_mm(session.paper, session.landscape)
        warnings = []

        if session.cols % session.panels:
            warnings.append(
                self.tr("%1 colonnes ne se divisent pas en %2 panneaux : la coupe "
                        "tomberait au milieu d'une carte.")
                .replace("%1", str(session.cols)).replace("%2", str(session.panels))
            )
            self._summary.setText("")
            self._warnings.setText("\n".join(warnings))
            return

        per_panel = session.cols // session.panels
        card_w, card_h = card_pixel_size(paper, per_panel, session.rows,
                                         self._card_aspect(), session.dpi)
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

        fit = session.grid_fit()
        if not fit.fits_exactly:
            warnings.append(fit.message())

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
        megapixels = total_w * total_h / 1e6
        if megapixels > 100:
            warnings.append(
                self.tr("Image de %1 Mpx : l'export demandera beaucoup de mémoire.")
                .replace("%1", f"{megapixels:.0f}")
            )
        self._warnings.setText("\n".join(warnings))
