"""Tests de la vue d'exécution et de son travailleur."""

import numpy as np
import pytest

from pokemon_mosaic.cards import Card, CardSet
from pokemon_mosaic.control import RunControl
from pokemon_mosaic.links import Link


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
    s.set_algorithm(iterations=4000, snapshot_every=2, use_annealing=False)
    return s


def run_synchronously(session, previous_grid=None):
    """Exécute le travailleur dans le fil courant : déterministe et sans QThread."""
    from pokemon_mosaic.ui.runner import RunWorker

    control = RunControl()
    worker = RunWorker(session, control, previous_grid)
    seen = {"started": [], "snapshots": [], "result": [], "failed": []}
    worker.started_run.connect(lambda c, t: seen["started"].append((c, t)))
    worker.snapshot.connect(seen["snapshots"].append)
    worker.finished_run.connect(seen["result"].append)
    worker.failed.connect(seen["failed"].append)
    worker.run()
    return seen


# --- Le travailleur --------------------------------------------------------

def test_a_run_produces_snapshots_and_a_result(session):
    seen = run_synchronously(session)
    assert seen["failed"] == []
    assert len(seen["snapshots"]) > 1
    assert seen["result"][0].attempted == 4000


def test_the_run_only_uses_the_selected_cards(session):
    session.set_excluded([0, 1, 2, 3, 4], True)
    session.set_layout(cols=5, rows=3)
    seen = run_synchronously(session)
    cards, _ = seen["started"][0]
    assert len(cards) == 15
    assert [card.index for card in cards] == list(range(15))


def test_links_are_translated_for_the_selection(session):
    """Le travailleur doit passer par select_cards : subset seul laisserait les
    liens désigner d'autres cartes après renumérotation."""
    session.add_link(Link(cards=(10, 11)))
    session.set_excluded([0, 1], True)
    session.set_layout(cols=6, rows=3)
    seen = run_synchronously(session)

    cards, timeline = seen["started"][0]
    positions = {}
    final = timeline[-1].grid
    for row in range(final.shape[0]):
        for col in range(final.shape[1]):
            positions[int(final[row, col])] = (row, col)
    # Les cartes d'origine 10 et 11 sont devenues 8 et 9 après renumérotation.
    linked = [index for index, card in enumerate(cards)
              if card.source_index in (10, 11)]
    (r_a, c_a), (r_b, c_b) = (positions[i] for i in linked)
    assert r_a == r_b and abs(c_b - c_a) == 1


def test_a_run_without_cards_fails_cleanly(qt_app):
    from pokemon_mosaic.ui.session import Session

    seen = run_synchronously(Session())
    assert seen["failed"] and "Aucune carte" in seen["failed"][0]
    assert seen["result"] == []


def test_a_run_can_start_from_a_given_grid(session):
    """C'est ce qui permet de prolonger un calcul ou de repartir d'un cliché."""
    first = run_synchronously(session)
    final = first["started"][0][1][-1].grid.astype(int)

    second = run_synchronously(session, previous_grid=final)
    start = second["started"][0][1][0].grid.astype(int)
    np.testing.assert_array_equal(start, final)


def test_empty_cells_stay_put_across_the_run(session):
    from pokemon_mosaic.scoring import EMPTY

    session.set_layout(cols=6, rows=4)      # 24 cases pour 20 cartes
    seen = run_synchronously(session)
    timeline = seen["started"][0][1]
    first = {tuple(cell) for cell in np.argwhere(timeline[0].grid == EMPTY)}
    last = {tuple(cell) for cell in np.argwhere(timeline[-1].grid == EMPTY)}
    assert first == last and len(first) == 4


# --- L'écran ---------------------------------------------------------------

@pytest.fixture
def step(qt_app, session):
    from pokemon_mosaic.ui.run_step import RunStep

    widget = RunStep(session)
    widget.resize(700, 500)
    return widget, session


def feed(step_widget, session):
    """Rejoue une exécution complète dans l'écran, sans fil de fond."""
    seen = run_synchronously(session)
    cards, timeline = seen["started"][0]
    step_widget._on_started(cards, timeline)
    for snapshot in timeline:
        step_widget._on_snapshot(snapshot)
    return timeline


def test_the_slider_follows_the_latest_snapshot(step):
    widget, session = step
    timeline = feed(widget, session)
    assert widget._slider.value() == len(timeline) - 1
    assert widget._following


def test_moving_the_slider_stops_following(step):
    """Sinon l'image échapperait à l'utilisateur pendant qu'il examine un état."""
    widget, session = step
    feed(widget, session)
    widget._slider.setValue(1)
    assert not widget._following

    before = widget._slider.value()
    widget._on_snapshot(widget._timeline[-1])
    assert widget._slider.value() == before


def test_going_to_the_latest_resumes_following(step):
    widget, session = step
    timeline = feed(widget, session)
    widget._slider.setValue(1)
    widget._go_to_latest()
    assert widget._following
    assert widget._slider.value() == len(timeline) - 1


def test_the_position_label_counts_from_one(step):
    widget, session = step
    timeline = feed(widget, session)
    assert f"{len(timeline)}" in widget._position.text()
    widget._slider.setValue(0)
    assert widget._position.text().startswith("cliché 1 ")


def test_a_snapshot_is_rendered(step):
    widget, session = step
    feed(widget, session)
    widget._flush_render()          # le rendu est différé, à cadence bornée
    assert widget._image.pixmap() is not None
    assert not widget._image.pixmap().isNull()


def test_the_empty_colour_is_used_in_the_preview(step):
    widget, session = step
    session.set_layout(cols=6, rows=4)
    session.set_algorithm(empty_colour=(255, 0, 0))
    feed(widget, session)
    image = widget._render(widget._timeline[-1].grid)
    colours = {image.pixelColor(x, y).getRgb()[:3]
               for x in range(0, image.width(), 7)
               for y in range(0, image.height(), 7)}
    assert any(r > 200 and g < 60 and b < 60 for r, g, b in colours)


def test_shutdown_is_safe_without_a_run(step):
    widget, _ = step
    widget.shutdown()


def test_stop_and_pause_do_nothing_before_a_run(step):
    widget, _ = step
    widget._request_stop()
    widget._toggle_pause()      # ne doit pas lever


# --- Non-régressions de la revue -------------------------------------------

def test_clicking_start_passes_no_grid(step):
    """`clicked` transmet l'état coché du bouton : branché directement, il
    faisait recevoir False à previous_grid, et `.copy()` sur un booléen faisait
    échouer la préparation sans qu'aucun signal ne soit émis — interface figée.
    """
    widget, _ = step
    received = {}
    widget.start_run = lambda previous_grid=None: received.update(arg=previous_grid)
    widget._start.click()
    assert received["arg"] is None


def test_an_unexpected_preparation_failure_is_reported(session):
    """Sans cela, l'exception s'échappe du slot : ni finished_run ni failed n'est
    émis, thread.quit() n'est jamais appelé, et l'interface reste bloquée."""
    from pokemon_mosaic.ui.runner import RunWorker

    worker = RunWorker(session, RunControl(), previous_grid=False)
    failures = []
    worker.failed.connect(failures.append)
    worker.run()
    assert failures, "aucun échec remonté"
    assert "copy" in failures[0]


def test_a_run_that_fails_leaves_the_screen_usable(step):
    widget, _ = step
    widget._on_failed("quelque chose a cassé")
    assert widget._start.isEnabled()
    assert not widget._pause.isEnabled() and not widget._stop.isEnabled()


def test_pause_and_resume_drive_the_control_and_the_label(step):
    """La pause et la reprise passent par le contrôle, et le libellé suit.

    Test déterministe : le fait que la pause fige réellement la boucle est
    couvert par test_control.py, sur le vrai mécanisme et sans dépendre du
    minutage d'un fil de fond.
    """
    widget, _ = step
    widget._control = RunControl()
    widget._update_buttons(running=True)
    assert widget._pause.text() == "Pause"

    widget._pause.click()
    assert widget._control.paused
    assert widget._pause.text() == "Reprendre"

    widget._pause.click()
    assert not widget._control.paused
    assert widget._pause.text() == "Pause"


def test_stopping_asks_the_control_to_stop(step):
    widget, _ = step
    widget._control = RunControl()
    widget._update_buttons(running=True)
    widget._stop.click()
    assert widget._control.stop_requested


def test_shutdown_stops_a_real_background_run(qt_app, session):
    """Le seul test qui lance vraiment un fil : il vérifie qu'on sait l'arrêter,
    faute de quoi Qt abandonne le processus à la destruction du widget."""
    from PySide6.QtCore import QDeadlineTimer, QEventLoop

    from pokemon_mosaic.ui.run_step import RunStep

    session.set_algorithm(iterations=50_000_000, snapshot_every=5)
    widget = RunStep(session)
    widget._start.click()

    loop, deadline = QEventLoop(), QDeadlineTimer(500)
    while not deadline.hasExpired() and not widget._timeline:
        loop.processEvents(QEventLoop.AllEvents, 10)
    assert widget._timeline is not None, "le calcul n'a pas démarré"

    widget.shutdown()
    assert widget._thread is None, "le fil n'a pas été arrêté"


def test_the_preview_render_is_throttled(step):
    """Rendre un cliché coûte 56 ms sur une grille 17×17. Un rendu par cliché
    demanderait 3,9 s de fil principal pour 1,6 s de calcul : l'interface
    accumulerait du retard et le résultat n'apparaîtrait que bien après la fin.
    """
    widget, session = step
    timeline = feed(widget, session)
    assert len(timeline) > 3

    renders = []
    widget._render = lambda grid: renders.append(grid) or None
    for snapshot in timeline:
        widget._on_snapshot(snapshot)
    assert renders == [], "aucun rendu ne doit avoir lieu hors de la cadence"

    widget._flush_render()
    assert len(renders) == 1, "un seul rendu, celui du dernier état demandé"


def test_the_flush_renders_the_latest_requested_state(step):
    widget, session = step
    timeline = feed(widget, session)
    widget._slider.setValue(0)
    widget._slider.setValue(2)
    rendered = []
    widget._render = lambda grid: rendered.append(grid) or None
    widget._flush_render()
    assert len(rendered) == 1
    np.testing.assert_array_equal(rendered[0], timeline[2].grid)


def test_flushing_without_a_run_is_harmless(step):
    widget, _ = step
    widget._flush_render()


def test_the_stop_reason_is_translated(qt_app, session):
    """Le cœur ne dépend pas de Qt et renvoie ses libellés en français : sans
    traduction ici, l'interface anglaise affichait « stopped: itérations
    épuisées »."""
    from pokemon_mosaic.optimize import StopReason
    from pokemon_mosaic.ui.i18n import TRANSLATIONS_DIR, LanguageManager
    from pokemon_mosaic.ui.run_step import RunStep

    if not (TRANSLATIONS_DIR / "pokemon_mosaic_en.qm").exists():
        pytest.skip("traductions non compilées")

    widget = RunStep(session)
    assert widget._stop_reason(StopReason.EXHAUSTED) == "itérations épuisées"

    manager = LanguageManager(qt_app)
    try:
        manager.set_language("en")
        assert widget._stop_reason(StopReason.EXHAUSTED) == "iterations exhausted"
        assert widget._stop_reason(StopReason.REQUESTED) == "stopped by user"
    finally:
        manager.set_language("fr")


def test_an_unknown_stop_reason_is_passed_through(qt_app, session):
    from pokemon_mosaic.ui.run_step import RunStep

    assert RunStep(session)._stop_reason("quelque chose d'inédit") == \
        "quelque chose d'inédit"
