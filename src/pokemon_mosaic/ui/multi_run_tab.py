"""L'onglet du multi-lancement : plusieurs calculs d'affilée, cinq clichés gardés.

L'utilisateur dit combien de lancements enchaîner, vingt au plus. Ils tournent
l'un après l'autre avec les mêmes réglages : seul le tirage des échanges les
différencie. De chacun, on garde les cinq derniers clichés de sa timeline.
Voir `SPEC.md` §10, 2026-09-13.
"""

from dataclasses import dataclass

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..control import RunControl
from ..optimize import OptimizationResult
from ..timeline import Snapshot
from .estimates import estimated_seconds, format_duration
from .runner import KEPT_PER_RUN, MULTI_RUN_MAX, last_snapshots, start_multi_run
from .saved_column import mosaic_image
from .session import Session

# Le nombre proposé à l'ouverture : assez pour comparer, assez peu pour ne pas
# occuper la machine une heure sans l'avoir demandé.
DEFAULT_RUNS = 5
# Même cadence de rendu que le lancement simple, pour la même raison : un rendu
# par cliché accumulerait du retard sur le calcul.
RENDER_INTERVAL_MS = 100
SHUTDOWN_TIMEOUT_MS = 5000


@dataclass
class RunGroup:
    """Ce qu'un lancement laisse : ses derniers clichés, et de quoi les lire.

    `cards` est le jeu retenu au calcul : la grille en indexe le sous-ensemble
    renuméroté, comme un agencement gardé. `result` reste `None` tant que le
    lancement tourne, ou s'il a échoué.
    """

    rank: int
    cards: object
    snapshots: list[Snapshot]
    result: OptimizationResult | None = None


class MultiRunTab(QWidget):
    """Lance, suit et garde les résultats d'un multi-lancement."""

    status_message = Signal(str)
    # Vrai pendant le calcul : l'écran d'exécution n'en lance jamais deux.
    busy_changed = Signal(bool)

    def __init__(self, session: Session, parent=None):
        super().__init__(parent)
        self._session = session
        self._control: RunControl | None = None
        self._thread = None
        self._worker = None
        # ⚠️ **Les résultats restent tant que l'application est ouverte**, même
        # en changeant d'étape, et le multi-lancement suivant les remplace.
        self.groups: list[RunGroup] = []
        # Le lancement en cours et sa timeline, pour l'image en direct.
        self._current: int | None = None
        self._timeline = None
        self._cards = None
        self._count = 0
        self._pending = False
        # Vrai pendant un lancement simple : un seul calcul à la fois.
        self._blocked = False
        self._render_timer = QTimer(self)
        self._render_timer.setInterval(RENDER_INTERVAL_MS)
        self._render_timer.timeout.connect(self._flush_render)
        self._render_timer.start()
        self._build()
        session.algorithm_changed.connect(self._update_estimate)

    # --- Construction -----------------------------------------------------

    def _build(self) -> None:
        self._count_label = QLabel()
        self._count_field = QSpinBox()
        self._count_field.setRange(1, MULTI_RUN_MAX)
        self._count_field.setValue(DEFAULT_RUNS)
        self._count_field.valueChanged.connect(self._update_estimate)
        self._estimate = QLabel()

        self._start = QPushButton()
        self._pause = QPushButton()
        self._stop = QPushButton()
        self._start.clicked.connect(lambda: self.start())
        self._pause.clicked.connect(self._toggle_pause)
        self._stop.clicked.connect(self._request_stop)

        reglage = QHBoxLayout()
        reglage.addWidget(self._count_label)
        reglage.addWidget(self._count_field)
        reglage.addWidget(self._estimate, 1)
        reglage.addWidget(self._start)
        reglage.addWidget(self._pause)
        reglage.addWidget(self._stop)

        self._progress_label = QLabel()
        self._progress = QProgressBar()
        self._progress.setTextVisible(False)

        self._image = QLabel()
        self._image.setAlignment(Qt.AlignCenter)
        self._image.setFrameShape(QFrame.StyledPanel)
        self._image.setMinimumHeight(260)

        pile = QVBoxLayout(self)
        pile.addLayout(reglage)
        pile.addWidget(self._progress_label)
        pile.addWidget(self._progress)
        pile.addWidget(self._image, 1)
        self._update_buttons(running=False)
        self.retranslate_ui()

    def retranslate_ui(self) -> None:
        self._count_label.setText(self.tr("Nombre de lancements"))
        self._count_field.setToolTip(
            self.tr("Vingt au plus. Ils tournent l'un après l'autre, avec les "
                    "mêmes réglages."))
        self._start.setText(self.tr("Lancer"))
        self._stop.setText(self.tr("Arrêter"))
        self._update_pause_label()
        self._update_estimate()
        self._update_progress()

    # --- Commandes --------------------------------------------------------

    def is_busy(self) -> bool:
        return self._thread is not None

    def set_blocked(self, blocked: bool) -> None:
        """Interdit de lancer pendant un lancement simple, et le rend ensuite."""
        self._blocked = bool(blocked)
        self._start.setEnabled(not self.is_busy() and not self._blocked)

    def start(self) -> None:
        """Lance le multi-lancement, en remplaçant les résultats précédents."""
        if self._thread is not None or self._blocked:
            return
        self._control = RunControl()
        self.groups = []
        self._current = self._timeline = self._cards = None
        self._count = self._count_field.value()
        self._thread, self._worker = start_multi_run(
            self, self._session, self._control, self._count,
            run_started=self._on_run_started, snapshot=self._on_snapshot,
            run_finished=self._on_run_finished,
            finished_all=self._on_finished_all, failed=self._on_failed,
        )
        self._update_buttons(running=True)
        self._image.setPixmap(QPixmap())
        self._image.setText(self.tr("Calcul en cours…"))
        self._update_progress()
        self.status_message.emit(self.tr("Multi-lancement en cours…"))

    def _toggle_pause(self) -> None:
        if self._control is None:
            return
        if self._control.paused:
            self._control.resume()
        else:
            self._control.pause()
        self._update_pause_label()

    def _request_stop(self) -> None:
        if self._control is not None:
            self._control.stop()

    def shutdown(self) -> bool:
        """Arrête le calcul. Rend faux s'il résiste, comme le lancement simple."""
        if self._control is not None:
            self._control.stop()
        if self._thread is not None and self._thread.isRunning():
            self._thread.quit()
            if not self._thread.wait(SHUTDOWN_TIMEOUT_MS):
                self.status_message.emit(
                    self.tr("Arrêt en cours : %1 ne répond pas encore.")
                    .replace("%1", self.tr("le multi-lancement")))
                return False
        self._thread = self._worker = None
        return True

    # --- Réactions du calcul ---------------------------------------------

    def _on_run_started(self, rank: int, cards, timeline) -> None:
        self._current, self._cards, self._timeline = rank, cards, timeline
        # ⚠️ **Le groupe naît au départ du lancement**, et non à sa fin : un
        # arrêt ou un échec en plein calcul doit laisser ses clichés.
        self.groups.append(RunGroup(rank, cards, []))
        self._update_progress()

    def _on_snapshot(self, rank: int, _snapshot) -> None:
        if rank != self._current or not self.groups:
            return
        self.groups[-1].snapshots = last_snapshots(self._timeline, KEPT_PER_RUN)
        self._pending = True

    def _on_run_finished(self, rank: int, result) -> None:
        for groupe in self.groups:
            if groupe.rank == rank:
                groupe.result = result
                groupe.snapshots = last_snapshots(self._timeline, KEPT_PER_RUN)
        self._update_progress()

    def _on_finished_all(self, commences: int) -> None:
        self._end()
        self.status_message.emit(
            self.tr("Multi-lancement terminé : %n lancement(s).", "", commences))

    def _on_failed(self, message: str) -> None:
        self._end()
        self.status_message.emit(
            self.tr("Échec du multi-lancement : %1").replace("%1", message))

    def _end(self) -> None:
        self._thread = self._worker = None
        self._current = None
        self._update_buttons(running=False)
        self._update_progress()

    # --- Affichage --------------------------------------------------------

    def _flush_render(self) -> None:
        if not self._pending or not self._timeline:
            return
        self._pending = False
        image = mosaic_image(self._timeline[-1].grid, self._cards,
                             self._session.empty_colour)
        if image is None:
            return
        cadre = self._image.contentsRect().size()
        self._image.setText("")
        self._image.setPixmap(QPixmap.fromImage(image.scaled(
            cadre, Qt.KeepAspectRatio, Qt.SmoothTransformation)))

    def resizeEvent(self, event) -> None:
        """L'image s'ajuste au cadre : on la refait à sa nouvelle taille.

        Sans cela, elle ne se recalait qu'au cliché suivant, et jamais une fois
        le calcul fini."""
        super().resizeEvent(event)
        self._pending = True

    def per_run_seconds(self) -> float:
        """La durée estimée d'un lancement, bornée par le budget de temps."""
        session = self._session
        secondes = estimated_seconds(session.iterations, session.use_annealing)
        if session.stop_on_time:
            secondes = min(secondes, session.time_budget)
        return secondes

    def _update_estimate(self) -> None:
        total = self.per_run_seconds() * self._count_field.value()
        self._estimate.setText(
            self.tr("Durée estimée : %1").replace("%1", format_duration(total)))

    def _update_progress(self) -> None:
        finis = sum(1 for groupe in self.groups if groupe.result is not None)
        if self._current is not None:
            self._progress_label.setText(
                self.tr("Lancement %1 sur %2")
                .replace("%1", str(self._current + 1))
                .replace("%2", str(self._count)))
        elif self.groups:
            self._progress_label.setText(
                self.tr("%n lancement(s) terminé(s).", "", finis))
        else:
            self._progress_label.setText(
                self.tr("Chaque lancement garde ses cinq derniers clichés."))
        self._progress.setRange(0, max(1, self._count))
        self._progress.setValue(finis)

    def _update_buttons(self, running: bool) -> None:
        self._start.setEnabled(not running and not self._blocked)
        self._count_field.setEnabled(not running)
        self._pause.setEnabled(running)
        self._stop.setEnabled(running)
        self._update_pause_label()
        self.busy_changed.emit(running)

    def _update_pause_label(self) -> None:
        paused = self._control is not None and self._control.paused
        self._pause.setText(self.tr("Reprendre") if paused else self.tr("Pause"))
