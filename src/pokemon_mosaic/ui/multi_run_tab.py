"""L'onglet du multi-lancement : plusieurs calculs d'affilée, cinq clichés gardés.

L'utilisateur dit combien de lancements enchaîner, vingt au plus. Ils tournent
l'un après l'autre avec les mêmes réglages : seul le tirage des échanges les
différencie. De chacun, on garde les cinq derniers clichés de sa timeline, et
on les présente à la fin, un groupe par lancement. Voir `SPEC.md` §10,
2026-09-13.
"""

from dataclasses import dataclass

import numpy as np
from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..control import RunControl
from ..optimize import OptimizationResult, StopReason
from ..timeline import Snapshot
from . import theme
from .estimates import estimated_seconds, format_duration
from .library import store_in_library
from .runner import KEPT_PER_RUN, MULTI_RUN_MAX, last_snapshots, start_multi_run
from .saved_column import mosaic_image
from .session import MAX_SAVED, SavedGrid, Session
from .tutorial import Tutorial, Zone
from .tutorial_texts import TutorialTexts

# La visite de l'onglet, puis celle des groupes à leur première apparition :
# ils n'existent qu'après un multi-lancement.
TUTORIAL_MULTI = "multi-lancement"
TUTORIAL_GROUPS = "multi-lancement-groupes"

# Le nombre proposé à l'ouverture : assez pour comparer, assez peu pour ne pas
# occuper la machine une heure sans l'avoir demandé.
DEFAULT_RUNS = 5
# Même cadence de rendu que le lancement simple, pour la même raison : un rendu
# par cliché accumulerait du retard sur le calcul.
RENDER_INTERVAL_MS = 100
SHUTDOWN_TIMEOUT_MS = 5000
# La vignette d'un cliché dans la liste des groupes : cinq par ligne doivent
# tenir à côté de l'image sans la réduire à rien.
THUMB = QSize(72, 72)
RESULTS_WIDTH = 5 * (THUMB.width() + 14) + 36
# Le zoom de l'image en grand, et ses bornes, comme la fenêtre d'une case.
ZOOM_MIN, ZOOM_MAX, ZOOM_STEP = 1.0, 6.0, 1.25
# Les autres touches que l'écran d'exécution interprète pour le lancement
# simple : l'onglet les garde pour lui, voir `MultiRunTab.keyPressEvent`.
NAVIGATION_KEYS = (Qt.Key_Home, Qt.Key_End, Qt.Key_Plus, Qt.Key_Equal,
                   Qt.Key_Minus, Qt.Key_PageUp, Qt.Key_PageDown)


def thumb_step(grid, cards) -> int:
    """Le pas d'échantillonnage qui compose une vignette de groupe sans excès.

    L'image garde au moins deux fois la taille de la vignette dans chaque sens :
    la réduction lissée a encore de quoi faire, sans qu'on assemble la pleine
    taille pour rien.
    """
    if cards is None or not len(cards):
        return 1
    hauteur, largeur = cards[0].thumbnail.shape[:2]
    lignes, colonnes = grid.shape
    return max(1, min(largeur * colonnes // (2 * THUMB.width()),
                      hauteur * lignes // (2 * THUMB.height())))


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

    @property
    def interrupted(self) -> bool:
        """Arrêté avant son terme, par l'utilisateur ou par un échec."""
        return self.result is None or self.result.stopped_by == StopReason.REQUESTED


class ResultThumb(QFrame):
    """Un cliché d'un groupe, en petit. Toute la vignette se clique."""

    picked = Signal(int, int)       # (groupe, cliché)

    def __init__(self, group: int, index: int, image, parent=None):
        super().__init__(parent)
        self._key = (group, index)
        theme.mark(self, "slot")
        vignette = QLabel()
        vignette.setAlignment(Qt.AlignCenter)
        vignette.setFixedSize(THUMB)
        if image is not None:
            vignette.setPixmap(QPixmap.fromImage(image.scaled(
                THUMB, Qt.KeepAspectRatio, Qt.SmoothTransformation)))
        pile = QVBoxLayout(self)
        pile.setContentsMargins(4, 4, 4, 4)
        pile.addWidget(vignette)

    def set_current(self, current: bool) -> None:
        theme.mark(self, "slot-current" if current else "slot")

    def mousePressEvent(self, event) -> None:
        super().mousePressEvent(event)
        if event.button() == Qt.LeftButton:
            self.picked.emit(*self._key)


class MultiRunTab(QWidget):
    """Lance, suit et présente un multi-lancement."""

    status_message = Signal(str)
    # Vrai pendant le calcul : l'écran d'exécution n'en lance jamais deux.
    busy_changed = Signal(bool)
    # Émis quand les groupes apparaissent : leur visite peut commencer.
    tutorial_changed = Signal()

    def __init__(self, session: Session, arrangements_directory: str = "",
                 parent=None):
        super().__init__(parent)
        self._session = session
        self._texts = TutorialTexts(self)
        # Où la bibliothèque range les agencements. Vide : rien n'est écrit.
        self._arrangements_directory = arrangements_directory
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
        # Le cliché choisi dans les groupes, (groupe, cliché), et ses vignettes.
        self._selected: tuple[int, int] | None = None
        self._thumbs: dict[tuple[int, int], ResultThumb] = {}
        self._zoom = ZOOM_MIN
        self._render_timer = QTimer(self)
        self._render_timer.setInterval(RENDER_INTERVAL_MS)
        self._render_timer.timeout.connect(self._flush_render)
        self._render_timer.start()
        self._build()
        # Les flèches parcourent les groupes : l'onglet doit pouvoir prendre le
        # clavier, et ses cadres défilants ne pas le lui voler.
        self.setFocusPolicy(Qt.StrongFocus)
        self._view.setFocusPolicy(Qt.NoFocus)
        self._results_scroll.setFocusPolicy(Qt.NoFocus)
        session.algorithm_changed.connect(self._update_estimate)
        session.saved_changed.connect(self._update_actions)

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

        # L'image : en direct pendant le calcul, le cliché choisi ensuite.
        self._image = QLabel()
        self._image.setAlignment(Qt.AlignCenter)
        self._view = QScrollArea()
        self._view.setWidget(self._image)
        self._view.setWidgetResizable(False)
        self._view.setAlignment(Qt.AlignCenter)
        self._view.setFrameShape(QFrame.StyledPanel)
        self._view.setMinimumHeight(260)

        self._zoom_out = QPushButton("−")
        self._zoom_in = QPushButton("+")
        self._zoom_label = QLabel()
        for bouton in (self._zoom_out, self._zoom_in):
            bouton.setFixedWidth(32)
        self._zoom_out.clicked.connect(lambda: self._zoom_by(1 / ZOOM_STEP))
        self._zoom_in.clicked.connect(lambda: self._zoom_by(ZOOM_STEP))
        self._choice = QLabel()
        # ⚠️ **Garder n'est pas seulement enregistrer.** Garder prend une des
        # quatre cases, celles d'où part l'export, et écrit aussi dans la
        # bibliothèque ; enregistrer n'écrit que dans la bibliothèque, sans
        # limite, pour ce qu'on veut retrouver plus tard sans l'exporter.
        self._keep = QPushButton()
        self._keep.clicked.connect(self._keep_selected)
        self._save = QPushButton()
        self._save.clicked.connect(self._save_selected)

        actions = QHBoxLayout()
        actions.addWidget(self._zoom_out)
        actions.addWidget(self._zoom_label)
        actions.addWidget(self._zoom_in)
        actions.addWidget(self._choice, 1)
        actions.addWidget(self._keep)
        actions.addWidget(self._save)

        gauche = QVBoxLayout()
        gauche.addWidget(self._view, 1)
        gauche.addLayout(actions)

        # Les groupes, un par lancement, cinq vignettes chacun.
        self._results = QWidget()
        self._results_grid = QGridLayout(self._results)
        self._results_grid.setContentsMargins(0, 0, 0, 0)
        self._results_grid.setSpacing(4)
        self._results_scroll = QScrollArea()
        self._results_scroll.setWidget(self._results)
        self._results_scroll.setWidgetResizable(True)
        self._results_scroll.setFrameShape(QScrollArea.NoFrame)
        self._results_scroll.setFixedWidth(RESULTS_WIDTH)
        self._results_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._results_scroll.hide()

        milieu = QHBoxLayout()
        milieu.addLayout(gauche, 1)
        milieu.addWidget(self._results_scroll)

        pile = QVBoxLayout(self)
        pile.addLayout(reglage)
        pile.addWidget(self._progress_label)
        pile.addWidget(self._progress)
        pile.addLayout(milieu, 1)
        self._update_buttons(running=False)
        self.retranslate_ui()

    def retranslate_ui(self) -> None:
        self._count_label.setText(self.tr("Nombre de lancements"))
        self._count_field.setToolTip(
            self.tr("Vingt au plus. Ils tournent l'un après l'autre, avec les "
                    "mêmes réglages."))
        self._start.setText(self.tr("Lancer"))
        self._stop.setText(self.tr("Arrêter"))
        self._keep.setText(self.tr("Garder"))
        self._keep.setToolTip(
            self.tr("Le met dans une des quatre cases, pour l'export, et dans "
                    "la bibliothèque."))
        self._save.setText(self.tr("Enregistrer dans la bibliothèque"))
        self._save.setToolTip(
            self.tr("L'écrit dans la bibliothèque des agencements, sans prendre "
                    "de case."))
        self._zoom_out.setToolTip(self.tr("Dézoomer"))
        self._zoom_in.setToolTip(self.tr("Zoomer"))
        self._update_pause_label()
        self._update_estimate()
        self._update_progress()
        if self.groups and not self.is_busy():
            self._show_results()
        self._update_actions()

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
        self._selected = None
        self._show_results()
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
        self._image.resize(self._view.viewport().size())
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
        self._show_results()
        # ⚠️ **Le meilleur est choisi d'office**, et non rien : « Garder » sert
        # tout de suite, et l'image montre ce qui vaut le plus d'être regardé
        # plutôt que le dernier état du dernier lancement.
        meilleur = self.best()
        if meilleur is not None:
            self.select(*meilleur)
        if self.groups:
            self.tutorial_changed.emit()

    # --- Tutoriel ---------------------------------------------------------

    def tutorial(self) -> Tutorial:
        """La visite de l'onglet, ou celle des groupes une fois qu'il y en a.

        ⚠️ **Aucune visite pendant le calcul** : l'image change sous la bulle,
        et les groupes n'apparaissent qu'à la fin.
        """
        textes = self._texts
        pret = lambda: not self.is_busy()
        if self.groups and not self.is_busy():
            return Tutorial(TUTORIAL_GROUPS, lambda: [
                Zone(lambda: self._results_scroll, textes.multi_groups),
                Zone(lambda: self._choice if self._choice.text() else None,
                     textes.multi_choice),
                Zone(lambda: self._keep, textes.multi_keep),
                Zone(lambda: self._save, textes.multi_save),
            ], pret)
        return Tutorial(TUTORIAL_MULTI, lambda: [
            Zone(lambda: self._count_field, textes.multi_count),
            Zone(lambda: self._estimate, textes.multi_estimate),
            Zone(lambda: self._start, textes.multi_start),
            Zone(lambda: self._pause, textes.multi_pause),
            Zone(lambda: self._stop, textes.multi_stop),
            Zone(lambda: self._progress, textes.multi_progress),
            Zone(lambda: self._view, textes.multi_view),
        ], pret)

    # --- Les groupes ------------------------------------------------------

    def best(self) -> tuple[int, int] | None:
        """Le cliché au plus petit score, tous groupes confondus."""
        choix = [(cliche.score, rang, index)
                 for rang, groupe in enumerate(self.groups)
                 for index, cliche in enumerate(groupe.snapshots)]
        if not choix:
            return None
        _, rang, index = min(choix)
        return rang, index

    def selected(self) -> tuple[RunGroup, Snapshot] | None:
        if self._selected is None:
            return None
        rang, index = self._selected
        if not (0 <= rang < len(self.groups)
                and 0 <= index < len(self.groups[rang].snapshots)):
            return None
        groupe = self.groups[rang]
        return groupe, groupe.snapshots[index]

    def locate(self, saved) -> tuple[int, int] | None:
        """Le cliché d'un groupe qui porte cet agencement gardé, s'il y est.

        Par le jeu de cartes, l'itération **et** la grille : deux lancements
        passent par les mêmes numéros d'itération sans ranger les mêmes cartes.
        """
        for rang, groupe in enumerate(self.groups):
            if groupe.cards is not saved.cards:
                continue
            for index, cliche in enumerate(groupe.snapshots):
                if (cliche.iteration == saved.iteration
                        and np.array_equal(cliche.grid, saved.grid)):
                    return rang, index
        return None

    def select(self, group: int, index: int) -> None:
        """Choisit un cliché d'un groupe et le montre en grand."""
        if self.is_busy():
            return
        self._selected = (group, index)
        if self.selected() is None:
            self._selected = None
        for cle, vignette in self._thumbs.items():
            vignette.set_current(cle == self._selected)
        if self._selected in self._thumbs:
            # Choisie au clavier, la vignette peut être hors de la vue.
            self._results_scroll.ensureWidgetVisible(self._thumbs[self._selected])
        self._pending = True
        self._flush_render()
        self._update_actions()

    def move_selection(self, d_group: int, d_index: int) -> None:
        """Passe au cliché voisin : même groupe à gauche et à droite, groupe
        voisin en haut et en bas.

        ⚠️ **Le rang est ramené au groupe d'arrivée.** Un lancement interrompu
        peut n'avoir qu'un cliché : descendre depuis le cinquième d'un groupe
        complet tombe sur son dernier, au lieu de ne rien faire.
        """
        if self._selected is None or not self.groups:
            return
        rang, index = self._selected
        rang = max(0, min(len(self.groups) - 1, rang + d_group))
        dernier = len(self.groups[rang].snapshots) - 1
        if dernier < 0:
            return
        index = max(0, min(dernier, index + d_index))
        if (rang, index) != self._selected:
            self.select(rang, index)

    def keyPressEvent(self, event) -> None:
        """Les flèches parcourent les groupes.

        ⚠️ **Les touches de navigation s'arrêtent ici**, même inutilisées.
        Ignorées, elles remontaient à l'écran d'exécution, qui déplaçait la
        timeline cachée du lancement simple et son zoom : « Repartir de ce
        cliché » serait ensuite parti d'un autre cliché que celui laissé.
        """
        deplacements = {Qt.Key_Left: (0, -1), Qt.Key_Right: (0, 1),
                        Qt.Key_Up: (-1, 0), Qt.Key_Down: (1, 0)}
        if event.key() in deplacements:
            self.move_selection(*deplacements[event.key()])
            event.accept()
            return
        if event.key() in NAVIGATION_KEYS:
            event.accept()
            return
        super().keyPressEvent(event)

    def _show_results(self) -> None:
        """Pose un groupe par lancement : son titre, puis ses clichés."""
        while self._results_grid.count():
            element = self._results_grid.takeAt(0)
            if element.widget() is not None:
                element.widget().deleteLater()
        self._thumbs = {}
        ligne = 0
        for rang, groupe in enumerate(self.groups):
            titre = QLabel(self._group_title(groupe))
            titre.setWordWrap(True)
            self._results_grid.addWidget(titre, ligne, 0, 1, KEPT_PER_RUN)
            ligne += 1
            for index, cliche in enumerate(groupe.snapshots):
                # ⚠️ **Composée petite.** À pleine taille, cent mosaïques de
                # plusieurs dizaines de mégapixels, réduites ensuite à 72 px,
                # figeaient l'interface à la fin d'un multi-lancement.
                image = mosaic_image(cliche.grid, groupe.cards,
                                     self._session.empty_colour,
                                     step=thumb_step(cliche.grid, groupe.cards))
                vignette = ResultThumb(rang, index, image)
                vignette.set_current((rang, index) == self._selected)
                    # Le clic donne aussi le clavier à l'onglet, sans rien faire de
                # plus : Qt le passe à l'ancêtre qui prend le focus au clic.
                vignette.picked.connect(self.select)
                self._results_grid.addWidget(vignette, ligne, index)
                self._thumbs[(rang, index)] = vignette
            ligne += 1
        self._results_grid.setRowStretch(ligne, 1)
        self._results_scroll.setVisible(bool(self.groups) and not self.is_busy())

    def _group_title(self, groupe: RunGroup) -> str:
        titre = self.tr("Lancement %1").replace("%1", str(groupe.rank + 1))
        if groupe.snapshots:
            # ⚠️ **Le plus petit, et non le dernier.** En recuit, la timeline
            # prend aussi des échanges qui dégradent : le dernier cliché n'est
            # pas toujours le meilleur des cinq.
            titre += ", " + self.tr("meilleur score %1").replace(
                "%1", f"{min(c.score for c in groupe.snapshots):.0f}")
        if groupe.interrupted:
            titre += ", " + self.tr("interrompu")
        return titre

    def _keep_selected(self) -> None:
        """Range le cliché choisi dans une case, et dans la bibliothèque."""
        choix = self.selected()
        if choix is None:
            return
        groupe, cliche = choix
        rang = self._session.save_grid(cliche.grid, groupe.cards,
                                       cliche.iteration, cliche.score)
        if rang is None:
            self.status_message.emit(
                self.tr("Les quatre cases sont prises : retirez-en une."))
            return
        try:
            nom = store_in_library(self._session, self._arrangements_directory,
                                   self._session.saved[rang])
        except OSError as erreur:
            self.status_message.emit(
                self.tr("Agencement gardé, mais non enregistré : %1")
                .replace("%1", str(erreur)))
            return
        self.status_message.emit(
            self.tr("Agencement gardé : %1").replace("%1", nom)
            if nom else self.tr("Agencement gardé."))

    def _save_selected(self) -> None:
        """Écrit le cliché choisi dans la bibliothèque, sans prendre de case."""
        choix = self.selected()
        if choix is None or not self._arrangements_directory:
            return
        groupe, cliche = choix
        agencement = SavedGrid(cliche.grid.copy(), groupe.cards,
                               cliche.iteration, cliche.score)
        try:
            nom = store_in_library(self._session, self._arrangements_directory,
                                   agencement)
        except OSError as erreur:
            self.status_message.emit(
                self.tr("Échec de l'enregistrement : %1")
                .replace("%1", str(erreur)))
            return
        self.status_message.emit(
            self.tr("Agencement enregistré : %1").replace("%1", nom))

    def _update_actions(self) -> None:
        choisi = self.selected() is not None and not self.is_busy()
        self._keep.setEnabled(choisi
                              and self._session.saved_count() < MAX_SAVED)
        self._save.setEnabled(choisi and bool(self._arrangements_directory))
        choix = self.selected()
        if choix is None or self.is_busy():
            self._choice.setText("")
        else:
            groupe, cliche = choix
            self._choice.setText(
                self.tr("Lancement %1, cliché %2, score %3")
                .replace("%1", str(groupe.rank + 1))
                .replace("%2", str(self._selected[1] + 1))
                .replace("%3", f"{cliche.score:.0f}"))
        self._zoom_label.setText(f"{self._zoom * 100:.0f} %")
        self._zoom_out.setEnabled(choisi and self._zoom > ZOOM_MIN)
        self._zoom_in.setEnabled(choisi and self._zoom < ZOOM_MAX)

    # --- Affichage --------------------------------------------------------

    def _zoom_by(self, facteur: float) -> None:
        voulu = max(ZOOM_MIN, min(ZOOM_MAX, self._zoom * facteur))
        if voulu == self._zoom:
            return
        self._zoom = voulu
        self._pending = True
        self._flush_render()
        self._update_actions()

    def _shown(self):
        """La grille et le jeu à montrer : en direct, sinon le cliché choisi."""
        if self.is_busy():
            if not self._timeline:
                return None
            return self._timeline[-1].grid, self._cards, ZOOM_MIN
        choix = self.selected()
        if choix is not None:
            groupe, cliche = choix
            return cliche.grid, groupe.cards, self._zoom
        if self._timeline:
            return self._timeline[-1].grid, self._cards, ZOOM_MIN
        return None

    def _flush_render(self) -> None:
        if not self._pending:
            return
        montre = self._shown()
        if montre is None:
            return
        self._pending = False
        grille, cartes, zoom = montre
        image = mosaic_image(grille, cartes, self._session.empty_colour)
        if image is None:
            return
        ajuste = image.scaled(self._view.viewport().size(), Qt.KeepAspectRatio,
                              Qt.SmoothTransformation)
        pixmap = QPixmap.fromImage(image.scaled(
            ajuste.size() * zoom, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self._image.setText("")
        self._image.setPixmap(pixmap)
        self._image.resize(pixmap.size())

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
            # ⚠️ Un lancement arrêté a bien un résultat, mais n'est pas allé à
            # son terme : « 4 lancements terminés » se lisait après en avoir
            # interrompu un.
            menes = sum(1 for groupe in self.groups if not groupe.interrupted)
            # Le score se lit à l'envers de ce qu'on attend d'une note : sans
            # le dire, « meilleur score 2592 » passait pour moins bon que 2970.
            self._progress_label.setText(
                self.tr("%n lancement(s) terminé(s).", "", menes) + " "
                + self.tr("Plus le score est bas, plus l'agencement est optimisé."))
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
        self._update_actions()
        self.busy_changed.emit(running)

    def _update_pause_label(self) -> None:
        paused = self._control is not None and self._control.paused
        self._pause.setText(self.tr("Reprendre") if paused else self.tr("Pause"))
