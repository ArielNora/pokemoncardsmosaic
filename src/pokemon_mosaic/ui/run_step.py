"""Vue d'exécution : l'image se construit, la timeline se remplit."""


import numpy as np
from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSlider,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..control import RunControl
from ..optimize import StopReason
from .runner import start_run
from .saved_column import SavedColumn, SavedDialog, mosaic_image
from .session import MAX_SAVED, Session

# Un cran de zoom. 1,25 laisse une progression douce sans multiplier les clics.
ZOOM_STEP = 1.25
# Au-delà de la résolution des vignettes, agrandir n'ajoute aucun détail : le
# plafond se calcule donc à partir de l'échelle d'ajustement, pas en dur.
ZOOM_CEILING = 8.0

# Rendre un cliché coûte 56 ms sur une grille 17×17 : recopie des vignettes, puis
# réduction lissée de 12,6 Mpx. À raison d'un rendu par cliché, l'affichage
# demanderait 3,9 s de fil principal là où le calcul en prend 1,6, l'interface
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


# Le bouton d'accueil : plus gros que ceux de la barre du bas, c'est le seul
# geste de l'écran tant que rien n'a tourné.
WELCOME_BOOST = 3
WELCOME_BUTTON = QSize(220, 52)


class RunStep(QWidget):
    """Pilote une exécution et laisse naviguer dans ses états successifs."""

    status_message = Signal(str)
    # La fenêtre en dépend pour le bouton « Suivant » : il ne s'allume qu'une
    # fois un agencement gardé.
    advance_state_changed = Signal()

    def __init__(self, session: Session, parent=None):
        super().__init__(parent)
        self._session = session
        self._control: RunControl | None = None
        self._thread = None
        self._worker = None
        # Sélection et liens au moment où le calcul a démarré. Repartir d'un
        # cliché n'a de sens que si la numérotation des cartes n'a pas bougé.
        self._run_signature: tuple | None = None
        self._cards = None
        self._timeline = None
        self._following = True      # suit le dernier cliché tant qu'on ne touche pas
        # Vrai le temps d'un réglage de curseur que nous provoquons : ce n'est
        # pas un geste de l'utilisateur et il ne doit rien conclure de la
        # position qui en résulte.
        self._adjusting = False
        # Longueur de la timeline au dernier cliché reçu, pour repérer un
        # élagage : le seul événement qui la fasse diminuer.
        self._last_count = 0
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
        # de réglage, et cliquer dessus ne ferait rien, `_extend_run` sort
        # aussitôt sur `can_resume()`.
        session.algorithm_changed.connect(self._update_resume_buttons)

    # --- Construction -----------------------------------------------------

    def _build(self) -> None:
        self._image = QLabel()
        self._image.setAlignment(Qt.AlignCenter)

        # Zone défilante : une image zoomée dépasse la fenêtre, il faut pouvoir
        # la parcourir. `setWidgetResizable(False)` est indispensable, vrai, le
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

        # ⚠️ **Un écran qui n'a rien encore à montrer offre le geste à faire.**
        # Une phrase seule laissait chercher où l'on lance : le bouton du bas se
        # perdait dans une rangée de six, tous éteints sauf lui.
        self._welcome_text = QLabel()
        self._welcome_text.setAlignment(Qt.AlignCenter)
        self._welcome_text.setWordWrap(True)
        self._welcome_start = QPushButton()
        gros = self._welcome_start.font()
        gros.setPointSize(gros.pointSize() + WELCOME_BOOST)
        self._welcome_start.setFont(gros)
        self._welcome_start.setMinimumSize(WELCOME_BUTTON)
        self._welcome_start.clicked.connect(lambda: self.start_run())

        accueil = QVBoxLayout()
        accueil.addStretch(1)
        accueil.addWidget(self._welcome_text)
        accueil.addSpacing(16)
        accueil.addWidget(self._welcome_start, 0, Qt.AlignCenter)
        accueil.addStretch(1)
        self._welcome = QWidget()
        self._welcome.setLayout(accueil)

        # Une pile plutôt qu'un texte posé dans le label de l'image : un bouton
        # ne se met pas dans un `QLabel`, et l'écran d'accueil n'a rien à faire
        # d'une zone défilante ni d'un cadre.
        self._view = QStackedWidget()
        self._view.addWidget(self._welcome)
        self._view.addWidget(self._scroll)

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

        self._extend.setEnabled(False)
        self._resume.setEnabled(False)
        # ⚠️ **Mettre de côté n'est pas exporter.** L'export écrit un fichier
        # tout de suite ; garder un agencement ne fait que le réserver pour
        # l'étape suivante, où on l'habillera.
        self._keep = QPushButton()
        self._keep.clicked.connect(self._keep_current)
        self._keep.setEnabled(False)

        self._saved = SavedColumn(self._session)
        self._saved.slot_picked.connect(self._show_saved)
        self._session.saved_changed.connect(self._update_keep)

        controls = QHBoxLayout()
        controls.addWidget(self._start)
        controls.addWidget(self._pause)
        controls.addWidget(self._stop)
        controls.addWidget(self._extend)
        controls.addWidget(self._resume)
        controls.addWidget(self._keep)
        controls.addStretch(1)
        self._summary = QLabel()
        controls.addWidget(self._summary)

        # La colonne longe l'image et la timeline : elle appartient à ce qu'on
        # regarde, pas à la barre de commandes.
        milieu = QHBoxLayout()
        milieu.addWidget(self._view, 1)
        milieu.addWidget(self._saved)

        layout = QVBoxLayout(self)
        layout.addLayout(milieu, 1)
        layout.addLayout(timeline_row)
        layout.addLayout(controls)
        # « Pause » et « Arrêter » naissaient actifs : cliquables sans effet tant
        # qu'aucun calcul ne tourne, et deux boutons de plus à ignorer sur un
        # écran qui n'en propose qu'un.
        self._update_buttons(running=False)
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
        self._zoom_fit.setText(self.tr("Ajuster"))
        self._zoom_out.setToolTip(self.tr("Dézoomer (touche −)"))
        self._zoom_in.setToolTip(self.tr("Zoomer (touche +)"))
        self._zoom_fit.setToolTip(self.tr("Revenir à l'image entière"))
        self._slider.setToolTip(
            self.tr("Flèches gauche et droite pour parcourir les clichés.")
        )
        self._welcome_start.setText(self.tr("Lancer le calcul"))
        self._keep.setText(self.tr("Enregistrer"))
        self._saved.retranslate_ui()
        self._welcome_text.setText(
            self.tr("Tout est réglé. Lancez le calcul pour voir la mosaïque se "
                    "construire, cliché après cliché.")
        )
        self._update_pause_label()
        self._update_position()
        self._update_zoom_label()
        self._update_view()

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
        # Le premier cliché n'arrive pas instantanément : sans ce mot, l'écran
        # resterait sur son invitation alors que le calcul a démarré.
        self._show_placeholder(self.tr("Calcul en cours…"))
        self._update_view()
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
        score**. Mesuré : la même grille vaut 621,7 avec une bande de 0,10 et
        552,0 avec 0,30, soit 11 % d'écart. Prolonger sans le prendre en compte
        mêlait deux métriques dans une seule timeline, et la courbe montrait une
        chute soudaine alors qu'aucune carte n'avait bougé.

        ⚠️ **Les cartes d'un lien ne suffisent pas : sa forme et son ordre
        comptent aussi.** L'optimiseur exige que chaque bloc soit déjà intact
        *dans sa forme courante*. Un 3×1 rouvert en 1×3 garde les mêmes cartes,
        donc gardait la même signature : le bouton restait actif et le calcul
        échouait au lancement sur un message citant `build_initial_grid`.

        ⚠️ **La position des cases vides en fait partie.** Reprendre saute
        `build_initial_grid`, donc les trous restent là où ils étaient. Mesuré :
        trous demandés en (1,2) et (2,3), grille reprise gardant (0,0) et (1,2),
        sans le moindre signe.
        """
        session = self._session
        return (
            tuple(session.selected_indices()),
            tuple(sorted((link.cards, link.shape, link.ordered)
                         for link in session.usable_links().active)),
            (session.rows, session.cols),
            tuple(sorted(session.empty_cells())),
            session.strip_size,
        )

    def can_resume(self) -> bool:
        """Vrai si un calcul terminé peut être repris tel quel.

        Un export en cours compte comme occupé : c'est cette méthode, et elle
        seule, qui décide de l'état des boutons, les griser à part la ferait
        diverger de ce qu'ils montrent.
        """
        return (bool(self._timeline)
                and self._thread is None
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
        """Grille du cliché affiché : c'est elle que l'export écrit."""
        if not self._timeline:
            return None
        index = max(0, min(len(self._timeline) - 1, self._slider.value()))
        return self._timeline[index].grid

    # --- Agencements mis de côté ------------------------------------------

    def _keep_current(self) -> None:
        """Range le cliché affiché dans la première case libre."""
        grid = self.current_grid()
        if grid is None or self._cards is None:
            return
        index = max(0, min(len(self._timeline) - 1, self._slider.value()))
        cliche = self._timeline[index]
        rang = self._session.save_grid(grid, self._cards,
                                       cliche.iteration, cliche.score)
        if rang is None:
            self.status_message.emit(
                self.tr("Les cinq cases sont prises : retirez-en une."))
            return
        self._update_current_slot()
        self.status_message.emit(self.tr("Agencement gardé."))

    def _show_saved(self, slot: int) -> None:
        """Retourne au cliché d'une case gardée, ou l'ouvre à part.

        ⚠️ **La timeline s'élague, et un nouveau calcul la remplace.** Le rang
        d'un cliché ne veut donc rien dire une heure plus tard. On le retrouve
        par son numéro d'itération **et** sa grille, deux calculs pouvant passer
        par la même itération sans y ranger les mêmes cartes.

        Faute de le retrouver, le curseur ne bouge pas : le montrer au plus
        proche donnerait à voir autre chose que ce que la case promet. Une
        fenêtre à part le montre pour lui-même, et le dit.
        """
        saved = self._session.saved[slot]
        if saved is None:
            return
        rang = self._snapshot_of(saved)
        if rang is not None:
            self._following = False
            self._slider.setValue(rang)
            self._update_current_slot()
            return
        self._open_saved_dialog(saved)

    def _open_saved_dialog(self, saved) -> None:
        """Ouvre la fenêtre d'un agencement que la timeline n'a plus.

        À part pour que les tests puissent l'intercepter : un `exec()` modal
        n'a pas de fin dans une suite qui ne clique sur rien.
        """
        dialogue = SavedDialog(saved, self._session.empty_colour, parent=self)
        try:
            dialogue.exec()
        finally:
            # Parenté à l'écran, la fenêtre lui survivrait.
            dialogue.deleteLater()

    def _snapshot_of(self, saved) -> int | None:
        """Le rang du cliché qui porte cet agencement, s'il est encore là."""
        for rang, cliche in enumerate(self._timeline or []):
            if (cliche.iteration == saved.iteration
                    and np.array_equal(cliche.grid, saved.grid)):
                return rang
        return None

    def _update_current_slot(self) -> None:
        """⚠️ **La case verte est celle qu'on regarde**, et rien de plus.

        Marquée à la sauvegarde et laissée telle quelle, elle prétendait montrer
        l'agencement affiché alors que le curseur était parti ailleurs.
        """
        courant = None
        if self._timeline:
            index = max(0, min(len(self._timeline) - 1, self._slider.value()))
            cliche = self._timeline[index]
            for numero, place in enumerate(self._session.saved):
                if (place is not None and place.iteration == cliche.iteration
                        and np.array_equal(place.grid, cliche.grid)):
                    courant = numero
                    break
        self._saved.set_current(courant)

    def _update_keep(self) -> None:
        """Garder n'a de sens que sur un cliché, et tant qu'il reste une case."""
        libre = self._session.saved_count() < MAX_SAVED
        self._keep.setEnabled(bool(self._timeline) and libre)
        self._update_current_slot()
        self.advance_state_changed.emit()

    def can_advance(self) -> bool:
        """⚠️ **L'export part des agencements gardés**, pas du cliché affiché :
        sans une case au moins, l'étape suivante n'aurait rien à habiller."""
        return self._session.saved_count() > 0

    def shutdown(self) -> bool:
        """Arrête le calcul. Rend faux s'il résiste.

        Le résultat compte : le `QThread` a pour parent ce widget, donc la
        fenêtre détruite l'emporte avec elle, référence Python ou non. Fermer
        malgré un fil actif fait abandonner le processus par Qt.

        L'export a quitté cet écran pour l'étape 4, qui arrête le sien de la
        même façon : deux fils ne se croisent plus ici.
        """
        if self._control is not None:
            self._control.stop()
        if self._thread is not None and self._thread.isRunning():
            self._thread.quit()
            if not self._thread.wait(SHUTDOWN_TIMEOUT_MS):
                # `status_message` et non `print` : depuis un paquet `.app`, la
                # sortie standard ne va nulle part que l'utilisateur puisse lire.
                self.status_message.emit(
                    self.tr("Arrêt en cours : %1 ne répond pas encore.")
                    .replace("%1", self.tr("le calcul"))
                )
                return False
        # Une référence n'est lâchée que si son fil est réellement terminé :
        # lâcher celle d'un fil encore actif rouvrirait le même crash.
        self._thread = self._worker = None
        return True

    # --- Réactions du calcul ---------------------------------------------

    def _on_started(self, cards, timeline) -> None:
        self._cards = cards
        self._timeline = timeline
        # L'accueil a fait son office : il y a désormais quelque chose à voir.
        self._update_view()
        self._update_keep()
        self._slider.setEnabled(True)
        # Le plafond se déduit de la grille : une grille plus petite que la
        # précédente l'abaisse, et le zoom hérité doit redescendre avec lui.
        self._zoom = min(self._zoom, self._max_zoom())
        self._update_zoom_label()

    def _on_snapshot(self, snapshot) -> None:
        # ⚠️ **Au premier cliché, pas au démarrage.** Le bouton se réveillait
        # dans `_on_started`, où la timeline est encore vide : il restait donc
        # éteint tout le calcul, et seul un « Prolonger » le rallumait.
        self._update_keep()
        count = len(self._timeline)
        # ⚠️ **L'élagage fait baisser le maximum.** La timeline se divise par
        # deux dès 70 clichés : Qt écrête alors la position courante et émet
        # `valueChanged`. Sans ce garde, `_on_slider_moved` en déduisait que
        # l'utilisateur était revenu en butée et rebasculait en suivi du direct,
        # mesuré, curseur 45 ramené à 44 et l'image se remettant à défiler
        # sous ses yeux, précisément ce que la ligne suivante veut éviter.
        self._adjusting = True
        try:
            self._slider.setMaximum(max(0, count - 1))
        finally:
            self._adjusting = False
        # On ne déplace le curseur que si l'utilisateur suit le direct : sinon il
        # verrait l'image lui échapper pendant qu'il examine un état antérieur.
        if self._following:
            self._slider.setValue(count - 1)
            self._show(count - 1)
        elif count < self._last_count:
            # ⚠️ L'élagage **renumérote** : la case du curseur ne désigne plus
            # le même cliché. Sans ce rendu, l'écran garderait l'image
            # précédente sous une étiquette qui a changé, et l'export, qui lit
            # `current_grid()`, écrirait la grille du nouveau cliché, différente
            # de ce que l'utilisateur regarde. Mesuré : index 20 passé de
            # l'itération 20 à l'itération 40, image inchangée.
            self._show(self._slider.value())
        self._last_count = count
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
            self.tr("Score %1 → %2 (%3 % de gain), arrêt : %4")
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
        # Revenir sur le dernier cliché remet en mode « suivre le direct »,
        # mais seulement si c'est bien l'utilisateur qui l'y a mis.
        if not self._adjusting:
            self._following = value >= len(self._timeline) - 1
        self._show(value)
        self._update_position()
        self._update_resume_buttons()
        self._update_current_slot()

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
        image = mosaic_image(grid, self._cards, self._session.empty_colour)
        if image is None:
            return None
        width, height = image.width(), image.height()
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

    def _update_view(self) -> None:
        """L'accueil tant que rien n'a tourné, l'image dès qu'il y a un cliché."""
        rien_encore = not self._timeline and self._thread is None
        self._view.setCurrentWidget(self._welcome if rien_encore else self._scroll)

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
            # Un tiret tenait lieu de « rien » ; il ne se lit pas, et la règle
            # d'écriture l'exclut. Le mot le dit.
            self._position.setText(self.tr("aucun cliché"))
            return
        self._position.setText(
            self.tr("cliché %1 / %2")
            .replace("%1", str(self._slider.value() + 1))
            .replace("%2", str(len(self._timeline)))
        )
