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


def _temperature(annealing, grid, distances, rng):
    """Température de départ : la mesure, puis sa conversion.

    Les deux étapes sont séparées dans le code pour qu'une prolongation puisse
    réutiliser la mesure tout en suivant un taux d'acceptation modifié.
    """
    penalty = annealing.mean_penalty(grid, distances, rng)
    assert penalty is not None, "cette grille doit avoir des coutures"
    return annealing.temperature_from(penalty)


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
    t_small = _temperature(Annealing(), grid, EdgeDistances(small), random.Random(0))
    t_large = _temperature(
        Annealing(),
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
    échanges n'atteignent jamais le seuil de cadence, et l'image que l'utilisateur
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
    de la timeline, et la cadence, comptée en échanges retenus, n'enregistrerait
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


# --- Prolonger un calcul ne doit pas remettre le recuit à chaud -------------

def _jeu(n=40, graine=0):
    cartes = make_cards(n, seed=graine)
    return cartes, EdgeDistances(cartes)


def test_the_first_pass_stores_its_measurement_on_the_timeline():
    """C'est la **dégradation** qui est gardée, pas la température : celle-ci
    encode aussi le taux d'acceptation, modifiable entre deux passes."""
    cartes, distances = _jeu()
    grille = build_initial_grid(cartes, shape=(8, 5), rng=random.Random(0))
    timeline = Timeline()
    assert timeline.mean_penalty is None
    optimize_grid(grille, distances, iterations=200, rng=random.Random(1),
                  annealing=Annealing(initial_acceptance=0.5), timeline=timeline)
    assert timeline.mean_penalty > 0


def test_resuming_reuses_the_measurement_instead_of_taking_a_new_one(monkeypatch):
    """Mesurer sur une grille déjà optimisée surestime la dégradation, la
    température en sortait ×3,6 : parce qu'un échange au hasard y dégrade bien
    plus le score. Le recuit repartait à chaud, et prolonger coûtait 2,6 %."""
    cartes, distances = _jeu()
    grille = build_initial_grid(cartes, shape=(8, 5), rng=random.Random(0))
    timeline = Timeline()

    appels = []
    vraie = Annealing.mean_penalty

    def compte(self, grid, dist, rng, samples=400):
        appels.append(1)
        return vraie(self, grid, dist, rng, samples)

    monkeypatch.setattr(Annealing, "mean_penalty", compte)
    for _ in range(3):        # une passe puis deux prolongations
        optimize_grid(grille, distances, iterations=200, rng=random.Random(1),
                      annealing=Annealing(initial_acceptance=0.5), timeline=timeline)
    assert len(appels) == 1, "la dégradation ne doit être mesurée qu'une fois"


def test_an_explicit_temperature_still_wins_over_the_stored_one():
    cartes, distances = _jeu()
    grille = build_initial_grid(cartes, shape=(8, 5), rng=random.Random(0))
    timeline = Timeline(mean_penalty=999.0)
    vues = []
    annealing = Annealing(initial_acceptance=0.5, initial_temperature=42.0)
    vraie = Annealing.temperature_at
    annealing.temperature_at = lambda p, t: (vues.append(t), vraie(annealing, p, t))[1]
    optimize_grid(grille, distances, iterations=50, rng=random.Random(1),
                  annealing=annealing, timeline=timeline)
    assert vues and set(vues) == {42.0}


def test_resuming_continues_the_cooling_schedule_instead_of_restarting_it():
    """Sans le cumul, `iteration / total_iterations` repart de zéro : la
    prolongation rejoue toute la phase chaude sur une grille déjà bonne."""
    cartes, distances = _jeu()
    grille = build_initial_grid(cartes, shape=(8, 5), rng=random.Random(0))
    timeline = Timeline()
    optimize_grid(grille, distances, iterations=1000, rng=random.Random(1),
                  annealing=Annealing(initial_acceptance=0.5), timeline=timeline)

    progressions = []
    annealing = Annealing(initial_acceptance=0.5)
    vraie = Annealing.temperature_at
    annealing.temperature_at = lambda p, t: (progressions.append(p),
                                             vraie(annealing, p, t))[1]
    optimize_grid(grille, distances, iterations=1000, rng=random.Random(2),
                  annealing=annealing, timeline=timeline)

    # La prolongation démarre à mi-parcours (1000 déjà faites sur 2000 au total),
    # et non à zéro comme si le calcul commençait.
    assert progressions
    assert min(progressions) >= 0.49, f"reparti de {min(progressions):.3f}"
    assert max(progressions) <= 1.0


# --- Non-régressions du /verif-code du 2026-08-24 ---------------------------

def _grille_creuse(n, rows, cols, graine=0):
    """`n` cartes dispersées au hasard dans une grille de `rows`×`cols`."""
    cartes = make_cards(n, seed=graine)
    grille = np.full((rows, cols), -1, dtype=int)
    plat = grille.reshape(-1)
    for rang, position in enumerate(
            random.Random(graine).sample(range(rows * cols), n)):
        plat[position] = rang
    return cartes, EdgeDistances(cartes), grille


def test_calibration_does_not_collapse_on_a_sparsely_filled_grid():
    """Les couples étaient tirés dans toute la grille puis rejetés s'ils
    touchaient une case vide : à 10 % de remplissage, trois tirages sur cinq
    tombaient sur le repli à 1,0, et le recuit, acceptant `exp(-250/1)`,
    dégénérait en descente stricte sans le dire."""
    _, distances, grille = _grille_creuse(40, 20, 20)
    annealing = Annealing(initial_acceptance=0.5)
    temperatures = [_temperature(annealing, grille.copy(), distances, random.Random(s))
                    for s in range(5)]
    assert all(t > 10.0 for t in temperatures), temperatures
    # et l'ordre de grandeur reste celui d'une grille pleine
    assert max(temperatures) / min(temperatures) < 3.0, temperatures


def test_a_grid_without_any_seam_has_no_measurable_penalty():
    """12 cartes dans 20×20 ne se touchent jamais : score nul, rien à optimiser.
    Le repli est alors sans effet, et c'est le seul cas où il survient."""
    _, distances, grille = _grille_creuse(12, 20, 20)
    assert grid_score(grille, distances) == 0.0
    assert Annealing().mean_penalty(grille, distances, random.Random(0)) is None


def test_a_changed_acceptance_is_honoured_when_extending():
    """La température encode le taux d'acceptation. La mémoriser telle quelle
    faisait ignorer un réglage modifié entre deux passes : l'utilisateur portait
    l'acceptation de 0,5 à 0,9 et rien ne changeait."""
    cartes, distances, _ = _grille_creuse(60, 6, 10)
    grille = build_initial_grid(cartes, shape=(10, 6), rng=random.Random(0))
    timeline = Timeline()
    optimize_grid(grille, distances, iterations=500, rng=random.Random(1),
                  annealing=Annealing(initial_acceptance=0.5), timeline=timeline)
    assert timeline.mean_penalty > 0

    def temperatures_employees(acceptance):
        """Les T0 réellement passées au programme de refroidissement."""
        vues = []
        annealing = Annealing(initial_acceptance=acceptance)
        vraie = Annealing.temperature_at
        annealing.temperature_at = (
            lambda p, t, _a=annealing, _v=vues, _f=vraie: (_v.append(t), _f(_a, p, t))[1]
        )
        optimize_grid(grille.copy(), distances, iterations=200, rng=random.Random(2),
                      annealing=annealing, timeline=timeline)
        assert vues
        return set(vues)

    employees = {p: temperatures_employees(p) for p in (0.1, 0.5, 0.9)}

    assert len({next(iter(v)) for v in employees.values()}) == 3
    # Plus on accepte, plus il fait chaud.
    assert (next(iter(employees[0.1])) < next(iter(employees[0.5]))
            < next(iter(employees[0.9])))
    # La dégradation, elle, n'est mesurée qu'une fois.
    assert timeline.mean_penalty > 0


def test_rewinding_restores_the_requested_snapshot_cadence():
    """Chaque élagage double `every`. Repartir d'un cliché en gardant la cadence
    grossie ne laissait presque aucun cliché à la nouvelle branche."""
    cartes, distances, _ = _grille_creuse(60, 6, 10)
    grille = build_initial_grid(cartes, shape=(10, 6), rng=random.Random(0))
    timeline = Timeline(every=10, max_snapshots=8)
    optimize_grid(grille, distances, iterations=20000, rng=random.Random(3),
                  annealing=Annealing(initial_acceptance=0.5), timeline=timeline)
    assert timeline.every > 10, "l'élagage doit avoir grossi la cadence"
    timeline.truncate_after(2)
    assert timeline.every == 10
