"""Tests de l'étape 2 : les cases vides, et les trois onglets de mise en page."""

import pytest
from test_ui_session import card_set_in


@pytest.fixture
def session(qt_app, tmp_path):
    from pokemon_mosaic.ui.session import Session

    s = Session()
    s.set_cards(card_set_in(tmp_path, {"s/a": [str(i) for i in range(20)]}), str(tmp_path))
    return s


# --- Les cases vides ne se posent plus toutes seules -----------------------

def test_no_empty_cell_is_placed_by_default(session):
    """⚠️ L'application en répartissait d'office, quitte à les remplacer : la
    grille s'ouvrait déjà trouée, à des endroits que personne n'avait choisis,
    et rien ne disait qu'on pouvait les déplacer."""
    session.set_layout(cols=5, rows=5)      # 25 cases pour 20 cartes
    assert session.empty_cells() == []
    assert session.missing_empty_cells() == 5


def test_the_counter_falls_as_the_cells_are_placed(session):
    session.set_layout(cols=5, rows=5)
    session.toggle_empty_cell(0, 0)
    session.toggle_empty_cell(2, 3)
    assert session.missing_empty_cells() == 3
    assert session.empty_cells() == [(0, 0), (2, 3)]


def test_the_counter_follows_the_selection(session):
    session.set_layout(cols=5, rows=5)
    assert session.missing_empty_cells() == 5
    session.set_excluded([0, 1], True)      # 18 cartes -> 7 trous demandés
    assert session.missing_empty_cells() == 7


def test_toggling_twice_removes_the_cell(session):
    session.set_layout(cols=5, rows=5)
    session.toggle_empty_cell(1, 1)
    session.toggle_empty_cell(1, 1)
    assert session.empty_cells() == []


def test_clicks_outside_the_grid_are_ignored(session):
    session.set_layout(cols=4, rows=4)
    session.toggle_empty_cell(9, 9)
    session.toggle_empty_cell(-1, 0)
    assert session.empty_cells() == []


def test_changing_the_grid_drops_the_placement(session):
    """Les positions choisies n'ont plus de sens sur une autre grille : elles
    tomberaient à des endroits qui ne veulent plus rien dire."""
    session.set_layout(cols=5, rows=5)
    session.toggle_empty_cell(2, 2)
    session.set_layout(cols=4, rows=6)
    assert session.empty_cells() == []


@pytest.mark.parametrize("change", [
    {"dpi": 150}, {"panels": 2}, {"landscape": True}, {"paper": "A3"},
])
def test_manual_empty_cells_survive_unrelated_settings(session, change):
    """Seule la grille les invalide : changer le papier ou la finesse ne déplace
    aucune case."""
    session.set_layout(cols=4, rows=6)
    session.toggle_empty_cell(1, 1)
    session.set_layout(**change)
    assert session.empty_cells() == [(1, 1)]


def test_removing_them_all_leaves_nothing(session):
    session.set_layout(cols=5, rows=5)
    session.auto_place_empty_cells()
    assert len(session.empty_cells()) == 5
    session.reset_empty_cells()
    assert session.empty_cells() == []


# --- Le placement automatique, sur bouton ----------------------------------

def test_auto_placing_fills_exactly_what_is_missing(session):
    session.set_layout(cols=5, rows=5)
    session.auto_place_empty_cells()
    assert len(session.empty_cells()) == 5
    assert session.missing_empty_cells() == 0


def test_auto_placing_keeps_what_was_placed_by_hand(session):
    """Le bouton achève un placement commencé aussi bien qu'il en fait un de
    bout en bout."""
    session.set_layout(cols=5, rows=5)
    session.toggle_empty_cell(4, 4)
    session.auto_place_empty_cells()
    assert (4, 4) in session.empty_cells()
    assert len(session.empty_cells()) == 5


def test_auto_placing_spreads_the_holes(session):
    session.set_layout(cols=5, rows=5)
    session.auto_place_empty_cells()
    lignes = {row for row, _ in session.empty_cells()}
    assert len(lignes) >= 4, f"les trous s'agglutinent : {session.empty_cells()}"


# --- Les signaux ------------------------------------------------------------

def test_layout_change_emits_once_per_call(session):
    seen = []
    session.layout_changed.connect(lambda: seen.append(1))
    session.set_layout(cols=6, rows=4, dpi=150)
    assert len(seen) == 1


def test_setting_the_same_values_emits_nothing(session):
    session.set_layout(cols=6, rows=4)
    seen = []
    session.layout_changed.connect(lambda: seen.append(1))
    session.set_layout(cols=6, rows=4)
    assert seen == []


# --- Le fil de fer ----------------------------------------------------------

def test_wireframe_maps_clicks_to_cells(qt_app, session):
    from pokemon_mosaic.ui.wireframe import WireframeView

    session.set_layout(cols=4, rows=5)
    vue = WireframeView(session)
    vue.resize(400, 500)
    vue.grab()                               # force le calcul de géométrie

    scale, _, _, (card_w, card_h) = vue._geometry
    gx, gy = vue._grid_origin(vue._geometry)
    assert vue.cell_at(gx + card_w * scale * 1.5,
                       gy + card_h * scale * 2.5) == (2, 1)
    assert vue.cell_at(gx - 10, gy - 10) is None


def test_wireframe_refuses_a_grid_that_cannot_be_split(qt_app, session):
    from pokemon_mosaic.ui.wireframe import WireframeView

    session.set_layout(cols=5, rows=4, panels=2)
    vue = WireframeView(session)
    vue.resize(400, 500)
    vue.grab()
    assert vue._geometry is None


def test_the_paperless_wireframe_ignores_the_panels(qt_app, session):
    """Le découpage ne concerne que la feuille : sans elle, une grille non
    divisible reste parfaitement dessinable."""
    from pokemon_mosaic.ui.wireframe import WireframeView

    session.set_layout(cols=5, rows=4, panels=2)
    vue = WireframeView(session, show_paper=False)
    vue.resize(400, 500)
    vue.grab()
    assert vue._geometry is not None
    assert vue.cell_at(*_centre_de_case(vue, 0, 0)) == (0, 0)


def _centre_de_case(vue, row, col):
    scale, _, _, (card_w, card_h) = vue._geometry
    gx, gy = vue._grid_origin(vue._geometry)
    return (gx + card_w * scale * (col + 0.5), gy + card_h * scale * (row + 0.5))


# --- Les onglets ------------------------------------------------------------

@pytest.fixture
def ecran(session):
    from pokemon_mosaic.ui.layout_step import LayoutStep

    return LayoutStep(session)


def test_the_three_parts_are_listed(ecran):
    titres = [ecran._list.item(i).text() for i in range(ecran._list.count())]
    assert len(titres) == 3
    assert all(titres), "un onglet sans titre"


def test_nothing_is_ready_before_the_user_says_so(session, ecran):
    """Une partie n'est prête qu'une fois validée : au premier passage, elles
    portent toutes l'avertissement."""
    ecran.show()
    session.auto_place_empty_cells()
    assert ecran._tabs[0].is_valid(), "la grille est pourtant en état"
    assert not ecran._ready(0)
    assert not ecran.all_ready()


def test_advancing_marks_the_part_ready_and_moves_on(session, ecran):
    ecran.show()
    session.auto_place_empty_cells()

    assert ecran.advance() is True, "il reste des parties : le clic est consommé"
    assert ecran._ready(0)
    assert ecran._list.currentRow() == 1


def test_the_last_part_hands_the_click_back(session, ecran):
    ecran.show()
    session.auto_place_empty_cells()
    for _ in range(2):
        ecran.advance()

    assert ecran.advance() is False, "la fenêtre doit changer d'étape"
    assert ecran.all_ready()


def test_a_validated_part_that_breaks_loses_its_tick(session, ecran):
    """Revenir en arrière ne défait rien, mais rendre la grille invalide
    rallume l'avertissement : la coche promettrait sinon un état qui n'est plus."""
    ecran.show()
    session.auto_place_empty_cells()
    ecran.advance()
    assert ecran._ready(0)

    session.set_layout(cols=2, rows=2)       # 4 cases pour 20 cartes
    assert not ecran._ready(0)


def test_an_incomplete_grid_blocks_the_way(session, ecran):
    ecran.show()
    ecran._list.setCurrentRow(0)
    session.set_layout(cols=5, rows=5)        # 25 cases pour 20 cartes
    assert session.missing_empty_cells() > 0
    assert not ecran.can_advance()

    session.auto_place_empty_cells()
    assert ecran.can_advance()


def test_the_other_parts_never_block(session, ecran):
    """Format, orientation et finesse ont toujours une valeur acceptable : rien
    n'y est à compléter."""
    ecran.show()
    for position in (1, 2):
        ecran._list.setCurrentRow(position)
        assert ecran.can_advance()


# --- L'onglet des dimensions ------------------------------------------------

def test_the_status_line_says_red_when_cards_are_left_out(session, ecran):
    grille = ecran._tabs[0]
    session.set_layout(cols=2, rows=2)
    assert grille._status.property("role") == "error"
    assert "16" in grille._status.text()      # 20 cartes moins 4 cases


def test_the_status_line_says_amber_while_holes_remain(session, ecran):
    grille = ecran._tabs[0]
    session.set_layout(cols=5, rows=5)
    assert grille._status.property("role") == "warning"
    assert "5" in grille._status.text()


def test_the_status_line_turns_green_at_zero(session, ecran):
    grille = ecran._tabs[0]
    session.set_layout(cols=5, rows=5)
    session.auto_place_empty_cells()
    assert grille._status.property("role") == "ok"


def test_an_exact_grid_is_green_without_any_hole(session, ecran):
    grille = ecran._tabs[0]
    session.set_layout(cols=4, rows=5)        # 20 cases pour 20 cartes
    assert grille._status.property("role") == "ok"
    assert session.empty_cells() == []


def test_five_suggestions_are_offered(session, ecran):
    assert ecran._tabs[0]._suggestions.count() == 5


def test_the_grid_tab_says_nothing_of_the_paper(ecran):
    """Le format se décide à l'onglet suivant : le mêler ici obligeait à tout
    arbitrer d'un coup."""
    grille = ecran._tabs[0]
    assert not hasattr(grille, "_paper")
    assert not hasattr(grille, "_dpi")
    assert not grille._wireframe._show_paper


# --- La grille proposée au premier passage ---------------------------------

def test_the_first_visit_fits_the_grid_to_the_selection(session, ecran):
    session.set_layout(cols=17, rows=17)
    ecran._tabs[0]._auto_fit_pending = True   # le préréglage a désarmé
    ecran.show()
    assert (session.cols, session.rows) == (4, 5)   # 20 cases pour 20 cartes


def test_the_grid_is_only_fitted_once(session, ecran):
    ecran.show()
    session.set_layout(cols=10, rows=10)
    ecran.hide()
    ecran.show()
    assert (session.cols, session.rows) == (10, 10)


def test_a_hand_picked_grid_survives_the_first_visit(session, ecran):
    ecran._tabs[0]._cols.setValue(4)
    ecran._tabs[0]._rows.setValue(6)
    ecran.show()
    assert (session.cols, session.rows) == (4, 6)


def test_a_preset_grid_survives_the_first_visit(session, ecran):
    session.set_layout(cols=2, rows=10)       # venu d'ailleurs, pas des champs
    ecran.show()
    assert (session.cols, session.rows) == (2, 10)


def test_a_preset_that_repeats_the_current_grid_survives_too(session, ecran):
    """⚠️ Comparer les champs à la session ne suffisait pas : un préréglage qui
    rétablit la grille déjà en place ne fait bouger ni l'un ni l'autre."""
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


def test_a_new_card_set_reopens_the_question(session, ecran, tmp_path):
    ecran.show()
    ecran.hide()
    jeu = card_set_in(tmp_path / "autre", {"s/b": [str(i) for i in range(12)]})
    session.set_cards(jeu, str(tmp_path / "autre"))
    ecran.show()
    assert (session.cols, session.rows) == (3, 4)   # 12 cases pour 12 cartes


def test_nothing_moves_without_a_card(qt_app):
    from pokemon_mosaic.ui.layout_step import LayoutStep
    from pokemon_mosaic.ui.session import Session

    vide = Session()
    ecran = LayoutStep(vide)
    avant = (vide.cols, vide.rows)
    ecran.show()
    assert (vide.cols, vide.rows) == avant


def test_the_fitted_grid_never_drops_a_card(session, ecran):
    """Le classement brut peut placer en tête une grille trop petite : 17 cartes
    ont pour meilleure proposition 4×4, qui en abandonne une."""
    from pokemon_mosaic.layout import paper_size_mm, suggest_grids

    session.set_excluded([0, 1, 2], True)     # 17 cartes retenues
    paper = paper_size_mm(session.paper, session.landscape)
    classement = suggest_grids(17, 713 / 984, paper[0] / paper[1])
    assert classement[0].card_delta < 0, "le classement brut perd bien des cartes"

    ecran.show()
    assert session.grid_fit().surplus == 0


# --- L'onglet du format -----------------------------------------------------

def test_the_paper_tab_follows_the_session(session, ecran):
    papier = ecran._tabs[1]
    session.set_layout(paper="A3")
    assert papier._paper.currentText() == "A3"


def test_an_unknown_paper_falls_back_instead_of_lying(session, ecran):
    """Un préréglage écrit à la main peut porter un format inconnu : la liste
    l'ignore, et sans retour la session garderait une valeur qui ferait échouer
    l'export."""
    session.set_layout(paper="B3")
    ecran._tabs[1].refresh()
    assert session.paper in ("A4", ecran._tabs[1]._paper.currentText())
    assert session.paper != "B3"


def test_the_page_preview_scales_the_sheet_and_the_card(qt_app, session):
    """L'étalon entre dans le calcul d'échelle : sur un A6 il fait plus de la
    moitié de la largeur de la feuille, et l'oublier le ferait sortir du cadre."""
    from pokemon_mosaic.layout import REAL_CARD_MM
    from pokemon_mosaic.ui.page_preview import GAP, GUTTER, PagePreview

    session.set_layout(paper="A6")
    vue = PagePreview(session)
    vue.resize(420, 320)
    feuille = vue._sheet_mm()
    scale = vue._scale(feuille)
    largeur = (feuille[0] + GAP / 2 + REAL_CARD_MM[0]) * scale
    assert largeur <= vue.width() - 2 * GUTTER


# --- L'onglet d'impression --------------------------------------------------

def test_a_link_wider_than_the_grid_is_flagged(qt_app, session):
    from pokemon_mosaic.links import Link

    session.links.add(Link(cards=(0, 1, 2), shape=(3, 1)))
    session.set_layout(cols=2, rows=10)
    from pokemon_mosaic.ui.layout_step import LayoutStep

    ecran = LayoutStep(session)
    assert "3×1" in ecran._tabs[2]._warnings.text()


def test_a_link_taller_than_the_grid_is_flagged_too(qt_app, session):
    from pokemon_mosaic.links import Link
    from pokemon_mosaic.ui.layout_step import LayoutStep

    session.links.add(Link(cards=(0, 1, 2), shape=(1, 3)))
    session.set_layout(cols=10, rows=2)
    ecran = LayoutStep(session)
    assert "1×3" in ecran._tabs[2]._warnings.text()


def test_no_warning_when_the_link_fits(qt_app, session):
    from pokemon_mosaic.links import Link
    from pokemon_mosaic.ui.layout_step import LayoutStep

    session.links.add(Link(cards=(0, 1, 2), shape=(3, 1)))
    session.set_layout(cols=5, rows=4)
    ecran = LayoutStep(session)
    assert "occupe" not in ecran._tabs[2]._warnings.text()


def test_a_dpi_outside_the_field_bounds_comes_back_corrected(session, ecran):
    session.set_layout(dpi=5000)
    ecran._tabs[2].refresh()
    assert session.dpi == 1200


def test_a_mostly_empty_sheet_is_reported(session, ecran):
    """441 cartes en 20×23 sur deux A4 ne couvrent que 43,9 % du papier."""
    session.set_layout(panels=2, cols=20, rows=23)
    assert "44 %" in ecran._tabs[2]._warnings.text()
    assert "marge vide" in ecran._tabs[2]._warnings.text()


def test_a_grid_that_follows_the_sheet_says_nothing(session, ecran):
    session.set_layout(panels=2, cols=30, rows=15)
    assert "marge vide" not in ecran._tabs[2]._warnings.text()


def test_a_click_on_a_cell_hidden_by_the_quota_still_lands(session, tmp_path):
    """⚠️ Les cases hors quota restaient stockées sans être dessinées : cliquer
    l'une d'elles la retirait d'une liste invisible au lieu de poser un trou, et
    le clic était avalé sans le moindre retour. Mesuré — cinq trous posés puis
    quatre cartes réintégrées, un seul trou affiché, clic sans aucun effet."""
    session.set_layout(cols=5, rows=5)
    session.auto_place_empty_cells()
    assert len(session.empty_cells()) == 5

    jeu = card_set_in(tmp_path / "encore", {"s/b": [str(i) for i in range(4)]})
    for rang, carte in enumerate(jeu.cards, start=session.total_cards):
        carte.index = rang
    session.append_cards(jeu.cards)          # 24 cartes -> un seul trou demandé
    assert len(session.empty_cells()) == 1

    pleine = next((r, c) for r in range(5) for c in range(5)
                  if (r, c) not in session.empty_cells())
    session.toggle_empty_cell(*pleine)
    assert session.empty_cells() == [pleine], "le clic a été avalé"


def test_the_preset_records_only_the_cells_in_force(session):
    """Les cases hors quota ne sont plus en vigueur : les mémoriser ferait
    revenir des trous que l'écran n'affiche plus."""
    session.set_layout(cols=5, rows=5)
    session.auto_place_empty_cells()
    session.set_layout(cols=4, rows=5)       # 20 cases pour 20 cartes
    assert session.to_preset("essai").layout["empty_cells"] is None


# --- Les deux compteurs en grand --------------------------------------------

def test_the_big_counter_steps_and_clamps(qt_app):
    from pokemon_mosaic.ui.big_spin import BigSpin

    champ = BigSpin(1, 5)
    vus = []
    champ.value_changed.connect(vus.append)

    champ._up.click()
    assert champ.value() == 2 and vus == [2]
    champ.setValue(99)
    assert champ.value() == 5, "la borne haute doit écrêter"
    champ._up.click()
    assert champ.value() == 5, "on n'émet pas pour une valeur inchangée"
    assert vus == [2, 5]
    assert not champ._up.isEnabled()


def test_the_big_counter_accepts_a_typed_number(qt_app):
    """Passer de 4 à 21 à la flèche demanderait dix-sept clics."""
    from pokemon_mosaic.ui.big_spin import BigSpin

    champ = BigSpin(1, 200)
    champ._field.setText("21")
    champ._field.editingFinished.emit()
    assert champ.value() == 21


def test_an_emptied_field_keeps_the_previous_value(qt_app):
    """Retomber sur la borne basse donnerait une valeur que personne n'a
    demandée."""
    from pokemon_mosaic.ui.big_spin import BigSpin

    champ = BigSpin(1, 200)
    champ.setValue(12)
    champ._field.setText("")
    champ._field.editingFinished.emit()
    assert champ.value() == 12
    assert champ._field.text() == "12"


def test_the_grid_tab_drives_the_session_from_the_big_counters(session, ecran):
    grille = ecran._tabs[0]
    grille._cols.setValue(7)
    grille._rows.setValue(4)
    assert (session.cols, session.rows) == (7, 4)


# --- Poser plusieurs cases vides d'un glissement ----------------------------

def geste(vue, cases):
    """Un vrai enfoncé-déplacé-relâché, et non l'appel des slots."""
    from PySide6.QtCore import QEvent, QPointF, Qt
    from PySide6.QtGui import QMouseEvent
    from PySide6.QtWidgets import QApplication

    def point(row, col):
        scale, _, _, (cw, ch) = vue._geometry
        gx, gy = vue._grid_origin(vue._geometry)
        return QPointF(gx + cw * scale * (col + 0.5), gy + ch * scale * (row + 0.5))

    app = QApplication.instance()
    p = point(*cases[0])
    app.sendEvent(vue, QMouseEvent(QEvent.MouseButtonPress, p, p, Qt.LeftButton,
                                   Qt.LeftButton, Qt.NoModifier))
    for case in cases[1:]:
        p = point(*case)
        app.sendEvent(vue, QMouseEvent(QEvent.MouseMove, p, p, Qt.NoButton,
                                       Qt.LeftButton, Qt.NoModifier))
    app.sendEvent(vue, QMouseEvent(QEvent.MouseButtonRelease, p, p, Qt.LeftButton,
                                   Qt.NoButton, Qt.NoModifier))


@pytest.fixture
def grille(session, ecran):
    session.set_layout(cols=6, rows=6)       # 36 cases pour 20 cartes
    vue = ecran._tabs[0]._wireframe
    vue.resize(400, 500)
    vue.grab()                               # force le calcul de géométrie
    return vue


def test_dragging_places_several_cells_at_once(session, grille):
    geste(grille, [(0, col) for col in range(6)])
    assert session.empty_cells() == [(0, col) for col in range(6)]


def test_a_drag_started_on_a_hole_erases_along_its_path(session, grille):
    """⚠️ Le mode est décidé par la **première** case. Basculer case par case
    ferait clignoter tout ce sur quoi on repasse : un aller-retour du curseur
    défaisait ce que l'aller venait de poser."""
    geste(grille, [(0, col) for col in range(6)])
    geste(grille, [(0, 1), (0, 2), (0, 3)])
    assert session.empty_cells() == [(0, 0), (0, 4), (0, 5)]


def test_a_single_cell_gesture_stays_a_click(session, grille):
    geste(grille, [(2, 2)])
    assert session.empty_cells() == [(2, 2)]
    geste(grille, [(2, 2)])
    assert session.empty_cells() == [], "un second clic doit retirer le trou"


def test_a_drag_stops_at_the_quota_instead_of_chasing(session, ecran):
    """Poser au-delà en évinçant les plus anciennes ferait courir les trous
    derrière le curseur au lieu d'en poser."""
    session.set_layout(cols=5, rows=5)       # 25 cases, 20 cartes -> 5 trous
    vue = ecran._tabs[0]._wireframe
    vue.resize(400, 500)
    vue.grab()

    geste(vue, [(4, col) for col in range(5)] + [(3, col) for col in range(5)])
    assert session.empty_cells() == [(4, col) for col in range(5)]


def test_a_gesture_that_starts_outside_the_grid_does_nothing(session, grille):
    from PySide6.QtCore import QEvent, QPointF, Qt
    from PySide6.QtGui import QMouseEvent
    from PySide6.QtWidgets import QApplication

    dehors = QPointF(2, 2)
    QApplication.instance().sendEvent(
        grille, QMouseEvent(QEvent.MouseButtonPress, dehors, dehors,
                            Qt.LeftButton, Qt.LeftButton, Qt.NoModifier))
    geste(grille, [(1, 1), (1, 2)])
    assert session.empty_cells() == [(1, 1), (1, 2)]


def test_the_right_button_paints_nothing(session, grille):
    """⚠️ Un clic droit — le réflexe pour chercher un menu contextuel — basculait
    une case, et le moindre mouvement en posait toute une rangée. Mesuré : six
    cases vides posées par un glissement que personne n'avait voulu."""
    from PySide6.QtCore import QEvent, QPointF, Qt
    from PySide6.QtGui import QMouseEvent
    from PySide6.QtWidgets import QApplication

    def point(row, col):
        scale, _, _, (cw, ch) = grille._geometry
        gx, gy = grille._grid_origin(grille._geometry)
        return QPointF(gx + cw * scale * (col + 0.5), gy + ch * scale * (row + 0.5))

    app = QApplication.instance()
    p = point(0, 0)
    app.sendEvent(grille, QMouseEvent(QEvent.MouseButtonPress, p, p,
                                      Qt.RightButton, Qt.RightButton, Qt.NoModifier))
    for col in range(1, 6):
        p = point(0, col)
        app.sendEvent(grille, QMouseEvent(QEvent.MouseMove, p, p, Qt.NoButton,
                                          Qt.RightButton, Qt.NoModifier))
    app.sendEvent(grille, QMouseEvent(QEvent.MouseButtonRelease, p, p,
                                      Qt.RightButton, Qt.NoButton, Qt.NoModifier))
    assert session.empty_cells() == []
