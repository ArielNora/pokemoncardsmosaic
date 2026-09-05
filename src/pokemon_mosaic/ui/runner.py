"""Exécution de l'optimisation dans un fil de fond, pilotée depuis l'interface.

Le calcul dure plusieurs secondes et doit rester interruptible : il vit donc dans
un QThread, et communique par signaux. La grille est modifiée sur place par
`optimize_grid`, mais les clichés de la timeline en sont des copies, c'est
seulement eux que l'interface lit, jamais la grille en cours de modification.
"""

import numpy as np
from PySide6.QtCore import QObject, QThread, Signal

from ..control import RunControl
from ..optimize import (
    OptimizationResult,
    build_initial_grid,
    optimize_grid,
    select_cards,
)
from ..scoring import EMPTY, EdgeDistances
from ..timeline import Timeline


class RunWorker(QObject):
    """Prépare puis optimise la grille. Destiné à vivre dans un QThread."""

    started_run = Signal(object, object)   # (CardSet retenu, Timeline)
    snapshot = Signal(object)              # dernier Snapshot enregistré
    finished_run = Signal(object)          # OptimizationResult
    failed = Signal(str)

    def __init__(self, session, control: RunControl, previous_grid=None,
                 timeline=None):
        super().__init__()
        self._session = session
        self._control = control
        # Grille de départ imposée : sert à prolonger un calcul ou à repartir
        # d'un cliché choisi dans la timeline.
        self._previous_grid = previous_grid
        # Timeline à poursuivre. Fournie, ses clichés sont conservés et les
        # nouveaux s'y ajoutent à la suite ; absente, on en ouvre une neuve.
        self._timeline = timeline

    def run(self) -> None:
        try:
            cards, links, timeline, grid, distances = self._prepare()
        except Exception as error:  # noqa: BLE001 - voir ci-dessous
            # Volontairement large : une exception qui s'échappe de ce slot
            # n'émettrait ni finished_run ni failed, donc thread.quit() ne
            # serait jamais appelé. L'interface resterait figée sur un calcul
            # qui n'existe plus, sans possibilité d'en relancer un.
            self.failed.emit(str(error))
            return

        self.started_run.emit(cards, timeline)

        try:
            result: OptimizationResult = optimize_grid(
                grid, distances, links.group_map(),
                annealing=self._session.annealing(),
                stop=self._session.stop_conditions(),
                timeline=timeline,
                control=self._control,
            )
        except Exception as error:  # noqa: BLE001 - remonté plutôt qu'avalé
            self.failed.emit(str(error))
            return
        self.finished_run.emit(result)

    def _prepare(self):
        session = self._session
        if session.card_set is None or session.selected_count == 0:
            raise ValueError("Aucune carte retenue.")

        # `select_cards` et non `subset` : les liens doivent être traduits en même
        # temps que les cartes sont renumérotées.
        cards, links = select_cards(
            session.card_set, session.selected_indices(), session.usable_links()
        )
        distances = EdgeDistances(cards.cards)
        # Le rappel s'exécute dans ce fil ; la connexion étant automatiquement
        # mise en file d'attente, l'interface le reçoit dans le sien.
        if self._timeline is not None:
            timeline = self._timeline
            timeline.on_record = self.snapshot.emit
            # La cadence reste celle de la timeline poursuivie, et non celle des
            # réglages : elle a pu doubler à chaque éclaircissage, et repartir du
            # réglage d'origine rendrait la seconde moitié bien plus dense que la
            # première pour un même nombre d'échanges retenus.
        else:
            timeline = Timeline(every=session.snapshot_every,
                                on_record=self.snapshot.emit)

        if self._previous_grid is not None:
            grid = self._previous_grid.copy()
            _check_resumable(grid, cards, session)
        else:
            grid = build_initial_grid(
                cards, shape=(session.cols, session.rows), links=links,
                empty_cells=session.empty_cells(),
            )
        return cards, links, timeline, grid, distances


def _check_resumable(grid, cards, session) -> None:
    """Refuse de repartir d'une grille qui ne décrit plus la sélection courante.

    Les cartes retenues sont renumérotées de 0 à n-1 à chaque préparation : si la
    sélection ou la grille a changé depuis le calcul d'origine, les indices de
    l'ancienne grille désignent d'autres cartes. Rien ne planterait : le poster
    serait simplement composé de cartes que l'utilisateur n'a pas choisies.
    """
    if grid.shape != (session.rows, session.cols):
        raise ValueError(
            f"La grille du cliché fait {grid.shape[1]}×{grid.shape[0]} alors que "
            f"la mise en page en demande {session.cols}×{session.rows}."
        )
    placed = {int(value) for value in np.unique(grid)} - {EMPTY}
    if placed - set(range(len(cards))):
        raise ValueError(
            "Le cliché désigne des cartes qui ne font plus partie de la sélection."
        )


def start_run(parent, session, control, previous_grid=None, timeline=None,
              **handlers):
    """Lance une optimisation en fond. Renvoie (thread, worker) à garder en vie."""
    thread = QThread(parent)
    worker = RunWorker(session, control, previous_grid, timeline)
    worker.moveToThread(thread)

    thread.started.connect(worker.run)
    for name, slot in handlers.items():
        getattr(worker, name).connect(slot)
    worker.finished_run.connect(thread.quit)
    worker.failed.connect(thread.quit)
    thread.finished.connect(worker.deleteLater)

    thread.start()
    return thread, worker
