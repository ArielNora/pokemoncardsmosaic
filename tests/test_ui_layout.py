"""Tests de l'étape 2 : réglages de mise en page et cases vides."""

import numpy as np
import pytest

from test_ui_session import card_set_in


@pytest.fixture
def session(qt_app, tmp_path):
    from pokemon_mosaic.ui.session import Session

    s = Session()
    s.set_cards(card_set_in(tmp_path, {"s/a": [str(i) for i in range(20)]}), str(tmp_path))
    return s


def test_empty_cells_match_the_shortfall(session):
    session.set_layout(cols=5, rows=5)      # 25 cases pour 20 cartes
    assert len(session.empty_cells()) == 5
    session.set_layout(cols=4, rows=5)      # 20 cases, pile poil
    assert session.empty_cells() == []


def test_empty_cells_follow_the_selection(session):
    session.set_layout(cols=5, rows=5)
    assert len(session.empty_cells()) == 5
    session.set_excluded([0, 1], True)      # 18 cartes -> 7 vides
    assert len(session.empty_cells()) == 7


def test_clicking_pins_the_empty_cells(session):
    """Le premier clic fige la répartition automatique avant de la modifier,
    sinon le reste des trous sauterait à chaque clic."""
    session.set_layout(cols=5, rows=5)
    automatic = session.empty_cells()
    target = next((r, c) for r in range(5) for c in range(5)
                  if (r, c) not in automatic)

    session.toggle_empty_cell(*target)
    pinned = session.empty_cells()
    assert target in pinned, "le clic doit poser un trou là où on a cliqué"
    assert len(pinned) == 5, "le nombre de trous est fixé par la grille"
    # Un seul trou a cédé sa place : le reste du placement est conservé.
    assert len(set(automatic) & set(pinned)) == 4


def test_toggling_twice_removes_the_cell(session):
    session.set_layout(cols=5, rows=5)
    session.toggle_empty_cell(2, 2)
    assert (2, 2) in session.empty_cells()
    session.toggle_empty_cell(2, 2)
    assert (2, 2) not in session.empty_cells()


def test_clicks_outside_the_grid_are_ignored(session):
    session.set_layout(cols=5, rows=5)
    session.toggle_empty_cell(99, 0)
    session.toggle_empty_cell(0, -1)
    assert len(session.empty_cells()) == 5


def test_changing_the_grid_drops_manual_placement(session):
    """Les positions choisies à la main n'ont plus de sens sur une autre grille."""
    session.set_layout(cols=5, rows=5)
    session.toggle_empty_cell(4, 4)
    assert (4, 4) in session.empty_cells()
    session.set_layout(cols=7, rows=4)
    assert session.empty_cells() == sorted(session.empty_cells())
    assert len(session.empty_cells()) == 8


def test_reset_returns_to_the_automatic_placement(session):
    session.set_layout(cols=5, rows=5)
    automatic = session.empty_cells()
    session.toggle_empty_cell(0, 0)
    session.reset_empty_cells()
    assert session.empty_cells() == automatic


def test_layout_change_emits_once_per_call(session):
    calls = []
    session.layout_changed.connect(lambda: calls.append(1))
    session.set_layout(paper="A3", panels=2, cols=24, rows=12)
    assert len(calls) == 1


def test_setting_the_same_values_emits_nothing(session):
    session.set_layout(cols=5, rows=5)
    calls = []
    session.layout_changed.connect(lambda: calls.append(1))
    session.set_layout(cols=5, rows=5)
    assert calls == []


def test_form_follows_a_layout_changed_elsewhere(qt_app, session):
    """Un préréglage chargé doit se voir dans les champs, pas seulement l'aperçu."""
    from pokemon_mosaic.ui.layout_step import LayoutStep

    step = LayoutStep(session)
    session.set_layout(paper="A3", landscape=True, dpi=150, panels=2, cols=24, rows=12)
    assert step._paper.currentText() == "A3"
    assert step._landscape.isChecked()
    assert (step._dpi.value(), step._panels.value()) == (150, 2)
    assert (step._cols.value(), step._rows.value()) == (24, 12)


def test_wireframe_maps_clicks_to_cells(qt_app, session):
    from pokemon_mosaic.ui.wireframe import WireframeView

    session.set_layout(cols=4, rows=4)
    view = WireframeView(session)
    view.resize(400, 500)
    view.grab()  # force un rendu pour que la géométrie soit connue

    geometry = view._geometry
    assert geometry is not None
    scale, _, _, (card_w, card_h) = geometry
    gx, gy = view._grid_origin(geometry)
    # Centre de la case (2, 1)
    x = gx + (1 + 0.5) * card_w * scale
    y = gy + (2 + 0.5) * card_h * scale
    assert view.cell_at(x, y) == (2, 1)
    assert view.cell_at(gx - 50, gy - 50) is None


def test_wireframe_refuses_a_grid_that_cannot_be_split(qt_app, session):
    session.set_layout(cols=5, rows=4, panels=2)
    from pokemon_mosaic.ui.wireframe import WireframeView

    view = WireframeView(session)
    view.resize(400, 500)
    assert view._layout() is None
