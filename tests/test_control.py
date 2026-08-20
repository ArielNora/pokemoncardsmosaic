"""Tests du contrôle d'exécution : arrêt, pause, budget de temps."""

import random
import threading
import time

import numpy as np
import pytest
from test_scoring import make_cards

from pokemon_mosaic.control import RunControl
from pokemon_mosaic.optimize import StopConditions, optimize_grid
from pokemon_mosaic.scoring import EdgeDistances


@pytest.fixture
def problem():
    cards = make_cards(40)
    return EdgeDistances(cards), np.arange(40).reshape(5, 8)


# --- Le contrôle seul ------------------------------------------------------

def test_a_fresh_control_lets_the_work_proceed():
    control = RunControl()
    assert control.checkpoint() is True
    assert not control.paused and not control.stop_requested


def test_stop_is_reported():
    control = RunControl()
    control.stop()
    assert control.checkpoint() is False


def test_stop_releases_a_pending_pause():
    """Sans cela, arrêter un calcul en pause le laisserait bloqué à attendre une
    reprise qui ne viendrait jamais."""
    control = RunControl()
    control.pause()
    control.stop()
    assert not control.paused
    assert control.checkpoint() is False


def test_pause_blocks_until_resume():
    control = RunControl()
    control.pause()
    released = threading.Event()

    def worker():
        control.checkpoint()
        released.set()

    thread = threading.Thread(target=worker)
    thread.start()
    assert not released.wait(0.15), "le calcul aurait dû rester suspendu"
    control.resume()
    assert released.wait(1.0), "la reprise n'a pas relâché le calcul"
    thread.join()


def test_paused_time_is_accounted_separately():
    control = RunControl()
    control.pause()
    threading.Timer(0.2, control.resume).start()
    control.checkpoint()
    assert control.paused_seconds >= 0.15


# --- Le contrôle dans la boucle -------------------------------------------

def test_stopping_ends_the_run_early(problem):
    distances, grid = problem
    control = RunControl()
    control.stop()
    result = optimize_grid(grid, distances, iterations=1_000_000,
                           rng=random.Random(0), control=control)
    assert result.stopped_by == "arrêt demandé"
    assert result.attempted < 1_000_000


def test_stopping_mid_run_keeps_a_usable_grid(problem):
    """Un arrêt doit rendre la meilleure grille rencontrée, pas un état bancal."""
    from pokemon_mosaic.scoring import grid_score

    distances, grid = problem
    control = RunControl()
    threading.Timer(0.05, control.stop).start()
    result = optimize_grid(grid, distances, iterations=50_000_000,
                           rng=random.Random(0), control=control)

    assert result.stopped_by == "arrêt demandé"
    assert grid_score(grid, distances) == pytest.approx(result.final_score)
    assert sorted(int(v) for v in grid.flatten()) == list(range(40))


def test_a_pause_does_not_consume_the_time_budget(problem):
    """Suspendre le calcul pour examiner la timeline ne doit pas faire expirer
    le budget de temps."""
    distances, grid = problem
    control = RunControl()
    control.pause()
    threading.Timer(0.5, control.resume).start()

    # Le calcul lui-même doit être court devant le budget, et la pause plus
    # longue que lui : c'est la seule façon d'isoler ce qu'on veut mesurer.
    result = optimize_grid(grid, distances, iterations=5_000,
                           rng=random.Random(0), control=control,
                           stop=StopConditions(max_iterations=5_000, time_budget=0.3))

    assert control.paused_seconds >= 0.3, "la pause n'a pas duré assez pour trancher"
    assert result.stopped_by == "itérations épuisées", (
        f"arrêté par « {result.stopped_by} » alors que la pause ne compte pas"
    )


def test_elapsed_excludes_the_pause(problem):
    distances, grid = problem
    control = RunControl()
    control.pause()
    threading.Timer(0.3, control.resume).start()
    started = time.monotonic()
    result = optimize_grid(grid, distances, iterations=20_000,
                           rng=random.Random(0), control=control)
    wall_clock = time.monotonic() - started
    assert result.elapsed < wall_clock - 0.2


def test_running_without_control_is_unchanged(problem):
    distances, grid = problem
    result = optimize_grid(grid, distances, iterations=2000, rng=random.Random(0))
    assert result.stopped_by == "itérations épuisées"
    assert result.attempted == 2000


# --- Non-régressions de la revue -------------------------------------------

def test_stopping_then_pausing_does_not_block():
    """checkpoint() attendait la reprise avant de regarder l'arrêt : cliquer
    Pause juste après Arrêter bloquait le fil de calcul indéfiniment, et la
    fenêtre se figeait à la fermeture puisqu'elle l'attend.
    """
    control = RunControl()
    control.stop()
    control.pause()

    returned = threading.Event()
    threading.Thread(
        target=lambda: (control.checkpoint(), returned.set()), daemon=True
    ).start()
    assert returned.wait(2.0), "checkpoint est resté bloqué"


def test_snapshot_times_match_the_reported_duration(problem):
    """Les clichés portaient le temps de pause alors que le résultat l'excluait :
    la timeline aurait affiché des horodatages dépassant la durée annoncée."""
    from pokemon_mosaic.timeline import Timeline

    distances, grid = problem
    control = RunControl()
    timeline = Timeline(every=5)
    control.pause()
    threading.Timer(0.3, control.resume).start()

    result = optimize_grid(grid, distances, iterations=20_000,
                           rng=random.Random(0), timeline=timeline, control=control)

    assert control.paused_seconds >= 0.2
    assert timeline[-1].elapsed == pytest.approx(result.elapsed, abs=0.05)
    assert all(snapshot.elapsed <= result.elapsed + 0.05 for snapshot in timeline)


def test_a_reused_control_does_not_charge_the_previous_pause(problem):
    """La prolongation prévue par la spec réutilisera le contrôle. Retrancher son
    cumul rendrait la durée de la seconde exécution négative."""
    distances, grid = problem
    control = RunControl()

    control.pause()
    threading.Timer(0.3, control.resume).start()
    optimize_grid(grid, distances, iterations=5_000, rng=random.Random(0),
                  control=control)
    assert control.paused_seconds >= 0.2

    second = optimize_grid(grid, distances, iterations=5_000, rng=random.Random(1),
                           control=control)
    assert second.elapsed > 0, f"durée négative : {second.elapsed}"
    assert second.elapsed < 0.3
