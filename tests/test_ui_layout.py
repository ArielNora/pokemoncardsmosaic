"""Tests de l'étape 2 : réglages de mise en page et cases vides."""

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


@pytest.mark.parametrize("change", [
    {"dpi": 600}, {"paper": "A1"}, {"landscape": True}, {"panels": 2},
])
def test_manual_empty_cells_survive_unrelated_settings(session, change):
    """Le formulaire renvoie les six réglages d'un bloc : tester la présence de
    « cols » au lieu de sa valeur effaçait le placement manuel dès qu'on touchait
    au DPI, au format, à l'orientation ou au nombre de panneaux."""
    session.set_layout(cols=6, rows=4)
    automatic = set(session.empty_cells())
    chosen = [cell for cell in ((r, c) for r in range(4) for c in range(6))
              if cell not in automatic][:3]
    for cell in chosen:
        session.toggle_empty_cell(*cell)
    placed = session.empty_cells()
    assert all(cell in placed for cell in chosen)

    session.set_layout(cols=6, rows=4, **change)   # comme le fait le formulaire
    assert session.empty_cells() == placed
    assert session._empty_pinned


def test_changing_the_grid_still_resets_the_placement(session):
    session.set_layout(cols=6, rows=4)
    session.toggle_empty_cell(0, 0)
    session.set_layout(cols=5, rows=5)
    assert not session._empty_pinned


def test_a_link_wider_than_the_grid_is_flagged_at_step_two(qt_app, session):
    """La vérification existait mais n'était appelée nulle part : un lien trop
    large ne serait apparu qu'au lancement du calcul, bien après le réglage."""
    from pokemon_mosaic.links import Link
    from pokemon_mosaic.ui.layout_step import LayoutStep

    session.add_link(Link(cards=(0, 1, 2)))
    step = LayoutStep(session)
    session.set_layout(cols=2, rows=10)
    assert "3×1" in step._warnings.text()


def test_a_link_taller_than_the_grid_is_flagged_too(qt_app, session):
    """La hauteur n'était vérifiée nulle part tant qu'un lien tenait sur une
    seule rangée."""
    from pokemon_mosaic.links import Link
    from pokemon_mosaic.ui.layout_step import LayoutStep

    session.add_link(Link(cards=(0, 1, 2), shape=(1, 3)))
    step = LayoutStep(session)
    session.set_layout(cols=10, rows=2)
    assert "1×3" in step._warnings.text()


def test_no_warning_when_the_link_fits(qt_app, session):
    from pokemon_mosaic.links import Link
    from pokemon_mosaic.ui.layout_step import LayoutStep

    session.add_link(Link(cards=(0, 1, 2)))
    step = LayoutStep(session)
    session.set_layout(cols=5, rows=4)
    assert "colonne" not in step._warnings.text()


def test_an_unknown_paper_falls_back_instead_of_lying(session):
    """Une liste déroulante ignore une valeur qu'elle ne propose pas. Sans retour
    vers la session, le formulaire décrirait un poster que l'export refuserait de
    produire, `paper_size_mm` ne connaissant pas ce format."""
    from pokemon_mosaic.ui.layout_step import LayoutStep

    step = LayoutStep(session)
    before = session.paper
    session.set_layout(paper="A9")
    assert session.paper == step._paper.currentText() == before


def test_a_dpi_outside_the_field_bounds_comes_back_corrected(session):
    from pokemon_mosaic.ui.layout_step import LayoutStep

    step = LayoutStep(session)
    session.set_layout(dpi=5000)
    assert step._dpi.value() == session.dpi == 1200


# --- La grille proposée au premier passage ---------------------------------

@pytest.fixture
def ecran(session):
    from pokemon_mosaic.ui.layout_step import LayoutStep

    return LayoutStep(session)


def test_the_first_visit_fits_the_grid_to_the_selection(session, ecran):
    """20 cartes retenues : l'écran s'ouvre sur la grille la mieux ajustée, et
    non sur la valeur par défaut de la session."""
    session.set_layout(cols=17, rows=17)
    ecran._auto_fit_pending = True          # le préréglage a désarmé

    ecran.show()
    assert (session.cols, session.rows) == (5, 5)   # 25 cases pour 20 cartes


def test_the_grid_is_only_fitted_once(session, ecran):
    ecran.show()
    ajustee = (session.cols, session.rows)

    session.set_layout(cols=10, rows=10)
    ecran.hide()
    ecran.show()
    assert (session.cols, session.rows) == (10, 10)
    assert (session.cols, session.rows) != ajustee


def test_a_hand_picked_grid_survives_the_first_visit(session, ecran):
    """L'utilisateur peut régler la grille depuis l'étape 2 avant même que
    l'écran ne soit affiché dans un test ; son choix prime."""
    ecran._cols.setValue(4)
    ecran._rows.setValue(5)
    ecran.show()
    assert (session.cols, session.rows) == (4, 5)


def test_a_preset_grid_survives_the_first_visit(session, ecran):
    """Un préréglage décrit une grille voulue : l'ajustement automatique n'a
    pas à l'écraser au premier passage sur l'écran."""
    session.set_layout(cols=2, rows=10)     # venu d'ailleurs, pas des champs
    ecran.show()
    assert (session.cols, session.rows) == (2, 10)


def test_a_preset_that_repeats_the_current_grid_survives_too(session, ecran):
    """⚠️ Comparer les champs à la session ne suffisait pas : un préréglage qui
    rétablit la grille déjà en place ne fait bouger ni l'un ni l'autre. Mesuré —
    préréglage à 17×17, session par défaut à 17×17, grille ramenée à 5×5."""
    from pokemon_mosaic.presets import Preset

    voulue = (session.cols, session.rows)
    session.apply_preset(Preset(
        name="essai", excluded=[], active_links=[], algorithm={},
        layout={"cols": voulue[0], "rows": voulue[1], "paper": session.paper,
                "landscape": session.landscape, "dpi": session.dpi,
                "panels": session.panels},
    ))
    ecran.show()
    assert (session.cols, session.rows) == voulue


def test_a_clamped_field_is_not_a_choice(session, ecran):
    """Le retour d'un champ qui a écrêté une valeur de préréglage ne doit pas
    passer pour un choix de grille : sinon un DPI hors bornes désarmerait
    l'ajustement automatique au passage."""
    session.set_algorithm()                 # sans effet, juste pour le décor
    ecran._sync_form()                      # déclenche _push_back_clamped
    assert ecran._auto_fit_pending


def test_a_new_card_set_reopens_the_question(session, ecran, tmp_path):
    """La grille calculée pour les cartes précédentes n'a plus de raison de
    convenir aux nouvelles."""
    ecran.show()
    ecran.hide()

    jeu = card_set_in(tmp_path / "autre", {"s/b": [str(i) for i in range(12)]})
    session.set_cards(jeu, str(tmp_path / "autre"))
    ecran.show()
    assert (session.cols, session.rows) == (4, 4)   # 16 cases pour 12 cartes


def test_nothing_moves_without_a_card(qt_app):
    """Sans carte retenue, il n'y a pas de grille à déduire."""
    from pokemon_mosaic.ui.layout_step import LayoutStep
    from pokemon_mosaic.ui.session import Session

    vide = Session()
    ecran = LayoutStep(vide)
    avant = (vide.cols, vide.rows)
    ecran.show()
    assert (vide.cols, vide.rows) == avant


def test_the_fitted_grid_never_drops_a_card(session, ecran):
    """Sur A4 seules des grilles presque carrées passent : la plus proche de
    20 cartes est 4×4, qui en abandonne quatre juste après l'écran où
    l'utilisateur vient de les choisir une par une."""
    from pokemon_mosaic.layout import paper_size_mm, suggest_grids

    paper = paper_size_mm(session.paper, session.landscape)
    classement = suggest_grids(20, 713 / 984, paper[0] / paper[1])
    assert (classement[0].cols, classement[0].rows) == (4, 4), \
        "le classement brut perd bien des cartes"

    ecran.show()
    assert session.cols * session.rows >= session.selected_count
    assert session.grid_fit().surplus == 0
