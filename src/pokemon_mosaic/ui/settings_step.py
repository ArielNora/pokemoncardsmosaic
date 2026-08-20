"""Étape 3 — réglages de l'algorithme, de base et avancés."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .estimates import estimated_gain, estimated_seconds, estimated_snapshots, format_duration
from .session import Session
from .strip_preview import StripPreview

# En deçà, la timeline offrira trop peu d'états pour être navigable.
USEFUL_SNAPSHOTS = 10


class SettingsStep(QWidget):
    """Deux colonnes : les réglages à gauche, ce qu'ils impliquent à droite."""

    def __init__(self, session: Session, parent=None):
        super().__init__(parent)
        self._session = session
        self._updating = False
        self._build()
        session.algorithm_changed.connect(self._refresh)
        session.cards_loaded.connect(self._refresh)

    # --- Construction -----------------------------------------------------

    def _build(self) -> None:
        self._labels = {}
        basic = self._build_basic()
        advanced = self._build_advanced()

        left = QVBoxLayout()
        left.addWidget(basic)
        left.addWidget(advanced)
        left.addStretch(1)
        left_panel = QWidget()
        left_panel.setLayout(left)
        left_panel.setFixedWidth(430)

        self._preview_box = QGroupBox()
        self._preview = StripPreview(self._session)
        self._preview.setMaximumHeight(260)
        self._preview_hint = QLabel()
        self._preview_hint.setWordWrap(True)
        self._preview_hint.setAlignment(Qt.AlignTop)
        preview_layout = QVBoxLayout(self._preview_box)
        preview_layout.addWidget(self._preview_hint)
        preview_layout.addWidget(self._preview)
        # L'espace libre va sous l'aperçu, sinon celui-ci flotterait au milieu
        # d'un grand vide, l'intitulé se retrouvant centré verticalement.
        preview_layout.addStretch(1)

        self._projection_box = QGroupBox()
        self._duration = QLabel()
        self._gain = QLabel()
        self._snapshots = QLabel()
        self._snapshots.setWordWrap(True)
        projection = QVBoxLayout(self._projection_box)
        for label in (self._duration, self._gain, self._snapshots):
            projection.addWidget(label)

        right = QVBoxLayout()
        right.addWidget(self._preview_box, 1)
        right.addWidget(self._projection_box)
        right_panel = QWidget()
        right_panel.setLayout(right)

        layout = QHBoxLayout(self)
        layout.addWidget(left_panel)
        layout.addWidget(right_panel, 1)
        self._connect_all()
        self.retranslate_ui()

    def _build_basic(self) -> QGroupBox:
        self._iterations = QSpinBox()
        self._iterations.setRange(1000, 50_000_000)
        self._iterations.setSingleStep(50_000)
        self._iterations.setGroupSeparatorShown(True)
        self._snapshot_every = QSpinBox()
        self._snapshot_every.setRange(1, 1000)
        self._stop_on_stagnation = QCheckBox()
        self._stagnation = QSpinBox()
        self._stagnation.setRange(1000, 10_000_000)
        self._stagnation.setSingleStep(10_000)
        self._stagnation.setGroupSeparatorShown(True)
        self._stagnation.setMinimumWidth(190)
        self._stop_on_time = QCheckBox()
        self._time_budget = QDoubleSpinBox()
        self._time_budget.setRange(1.0, 3600.0)
        self._time_budget.setSuffix(" s")
        self._empty_colour = QPushButton()
        self._empty_colour.clicked.connect(self._pick_empty_colour)

        box = QGroupBox()
        self._basic_box = box
        form = QFormLayout(box)
        for key, widget in (("iterations", self._iterations),
                            ("snapshot_every", self._snapshot_every),
                            ("empty_colour", self._empty_colour)):
            label = QLabel()
            self._labels[key] = label
            form.addRow(label, widget)
        # Les seuils : la case à cocher sert d'intitulé, l'unité est un suffixe
        # du champ. Une étiquette séparée se ferait tronquer par le champ voisin.
        form.addRow(self._stop_on_stagnation, self._stagnation)
        form.addRow(self._stop_on_time, self._time_budget)
        return box

    def _build_advanced(self) -> QGroupBox:
        self._algorithm = QComboBox()
        self._algorithm.addItem("", True)      # recuit
        self._algorithm.addItem("", False)     # descente stricte
        self._acceptance = QDoubleSpinBox()
        self._acceptance.setRange(0.01, 0.99)
        self._acceptance.setSingleStep(0.05)
        self._strip_size = QDoubleSpinBox()
        self._strip_size.setRange(0.01, 0.50)
        self._strip_size.setSingleStep(0.05)
        self._stop_on_score = QCheckBox()
        self._target_score = QDoubleSpinBox()
        self._target_score.setRange(0.0, 10_000_000.0)
        self._target_score.setDecimals(0)
        self._target_score.setMinimumWidth(190)

        box = QGroupBox()
        self._advanced_box = box
        form = QFormLayout(box)
        for key, widget in (("algorithm", self._algorithm),
                            ("acceptance", self._acceptance),
                            ("strip_size", self._strip_size)):
            label = QLabel()
            self._labels[key] = label
            form.addRow(label, widget)
        form.addRow(self._stop_on_score, self._target_score)
        return box

    def _connect_all(self) -> None:
        for widget in (self._iterations, self._snapshot_every, self._stagnation,
                       self._time_budget, self._acceptance, self._strip_size,
                       self._target_score):
            widget.valueChanged.connect(self._on_form_changed)
        for widget in (self._stop_on_stagnation, self._stop_on_time,
                       self._stop_on_score):
            widget.toggled.connect(self._on_form_changed)
        self._algorithm.currentIndexChanged.connect(self._on_form_changed)

    def retranslate_ui(self) -> None:
        self._basic_box.setTitle(self.tr("Réglages de base"))
        self._advanced_box.setTitle(self.tr("Réglages avancés"))
        self._labels["iterations"].setText(self.tr("Durée du calcul (itérations)"))
        self._labels["snapshot_every"].setText(self.tr("Un cliché tous les N échanges retenus"))
        self._labels["empty_colour"].setText(self.tr("Couleur des cases vides"))
        self._stop_on_stagnation.setText(self.tr("Arrêter sur stagnation après"))
        self._stagnation.setSuffix(self.tr(" itérations sans gain"))
        self._target_score.setPrefix(self.tr("score "))
        self._stop_on_time.setText(self.tr("Arrêter sur le temps"))
        self._stop_on_score.setText(self.tr("Arrêter sur score atteint"))
        self._labels["algorithm"].setText(self.tr("Algorithme"))
        self._labels["acceptance"].setText(self.tr("Tolérance d'acceptation"))
        self._labels["strip_size"].setText(self.tr("Épaisseur des bandes de bord"))
        self._algorithm.setItemText(0, self.tr("Recuit simulé"))
        self._algorithm.setItemText(1, self.tr("Descente stricte"))
        self._preview_box.setTitle(self.tr("Effet de l'épaisseur des bandes"))
        self._preview_hint.setText(
            self.tr("À gauche, la zone mesurée sur une carte. À droite, une petite "
                    "grille d'essai réoptimisée à cette épaisseur.")
        )
        self._projection_box.setTitle(self.tr("Ce que ces réglages impliquent"))
        self._refresh()

    # --- Réactions --------------------------------------------------------

    def _on_form_changed(self, *_) -> None:
        if self._updating:
            return
        self._session.set_algorithm(
            iterations=self._iterations.value(),
            snapshot_every=self._snapshot_every.value(),
            stop_on_stagnation=self._stop_on_stagnation.isChecked(),
            stagnation_iterations=self._stagnation.value(),
            stop_on_time=self._stop_on_time.isChecked(),
            time_budget=self._time_budget.value(),
            use_annealing=self._algorithm.currentData(),
            acceptance=self._acceptance.value(),
            strip_size=self._strip_size.value(),
            stop_on_score=self._stop_on_score.isChecked(),
            target_score=self._target_score.value(),
        )

    def _pick_empty_colour(self) -> None:
        current = QColor(*self._session.empty_colour)
        chosen = QColorDialog.getColor(current, self, self.tr("Couleur des cases vides"))
        if chosen.isValid():
            self._session.set_algorithm(
                empty_colour=(chosen.red(), chosen.green(), chosen.blue())
            )

    def _sync_form(self) -> None:
        """Recopie la session dans les champs, sans réémettre."""
        self._updating = True
        session = self._session
        self._iterations.setValue(session.iterations)
        self._snapshot_every.setValue(session.snapshot_every)
        self._stop_on_stagnation.setChecked(session.stop_on_stagnation)
        self._stagnation.setValue(session.stagnation_iterations)
        self._stop_on_time.setChecked(session.stop_on_time)
        self._time_budget.setValue(session.time_budget)
        self._algorithm.setCurrentIndex(0 if session.use_annealing else 1)
        self._acceptance.setValue(session.acceptance)
        self._strip_size.setValue(session.strip_size)
        self._stop_on_score.setChecked(session.stop_on_score)
        self._target_score.setValue(session.target_score)
        self._updating = False
        self._push_back_clamped()

    def _push_back_clamped(self) -> None:
        """Renvoie à la session ce que les champs ont réellement accepté.

        Un préréglage écrit à la main peut porter une valeur hors bornes — le
        format est du JSON, et la spec assume qu'on le retouche. Le champ
        l'écrête pour l'afficher ; sans ce retour, la session garderait la valeur
        d'origine et le formulaire annoncerait un calcul différent de celui qui
        aura lieu.
        """
        session = self._session
        accepted = {
            "iterations": self._iterations.value(),
            "snapshot_every": self._snapshot_every.value(),
            "stagnation_iterations": self._stagnation.value(),
            "time_budget": self._time_budget.value(),
            "acceptance": self._acceptance.value(),
            "strip_size": self._strip_size.value(),
            "target_score": self._target_score.value(),
        }
        drifted = {name: value for name, value in accepted.items()
                   if getattr(session, name) != value}
        if drifted:
            session.set_algorithm(**drifted)

    def _refresh(self) -> None:
        self._sync_form()
        self._update_enabled()
        self._update_projections()
        self._update_colour_button()
        # L'aperçu se charge lui-même de savoir s'il doit se reconstruire, et de
        # différer le calcul : le relancer d'ici le ferait travailler pour des
        # réglages qui ne le concernent pas.

    def _update_enabled(self) -> None:
        """Un champ dont le seuil est décoché reste visible mais inactif."""
        self._stagnation.setEnabled(self._session.stop_on_stagnation)
        self._time_budget.setEnabled(self._session.stop_on_time)
        self._target_score.setEnabled(self._session.stop_on_score)
        # La tolérance ne veut rien dire en descente stricte : elle n'accepte
        # jamais un coup dégradant.
        self._acceptance.setEnabled(self._session.use_annealing)

    def _update_colour_button(self) -> None:
        red, green, blue = self._session.empty_colour
        self._empty_colour.setStyleSheet(
            f"background-color: rgb({red}, {green}, {blue}); min-height: 18px;"
        )

    def _update_projections(self) -> None:
        session = self._session
        annealing = session.use_annealing
        seconds = estimated_seconds(session.iterations, annealing)
        gain = estimated_gain(session.iterations, annealing)
        low, high = estimated_snapshots(session.iterations, session.snapshot_every,
                                        annealing)

        self._duration.setText(
            self.tr("Durée estimée : %1").replace("%1", format_duration(seconds))
        )
        self._gain.setText(
            self.tr("Gain attendu sur le score : environ %1 %").replace(
                "%1", f"{gain * 100:.0f}")
        )
        text = self.tr("Timeline : entre %1 et %2 clichés").replace(
            "%1", str(low)).replace("%2", str(high))
        if high < USEFUL_SNAPSHOTS:
            text += "  —  " + self.tr("trop peu pour naviguer, resserrez la cadence")
        self._snapshots.setText(text)
