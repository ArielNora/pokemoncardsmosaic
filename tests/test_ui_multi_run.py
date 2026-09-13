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
        # Une réaction ou une liste : l'onglet et le test écoutent parfois le
        # même signal.
        for une in reaction if isinstance(reaction, list) else [reaction]:
            getattr(worker, nom).connect(une)
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


# --- L'onglet ----------------------------------------------------------------

@pytest.fixture
def tab(qt_app, session):
    from pokemon_mosaic.ui.multi_run_tab import MultiRunTab

    widget = MultiRunTab(session)
    widget.resize(700, 500)
    return widget, session


def feed_tab(widget, session, count, **reactions):
    """Rejoue un multi-lancement dans l'onglet, sans fil de fond."""
    widget._count = count
    widget._update_buttons(running=True)
    widget._thread = object()
    # L'onglet d'abord : une réaction du test lit ce qu'il vient d'afficher.
    handlers = {"run_started": [widget._on_run_started],
                "snapshot": [widget._on_snapshot],
                "run_finished": [widget._on_run_finished],
                "finished_all": [widget._on_finished_all],
                "failed": [widget._on_failed]}
    for nom, reaction in reactions.items():
        handlers[nom].append(reaction)
    return multi_run(session, count, **handlers)


@pytest.fixture
def capture_multi_runs(monkeypatch):
    from pokemon_mosaic.ui import multi_run_tab as module

    calls = []

    def fake(parent, session, control, count, **handlers):
        calls.append(count)
        return object(), object()

    monkeypatch.setattr(module, "start_multi_run", fake)
    return calls


def test_the_count_field_stops_at_twenty(tab):
    widget, _ = tab
    widget._count_field.setValue(35)

    assert widget._count_field.value() == 20


def test_launching_passes_the_chosen_count(tab, capture_multi_runs):
    widget, _ = tab
    widget._count_field.setValue(7)

    widget._start.click()

    assert capture_multi_runs == [7]
    assert widget.is_busy()
    assert not widget._start.isEnabled() and widget._stop.isEnabled()


def test_the_estimate_multiplies_one_run_by_the_count(tab):
    from pokemon_mosaic.ui.estimates import format_duration

    widget, session = tab
    session.set_algorithm(iterations=1_270_000, use_annealing=False)
    widget._count_field.setValue(4)

    assert format_duration(40) in widget._estimate.text()


def test_the_estimate_is_capped_by_the_time_budget(tab):
    from pokemon_mosaic.ui.estimates import format_duration

    widget, session = tab
    session.set_algorithm(iterations=1_270_000, use_annealing=False,
                          stop_on_time=True, time_budget=3.0)
    widget._count_field.setValue(4)

    assert format_duration(12) in widget._estimate.text()


def test_each_run_leaves_a_group_of_its_last_five_snapshots(tab):
    widget, session = tab
    seen = feed_tab(widget, session, 3)

    assert [groupe.rank for groupe in widget.groups] == [0, 1, 2]
    for groupe, (_, _, timeline) in zip(widget.groups, seen["started"], strict=True):
        assert len(groupe.snapshots) == 5
        assert groupe.snapshots == timeline.snapshots[-5:]
        assert groupe.result is not None and groupe.cards is not None
    assert not widget.is_busy() and widget._start.isEnabled()


def test_the_progress_names_the_run_in_progress(tab):
    widget, session = tab
    vus = []

    feed_tab(widget, session, 3,
             snapshot=lambda rang, _s: vus.append(widget._progress_label.text()))

    # Compté depuis un : le premier lancement n'est pas « 0 sur 3 ».
    assert set(vus) == {"Lancement 1 sur 3", "Lancement 2 sur 3",
                        "Lancement 3 sur 3"}
    assert widget._progress.value() == 3


def test_the_live_image_follows_a_resize(tab):
    """Refaite au seul cliché suivant, elle gardait l'ancienne échelle, et pour
    toujours une fois le calcul fini."""
    widget, session = tab
    widget.show()
    feed_tab(widget, session, 1)
    widget._flush_render()
    avant = widget._image.pixmap().width()

    widget.resize(1400, 1000)
    widget._flush_render()

    assert widget._image.pixmap().width() > avant


def test_a_stopped_multi_run_keeps_the_interrupted_run(tab):
    widget, session = tab

    def arrete(rang, _cliche):
        if rang == 1:
            widget._request_stop()

    widget._control = RunControl()
    from pokemon_mosaic.ui.runner import MultiRunWorker

    worker = MultiRunWorker(session, widget._control, 4)
    widget._count = 4
    worker.run_started.connect(widget._on_run_started)
    worker.snapshot.connect(widget._on_snapshot)
    worker.snapshot.connect(arrete)
    worker.run_finished.connect(widget._on_run_finished)
    worker.finished_all.connect(widget._on_finished_all)
    worker.run()

    assert [groupe.rank for groupe in widget.groups] == [0, 1]
    assert widget.groups[1].snapshots
    assert widget.groups[1].result.stopped_by == StopReason.REQUESTED


def test_a_failure_keeps_the_groups_already_done(tab):
    widget, session = tab
    widget._thread = object()
    widget._on_run_started(0, session.card_set, Timeline())
    widget._on_run_finished(0, object())

    widget._on_failed("disque plein")

    assert len(widget.groups) == 1
    assert not widget.is_busy()


def test_a_new_multi_run_replaces_the_previous_results(tab, capture_multi_runs):
    widget, session = tab
    feed_tab(widget, session, 2)
    widget._thread = None

    widget._start.click()

    assert widget.groups == []


def test_shutdown_is_safe_without_a_multi_run(tab):
    widget, _ = tab

    assert widget.shutdown()


# --- Dans l'écran d'exécution -----------------------------------------------

@pytest.fixture
def step(qt_app, session):
    from pokemon_mosaic.ui.run_step import RunStep

    widget = RunStep(session)
    widget.resize(900, 600)
    return widget, session


def test_the_run_step_has_two_tabs(step):
    widget, _ = step

    assert [widget._tabs.tabText(i) for i in range(widget._tabs.count())] == [
        "Lancement", "Multi-lancement"]
    assert widget._tabs.widget(1) is widget._multi


def test_a_multi_run_blocks_the_single_run(step, capture_multi_runs, monkeypatch):
    """Un seul calcul à la fois : deux fils côte à côte surchargeraient la
    machine."""
    from pokemon_mosaic.ui import run_step as module

    widget, _ = step
    lances = []
    monkeypatch.setattr(module, "start_run",
                        lambda *a, **k: lances.append(1) or (object(), object()))

    widget._multi._start.click()

    assert not widget._start.isEnabled()
    assert not widget._welcome_start.isEnabled()
    widget.start_run()
    assert lances == []


def test_a_single_run_blocks_the_multi_run(step, capture_multi_runs, monkeypatch):
    from pokemon_mosaic.ui import run_step as module

    widget, _ = step
    monkeypatch.setattr(module, "start_run",
                        lambda *a, **k: (object(), object()))

    widget.start_run()

    assert not widget._multi._start.isEnabled()
    widget._multi.start()
    assert capture_multi_runs == []


def test_resuming_is_refused_while_a_multi_run_turns(step, capture_multi_runs):
    """« Repartir de ce cliché » tronquait la timeline puis se voyait refuser
    le lancement : les clichés suivants étaient perdus pour rien."""
    from pokemon_mosaic.ui.runner import RunWorker

    widget, session = step
    # Ce que `start_run` pose avant de lancer : la reprise en dépend.
    widget._run_signature = widget._signature()
    worker = RunWorker(session, RunControl())
    worker.started_run.connect(widget._on_started)
    worker.snapshot.connect(widget._on_snapshot)
    worker.finished_run.connect(widget._on_finished)
    worker.run()
    longueur = len(widget._timeline)
    widget._slider.setValue(0)
    assert widget.can_resume()

    widget._multi._start.click()

    assert not widget.can_resume()
    assert not widget._resume.isEnabled() and not widget._extend.isEnabled()
    widget._resume_from_snapshot()
    assert len(widget._timeline) == longueur


def test_the_single_run_comes_back_after_the_multi_run(step, capture_multi_runs):
    widget, _ = step
    widget._multi._start.click()

    widget._multi._on_finished_all(0)

    assert widget._start.isEnabled() and widget._multi._start.isEnabled()
