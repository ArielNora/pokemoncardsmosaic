"""Vue d'exécution — l'image se construit, la timeline se remplit."""

import numpy as np
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from ..control import RunControl
from ..optimize import StopReason
from ..scoring import EMPTY
from .runner import start_run
from .session import Session

PREVIEW_MAX_WIDTH = 900

# Rendre un cliché coûte 56 ms sur une grille 17×17 : recopie des vignettes, puis
# réduction lissée de 12,6 Mpx. À raison d'un rendu par cliché, l'affichage
# demanderait 3,9 s de fil principal là où le calcul en prend 1,6 — l'interface
# accumulerait du retard et le résultat n'apparaîtrait que bien après la fin.
# On borne donc la cadence : les clichés sont tous enregistrés, seul l'affichage
# est limité.
RENDER_INTERVAL_MS = 100


class RunStep(QWidget):
    """Pilote une exécution et laisse naviguer dans ses états successifs."""

    status_message = Signal(str)

    def __init__(self, session: Session, parent=None):
        super().__init__(parent)
        self._session = session
        self._control: RunControl | None = None
        self._thread = None
        self._worker = None
        self._cards = None
        self._timeline = None
        self._following = True      # suit le dernier cliché tant qu'on ne touche pas
        self._pending_index: int | None = None
        self._render_timer = QTimer(self)
        self._render_timer.setInterval(RENDER_INTERVAL_MS)
        self._render_timer.timeout.connect(self._flush_render)
        self._render_timer.start()
        self._build()

    # --- Construction -----------------------------------------------------

    def _build(self) -> None:
        self._image = QLabel()
        self._image.setAlignment(Qt.AlignCenter)
        self._image.setMinimumHeight(340)

        self._slider = QSlider(Qt.Horizontal)
        self._slider.setEnabled(False)
        self._slider.valueChanged.connect(self._on_slider_moved)
        self._position = QLabel()
        # Sans largeur minimale, le curseur mange l'étiquette et « cliché 62 / 62 »
        # s'affiche tronqué en « cliché 62 / 6 ».
        self._position.setMinimumWidth(130)
        self._position.setAlignment(Qt.AlignCenter)
        self._latest = QPushButton()
        self._latest.clicked.connect(self._go_to_latest)

        timeline_row = QHBoxLayout()
        timeline_row.addWidget(self._slider, 1)
        timeline_row.addWidget(self._position)
        timeline_row.addWidget(self._latest)

        self._start = QPushButton()
        self._pause = QPushButton()
        self._stop = QPushButton()
        # `clicked` transmet l'état coché du bouton en premier argument : le
        # brancher directement sur start_run ferait recevoir False à
        # `previous_grid`, qui n'accepte qu'une grille ou None.
        self._start.clicked.connect(lambda: self.start_run())
        self._pause.clicked.connect(self._toggle_pause)
        self._stop.clicked.connect(self._request_stop)

        controls = QHBoxLayout()
        controls.addWidget(self._start)
        controls.addWidget(self._pause)
        controls.addWidget(self._stop)
        controls.addStretch(1)
        self._summary = QLabel()
        controls.addWidget(self._summary)

        layout = QVBoxLayout(self)
        layout.addWidget(self._image, 1)
        layout.addLayout(timeline_row)
        layout.addLayout(controls)
        self.retranslate_ui()

    def retranslate_ui(self) -> None:
        self._start.setText(self.tr("Lancer"))
        self._stop.setText(self.tr("Arrêter"))
        self._latest.setText(self.tr("Dernier"))
        self._update_pause_label()
        self._update_position()
        if not self._timeline:
            self._image.setText(self.tr("Lancez le calcul pour voir la mosaïque "
                                        "se construire."))

    # --- Commandes --------------------------------------------------------

    def start_run(self, previous_grid=None) -> None:
        if self._thread is not None:
            return
        self._control = RunControl()
        self._following = True
        self._thread, self._worker = start_run(
            self, self._session, self._control, previous_grid,
            started_run=self._on_started, snapshot=self._on_snapshot,
            finished_run=self._on_finished, failed=self._on_failed,
        )
        self._update_buttons(running=True)
        self.status_message.emit(self.tr("Calcul en cours…"))

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

    def shutdown(self) -> None:
        """Arrête le calcul avant que les widgets ne disparaissent."""
        if self._control is not None:
            self._control.stop()
        if self._thread is not None and self._thread.isRunning():
            self._thread.quit()
            if not self._thread.wait(5000):
                print("Le calcul ne s'est pas arrêté dans le délai imparti.")
                return
        self._thread = self._worker = None

    # --- Réactions du calcul ---------------------------------------------

    def _on_started(self, cards, timeline) -> None:
        self._cards = cards
        self._timeline = timeline
        self._slider.setEnabled(True)

    def _on_snapshot(self, snapshot) -> None:
        count = len(self._timeline)
        self._slider.setMaximum(max(0, count - 1))
        # On ne déplace le curseur que si l'utilisateur suit le direct : sinon il
        # verrait l'image lui échapper pendant qu'il examine un état antérieur.
        if self._following:
            self._slider.setValue(count - 1)
            self._show(count - 1)
        self._update_position()

    def _stop_reason(self, reason: str) -> str:
        """Traduit la raison d'arrêt renvoyée par le cœur.

        Le cœur ne dépend pas de Qt et renvoie donc des libellés en français ;
        c'est ici qu'ils passent par `tr()`.
        """
        return {
            StopReason.EXHAUSTED: self.tr("itérations épuisées"),
            StopReason.SCORE: self.tr("score atteint"),
            StopReason.STAGNATION: self.tr("stagnation"),
            StopReason.TIME: self.tr("budget de temps"),
            StopReason.REQUESTED: self.tr("arrêt demandé"),
        }.get(reason, reason)

    def _on_finished(self, result) -> None:
        self._thread = self._worker = None
        self._update_buttons(running=False)
        self._summary.setText(
            self.tr("Score %1 → %2 (%3 % de gain) — arrêt : %4")
            .replace("%1", f"{result.initial_score:.0f}")
            .replace("%2", f"{result.final_score:.0f}")
            .replace("%3", f"{result.gain * 100:.1f}")
            .replace("%4", self._stop_reason(result.stopped_by))
        )
        self.status_message.emit(self.tr("Calcul terminé."))

    def _on_failed(self, message: str) -> None:
        self._thread = self._worker = None
        self._update_buttons(running=False)
        self.status_message.emit(
            self.tr("Échec du calcul : %1").replace("%1", message)
        )

    # --- Timeline ---------------------------------------------------------

    def _on_slider_moved(self, value: int) -> None:
        if self._timeline is None:
            return
        # Revenir sur le dernier cliché remet en mode « suivre le direct ».
        self._following = value >= len(self._timeline) - 1
        self._show(value)
        self._update_position()

    def _go_to_latest(self) -> None:
        if self._timeline:
            self._following = True
            self._slider.setValue(len(self._timeline) - 1)

    def _show(self, index: int) -> None:
        """Demande l'affichage d'un cliché ; le rendu a lieu à la cadence bornée."""
        self._pending_index = index

    def _flush_render(self) -> None:
        index, self._pending_index = self._pending_index, None
        if index is None or self._timeline is None:
            return
        if not (0 <= index < len(self._timeline)):
            return
        image = self._render(self._timeline[index].grid)
        if image is not None:
            self._image.setPixmap(QPixmap.fromImage(image))

    def _render(self, grid: np.ndarray) -> QImage | None:
        """Assemble un cliché à partir des vignettes déjà en mémoire."""
        if self._cards is None or not len(self._cards):
            return None
        tile_h, tile_w = self._cards[0].thumbnail.shape[:2]
        rows, cols = grid.shape
        canvas = np.full((rows * tile_h, cols * tile_w, 3),
                         self._session.empty_colour, dtype=np.uint8)
        for row in range(rows):
            for col in range(cols):
                index = int(grid[row, col])
                if index == EMPTY:
                    continue
                canvas[row * tile_h:(row + 1) * tile_h,
                       col * tile_w:(col + 1) * tile_w] = self._cards[index].thumbnail

        canvas = np.ascontiguousarray(canvas)
        height, width, _ = canvas.shape
        image = QImage(canvas.data, width, height, 3 * width,
                       QImage.Format_RGB888).copy()
        available = min(PREVIEW_MAX_WIDTH, max(1, self._image.width()))
        return image.scaledToWidth(available, Qt.SmoothTransformation)

    # --- Affichage --------------------------------------------------------

    def _update_buttons(self, running: bool) -> None:
        self._start.setEnabled(not running)
        self._pause.setEnabled(running)
        self._stop.setEnabled(running)
        self._update_pause_label()

    def _update_pause_label(self) -> None:
        paused = self._control is not None and self._control.paused
        self._pause.setText(self.tr("Reprendre") if paused else self.tr("Pause"))

    def _update_position(self) -> None:
        if not self._timeline:
            self._position.setText("—")
            return
        self._position.setText(
            self.tr("cliché %1 / %2")
            .replace("%1", str(self._slider.value() + 1))
            .replace("%2", str(len(self._timeline)))
        )
