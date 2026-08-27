"""Vue d'exécution — l'image se construit, la timeline se remplit."""

import os

import numpy as np
from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from ..control import RunControl
from ..optimize import StopReason
from ..scoring import EMPTY
from .export_dialog import ExportDialog
from .exporter import start_export
from .runner import start_run
from .session import Session

# Un cran de zoom. 1,25 laisse une progression douce sans multiplier les clics.
ZOOM_STEP = 1.25
# Au-delà de la résolution des vignettes, agrandir n'ajoute aucun détail : le
# plafond se calcule donc à partir de l'échelle d'ajustement, pas en dur.
ZOOM_CEILING = 8.0

# Rendre un cliché coûte 56 ms sur une grille 17×17 : recopie des vignettes, puis
# réduction lissée de 12,6 Mpx. À raison d'un rendu par cliché, l'affichage
# demanderait 3,9 s de fil principal là où le calcul en prend 1,6 — l'interface
# accumulerait du retard et le résultat n'apparaîtrait que bien après la fin.
# On borne donc la cadence : les clichés sont tous enregistrés, seul l'affichage
# est limité.
RENDER_INTERVAL_MS = 100

# L'annulation étant vérifiée à chaque ligne de cartes, l'arrêt prend au plus le
# temps de finir la ligne en cours ; ce délai n'est qu'un filet.
SHUTDOWN_TIMEOUT_MS = 5000


class ImageView(QScrollArea):
    """Cadre défilant pour l'aperçu. Ctrl+molette zoome au lieu de défiler."""

    zoom_requested = Signal(int)    # +1 pour zoomer, -1 pour dézoomer

    def wheelEvent(self, event) -> None:
        if event.modifiers() & Qt.ControlModifier:
            steps = event.angleDelta().y()
            if steps:
                self.zoom_requested.emit(1 if steps > 0 else -1)
            event.accept()
            return
        super().wheelEvent(event)


class RunStep(QWidget):
    """Pilote une exécution et laisse naviguer dans ses états successifs."""

    status_message = Signal(str)

    def __init__(self, session: Session, parent=None):
        super().__init__(parent)
        self._session = session
        self._control: RunControl | None = None
        self._thread = None
        self._worker = None
        self._export_thread = None
        self._export_worker = None
        # Sélection et liens au moment où le calcul a démarré. Repartir d'un
        # cliché n'a de sens que si la numérotation des cartes n'a pas bougé.
        self._run_signature: tuple | None = None
        self._cards = None
        self._timeline = None
        self._following = True      # suit le dernier cliché tant qu'on ne touche pas
        self._pending_index: int | None = None
        # Point de l'image à ramener au centre après le prochain rendu, posé par
        # le zoom : la taille de l'image n'est connue qu'une fois celui-ci fait.
        self._pending_centre: tuple[float, float] | None = None
        self._render_timer = QTimer(self)
        self._render_timer.setInterval(RENDER_INTERVAL_MS)
        self._render_timer.timeout.connect(self._flush_render)
        self._render_timer.start()
        # Facteur appliqué **par-dessus** l'ajustement à la fenêtre : 1 montre
        # l'image entière, haut et bas compris. C'est un attribut de l'écran et
        # non du cliché, donc parcourir la timeline conserve le zoom.
        self._zoom = 1.0
        self._build()
        # Changer la sélection, les liens ou la grille rend les clichés
        # inexploitables : les commandes de reprise doivent s'éteindre aussitôt,
        # et non échouer au moment du clic.
        session.selection_changed.connect(self._update_resume_buttons)
        session.links_changed.connect(self._update_resume_buttons)
        session.layout_changed.connect(self._update_resume_buttons)
        # L'épaisseur des bandes entre dans la signature de reprise : sans ce
        # rafraîchissement, les boutons resteraient actifs après un changement
        # de réglage, et cliquer dessus ne ferait rien — `_extend_run` sort
        # aussitôt sur `can_resume()`.
        session.algorithm_changed.connect(self._update_resume_buttons)

    # --- Construction -----------------------------------------------------

    def _build(self) -> None:
        self._image = QLabel()
        self._image.setAlignment(Qt.AlignCenter)

        # Zone défilante : une image zoomée dépasse la fenêtre, il faut pouvoir
        # la parcourir. `setWidgetResizable(False)` est indispensable — vrai, le
        # label serait étiré à la taille du cadre et l'image rognée sans barres.
        self._scroll = ImageView()
        self._scroll.setWidget(self._image)
        self._scroll.setWidgetResizable(False)
        self._scroll.setAlignment(Qt.AlignCenter)
        self._scroll.setFrameShape(QFrame.StyledPanel)
        self._scroll.setMinimumHeight(340)
        # Le cadre ne prend pas le clavier : les flèches doivent servir à parcourir
        # la timeline, pas à faire défiler la vue.
        self._scroll.setFocusPolicy(Qt.NoFocus)
        self._scroll.zoom_requested.connect(self._zoom_by)
        self.setFocusPolicy(Qt.StrongFocus)

        self._zoom_out = QPushButton("−")
        self._zoom_in = QPushButton("+")
        self._zoom_fit = QPushButton()
        self._zoom_label = QLabel()
        self._zoom_label.setMinimumWidth(52)
        self._zoom_label.setAlignment(Qt.AlignCenter)
        self._zoom_out.clicked.connect(lambda: self._zoom_by(-1))
        self._zoom_in.clicked.connect(lambda: self._zoom_by(1))
        self._zoom_fit.clicked.connect(self._reset_zoom)
        for button in (self._zoom_out, self._zoom_in):
            button.setFixedWidth(32)

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
        timeline_row.addSpacing(16)
        timeline_row.addWidget(self._zoom_out)
        timeline_row.addWidget(self._zoom_label)
        timeline_row.addWidget(self._zoom_in)
        timeline_row.addWidget(self._zoom_fit)

        self._start = QPushButton()
        self._pause = QPushButton()
        self._stop = QPushButton()
        # `clicked` transmet l'état coché du bouton en premier argument : le
        # brancher directement sur start_run ferait recevoir False à
        # `previous_grid`, qui n'accepte qu'une grille ou None.
        self._start.clicked.connect(lambda: self.start_run())
        self._pause.clicked.connect(self._toggle_pause)
        self._stop.clicked.connect(self._request_stop)

        self._extend = QPushButton()
        self._resume = QPushButton()
        self._extend.clicked.connect(lambda: self._extend_run())
        self._resume.clicked.connect(lambda: self._resume_from_snapshot())

        # L'export porte sur le cliché affiché, d'où sa place à côté des
        # commandes de calcul et non dans un menu : c'est la timeline qui choisit
        # ce qui est exporté.
        self._export = QPushButton()
        self._export.clicked.connect(lambda: self._open_export())
        self._export.setEnabled(False)
        self._extend.setEnabled(False)
        self._resume.setEnabled(False)
        self._cancel_export = QPushButton()
        self._cancel_export.clicked.connect(self._request_export_stop)
        self._cancel_export.hide()
        self._export_progress = QProgressBar()
        self._export_progress.hide()

        controls = QHBoxLayout()
        controls.addWidget(self._start)
        controls.addWidget(self._pause)
        controls.addWidget(self._stop)
        controls.addWidget(self._extend)
        controls.addWidget(self._resume)
        controls.addWidget(self._export)
        controls.addWidget(self._cancel_export)
        controls.addWidget(self._export_progress)
        controls.addStretch(1)
        self._summary = QLabel()
        controls.addWidget(self._summary)

        layout = QVBoxLayout(self)
        layout.addWidget(self._scroll, 1)
        layout.addLayout(timeline_row)
        layout.addLayout(controls)
        self.retranslate_ui()

    def retranslate_ui(self) -> None:
        self._start.setText(self.tr("Lancer"))
        self._stop.setText(self.tr("Arrêter"))
        self._latest.setText(self.tr("Dernier"))
        self._extend.setText(self.tr("Prolonger"))
        self._resume.setText(self.tr("Repartir de ce cliché"))
        self._extend.setToolTip(
            self.tr("Poursuit le calcul depuis le dernier cliché, "
                    "en conservant toute la timeline.")
        )
        self._resume.setToolTip(
            self.tr("Relance le calcul depuis le cliché affiché. "
                    "Les clichés suivants sont abandonnés.")
        )
        self._export.setText(self.tr("Exporter ce cliché…"))
        self._cancel_export.setText(self.tr("Annuler l'export"))
        self._zoom_fit.setText(self.tr("Ajuster"))
        self._zoom_out.setToolTip(self.tr("Dézoomer (touche −)"))
        self._zoom_in.setToolTip(self.tr("Zoomer (touche +)"))
        self._zoom_fit.setToolTip(self.tr("Revenir à l'image entière"))
        self._slider.setToolTip(
            self.tr("Flèches gauche et droite pour parcourir les clichés.")
        )
        self._update_pause_label()
        self._update_position()
        self._update_zoom_label()
        if not self._timeline:
            self._show_placeholder(self.tr("Lancez le calcul pour voir la mosaïque "
                                           "se construire."))

    # --- Commandes --------------------------------------------------------

    def start_run(self, previous_grid=None, timeline=None) -> None:
        if self._thread is not None:
            return
        self._control = RunControl()
        self._following = True
        self._run_signature = self._signature()
        self._thread, self._worker = start_run(
            self, self._session, self._control, previous_grid, timeline,
            started_run=self._on_started, snapshot=self._on_snapshot,
            finished_run=self._on_finished, failed=self._on_failed,
        )
        self._update_buttons(running=True)
        self.status_message.emit(self.tr("Calcul en cours…"))

    # --- Prolongation et reprise ------------------------------------------

    def _signature(self) -> tuple:
        """Ce qui doit être resté identique pour qu'un cliché reste interprétable.

        Les cartes retenues sont renumérotées de 0 à n-1 : changer la sélection
        ferait désigner d'autres cartes par les mêmes indices, en silence. Les
        liens comptent aussi, l'optimiseur exigeant que chaque bloc soit déjà
        intact dans la grille de départ.

        L'épaisseur des bandes en fait partie pour une autre raison : elle
        recalcule les signatures, donc les distances, donc **l'échelle du
        score**. Mesuré — la même grille vaut 621,7 avec une bande de 0,10 et
        552,0 avec 0,30, soit 11 % d'écart. Prolonger sans le prendre en compte
        mêlait deux métriques dans une seule timeline, et la courbe montrait une
        chute soudaine alors qu'aucune carte n'avait bougé.
        """
        session = self._session
        return (
            tuple(session.selected_indices()),
            tuple(sorted(link.cards for link in session.usable_links().active)),
            (session.rows, session.cols),
            session.strip_size,
        )

    def can_resume(self) -> bool:
        """Vrai si un calcul terminé peut être repris tel quel.

        Un export en cours compte comme occupé : c'est cette méthode, et elle
        seule, qui décide de l'état des boutons — les griser à part la ferait
        diverger de ce qu'ils montrent.
        """
        return (bool(self._timeline)
                and self._thread is None and self._export_thread is None
                and self._run_signature == self._signature())

    def _extend_run(self) -> None:
        """Poursuit le calcul depuis le dernier cliché, timeline conservée."""
        if not self.can_resume():
            return
        self._go_to_latest()
        self.start_run(previous_grid=self._timeline[-1].grid,
                       timeline=self._timeline)

    def _resume_from_snapshot(self) -> None:
        """Relance depuis le cliché affiché, en abandonnant les suivants."""
        if not self.can_resume():
            return
        index = self._slider.value()
        grid = self._timeline[index].grid
        self._timeline.truncate_after(index)
        # Le curseur doit suivre la timeline raccourcie avant que les nouveaux
        # clichés n'arrivent, sinon il pointerait hors de la liste.
        self._slider.setMaximum(len(self._timeline) - 1)
        self._slider.setValue(len(self._timeline) - 1)
        self.start_run(previous_grid=grid, timeline=self._timeline)

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

    # --- Export -----------------------------------------------------------

    def current_grid(self):
        """Grille du cliché affiché — c'est elle que l'export écrit."""
        if not self._timeline:
            return None
        index = max(0, min(len(self._timeline) - 1, self._slider.value()))
        return self._timeline[index].grid

    def _open_export(self) -> None:
        grid = self.current_grid()
        if grid is None or self._export_thread is not None:
            return
        dialog = ExportDialog(self._session, grid, self._cards, parent=self)
        try:
            if not dialog.exec():
                return
            settings, path = dialog.settings(), dialog.path()
            full_resolution = dialog.full_resolution()
        finally:
            # Parenté à l'écran, le dialogue survivrait à sa fermeture.
            dialog.deleteLater()
        self._start_export(grid, settings, path, full_resolution)

    def _start_export(self, grid, settings, path, full_resolution) -> None:
        self._export.setEnabled(False)
        self._cancel_export.show()
        # Un seul panneau n'a aucune étape intermédiaire à annoncer : une barre
        # figée à 0 % pendant plusieurs secondes se lit comme un export bloqué.
        # Indéterminée, elle dit la seule chose vraie — que ça travaille.
        self._export_progress.setRange(0, settings.panels if settings.panels > 1 else 0)
        self._export_progress.setValue(0)
        self._export_progress.show()
        self.status_message.emit(self.tr("Export en cours…"))
        self._export_thread, self._export_worker = start_export(
            self, grid, self._cards, settings, path, full_resolution,
            progress=self._on_export_progress, exported=self._on_exported,
            cancelled=self._on_export_cancelled, failed=self._on_export_failed,
        )
        self._update_resume_buttons()

    def _request_export_stop(self) -> None:
        if self._export_worker is not None:
            self._export_worker.cancel()
            self._cancel_export.setEnabled(False)

    def _on_export_progress(self, panel: int, total: int, target: str) -> None:
        self._export_progress.setValue(panel)
        if target:
            self.status_message.emit(
                self.tr("Panneau %1 / %2 : %3")
                .replace("%1", str(panel + 1)).replace("%2", str(total))
                .replace("%3", os.path.basename(target))
            )

    def _end_export(self) -> None:
        self._export_thread = self._export_worker = None
        self._export.setEnabled(bool(self._timeline))
        self._cancel_export.hide()
        self._cancel_export.setEnabled(True)
        self._export_progress.hide()
        self._update_resume_buttons()

    def _on_exported(self, written: list) -> None:
        self._end_export()
        self.status_message.emit(
            self.tr("%n fichier(s) écrit(s) : %1", "", len(written))
            .replace("%1", ", ".join(os.path.basename(p) for p in written))
        )

    def _on_export_cancelled(self) -> None:
        self._end_export()
        self.status_message.emit(
            self.tr("Export annulé ; les fichiers partiels ont été effacés.")
        )

    def _on_export_failed(self, message: str) -> None:
        self._end_export()
        self.status_message.emit(
            self.tr("Échec de l'export : %1").replace("%1", message)
        )

    def shutdown(self) -> bool:
        """Arrête calcul et export. Rend faux si l'un d'eux résiste.

        Le résultat compte : le `QThread` a pour parent ce widget, donc la
        fenêtre détruite l'emporte avec elle, référence Python ou non. Fermer
        malgré un fil actif fait abandonner le processus par Qt.
        """
        if self._control is not None:
            self._control.stop()
        if self._export_worker is not None:
            self._export_worker.cancel()

        # ⚠️ Les deux fils sont traités jusqu'au bout, quoi qu'il arrive. Sortir
        # dès le premier échec laissait le fil d'export **actif** derrière soi :
        # la fenêtre se fermait, son parent était détruit, et Qt abandonnait le
        # processus — précisément le crash que cette méthode existe pour éviter.
        # Vérifié : avec un calcul qui s'obstine, le fil d'export ne recevait ni
        # `quit()` ni `wait()`.
        recalcitrants = []
        for nom, fil in ((self.tr("le calcul"), self._thread),
                         (self.tr("l'export"), self._export_thread)):
            if fil is None or not fil.isRunning():
                continue
            fil.quit()
            if not fil.wait(SHUTDOWN_TIMEOUT_MS):
                recalcitrants.append(nom)

        # Une référence n'est lâchée que si son fil est réellement terminé :
        # lâcher celle d'un fil encore actif rouvrirait le même crash.
        if self._thread is None or not self._thread.isRunning():
            self._thread = self._worker = None
        if self._export_thread is None or not self._export_thread.isRunning():
            self._export_thread = self._export_worker = None

        if recalcitrants:
            # `status_message` et non `print` : depuis un paquet `.app`, la
            # sortie standard ne va nulle part que l'utilisateur puisse lire.
            self.status_message.emit(
                self.tr("Arrêt en cours : %1 ne répond pas encore.")
                .replace("%1", " et ".join(recalcitrants))
            )
        return not recalcitrants

    # --- Réactions du calcul ---------------------------------------------

    def _on_started(self, cards, timeline) -> None:
        self._cards = cards
        self._timeline = timeline
        self._slider.setEnabled(True)
        self._export.setEnabled(True)
        # Le plafond se déduit de la grille : une grille plus petite que la
        # précédente l'abaisse, et le zoom hérité doit redescendre avec lui.
        self._zoom = min(self._zoom, self._max_zoom())
        self._update_zoom_label()

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
        self._update_resume_buttons()

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
        if image is None:
            return
        self._image.setPixmap(QPixmap.fromImage(image))
        # Le cadre ne redimensionne pas son contenu : sans cet ajustement, le
        # label garderait son ancienne taille et l'image zoomée serait rognée
        # sans qu'aucune barre de défilement n'apparaisse.
        self._image.resize(image.size())

        if self._pending_centre is not None:
            centre, self._pending_centre = self._pending_centre, None
            # Le recentrage attend la mise en page du cadre : tant qu'elle n'a
            # pas eu lieu, les barres gardent l'amplitude de l'ancienne taille
            # et écrêteraient silencieusement la position demandée. `self` en
            # contexte : si l'écran disparaît entre-temps, Qt annule le rappel
            # au lieu de le lancer sur un objet détruit.
            QTimer.singleShot(0, self, lambda: self._restore_centre(centre))

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
        scale = self._fit_scale(image.size()) * self._zoom
        target = QSize(max(1, round(width * scale)), max(1, round(height * scale)))
        return image.scaled(target, Qt.KeepAspectRatio, Qt.SmoothTransformation)

    # --- Zoom -------------------------------------------------------------

    def _fit_scale(self, size: QSize) -> float:
        """Facteur qui fait tenir l'image **entière** dans le cadre.

        Le minimum des deux rapports, et non celui des largeurs : borner la seule
        largeur laissait le haut et le bas d'un poster en portrait hors du cadre.
        """
        viewport = self._scroll.viewport().size()
        if size.width() <= 0 or size.height() <= 0:
            return 1.0
        return min(max(1, viewport.width()) / size.width(),
                   max(1, viewport.height()) / size.height())

    def _max_zoom(self) -> float:
        """Plafond de zoom : la résolution des vignettes, sans jamais passer
        sous 1, qui est l'image entière."""
        if not self._timeline or self._cards is None or not len(self._cards):
            return ZOOM_CEILING
        tile_h, tile_w = self._cards[0].thumbnail.shape[:2]
        rows, cols = self._timeline[0].grid.shape
        native = QSize(cols * tile_w, rows * tile_h)
        fit = self._fit_scale(native)
        return max(1.0, min(ZOOM_CEILING, 1.0 / fit)) if fit > 0 else ZOOM_CEILING

    def _zoom_by(self, steps: int) -> None:
        """Zoome d'un cran, en gardant sous les yeux ce qui était au centre."""
        factor = ZOOM_STEP ** steps
        target = min(self._max_zoom(), max(1.0, self._zoom * factor))
        if abs(target - self._zoom) < 1e-9:
            return
        # Le point visé est relevé au premier cran d'une rafale seulement : les
        # crans suivants arrivent avant le rendu, et liraient un centre calculé
        # sur une image qui n'a pas encore changé de taille.
        if self._pending_centre is None:
            self._pending_centre = self._relative_centre()
        self._zoom = target
        # Le rendu passe par la cadence bornée comme tout le reste. Rendre à
        # chaque cran coûterait 55 ms, et une rafale de molette en produit des
        # dizaines par seconde : le fil principal serait bloqué une seconde
        # entière pour un seul geste.
        self._show(self._slider.value())
        self._update_zoom_label()

    def _reset_zoom(self) -> None:
        if self._zoom == 1.0:
            return
        self._zoom = 1.0
        self._show(self._slider.value())
        self._flush_render()
        self._update_zoom_label()

    @staticmethod
    def _axis_centre(offset: int, visible: int, total: int) -> float:
        """Point visible au milieu d'un axe, en proportion de 0 à 1.

        Une image plus petite que le cadre est centrée par le cadre lui-même et
        sa barre reste à zéro : son milieu vaut 0,5, et non le rapport calculé,
        qui dériverait avec la place libre autour d'elle.
        """
        if total <= 0 or total <= visible:
            return 0.5
        return (offset + visible / 2) / total

    def _relative_centre(self) -> tuple[float, float]:
        """Point de l'image au centre du cadre, en proportions de 0 à 1."""
        size, viewport = self._image.size(), self._scroll.viewport()
        return (self._axis_centre(self._scroll.horizontalScrollBar().value(),
                                  viewport.width(), size.width()),
                self._axis_centre(self._scroll.verticalScrollBar().value(),
                                  viewport.height(), size.height()))

    def _restore_centre(self, centre: tuple[float, float]) -> None:
        x, y = centre
        size, viewport = self._image.size(), self._scroll.viewport()
        # Les barres bornent d'elles-mêmes les valeurs hors plage.
        self._scroll.horizontalScrollBar().setValue(
            round(x * size.width() - viewport.width() / 2))
        self._scroll.verticalScrollBar().setValue(
            round(y * size.height() - viewport.height() / 2))

    def _update_zoom_label(self) -> None:
        self._zoom_label.setText(f"{round(self._zoom * 100)} %")
        self._zoom_in.setEnabled(self._zoom < self._max_zoom() - 1e-9)
        self._zoom_out.setEnabled(self._zoom > 1.0 + 1e-9)
        self._zoom_fit.setEnabled(self._zoom > 1.0 + 1e-9)

    # --- Clavier et redimensionnement -------------------------------------

    def _step(self, delta: int) -> None:
        """Avance ou recule d'un cliché."""
        if not self._timeline:
            return
        self._slider.setValue(
            max(0, min(len(self._timeline) - 1, self._slider.value() + delta))
        )

    def keyPressEvent(self, event) -> None:
        """Flèches pour parcourir la timeline, +/− pour le zoom.

        Le cadre défilant est volontairement hors du parcours du clavier : sinon
        il consommerait les flèches pour se déplacer et la timeline ne bougerait
        que si le curseur avait le focus.
        """
        key = event.key()
        if key == Qt.Key_Left:
            self._step(-1)
        elif key == Qt.Key_Right:
            self._step(1)
        elif key == Qt.Key_Home:
            self._slider.setValue(0)
        elif key == Qt.Key_End:
            self._go_to_latest()
        elif key in (Qt.Key_Plus, Qt.Key_Equal):
            self._zoom_by(1)
        elif key == Qt.Key_Minus:
            self._zoom_by(-1)
        elif key in (Qt.Key_Up, Qt.Key_Down, Qt.Key_PageUp, Qt.Key_PageDown):
            # Haut et bas font défiler l'image zoomée : la timeline a déjà les
            # flèches horizontales, et une image agrandie doit rester parcourable.
            bar = self._scroll.verticalScrollBar()
            amount = (bar.singleStep() if key in (Qt.Key_Up, Qt.Key_Down)
                      else bar.pageStep())
            direction = -1 if key in (Qt.Key_Up, Qt.Key_PageUp) else 1
            bar.setValue(bar.value() + direction * amount)
        else:
            super().keyPressEvent(event)
            return
        event.accept()

    def resizeEvent(self, event) -> None:
        """L'ajustement dépend de la taille du cadre : on refait l'image."""
        super().resizeEvent(event)
        if self._timeline:
            # Agrandir la fenêtre augmente l'échelle d'ajustement et abaisse donc
            # le plafond : sans ce rabotage, le zoom resterait au-dessus, à
            # interpoler des pixels qui n'existent pas.
            self._zoom = min(self._zoom, self._max_zoom())
            self._show(self._slider.value())
        else:
            self._image.resize(self._scroll.viewport().size())
        self._update_zoom_label()

    # --- Affichage --------------------------------------------------------

    def _show_placeholder(self, text: str) -> None:
        """Texte d'attente, occupant tout le cadre faute d'image à montrer."""
        self._image.setText(text)
        self._image.resize(self._scroll.viewport().size())

    def _update_buttons(self, running: bool) -> None:
        self._start.setEnabled(not running)
        self._pause.setEnabled(running)
        self._stop.setEnabled(running)
        self._update_resume_buttons()
        self._update_pause_label()

    def _update_resume_buttons(self) -> None:
        resumable = self.can_resume()
        self._extend.setEnabled(resumable)
        # Repartir du dernier cliché, c'est prolonger : deux boutons pour le même
        # geste laisseraient croire qu'ils font des choses différentes.
        self._resume.setEnabled(
            resumable and self._slider.value() < len(self._timeline or []) - 1
        )

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
