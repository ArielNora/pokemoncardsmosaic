"""Tests du recuit simulé, des seuils d'arrêt et de la timeline."""

import random
from itertools import pairwise

import numpy as np
import pytest
from test_scoring import make_cards

from pokemon_mosaic.annealing import Annealing
from pokemon_mosaic.optimize import (
    StopConditions,
    build_initial_grid,
    optimize_grid,
)
from pokemon_mosaic.scoring import EdgeDistances, grid_score
from pokemon_mosaic.timeline import Timeline

# --- Recuit ---------------------------------------------------------------

def test_annealing_rejects_impossible_settings():
    with pytest.raises(ValueError, match="initial_acceptance"):
        Annealing(initial_acceptance=1.0)
    with pytest.raises(ValueError, match="final_ratio"):
        Annealing(final_ratio=0.0)


def test_improving_moves_are_always_accepted():
    """Quelle que soit la température, un coup qui améliore passe toujours."""
    annealing = Annealing()
    rng = random.Random(0)
    assert annealing.accepts(-10.0, temperature=0.001, rng=rng)
    assert annealing.accepts(0.0, temperature=0.0, rng=rng)


def test_worsening_moves_are_refused_at_zero_temperature():
    """À température nulle, le recuit redevient une descente stricte."""
    assert not Annealing().accepts(1.0, temperature=0.0, rng=random.Random(0))


def test_acceptance_probability_follows_the_temperature():
    """Un même coup dégradant passe plus souvent quand il fait plus chaud."""
    annealing = Annealing()
    delta = 10.0
    rates = []
    for temperature in (1.0, 10.0, 100.0):
        rng = random.Random(0)
        passed = sum(annealing.accepts(delta, temperature, rng) for _ in range(2000))
        rates.append(passed / 2000)
    assert rates[0] < rates[1] < rates[2]


def test_temperature_decreases_to_the_final_ratio():
    annealing = Annealing(final_ratio=0.01)
    assert annealing.temperature_at(0.0, 100.0) == pytest.approx(100.0)
    assert annealing.temperature_at(1.0, 100.0) == pytest.approx(1.0)
    assert annealing.temperature_at(0.5, 100.0) == pytest.approx(10.0)


def test_calibration_scales_with_the_data():
    """La température déduite doit suivre l'ampleur réelle des dégradations."""
    small = make_cards(30, seed=1)
    for card in small:
        for side in ("top", "bottom", "left", "right"):
            setattr(card, side, getattr(card, side) / 100)

    grid = np.arange(30).reshape(5, 6)
    t_small = Annealing().calibrate(grid, EdgeDistances(small), random.Random(0))
    t_large = Annealing().calibrate(
        grid, EdgeDistances(make_cards(30, seed=1)), random.Random(0)
    )
    assert t_large > t_small * 10


def test_annealing_returns_the_best_grid_seen():
    """L'état final peut être moins bon qu'un état traversé : c'est le meilleur qui compte."""
    cards = make_cards(40, seed=5)
    distances = EdgeDistances(cards)
    grid = np.arange(40).reshape(5, 8)
    result = optimize_grid(
        grid, distances, iterations=20000, rng=random.Random(0),
        annealing=Annealing(initial_acceptance=0.6),
    )
    assert grid_score(grid, distances) == pytest.approx(result.final_score)
    assert result.final_score <= result.initial_score


def test_annealing_beats_strict_descent_on_a_long_run():
    """Le plateau de la descente stricte est un minimum local ; le recuit en sort."""
    scores = {}
    for annealing in (None, Annealing(initial_acceptance=0.5)):
        cards = make_cards(60, seed=11)
        distances = EdgeDistances(cards)
        grid = np.arange(60).reshape(6, 10)
        result = optimize_grid(
            grid, distances, iterations=60000, rng=random.Random(3), annealing=annealing
        )
        scores[annealing is not None] = result.final_score
    assert scores[True] < scores[False]


# --- Seuils d'arrêt -------------------------------------------------------

def test_stop_on_target_score():
    cards = make_cards(40)
    distances = EdgeDistances(cards)
    grid = np.arange(40).reshape(5, 8)
    target = grid_score(grid, distances) * 0.9
    result = optimize_grid(
        grid, distances, iterations=500000, rng=random.Random(0),
        stop=StopConditions(target_score=target),
    )
    assert result.stopped_by == "score atteint"
    assert result.attempted < 500000


def test_stop_on_stagnation():
    cards = make_cards(30)
    distances = EdgeDistances(cards)
    grid = np.arange(30).reshape(5, 6)
    result = optimize_grid(
        grid, distances, iterations=500000, rng=random.Random(0),
        stop=StopConditions(stagnation_iterations=5000),
    )
    assert result.stopped_by == "stagnation"
    assert result.attempted < 500000


def test_stop_on_time_budget():
    cards = make_cards(40)
    distances = EdgeDistances(cards)
    grid = np.arange(40).reshape(5, 8)
    result = optimize_grid(
        grid, distances, iterations=10_000_000, rng=random.Random(0),
        stop=StopConditions(time_budget=0.2),
    )
    assert result.stopped_by == "budget de temps"
    assert result.elapsed < 2.0


def test_running_to_the_end_reports_it():
    cards = make_cards(30)
    distances = EdgeDistances(cards)
    grid = np.arange(30).reshape(5, 6)
    result = optimize_grid(grid, distances, iterations=2000, rng=random.Random(0))
    assert result.stopped_by == "itérations épuisées"
    assert result.attempted == 2000


# --- Timeline -------------------------------------------------------------

def test_timeline_records_by_accepted_swaps_not_attempts():
    cards = make_cards(40)
    distances = EdgeDistances(cards)
    grid = np.arange(40).reshape(5, 8)
    timeline = Timeline(every=5)
    result = optimize_grid(
        grid, distances, iterations=20000, rng=random.Random(0), timeline=timeline
    )
    # Un cliché initial, un tous les 5 échanges retenus, puis un cliché final imposé.
    assert len(timeline) == pytest.approx(2 + result.accepted // 5, abs=1)
    # Le dernier intervalle est libre : le cliché final est pris quoi qu'il arrive.
    gaps = [b.accepted - a.accepted for a, b in zip(timeline, list(timeline)[1:-1], strict=False)]
    assert all(gap >= 5 for gap in gaps)


def test_snapshots_are_independent_copies():
    """La grille continue d'être modifiée sur place : les clichés doivent être figés."""
    cards = make_cards(30)
    distances = EdgeDistances(cards)
    grid = np.arange(30).reshape(5, 6)
    timeline = Timeline(every=1)
    optimize_grid(grid, distances, iterations=3000, rng=random.Random(0), timeline=timeline)
    assert not np.array_equal(timeline[0].grid, grid)


def test_snapshots_stay_tiny():
    """Un cliché est une grille d'indices, pas une image."""
    cards = make_cards(289)
    distances = EdgeDistances(cards)
    grid = np.arange(289).reshape(17, 17)
    timeline = Timeline(every=1)
    optimize_grid(grid, distances, iterations=5000, rng=random.Random(0), timeline=timeline)
    assert timeline[0].nbytes == 289 * 2  # int16
    assert timeline.nbytes < 1024 * 1024  # bien moins d'un mégaoctet au total


def test_timeline_score_matches_the_recorded_grid():
    """Le score porté par un cliché doit être celui de la grille qu'il contient."""
    cards = make_cards(40)
    distances = EdgeDistances(cards)
    grid = np.arange(40).reshape(5, 8)
    timeline = Timeline(every=20)
    optimize_grid(grid, distances, iterations=20000, rng=random.Random(0), timeline=timeline)
    for snapshot in timeline:
        assert grid_score(snapshot.grid.astype(int), distances) == pytest.approx(
            snapshot.score, rel=1e-9
        )


def test_timeline_best_is_not_always_the_last():
    cards = make_cards(40)
    distances = EdgeDistances(cards)
    grid = np.arange(40).reshape(5, 8)
    timeline = Timeline(every=3)
    optimize_grid(
        grid, distances, iterations=20000, rng=random.Random(0), timeline=timeline,
        annealing=Annealing(initial_acceptance=0.7),
    )
    assert timeline.best().score <= timeline[-1].score


def test_timeline_thins_out_instead_of_growing_without_bound():
    """Le recuit accepte 90x plus d'échanges : la cadence doit s'adapter seule."""
    cards = make_cards(60)
    distances = EdgeDistances(cards)
    grid = np.arange(60).reshape(6, 10)
    timeline = Timeline(every=1, max_snapshots=50)
    optimize_grid(
        grid, distances, iterations=40000, rng=random.Random(0), timeline=timeline,
        annealing=Annealing(initial_acceptance=0.7),
    )
    assert len(timeline) <= 50
    assert timeline.every > 1, "l'intervalle aurait dû doubler"


def test_thinning_keeps_the_first_and_last_snapshots():
    cards = make_cards(40)
    distances = EdgeDistances(cards)
    grid = np.arange(40).reshape(5, 8)
    timeline = Timeline(every=1, max_snapshots=20)
    result = optimize_grid(
        grid, distances, iterations=20000, rng=random.Random(0), timeline=timeline,
        annealing=Annealing(initial_acceptance=0.7),
    )
    assert timeline[0].accepted == 0
    assert timeline[-1].accepted <= result.accepted
    accepted = [s.accepted for s in timeline]
    assert accepted == sorted(accepted)


def test_thinning_keeps_snapshots_spread_over_the_whole_run():
    """Après élagage, les clichés doivent rester répartis, pas groupés au début."""
    cards = make_cards(60)
    distances = EdgeDistances(cards)
    grid = np.arange(60).reshape(6, 10)
    timeline = Timeline(every=1, max_snapshots=40)
    optimize_grid(
        grid, distances, iterations=40000, rng=random.Random(0), timeline=timeline,
        annealing=Annealing(initial_acceptance=0.7),
    )
    # Le cliché final est imposé et peut suivre de près le précédent : on juge la
    # régularité sur le corps de la timeline, pas sur ce dernier point.
    body = list(timeline)[:-1]
    gaps = [b.accepted - a.accepted for a, b in pairwise(body)]
    assert max(gaps) <= 3 * min(gaps), f"répartition trop irrégulière : {gaps}"


def test_timeline_always_ends_on_the_returned_grid():
    """Le dernier cliché doit être l'état effectivement retenu.

    Sans cliché final imposé, le recuit laisse la timeline s'arrêter bien avant la
    fin : il accepte beaucoup à chaud et presque plus à froid, donc les derniers
    échanges n'atteignent jamais le seuil de cadence — et l'image que l'utilisateur
    voudrait exporter serait absente.
    """
    cards = make_cards(60)
    distances = EdgeDistances(cards)
    grid = np.arange(60).reshape(6, 10)
    timeline = Timeline(every=5, max_snapshots=30)
    result = optimize_grid(
        grid, distances, iterations=40000, rng=random.Random(0), timeline=timeline,
        annealing=Annealing(initial_acceptance=0.7),
    )
    assert timeline[-1].score == pytest.approx(result.final_score)
    np.testing.assert_array_equal(timeline[-1].grid.astype(int), grid)
    assert timeline.best().score == pytest.approx(result.final_score)


def test_max_iterations_is_the_real_bound():
    """Le champ était documenté comme la borne dure mais n'était jamais testé :
    la boucle bornait sur le paramètre `iterations`, et tout appelant ne
    remplissant que StopConditions tournait bien au-delà de sa demande."""
    cards = make_cards(30)
    distances = EdgeDistances(cards)
    grid = np.arange(30).reshape(5, 6)
    result = optimize_grid(
        grid, distances, iterations=5000, rng=random.Random(0),
        stop=StopConditions(max_iterations=10),
    )
    assert result.attempted == 10


def test_iterations_still_works_without_stop_conditions():
    cards = make_cards(30)
    distances = EdgeDistances(cards)
    grid = np.arange(30).reshape(5, 6)
    result = optimize_grid(grid, distances, iterations=250, rng=random.Random(0))
    assert result.attempted == 250


def test_cooling_follows_the_real_bound():
    """La température doit atteindre son plancher à la fin réelle du calcul,
    pas à celle d'un compteur inutilisé."""
    cards = make_cards(40)
    distances = EdgeDistances(cards)
    grid = np.arange(40).reshape(5, 8)
    result = optimize_grid(
        grid, distances, iterations=100000, rng=random.Random(0),
        annealing=Annealing(initial_acceptance=0.5),
        stop=StopConditions(max_iterations=3000),
    )
    assert result.attempted == 3000


# --- Prolongation d'une timeline -------------------------------------------

def test_truncate_after_keeps_the_chosen_snapshot():
    timeline = Timeline(every=1)
    grid = np.arange(4).reshape(2, 2)
    for i in range(5):
        timeline.record(grid, i, i, float(i), 0.0)
    timeline.truncate_after(2)
    assert [s.iteration for s in timeline] == [0, 1, 2]


def test_truncate_after_refuses_an_index_outside_the_timeline():
    timeline = Timeline(every=1)
    timeline.record(np.arange(4).reshape(2, 2), 0, 0, 0.0, 0.0)
    with pytest.raises(IndexError, match="hors de la timeline"):
        timeline.truncate_after(3)


def test_a_fresh_timeline_starts_at_iteration_zero():
    cards = make_cards(12, seed=3)
    distances = EdgeDistances(cards)
    timeline = Timeline(every=5)
    optimize_grid(build_initial_grid(cards, shape=(4, 3)), distances,
                  iterations=500, timeline=timeline, rng=random.Random(0))
    assert timeline[0].iteration == 0 and timeline[0].accepted == 0


def test_continuing_a_timeline_carries_the_counters_forward():
    """Sans report des compteurs, les itérations reviendraient à zéro au milieu
    de la timeline, et la cadence — comptée en échanges retenus — n'enregistrerait
    plus rien avant d'avoir rattrapé le seuil hérité."""
    cards = make_cards(12, seed=3)
    distances = EdgeDistances(cards)
    timeline = Timeline(every=5, max_snapshots=None)
    grid = build_initial_grid(cards, shape=(4, 3))
    optimize_grid(grid, distances, iterations=500, timeline=timeline,
                  rng=random.Random(0))
    first_pass = list(timeline)
    end_of_first = first_pass[-1]

    optimize_grid(grid.copy(), distances, iterations=500, timeline=timeline,
                  rng=random.Random(1))

    # Les clichés d'origine sont intacts, les nouveaux s'ajoutent à la suite.
    assert list(timeline)[: len(first_pass)] == first_pass
    assert len(timeline) > len(first_pass)
    iterations = [s.iteration for s in timeline]
    assert iterations == sorted(iterations), "les itérations doivent rester croissantes"
    assert timeline[-1].iteration > end_of_first.iteration
    assert timeline[-1].accepted >= end_of_first.accepted


def test_continuing_records_no_duplicate_starting_snapshot():
    """Le dernier cliché de la timeline **est** l'état de départ de la reprise."""
    cards = make_cards(12, seed=3)
    distances = EdgeDistances(cards)
    timeline = Timeline(every=1_000_000, max_snapshots=None)
    grid = build_initial_grid(cards, shape=(4, 3))
    optimize_grid(grid, distances, iterations=100, timeline=timeline,
                  rng=random.Random(0))
    before = len(timeline)

    optimize_grid(grid.copy(), distances, iterations=100, timeline=timeline,
                  rng=random.Random(1))
    # Une cadence hors d'atteinte : seul le cliché final imposé s'ajoute.
    assert len(timeline) == before + 1
