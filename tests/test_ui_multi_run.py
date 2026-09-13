"""Tests du multi-lancement : plusieurs calculs enchaînés, cinq clichés gardés."""

import numpy as np
import pytest

from pokemon_mosaic.cards import Card, CardSet
from pokemon_mosaic.control import RunControl
from pokemon_mosaic.optimize import StopReason
from pokemon_mosaic.timeline import Timeline


def card_set(n, size=(12, 16)):
    rng = np.random.default_rng(0)
    width, height = size
    ramp = np.linspace(0.0, 1.0, height)[:, None]
    cards = []
    for i in range(n):
        top, bottom = (rng.integers(0, 255, 3).astype(float) for _ in range(2))
        column = top * (1 - ramp) + bottom * ramp
        thumb = np.repeat(column[:, None, :], width, axis=1).astype(np.uint8)
        card = Card(path=f"/fake/{i}.png", index=i, thumbnail=thumb)
        card.calculate_features(0.1)
        cards.append(card)
    return CardSet(cards=cards, full_size=(713, 984), thumb_size=size)


@pytest.fixture
def session(qt_app):
    from pokemon_mosaic.ui.session import Session

    s = Session()
    s.set_cards(card_set(20), "/fake")
    s.set_layout(cols=5, rows=4)
    s.set_algorithm(iterations=3000, snapshot_every=2, use_annealing=False)
    return s


def multi_run(session, count, control=None, **reactions):
    """Exécute le multi-lancement dans le fil courant, sans QThread."""
    from pokemon_mosaic.ui.runner import MultiRunWorker

    control = control or RunControl()
    worker = MultiRunWorker(session, control, count)
    seen = {"started": [], "snapshots": [], "finished": [], "all": [], "failed": []}
    worker.run_started.connect(lambda r, c, t: seen["started"].append((r, c, t)))
    worker.snapshot.connect(lambda r, s: seen["snapshots"].append(r))
    worker.run_finished.connect(lambda r, res: seen["finished"].append((r, res)))
    worker.finished_all.connect(seen["all"].append)
    worker.failed.connect(seen["failed"].append)
    for nom, reaction in reactions.items():
        getattr(worker, nom).connect(reaction)
    worker.run()
    return seen


# --- Les cinq derniers clichés ---------------------------------------------

def test_the_last_five_snapshots_are_kept_in_order():
    from pokemon_mosaic.ui.runner import last_snapshots

    timeline = Timeline(every=1, max_snapshots=None)
    for i in range(8):
        timeline.record(np.zeros((2, 2), int), i, i, float(10 - i), 0.0)

    assert [s.iteration for s in last_snapshots(timeline)] == [3, 4, 5, 6, 7]


def test_a_short_timeline_gives_what_it_has():
    from pokemon_mosaic.ui.runner import last_snapshots

    timeline = Timeline(every=1, max_snapshots=None)
    for i in range(3):
        timeline.record(np.zeros((2, 2), int), i, i, 1.0, 0.0)

    assert len(last_snapshots(timeline)) == 3
    assert last_snapshots(None) == []


# --- L'enchaînement ----------------------------------------------------------

def test_the_runs_follow_one_another(session):
    seen = multi_run(session, 3)

    assert seen["failed"] == []
    assert [rang for rang, _, _ in seen["started"]] == [0, 1, 2]
    assert [rang for rang, _ in seen["finished"]] == [0, 1, 2]
    assert seen["all"] == [3]
    # Chaque cliché dit de quel lancement il vient, dans l'ordre.
    assert seen["snapshots"] == sorted(seen["snapshots"])
    assert set(seen["snapshots"]) == {0, 1, 2}


def test_each_run_has_its_own_timeline(session):
    seen = multi_run(session, 2)
    premiere, seconde = seen["started"][0][2], seen["started"][1][2]

    assert premiere is not seconde
    assert len(premiere) > 1 and len(seconde) > 1


def test_chance_alone_tells_the_runs_apart(session):
    """Mêmes réglages : seul le tirage des échanges les différencie."""
    seen = multi_run(session, 3)
    finales = [timeline[-1].grid for _, _, timeline in seen["started"]]

    assert not all(np.array_equal(finales[0], grille) for grille in finales[1:])


def test_the_count_is_capped_at_twenty(session):
    from pokemon_mosaic.ui.runner import MULTI_RUN_MAX, MultiRunWorker

    assert MULTI_RUN_MAX == 20
    assert MultiRunWorker(session, RunControl(), 50).count == 20
    assert MultiRunWorker(session, RunControl(), 0).count == 1


def test_the_settings_are_read_once_for_every_run(session):
    """Un réglage touché pendant le calcul ne change pas les lancements
    suivants : les groupes ne se compareraient plus."""
    def touche(rang, _cartes, _timeline):
        if rang == 0:
            session.set_algorithm(iterations=10)

    seen = multi_run(session, 2, run_started=touche)

    assert [result.attempted for _, result in seen["finished"]] == [3000, 3000]


def test_a_stop_ends_the_current_run_and_starts_no_other(session):
    """Le lancement interrompu garde ses clichés ; aucun autre ne commence."""
    control = RunControl()

    def arrete(rang, _cliche):
        if rang == 1:
            control.stop()

    seen = multi_run(session, 4, control=control, snapshot=arrete)

    assert [rang for rang, _, _ in seen["started"]] == [0, 1]
    assert seen["finished"][1][1].stopped_by == StopReason.REQUESTED
    assert len(seen["started"][1][2]) >= 1
    assert seen["all"] == [2]


def test_a_multi_run_without_cards_fails_cleanly(qt_app):
    from pokemon_mosaic.ui.session import Session

    seen = multi_run(Session(), 3)

    assert seen["failed"] and seen["started"] == [] and seen["all"] == []
