"""Tests des réglages d'algorithme et de leurs projections chiffrées."""

import pytest
from test_ui_session import card_set_in

from pokemon_mosaic.ui.estimates import (
    estimated_gain,
    estimated_seconds,
    estimated_snapshots,
    format_duration,
)


@pytest.fixture
def session(qt_app, tmp_path):
    from pokemon_mosaic.ui.session import Session

    s = Session()
    s.set_cards(card_set_in(tmp_path, {"a": [str(i) for i in range(6)]}), str(tmp_path))
    return s


# --- Réglages --------------------------------------------------------------

def test_unknown_setting_is_refused(session):
    with pytest.raises(AttributeError, match="Réglage inconnu"):
        session.set_algorithm(vitesse_lumiere=3)


def test_setting_change_emits_once(session):
    calls = []
    session.algorithm_changed.connect(lambda: calls.append(1))
    session.set_algorithm(iterations=500, snapshot_every=5)
    assert len(calls) == 1


def test_setting_the_same_values_emits_nothing(session):
    session.set_algorithm(iterations=500)
    calls = []
    session.algorithm_changed.connect(lambda: calls.append(1))
    session.set_algorithm(iterations=500)
    assert calls == []


def test_strip_size_recomputes_the_card_signatures(qt_app, tmp_path):
    """Sans recalcul, le score reposerait sur des mesures périmées.

    La vignette porte un dégradé vertical : une bande fine ne voit que le haut,
    une bande large moyenne bien plus bas. Sur une image unie, le réglage n'aurait
    aucun effet mesurable et le test ne prouverait rien.
    """
    import numpy as np

    from pokemon_mosaic.ui.session import Session

    session = Session()
    card_set = card_set_in(tmp_path, {"a": ["0"]})
    gradient = np.linspace(0, 255, 20, dtype=np.uint8)
    card_set.cards[0].thumbnail = np.repeat(
        gradient[:, None, None], 3, axis=2).repeat(10, axis=1)
    session.set_cards(card_set, str(tmp_path))
    session.set_algorithm(strip_size=0.1)

    thin = session.card_set[0].top.copy()
    session.set_algorithm(strip_size=0.5)
    thick = session.card_set[0].top
    assert thick.mean() > thin.mean() + 10


# --- Traduction vers le cœur ----------------------------------------------

def test_annealing_is_off_when_not_requested(session):
    session.set_algorithm(use_annealing=False)
    assert session.annealing() is None


def test_annealing_carries_the_acceptance(session):
    session.set_algorithm(use_annealing=True, acceptance=0.3)
    assert session.annealing().initial_acceptance == 0.3


def test_unchecked_thresholds_are_not_applied(session):
    session.set_algorithm(stagnation_iterations=99, time_budget=5.0, target_score=1.0)
    stop = session.stop_conditions()
    assert stop.stagnation_iterations is None
    assert stop.time_budget is None
    assert stop.target_score is None


def test_checked_thresholds_are_applied(session):
    session.set_algorithm(stop_on_stagnation=True, stagnation_iterations=99,
                          stop_on_time=True, time_budget=5.0,
                          stop_on_score=True, target_score=1.0)
    stop = session.stop_conditions()
    assert stop.stagnation_iterations == 99
    assert stop.time_budget == 5.0
    assert stop.target_score == 1.0


def test_unchecking_keeps_the_value_for_later(session):
    """Décocher puis recocher ne doit pas obliger à ressaisir la valeur."""
    session.set_algorithm(stop_on_time=True, time_budget=42.0)
    session.set_algorithm(stop_on_time=False)
    assert session.time_budget == 42.0
    session.set_algorithm(stop_on_time=True)
    assert session.stop_conditions().time_budget == 42.0


def test_iterations_reach_the_stop_conditions(session):
    session.set_algorithm(iterations=1234)
    assert session.stop_conditions().max_iterations == 1234


# --- Projections -----------------------------------------------------------

def test_duration_grows_with_the_iterations():
    assert estimated_seconds(2_000_000, True) > estimated_seconds(1_000_000, True)


def test_duration_matches_the_measured_rate():
    """1 M d'itérations prenaient 8,3 s au recuit sur le jeu de référence."""
    assert estimated_seconds(1_000_000, annealing=True) == pytest.approx(8.3, abs=1.0)


def test_gain_matches_the_measured_points():
    assert estimated_gain(1_000_000, annealing=True) == pytest.approx(0.675, abs=0.01)
    assert estimated_gain(1_000_000, annealing=False) == pytest.approx(0.610, abs=0.01)
    assert estimated_gain(200_000, annealing=True) == pytest.approx(0.648, abs=0.01)


def test_gain_never_decreases_with_more_iterations():
    values = [estimated_gain(n, True) for n in (1_000, 50_000, 200_000, 1_000_000)]
    assert values == sorted(values)


def test_gain_plateaus_beyond_the_measurements():
    """La courbe est un plateau : promettre mieux serait trompeur."""
    assert estimated_gain(50_000_000, True) == estimated_gain(1_000_000, True)


def test_annealing_is_announced_as_better():
    for iterations in (50_000, 200_000, 1_000_000):
        assert estimated_gain(iterations, True) > estimated_gain(iterations, False)


@pytest.mark.parametrize("iterations,every,annealing,actual", [
    (200_000, 10, False, 13),      # 60 cartes, descente stricte
    (1_000_000, 10, True, 68),     # 280 cartes, recuit
    (500_000, 10, True, 68),
])
def test_snapshot_range_brackets_the_measured_runs(iterations, every, annealing, actual):
    """Une valeur unique annonçait 61 clichés là où la timeline en produisait 13 :
    le taux d'acceptation varie d'un facteur cinq selon le jeu et l'avancement."""
    low, high = estimated_snapshots(iterations, every, annealing)
    assert low <= actual <= high


def test_snapshot_range_accounts_for_the_thinning():
    """Au-delà du plafond, la timeline jette un cliché sur deux : le compte final
    se situe entre la moitié et le plafond."""
    low, high = estimated_snapshots(1_000_000, every=10, annealing=True, maximum=70)
    assert (low, high) == (36, 70)


def test_snapshot_range_is_uncapped_on_request():
    low, high = estimated_snapshots(1_000_000, every=10, annealing=True, maximum=None)
    assert low > 1000 and high >= low


def test_snapshot_range_shrinks_when_the_cadence_grows():
    dense = estimated_snapshots(100_000, every=1, annealing=False, maximum=None)
    sparse = estimated_snapshots(100_000, every=50, annealing=False, maximum=None)
    assert dense[1] > sparse[1]


def test_snapshot_range_is_ordered():
    low, high = estimated_snapshots(300_000, every=10, annealing=False)
    assert low <= high


def test_snapshot_range_handles_a_zero_cadence():
    assert estimated_snapshots(1000, every=0, annealing=True) == (0, 0)


@pytest.mark.parametrize("seconds,expected", [
    (8.3, "8 s"), (59.4, "59 s"), (60, "1 min 00 s"), (605, "10 min 05 s"),
])
def test_duration_is_readable(seconds, expected):
    assert format_duration(seconds) == expected


# --- Non-régressions de la revue -------------------------------------------

def test_layout_settings_are_refused_by_set_algorithm(session):
    """Valider par hasattr acceptait set_algorithm(dpi=600) : le réglage était
    appliqué mais c'est algorithm_changed qui partait, et l'aperçu fil de fer,
    qui n'écoute que layout_changed, n'en savait jamais rien."""
    with pytest.raises(AttributeError, match="set_layout"):
        session.set_algorithm(dpi=600)
    assert session.dpi == 300


def test_qt_attributes_are_refused_by_set_algorithm(session):
    with pytest.raises(AttributeError, match="Réglage inconnu"):
        session.set_algorithm(objectName="n_importe_quoi")


def test_signatures_are_not_recomputed_when_strip_size_is_unchanged(session):
    """L'écran de réglages renvoie tous les champs d'un bloc : recalculer sur la
    seule présence de la clé coûtait 47 ms par cran de molette."""
    calls = []
    session.card_set.recalculate_features = lambda ss: calls.append(ss)
    session.set_algorithm(strip_size=session.strip_size, iterations=4321)
    assert calls == []


def test_signatures_are_recomputed_when_strip_size_changes(session):
    calls = []
    session.card_set.recalculate_features = lambda ss: calls.append(ss)
    session.set_algorithm(strip_size=0.42, iterations=4321)
    assert calls == [0.42]


def test_cards_arriving_late_use_the_current_strip_size(qt_app, tmp_path):
    """Le chargement dure ~4 s. Changer l'épaisseur pendant ce temps laissait les
    dossiers suivants sur l'ancienne valeur : le même jeu portait des signatures
    incomparables, et les distances entre les deux groupes n'avaient plus de sens.
    """
    import numpy as np

    from pokemon_mosaic.cards import Card
    from pokemon_mosaic.ui.session import Session

    def gradient_card(index):
        levels = np.linspace(0, 255, 40, dtype=np.uint8)
        thumb = np.repeat(levels[:, None, None], 3, axis=2).repeat(20, axis=1)
        card = Card(path=str(tmp_path / f"{index}.png"), index=index, thumbnail=thumb)
        card.calculate_features(0.1)
        return card

    session = Session()
    session.start_loading(str(tmp_path))
    session.append_cards([gradient_card(0), gradient_card(1)])
    session.set_algorithm(strip_size=0.5)
    session.append_cards([gradient_card(2), gradient_card(3)])

    tops = [round(float(card.top.mean()), 1) for card in session.card_set]
    assert len(set(tops)) == 1, f"signatures hétérogènes : {tops}"
