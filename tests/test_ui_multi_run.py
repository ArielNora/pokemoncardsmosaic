"""Tests du multi-lancement : plusieurs calculs enchaînés, cinq clichés gardés."""

from types import SimpleNamespace

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
    # L'interrompu ne compte pas parmi les lancements menés à leur terme.
    assert widget._progress_label.text().startswith("1 lancement(s) terminé(s).")


def test_a_failure_keeps_the_groups_already_done(tab):
    widget, session = tab
    widget._thread = object()
    widget._on_run_started(0, session.card_set, Timeline())
    # Un résultat réduit à ce que l'onglet en lit : sa raison d'arrêt.
    widget._on_run_finished(0, SimpleNamespace(stopped_by=StopReason.EXHAUSTED))

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


# --- Les groupes à la fin ---------------------------------------------------

def test_the_groups_appear_only_once_the_multi_run_ends(tab):
    """Montrés à la fin, et non au fil de l'eau : décidé par l'utilisateur."""
    widget, session = tab
    pendant = []

    feed_tab(widget, session, 3,
             snapshot=lambda _r, _s: pendant.append(len(widget._thumbs)))

    assert set(pendant) == {0}
    assert not widget._results_scroll.isHidden()
    assert sorted(widget._thumbs) == [(g, i) for g in range(3) for i in range(5)]


def test_each_group_is_titled_by_its_run(tab):
    widget, session = tab
    feed_tab(widget, session, 2)
    titres = [widget._results_grid.itemAtPosition(ligne, 0).widget().text()
              for ligne in (0, 2)]

    assert titres[0].startswith("Lancement 1") and titres[1].startswith("Lancement 2")
    assert "interrompu" not in titres[0]


def test_an_interrupted_run_says_so_in_its_title(tab):
    widget, session = tab

    def arrete(rang, _cliche):
        if rang == 1:
            widget._request_stop()

    widget._control = RunControl()
    feed_tab_with_control(widget, session, 3, widget._control, snapshot=arrete)

    assert "interrompu" in widget._group_title(widget.groups[1])
    assert "interrompu" not in widget._group_title(widget.groups[0])


def feed_tab_with_control(widget, session, count, control, **reactions):
    widget._count = count
    widget._thread = object()
    widget._update_buttons(running=True)
    handlers = {"run_started": [widget._on_run_started],
                "snapshot": [widget._on_snapshot],
                "run_finished": [widget._on_run_finished],
                "finished_all": [widget._on_finished_all],
                "failed": [widget._on_failed]}
    for nom, reaction in reactions.items():
        handlers[nom].append(reaction)
    return multi_run(session, count, control=control, **handlers)


def test_the_best_snapshot_is_chosen_at_the_end(tab):
    widget, session = tab
    feed_tab(widget, session, 3)
    _groupe, cliche = widget.selected()

    tous = [c.score for g in widget.groups for c in g.snapshots]
    assert cliche.score == min(tous)
    assert widget._thumbs[widget._selected].property("role") == "slot-current"


def test_clicking_a_thumbnail_chooses_that_snapshot(qt_app, tab):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    widget, session = tab
    widget.show()
    feed_tab(widget, session, 3)

    QTest.mouseClick(widget._thumbs[(1, 0)], Qt.LeftButton)

    groupe, cliche = widget.selected()
    assert groupe is widget.groups[1] and cliche is widget.groups[1].snapshots[0]
    roles = {cle: v.property("role") for cle, v in widget._thumbs.items()}
    assert roles[(1, 0)] == "slot-current"
    assert list(roles.values()).count("slot-current") == 1
    assert "Lancement 2, cliché 1" in widget._choice.text()


def test_keeping_puts_the_snapshot_in_a_slot_and_the_library(qt_app, session,
                                                             tmp_path):
    from pokemon_mosaic.arrangements import list_arrangements
    from pokemon_mosaic.ui.multi_run_tab import MultiRunTab

    bibliotheque = str(tmp_path / "agencements")
    widget = MultiRunTab(session, bibliotheque)
    feed_tab(widget, session, 3)
    widget.select(2, 4)
    groupe, cliche = widget.selected()

    widget._keep.click()

    garde = session.saved[0]
    assert np.array_equal(garde.grid, cliche.grid)
    assert garde.cards is groupe.cards and garde.iteration == cliche.iteration
    assert len(list_arrangements(bibliotheque)) == 1


def test_saving_writes_in_the_library_without_taking_a_slot(qt_app, session,
                                                            tmp_path):
    from pokemon_mosaic.arrangements import list_arrangements
    from pokemon_mosaic.ui.multi_run_tab import MultiRunTab

    bibliotheque = str(tmp_path / "agencements")
    widget = MultiRunTab(session, bibliotheque)
    feed_tab(widget, session, 2)
    widget.select(0, 1)
    widget._save.click()
    widget.select(1, 3)
    widget._save.click()

    assert session.saved_count() == 0
    assert len(list_arrangements(bibliotheque)) == 2


def test_keeping_stops_once_the_four_slots_are_taken(tab):
    widget, session = tab
    feed_tab(widget, session, 1)
    groupe, cliche = widget.selected()
    for _ in range(4):
        session.save_grid(cliche.grid, groupe.cards, 1, 1.0)
    messages = []
    widget.status_message.connect(messages.append)

    assert not widget._keep.isEnabled()
    widget._keep_selected()
    assert session.saved_count() == 4
    assert any("quatre cases" in message for message in messages)


def test_a_library_that_cannot_be_written_says_so(qt_app, session, tmp_path,
                                                   monkeypatch):
    from pokemon_mosaic.ui import library
    from pokemon_mosaic.ui.multi_run_tab import MultiRunTab

    widget = MultiRunTab(session, str(tmp_path / "agencements"))
    feed_tab(widget, session, 1)
    messages = []
    widget.status_message.connect(messages.append)
    monkeypatch.setattr(library, "save_arrangement",
                        lambda *a: (_ for _ in ()).throw(OSError("disque plein")))

    widget._save_selected()
    widget._keep_selected()

    assert sum("disque plein" in message for message in messages) == 2
    assert session.saved_count() == 1, "la case reste"


def test_without_a_library_saving_is_off(tab):
    widget, session = tab
    feed_tab(widget, session, 1)

    assert widget.selected() is not None
    assert not widget._save.isEnabled() and widget._keep.isEnabled()


def test_the_zoom_enlarges_the_chosen_snapshot(tab):
    widget, session = tab
    widget.show()
    feed_tab(widget, session, 1)
    avant = widget._image.pixmap().width()

    widget._zoom_in.click()

    assert widget._image.pixmap().width() > avant


def test_a_sampled_mosaic_keeps_one_pixel_out_of_step(qt_app):
    from pokemon_mosaic.ui.saved_column import mosaic_image

    jeu = card_set(4, size=(12, 16))
    grille = np.arange(4).reshape(2, 2)

    pleine = mosaic_image(grille, jeu, (0, 0, 0))
    petite = mosaic_image(grille, jeu, (0, 0, 0), step=4)

    assert (pleine.width(), pleine.height()) == (24, 32)
    assert (petite.width(), petite.height()) == (6, 8)
    assert petite.pixelColor(1, 1) == pleine.pixelColor(4, 4)


def test_the_group_thumbnails_are_not_composed_at_full_size(tab, monkeypatch):
    """Cent mosaïques à pleine taille, réduites à 72 px, figeaient l'interface
    à la fin d'un multi-lancement."""
    from pokemon_mosaic.ui import multi_run_tab as module

    widget, session = tab
    feed_tab(widget, session, 1)
    session.set_cards(card_set(20, size=(180, 250)), "/fake")
    widget.groups[0].cards = session.card_set
    tailles = []
    reel = module.mosaic_image

    def mesure(*args, **kwargs):
        image = reel(*args, **kwargs)
        tailles.append((image.width(), image.height()))
        return image

    monkeypatch.setattr(module, "mosaic_image", mesure)

    widget._show_results()

    assert len(tailles) == 5
    for largeur, hauteur in tailles:
        assert largeur <= 4 * module.THUMB.width()
        assert hauteur <= 4 * module.THUMB.height()


def test_the_title_gives_the_best_score_of_the_group(tab):
    """En recuit, le dernier cliché n'est pas toujours le meilleur."""
    from pokemon_mosaic.timeline import Snapshot
    from pokemon_mosaic.ui.multi_run_tab import RunGroup

    widget, _ = tab
    grille = np.zeros((2, 2), int)
    groupe = RunGroup(0, None, [Snapshot(grille, i, i, score, 0.0)
                                for i, score in enumerate([50.0, 30.0, 40.0])])
    groupe.result = SimpleNamespace(stopped_by=StopReason.EXHAUSTED)

    assert "meilleur score 30" in widget._group_title(groupe)


def test_the_end_says_that_a_lower_score_is_better(tab):
    """Demandé par l'utilisateur : « meilleur score 2592 » passait pour moins
    bon que 2970."""
    widget, session = tab
    feed_tab(widget, session, 2)

    assert widget._progress_label.text() == (
        "2 lancement(s) terminé(s). "
        "Plus le score est bas, plus l'agencement est optimisé.")


def press(widget, key):
    from PySide6.QtTest import QTest

    QTest.keyClick(widget, key)


@pytest.fixture
def three_groups(tab):
    """Trois groupes, le dernier réduit à deux clichés, le premier cliché
    choisi."""
    widget, session = tab
    widget.show()
    feed_tab(widget, session, 3)
    widget.groups[2].snapshots = widget.groups[2].snapshots[:2]
    widget._show_results()
    widget.select(0, 0)
    widget.setFocus()
    return widget


def test_left_and_right_move_within_the_group(qt_app, three_groups):
    from PySide6.QtCore import Qt

    widget = three_groups
    press(widget, Qt.Key_Right)
    press(widget, Qt.Key_Right)
    assert widget._selected == (0, 2)

    press(widget, Qt.Key_Left)
    assert widget._selected == (0, 1)
    assert widget._thumbs[(0, 1)].property("role") == "slot-current"


def test_up_and_down_move_between_groups(qt_app, three_groups):
    from PySide6.QtCore import Qt

    widget = three_groups
    widget.select(0, 3)
    press(widget, Qt.Key_Down)
    assert widget._selected == (1, 3)

    press(widget, Qt.Key_Up)
    assert widget._selected == (0, 3)


def test_moving_stops_at_the_edges(qt_app, three_groups):
    from PySide6.QtCore import Qt

    widget = three_groups
    press(widget, Qt.Key_Left)
    press(widget, Qt.Key_Up)
    assert widget._selected == (0, 0)

    widget.select(1, 4)
    press(widget, Qt.Key_Right)
    assert widget._selected == (1, 4)


def test_going_down_to_a_shorter_group_lands_on_its_last(qt_app, three_groups):
    """Un lancement interrompu peut n'avoir que deux clichés : descendre depuis
    le cinquième tombe sur son dernier au lieu de ne rien faire."""
    from PySide6.QtCore import Qt

    widget = three_groups
    widget.select(1, 4)

    press(widget, Qt.Key_Down)

    assert widget._selected == (2, 1)


def test_clicking_a_thumbnail_gives_the_arrows_to_the_tab(qt_app, three_groups):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    widget = three_groups
    widget.activateWindow()
    widget._count_field.setFocus()
    qt_app.processEvents()
    assert not widget.hasFocus()

    QTest.mouseClick(widget._thumbs[(1, 1)], Qt.LeftButton)
    qt_app.processEvents()

    assert widget.hasFocus(), "les flèches iraient au champ du nombre"
    press(widget, Qt.Key_Right)
    assert widget._selected == (1, 2)


def test_a_new_multi_run_forgets_the_choice(tab, capture_multi_runs):
    widget, session = tab
    feed_tab(widget, session, 2)
    widget._thread = None

    widget._start.click()

    assert widget.selected() is None and widget._thumbs == {}
    assert not widget._keep.isEnabled()


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


def test_a_slot_kept_from_the_multi_run_opens_in_its_group(step, monkeypatch):
    """La fenêtre l'aurait dit « plus dans la timeline », comme perdu, alors
    qu'il n'y a jamais été."""
    widget, session = step
    ouvertes = []
    monkeypatch.setattr(widget, "_open_saved_dialog", ouvertes.append)
    feed_tab(widget._multi, session, 2)
    widget._multi.select(1, 2)
    widget._multi._keep.click()
    widget._multi.select(0, 0)
    widget._tabs.setCurrentIndex(0)

    widget._show_saved(0)

    assert ouvertes == []
    assert widget._tabs.currentWidget() is widget._multi
    assert widget._multi._selected == (1, 2)


def test_a_slot_that_no_tab_holds_still_opens_its_window(step, monkeypatch):
    widget, session = step
    ouvertes = []
    monkeypatch.setattr(widget, "_open_saved_dialog", ouvertes.append)
    feed_tab(widget._multi, session, 1)
    groupe, cliche = widget._multi.selected()
    session.save_grid(cliche.grid[::-1].copy(), groupe.cards, 99999, 1.0)

    widget._show_saved(0)

    assert len(ouvertes) == 1


@pytest.mark.parametrize("touche", ["Key_Left", "Key_Right", "Key_Home",
                                    "Key_End", "Key_Plus", "Key_Minus"])
def test_the_multi_run_keys_never_reach_the_hidden_timeline(qt_app, step,
                                                             touche):
    """Ignorées par l'onglet, elles remontaient à l'écran d'exécution, qui
    déplaçait le curseur caché du lancement simple ou son zoom."""
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    from pokemon_mosaic.ui.runner import RunWorker

    widget, session = step
    worker = RunWorker(session, RunControl())
    worker.started_run.connect(widget._on_started)
    worker.snapshot.connect(widget._on_snapshot)
    worker.run()
    widget._slider.setValue(len(widget._timeline) // 2)
    position, zoom = widget._slider.value(), widget._zoom
    widget._tabs.setCurrentWidget(widget._multi)

    QTest.keyClick(widget._multi, getattr(Qt, touche))

    assert widget._slider.value() == position
    assert widget._zoom == zoom


def test_the_single_run_comes_back_after_the_multi_run(step, capture_multi_runs):
    widget, _ = step
    widget._multi._start.click()

    widget._multi._on_finished_all(0)

    assert widget._start.isEnabled() and widget._multi._start.isEnabled()


# --- La fenêtre ne s'élargit plus quand les groupes arrivent ----------------


def test_the_window_opens_wide_enough_for_the_groups(qt_app, session, tmp_path,
                                                     monkeypatch):
    """Les groupes du multi-lancement élargissaient la fenêtre en cours de route.

    Le minimum de la fenêtre passait de 1054 à 1434 pixels dès le premier groupe
    affiché : elle part maintenant assez large pour l'absorber. Sans écran, les
    mêmes mesures donnent 1003 et 1309, les polices n'étant pas les mêmes.
    """
    from PySide6.QtCore import QSettings

    from pokemon_mosaic.ui.i18n import LanguageManager
    from pokemon_mosaic.ui.main_window import START_SIZE, MainWindow

    reglages = QSettings(str(tmp_path / "reglages.ini"), QSettings.IniFormat)
    monkeypatch.setattr(MainWindow, "settings", staticmethod(lambda: reglages))
    fenetre = MainWindow(LanguageManager(qt_app), session,
                         presets_directory=str(tmp_path / "presets"))
    fenetre._go(2)
    onglet = fenetre._run_step._multi
    fenetre._run_step._tabs.setCurrentWidget(onglet)
    # Sans fenêtre affichée, les widgets cachés sortent du calcul de la taille
    # minimale : elle vaudrait 1003 au lieu de 1309, et le test ne mordrait pas.
    fenetre.show()

    feed_tab(onglet, session, 2)

    assert onglet.groups
    qt_app.processEvents()
    assert fenetre.minimumSizeHint().width() <= START_SIZE[0]


def test_a_narrow_screen_keeps_the_window_inside(qt_app):
    """Plus large que l'écran, la fenêtre s'ouvrirait avec ses bords dehors."""
    from PySide6.QtCore import QRect

    from pokemon_mosaic.ui.main_window import START_SIZE, start_size

    assert start_size(QRect(0, 0, 3000, 2000)) == START_SIZE
    assert start_size(QRect(0, 0, 1280, 700)) == (1280, 700)
