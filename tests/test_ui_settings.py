"""Tests des réglages d'algorithme et de leurs projections chiffrées.

Ils ont quitté leur écran pour l'étape des paramètres, dans un onglet unique,
« Paramètres avancés » : la métrique et son aperçu d'abord, puis une phrase par
réglage.
"""

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


# --- Écran de réglages -----------------------------------------------------

@pytest.fixture
def step(qt_app, session):
    from pokemon_mosaic.ui.algorithm_tabs import AdvancedTab

    return AdvancedTab(session), session


def test_every_advanced_setting_sits_inside_a_sentence(step):
    """⚠️ **Le texte fait partie du réglage.** « Tolérance d'acceptation : 0,30 »
    ne dit rien à personne, pas même à qui a écrit le programme six mois après.
    Chaque champ est donc précédé des mots qui disent ce qu'il complète."""
    widget, _ = step
    assert set(widget._sentences) == {
        "algorithm", "acceptance", "iterations", "stagnation", "time",
        "score", "snapshot_every"}
    for cle, (avant, _apres) in widget._sentences.items():
        assert avant.text(), f"la phrase de {cle} ne dit rien avant son champ"


def test_the_advanced_tab_opens_on_a_notice_that_nothing_is_required(step):
    """Sept réglages en tête d'écran se lisent comme sept décisions à prendre
    avant de pouvoir lancer quoi que ce soit."""
    widget, _ = step
    assert widget._notice.property("role") == "warning"
    assert widget._notice.font().bold()
    texte = widget._notice.text()
    assert "défaut" in texte and "suite" in texte
    # Il vient bien en premier dans la colonne défilante.
    colonne = widget._scroll.widget().layout()
    assert colonne.itemAt(0).widget() is widget._notice


def test_the_sentences_reuse_the_words_of_the_opening_paragraph(step):
    """Le vocabulaire s'apprend une fois : les mots en gras de l'introduction
    sont ceux que les réglages emploient plus bas."""
    widget, _ = step
    intro = widget._intro.text()
    phrases = " ".join(avant.text() + " " + apres.text()
                       for avant, apres in widget._sentences.values())
    for mot in ("itération", "échange", "métrique", "agencement"):
        assert f"<b>{mot}" in intro, f"« {mot} » n'est pas mis en avant"
        assert mot in phrases, f"« {mot} » ne resservirait à rien"


def test_the_iteration_limit_can_never_be_switched_off(step):
    """Les autres arrêts ne font que couper plus tôt : un calcul sans borne
    d'itérations n'existe pas."""
    widget, _ = step
    assert widget._always_iterations.isChecked()
    assert not widget._always_iterations.isEnabled()
    assert widget._iterations.isEnabled(), "le nombre, lui, reste modifiable"


def test_clicking_the_words_of_a_stop_line_ticks_it(step):
    """⚠️ Une case nue à côté d'un libellé n'offre que douze pixels à viser.
    Les mots de la ligne appartiennent donc à la case, et la cocher se fait en
    cliquant la phrase."""
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest

    widget, session = step
    # ⚠️ Posé, l'écran donne à la case sa vraie taille : sans cela le clic
    # tombe dans les 640 pixels par défaut d'un widget jamais disposé, et rate.
    widget.resize(900, 600)
    widget.show()
    case = widget._stop_on_time
    assert case.text(), "la phrase n'est pas portée par la case"
    assert not session.stop_on_time
    # Un point franchement dans le texte, bien après l'indicateur.
    QTest.mouseClick(case, Qt.LeftButton,
                     pos=QPoint(case.width() - 10, case.height() // 2))
    assert session.stop_on_time


def test_a_stop_line_wears_the_aura_of_its_state(step):
    """Comme « Suivant » : verte quand la ligne compte, rouge, plus discrète,
    quand elle est éteinte. Le rouge dit « pas actif », pas « cassé »."""
    from pokemon_mosaic.ui import theme

    widget, session = step
    couleurs = theme.colours(widget.palette())
    assert set(widget._glows) == {"iterations", "stagnation", "time", "score"}

    # Les itérations comptent toujours, la stagnation est décochée au départ.
    assert widget._glows["iterations"].color().name() == couleurs["ok"]
    eteinte = widget._glows["stagnation"]
    assert eteinte.color().name() == couleurs["error"]
    attente = (eteinte.color().alpha(), eteinte.blurRadius())

    session.set_algorithm(stop_on_stagnation=True)
    assert eteinte.color().name() == couleurs["ok"]
    prete = (eteinte.color().alpha(), eteinte.blurRadius())
    assert prete > attente, "le rouge doit rester le plus discret des deux"


def test_the_iteration_line_keeps_its_words_outside_the_disabled_box(step):
    """Sa case est grisée pour dire qu'on ne la décoche pas ; la phrase, elle,
    décrit le réglage actif et doit se lire normalement."""
    widget, _ = step
    avant, _apres = widget._sentences["iterations"]
    assert avant is not widget._always_iterations
    assert avant.isEnabled()


def test_the_acceptance_sentence_greys_out_in_strict_descent(step):
    """Elle promettrait sinon un comportement que le calcul n'aura pas : la
    descente stricte n'accepte jamais un échange dégradant."""
    widget, session = step
    session.set_algorithm(use_annealing=False)
    assert not any(morceau.isEnabled()
                   for morceau in widget._sentences["acceptance"])
    session.set_algorithm(use_annealing=True)
    assert all(morceau.isEnabled()
               for morceau in widget._sentences["acceptance"])


def test_the_thickness_is_the_only_one_that_shows_itself(step):
    """Elle se dessine ; les autres n'ont rien à montrer : on ne dessine pas un
    nombre d'itérations. ⚠️ Elle ouvre donc l'onglet, au-dessus des réglages
    qui s'en servent : séparée d'eux, elle obligeait à l'aller-retour pour
    comprendre l'un par l'autre."""
    widget, session = step
    widget._strip.setValue(0.25)
    assert session.strip_size == pytest.approx(0.25)
    assert widget._preview is not None
    colonne = widget._scroll.widget().layout()
    rangs = [colonne.indexOf(w) for w in (widget._metric_box,
                                          widget._settings_title)]
    assert rangs[0] < rangs[1], "la métrique passe après les réglages"


def test_the_algorithm_tab_never_blocks(step):
    """Il a une valeur qui marche partout : personne n'a à y toucher pour
    lancer un calcul."""
    assert step[0].is_valid()


def test_form_starts_from_the_session(step):
    widget, session = step
    assert widget._iterations.value() == session.iterations
    assert widget._algorithm.currentData() is session.use_annealing
    assert widget._strip.value() == pytest.approx(session.strip_size)


def test_form_follows_a_change_made_elsewhere(step):
    """Un préréglage chargé doit se voir dans les champs, pas seulement en sortie."""
    widget, session = step
    session.set_algorithm(iterations=250_000, use_annealing=False, acceptance=0.2)
    assert widget._iterations.value() == 250_000
    assert widget._algorithm.currentData() is False
    assert widget._acceptance.value() == pytest.approx(0.2)


def test_editing_a_field_reaches_the_session(step):
    widget, session = step
    widget._iterations.setValue(123_000)
    assert session.iterations == 123_000


def test_acceptance_is_disabled_in_strict_descent(step):
    """La tolérance ne veut rien dire sans recuit : la descente stricte n'accepte
    jamais un coup dégradant."""
    widget, session = step
    session.set_algorithm(use_annealing=True)
    assert widget._acceptance.isEnabled()
    session.set_algorithm(use_annealing=False)
    assert not widget._acceptance.isEnabled()


@pytest.mark.parametrize("flag,field", [
    ("stop_on_stagnation", "_stagnation"),
    ("stop_on_time", "_time_budget"),
    ("stop_on_score", "_target_score"),
])
def test_threshold_fields_follow_their_checkbox(step, flag, field):
    widget, session = step
    session.set_algorithm(**{flag: False})
    assert not getattr(widget, field).isEnabled()
    session.set_algorithm(**{flag: True})
    assert getattr(widget, field).isEnabled()


def test_projections_are_displayed(step):
    widget, session = step
    session.set_algorithm(iterations=1_000_000, use_annealing=True, snapshot_every=10)
    assert "8 s" in widget._projection.text()
    assert "68" in widget._projection.text()
    assert "36" in widget._projection.text() and "70" in widget._projection.text()


def test_projections_follow_the_algorithm(step):
    widget, session = step
    session.set_algorithm(iterations=1_000_000, use_annealing=True)
    annealed = widget._projection.text()
    session.set_algorithm(use_annealing=False)
    assert widget._projection.text() != annealed


def test_a_too_loose_cadence_is_flagged(step):
    """Sous une dizaine de clichés la timeline n'est plus navigable."""
    widget, session = step
    session.set_algorithm(iterations=10_000, snapshot_every=1000, use_annealing=False)
    assert "cadence" in widget._projection.text()


def test_a_usable_cadence_is_not_flagged(step):
    widget, session = step
    session.set_algorithm(iterations=1_000_000, snapshot_every=10, use_annealing=True)
    assert "cadence" not in widget._projection.text()


def test_the_preview_is_debounced(step):
    """L'aperçu coûte jusqu'à 294 ms : chaque cran de molette ne doit pas le payer.

    L'anti-rebond appartient à l'aperçu lui-même, pas à cet écran : c'est lui qui
    sait de quoi il dépend, et deux minuteurs concurrents se doublonnaient.
    """
    from pokemon_mosaic.ui.strip_preview import REBUILD_DELAY_MS

    widget, session = step
    widget._preview.refresh()
    session.set_algorithm(strip_size=0.2)
    assert widget._preview._timer.isActive()
    assert widget._preview._timer.interval() == REBUILD_DELAY_MS
    assert widget._preview._timer.isSingleShot()


def test_the_screen_does_not_schedule_the_preview_itself(step):
    """Relancer l'aperçu depuis l'écran le ferait travailler pour des réglages
    qui ne le concernent pas."""
    widget, session = step
    widget._preview.refresh()
    session.set_algorithm(iterations=333_000)
    assert not widget._preview._timer.isActive()


def test_screen_paints(step):
    widget, _ = step
    widget.resize(900, 600)
    assert not widget.grab().isNull()


@pytest.mark.parametrize("rate", [0.0005, 0.0010, 0.0015, 0.0020, 0.0030])
def test_range_holds_across_the_declared_acceptance_band(rate):
    """La fourchette ne tenait compte de l'élagage que lorsqu'il était certain.
    Entre les deux bornes, la timeline jetait un cliché sur deux et tombait sous
    le plancher annoncé : deux taux sur cinq sortaient de l'intervalle affiché.
    """
    import numpy as np

    from pokemon_mosaic.timeline import Timeline

    iterations, every, maximum = 1_000_000, 10, 70
    low, high = estimated_snapshots(iterations, every, annealing=False,
                                    maximum=maximum)

    # On rejoue exactement la séquence d'appels d'optimize_grid.
    timeline = Timeline(every=every, max_snapshots=maximum)
    grid = np.zeros((2, 2), dtype=int)
    accepted_total = int(iterations * rate)
    timeline.record(grid, 0, 0, 0.0, 0.0)
    for accepted in range(1, accepted_total + 1):
        timeline.maybe_record(grid, accepted, accepted, 0.0, 0.0)
    timeline.record(grid, accepted_total, accepted_total, 0.0, 0.0)

    assert low <= len(timeline) <= high, (
        f"taux {rate} : {len(timeline)} clichés hors de ({low}, {high})"
    )


def test_range_is_untouched_when_thinning_cannot_happen():
    """Sans dépassement du plafond, aucune raison d'abaisser le plancher."""
    low, high = estimated_snapshots(200_000, every=10, annealing=False, maximum=70)
    assert (low, high) == (11, 61)


def test_a_value_outside_the_field_bounds_comes_back_corrected(session):
    """Un préréglage écrit à la main peut porter une valeur hors bornes. Sans
    retour du champ vers la session, le formulaire annoncerait un calcul
    différent de celui qui aurait lieu."""
    from pokemon_mosaic.ui.algorithm_tabs import AdvancedTab

    avances = AdvancedTab(session)
    session.set_algorithm(iterations=99, strip_size=0.9, acceptance=5.0)

    assert avances._iterations.value() == session.iterations == 1000
    assert avances._strip.value() == session.strip_size == pytest.approx(0.5)
    assert avances._acceptance.value() == session.acceptance == pytest.approx(0.99)


def test_a_value_within_bounds_is_left_alone(session):
    from pokemon_mosaic.ui.algorithm_tabs import AdvancedTab

    step = AdvancedTab(session)
    session.set_algorithm(iterations=4242)
    assert step._iterations.value() == session.iterations == 4242
