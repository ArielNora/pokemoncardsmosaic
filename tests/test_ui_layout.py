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


def test_the_wireframe_draws_an_undivisible_grid_all_the_same(qt_app, session):
    """⚠️ Il refusait de dessiner quand les colonnes ne se divisaient pas en
    feuilles. Plusieurs feuilles ne sont qu'une façon d'avoir plus de place :
    la coupe tombe où elle tombe."""
    from pokemon_mosaic.ui.wireframe import WireframeView

    session.set_layout(cols=5, rows=4, panels=2)
    vue = WireframeView(session)
    vue.resize(400, 500)
    vue.grab()
    assert vue._geometry is not None


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


def test_the_menu_has_two_levels(ecran):
    """Les pages d'abord, puis la famille « Grille » et ses trois temps."""
    titres = [ecran._list.item(i).text() for i in range(ecran._list.count())]
    assert len(titres) == 5
    assert all(titres), "une ligne sans intitulé"
    assert titres[1].strip().endswith("Grille"), "l'intitulé de famille manque"
    assert not any(t.startswith(" ") for t in titres), "le retrait n'est pas du texte"


def test_the_family_row_is_not_a_tab(ecran):
    """Cliquable pour plier, jamais sélectionnable : elle n'a rien à montrer."""
    from PySide6.QtCore import Qt

    assert ecran._list.item(1).flags() == Qt.ItemIsEnabled
    assert not (ecran._list.item(1).flags() & Qt.ItemIsSelectable)
    assert ecran._rows[1] == -1


def click_family(ecran):
    """Un vrai clic sur l'intitulé, pour éprouver aussi le rang qui rebondit."""
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    ecran.show()
    rect = ecran._list.visualItemRect(ecran._list.item(1))
    QTest.mouseClick(ecran._list.viewport(), Qt.LeftButton, Qt.NoModifier,
                     rect.center())


def test_the_family_row_folds_its_three_tabs(session, ecran):
    """Un titre de groupe qui ne répond pas au clic passe pour un onglet en
    panne : il plie, comme n'importe quel accordéon."""
    click_family(ecran)
    assert ecran._collapsed
    assert all(ecran._list.isRowHidden(ecran._row_of(p)) for p in (1, 2, 3))
    assert not ecran._list.isRowHidden(ecran._row_of(0))

    click_family(ecran)
    assert not ecran._collapsed
    assert not any(ecran._list.isRowHidden(ecran._row_of(p)) for p in (1, 2, 3))


def test_folding_never_leaves_the_screen_without_a_tab(session, ecran):
    """⚠️ Garder affiché un onglet dont la ligne vient d'être cachée laisserait
    un écran que plus aucune sélection ne désigne, et un « Suivant » qui avance
    depuis un endroit invisible."""
    ecran.show()
    ecran._list.setCurrentRow(ecran._row_of(2))
    click_family(ecran)

    assert ecran._current_tab() == 0, "on revient aux pages"
    assert ecran._pages.currentIndex() == 0
    assert ecran.can_advance()


def test_clicking_the_family_never_makes_it_the_current_tab(session, ecran):
    """Elle n'a pas de contenu : le rang courant rebondit là où l'écran est
    resté."""
    ecran.show()
    click_family(ecran)                      # replie
    click_family(ecran)                      # déplie

    assert not ecran._collapsed
    assert ecran._current_tab() == 0, "le rang est resté sur l'intitulé"
    assert ecran._list.currentRow() == ecran._row_of(0)


def test_advancing_into_the_family_unfolds_it(session, ecran):
    ecran.show()
    session.auto_place_empty_cells()
    click_family(ecran)                      # replié, on est sur les pages
    assert ecran._collapsed

    ecran.advance()
    assert not ecran._collapsed
    assert ecran._current_tab() == 1


def test_the_folded_family_answers_for_its_tabs(session, ecran):
    """Ce qui reste à faire disparaîtrait sinon avec les lignes cachées."""
    ecran.show()
    session.auto_place_empty_cells()
    click_family(ecran)
    plie = ecran._list.item(1)
    assert not plie.icon().isNull()

    for position in (1, 2, 3):
        ecran._validated.add(position)
    ecran._refresh_badges()
    from pokemon_mosaic.ui.layout_step import state_icon

    attendu = state_icon(True, ecran.palette()).pixmap(22, 22).toImage()
    assert plie.icon().pixmap(22, 22).toImage() == attendu


def painted(ecran):
    """La colonne d'onglets telle qu'elle est réellement peinte.

    ⚠️ Rendue à la densité de l'écran : sur un écran Retina, l'image fait le
    double des coordonnées de la liste, et lire un pixel sans en tenir compte
    interroge une tout autre ligne.
    """
    ecran.resize(1000, 700)
    ecran.show()
    pixmap = ecran._list.grab()
    return pixmap.toImage(), pixmap.devicePixelRatio()


def dot(image, ratio, x, y) -> int:
    return image.pixel(int(x * ratio), int(y * ratio))


def box_edges(image, ratio, teinte, y) -> tuple[int, int]:
    """Les deux bords du cadre coloré, sur cette ligne.

    On cherche la **teinte** de la sélection plutôt que le premier pixel encré :
    le trait qui relie les petits onglets se trouve à leur gauche, et un simple
    « premier pixel différent du fond » s'y arrêterait.
    """
    trouves = [x for x in range(2, image.width() // int(ratio))
               if dot(image, ratio, x, y) == teinte]
    return (trouves[0], trouves[-1]) if trouves else (-1, -1)


def test_the_small_tabs_are_narrower_on_their_left_only(ecran):
    """⚠️ Le retrait est **géométrique** : quatre espaces dans le libellé
    décalaient le texte sans décaler l'onglet, qui gardait toute la largeur.
    Le bord droit reste aligné sur les primaires — décalé des deux côtés, le
    second rang aurait flotté au milieu de la colonne."""
    from pokemon_mosaic.ui.layout_step import SUB_TAB_INDENT

    image, ratio = painted(ecran)          # l'onglet des pages est sélectionné
    primaire = ecran._list.visualItemRect(ecran._list.item(0)).center().y()
    teinte = dot(image, ratio, 100, primaire)
    gauche, droite = box_edges(image, ratio, teinte, primaire)

    ecran._show(1)                          # un onglet de la famille
    image, ratio = painted(ecran)
    petit = ecran._list.visualItemRect(ecran._list.item(2)).center().y()
    gauche_petit, droite_petit = box_edges(image, ratio, teinte, petit)

    assert gauche_petit - gauche == pytest.approx(SUB_TAB_INDENT, abs=2)
    assert droite_petit == pytest.approx(droite, abs=1), "bord droit désaligné"


def test_a_single_line_joins_the_small_tabs_to_their_family(ecran):
    """Trois onglets décalés se lisent comme trois onglets décalés ; un trait
    unique qui les longe dit qu'ils sortent tous du même."""
    from pokemon_mosaic.ui.layout_step import TRUNK_X

    image, ratio = painted(ecran)
    haut = ecran._list.visualItemRect(ecran._list.item(2))
    bas = ecran._list.visualItemRect(ecran._list.item(4))
    x = haut.left() + TRUNK_X
    fond = dot(image, ratio, 100, haut.top() + 1)
    # Sans interruption d'un bout à l'autre des trois.
    for y in range(haut.top() + 2, bas.bottom() - 10):
        assert dot(image, ratio, x, y) != fond, y


def test_the_line_goes_away_with_the_folded_family(ecran):
    """Repliée, la famille n'a plus rien à rattacher."""
    from pokemon_mosaic.ui.layout_step import TRUNK_X

    bande = ecran._list.visualItemRect(ecran._list.item(2))
    click_family(ecran)
    image, ratio = painted(ecran)
    x = bande.left() + TRUNK_X
    fond = dot(image, ratio, 100, bande.center().y())
    assert all(dot(image, ratio, x, y) == fond
               for y in range(bande.top() + 2, bande.bottom()))


def test_nothing_is_ready_before_the_user_says_so(session, ecran):
    """Une partie n'est prête qu'une fois validée : au premier passage, elles
    portent toutes l'avertissement."""
    ecran.show()
    session.auto_place_empty_cells()
    assert ecran._tabs[1].is_valid(), "la grille est pourtant en état"
    assert not ecran._ready(1)
    assert not ecran.all_ready()


def test_advancing_marks_the_part_ready_and_moves_on(session, ecran):
    ecran.show()
    session.auto_place_empty_cells()

    assert ecran.advance() is True, "il reste des parties : le clic est consommé"
    assert ecran._ready(0)
    assert ecran._list.currentRow() == ecran._row_of(1)


def test_the_last_part_hands_the_click_back(session, ecran):
    ecran.show()
    session.auto_place_empty_cells()
    for _ in range(len(ecran._tabs) - 1):
        ecran.advance()

    assert ecran.advance() is False, "la fenêtre doit changer d'étape"
    assert ecran.all_ready()


def test_a_validated_part_that_breaks_loses_its_tick(session, ecran):
    """Revenir en arrière ne défait rien, mais rendre la grille invalide
    rallume l'avertissement : la coche promettrait sinon un état qui n'est plus."""
    ecran.show()
    session.auto_place_empty_cells()
    ecran._list.setCurrentRow(ecran._row_of(1))
    ecran.advance()
    assert ecran._ready(1)

    session.set_layout(cols=2, rows=2)       # 4 cases pour 20 cartes
    assert not ecran._ready(1)


def test_an_incomplete_grid_blocks_the_way(session, ecran):
    ecran.show()
    ecran._list.setCurrentRow(ecran._row_of(1))
    session.set_layout(cols=5, rows=5)        # 25 cases pour 20 cartes
    assert session.missing_empty_cells() > 0
    assert not ecran.can_advance()

    session.auto_place_empty_cells()
    assert ecran.can_advance()


def test_the_other_parts_never_block(session, ecran):
    """Format, orientation et finesse ont toujours une valeur acceptable : rien
    n'y est à compléter."""
    ecran.show()
    session.auto_place_empty_cells()
    for position in (0, 3):
        ecran._list.setCurrentRow(ecran._row_of(position))
        assert ecran.can_advance(), position


# --- L'onglet des dimensions ------------------------------------------------

def test_the_status_line_says_red_when_cards_are_left_out(session, ecran):
    grille = ecran._tabs[1]
    session.set_layout(cols=2, rows=2)
    assert grille._status.property("role") == "error"
    assert "16" in grille._status.text()      # 20 cartes moins 4 cases


def test_the_status_line_says_amber_while_holes_remain(session, ecran):
    grille = ecran._tabs[1]
    session.set_layout(cols=5, rows=5)
    assert grille._status.property("role") == "warning"
    assert "5" in grille._status.text()


def test_the_status_line_turns_green_at_zero(session, ecran):
    grille = ecran._tabs[1]
    session.set_layout(cols=5, rows=5)
    session.auto_place_empty_cells()
    assert grille._status.property("role") == "ok"


def test_an_exact_grid_is_green_without_any_hole(session, ecran):
    grille = ecran._tabs[1]
    session.set_layout(cols=4, rows=5)        # 20 cases pour 20 cartes
    assert grille._status.property("role") == "ok"
    assert session.empty_cells() == []


def test_five_suggestions_are_offered(session, ecran):
    assert ecran._tabs[1]._suggestions.count() == 5


def test_the_grid_tab_says_nothing_of_the_paper(ecran):
    """Le format se décide à l'onglet suivant : le mêler ici obligeait à tout
    arbitrer d'un coup."""
    grille = ecran._tabs[1]
    assert not hasattr(grille, "_paper")
    assert not hasattr(grille, "_dpi")


# --- La grille proposée au premier passage ---------------------------------

def test_the_first_visit_fits_the_grid_to_the_selection(session, ecran):
    session.set_layout(cols=17, rows=17)
    ecran._tabs[1]._auto_fit_pending = True   # le préréglage a désarmé
    ecran.show()
    ecran._list.setCurrentRow(ecran._row_of(1))   # on entre sur l'onglet
    assert (session.cols, session.rows) == (4, 5)   # 20 cases pour 20 cartes


def test_the_grid_is_only_fitted_once(session, ecran):
    ecran.show()
    ecran._list.setCurrentRow(ecran._row_of(1))
    session.set_layout(cols=10, rows=10)
    ecran.hide()
    ecran.show()
    assert (session.cols, session.rows) == (10, 10)


def test_a_hand_picked_grid_survives_the_first_visit(session, ecran):
    ecran._tabs[1]._cols.setValue(4)
    ecran._tabs[1]._rows.setValue(6)
    ecran.show()
    ecran._list.setCurrentRow(ecran._row_of(1))
    assert (session.cols, session.rows) == (4, 6)


def test_a_preset_grid_survives_the_first_visit(session, ecran):
    session.set_layout(cols=2, rows=10)       # venu d'ailleurs, pas des champs
    ecran.show()
    ecran._list.setCurrentRow(ecran._row_of(1))
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
    ecran._list.setCurrentRow(ecran._row_of(1))
    assert (session.cols, session.rows) == voulue


def test_a_new_card_set_reopens_the_question(session, ecran, tmp_path):
    ecran.show()
    ecran._list.setCurrentRow(ecran._row_of(1))
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
    ecran._list.setCurrentRow(ecran._row_of(1))
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
    ecran._list.setCurrentRow(ecran._row_of(1))
    assert session.grid_fit().surplus == 0


# --- L'onglet du format -----------------------------------------------------

def test_the_paper_tab_follows_the_session(session, ecran):
    papier = ecran._tabs[0]
    session.set_layout(paper="A3")
    assert papier._paper.value() == "A3"
    assert (papier._width.value(), papier._height.value()) == (29.7, 42.0)


def test_the_sheet_is_defined_by_its_two_sides(session, ecran):
    """⚠️ Le format nommé est une commodité, pas la définition : sept feuilles
    ont un nom, toutes ont deux côtés. Le nom suit donc les dimensions, et
    montre une croix quand aucune ne leur correspond."""
    papier = ecran._tabs[0]
    session.set_layout(paper="A4")
    papier._width.setValue(30.0)          # 30 × 29,7 cm : aucun format

    assert session.paper == "", "un format nommé qui ne l'est plus"
    assert session.paper_size_mm == (300.0, 297.0)
    assert papier._paper.value() == ""
    assert papier._paper._combo.currentText() == papier._paper.NONE

    # Et le chemin inverse : retomber sur des dimensions connues rend le nom.
    papier._width.setValue(21.0)
    assert session.paper == "A4"
    assert papier._paper._combo.currentText() == "A4"


def test_the_cross_cannot_be_chosen_from_the_list(session, ecran):
    """Elle dit qu'aucun format ne correspond : elle ne décrit aucune feuille,
    et n'a donc rien à proposer."""
    papier = ecran._tabs[0]
    session.set_layout(paper="A4")
    papier._width.setValue(30.0)
    modele = papier._paper._combo.model()
    assert not modele.item(0).isEnabled()


def test_the_two_sides_are_the_sheet_as_printed(session, ecran):
    """Ce que les champs montrent est ce qui sortira de l'imprimante : le
    paysage échange les deux nombres sous les yeux, sans que « A4 paysage »
    cesse d'être un A4."""
    papier = ecran._tabs[0]
    session.set_layout(paper="A4", landscape=True)
    assert (papier._width.value(), papier._height.value()) == (29.7, 21.0)
    assert session.paper == "A4", "l'orientation n'est pas une autre feuille"

    papier._width.setValue(40.0)          # saisie en paysage
    assert session.paper_size_mm == (210.0, 400.0), "rangée en portrait"
    assert session.paper_mm() == (400.0, 210.0)


def test_an_unknown_paper_falls_back_instead_of_lying(session, ecran):
    """Un préréglage écrit à la main peut porter un format inconnu : sans
    retour, la session garderait une valeur qui ferait échouer l'export.
    La correction est désormais dans la session — elle ne dépend plus de
    l'écran, qui pouvait n'avoir jamais été ouvert."""
    session.set_layout(paper="A4")
    session.set_layout(paper="B3")
    assert session.paper == "A4", "la feuille en place reste, le faux nom part"
    assert session.paper_size_mm == (210.0, 297.0)


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
    assert "3×1" in ecran._tabs[0]._warnings.text()


def test_a_link_taller_than_the_grid_is_flagged_too(qt_app, session):
    from pokemon_mosaic.links import Link
    from pokemon_mosaic.ui.layout_step import LayoutStep

    session.links.add(Link(cards=(0, 1, 2), shape=(1, 3)))
    session.set_layout(cols=10, rows=2)
    ecran = LayoutStep(session)
    assert "1×3" in ecran._tabs[0]._warnings.text()


def test_no_warning_when_the_link_fits(qt_app, session):
    from pokemon_mosaic.links import Link
    from pokemon_mosaic.ui.layout_step import LayoutStep

    session.links.add(Link(cards=(0, 1, 2), shape=(3, 1)))
    session.set_layout(cols=5, rows=4)
    ecran = LayoutStep(session)
    assert "occupe" not in ecran._tabs[0]._warnings.text()


def test_the_paper_tab_says_nothing_of_the_resolution(ecran):
    """⚠️ La finesse ne change rien de visible ici — tout s'y mesure en
    millimètres — et la demander d'abord obligeait à trancher une question
    d'impression avant d'avoir posé la mosaïque. Elle est passée à l'export."""
    papier = ecran._tabs[0]
    assert not hasattr(papier, "_dpi")
    assert "DPI" not in papier._warnings.text()


def test_a_mostly_empty_sheet_is_reported_without_being_judged(session, ecran):
    """⚠️ Le message conseillait d'allonger la grille pour mieux remplir. Depuis
    qu'ajouter une feuille veut dire « avoir plus de place », ce blanc est
    l'état normal, et l'onglet précédent l'annonce comme tel : deux écrans
    disaient le contraire du même blanc."""
    session.set_layout(panels=3, cols=6, rows=5)
    texte = ecran._tabs[0]._warnings.text()
    assert "%" in texte and "blanc" in texte
    assert "normal si vous avez ajouté des feuilles" in texte


def test_a_grid_that_follows_the_sheet_says_nothing(session, ecran):
    session.set_layout(panels=2, cols=30, rows=15)
    assert "sortira blanc" not in ecran._tabs[0]._warnings.text()


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
    grille = ecran._tabs[1]
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
        rect = next(r for lig, c, r in vue.grid_cells(vue.rects()[0])
                    if (lig, c) == (row, col))
        return QPointF(rect.center())

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
    """L'aperçu des pages de l'onglet des tailles, où l'on pose les cases vides."""
    session.set_layout(cols=6, rows=6)       # 36 cases pour 20 cartes
    vue = ecran._tabs[1]._preview
    vue.resize(700, 460)
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
    vue = ecran._tabs[1]._preview
    vue.resize(700, 460)
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
        rect = next(r for lig, c, r in grille.grid_cells(grille.rects()[0])
                    if (lig, c) == (row, col))
        return QPointF(rect.center())

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


# --- Ce que la ligne d'état et la grille montrent --------------------------

def test_the_suggestions_are_named(ecran):
    grille = ecran._tabs[1]
    assert grille._suggestions_title.text() == "Recommandations de grilles"
    assert grille._suggestions_title.font().bold()


def test_the_status_line_is_larger_than_the_interface(qt_app, ecran):
    """C'est le verdict de l'onglet : il se lit d'un coup d'œil depuis l'autre
    bout de l'écran, et non en se penchant sur le bas du panneau."""
    grille = ecran._tabs[1]
    assert grille._status.font().pointSize() > qt_app.font().pointSize()


def test_the_count_is_bold_in_every_state(session, ecran):
    """Sans texte enrichi, les balises s'afficheraient telles quelles."""
    from PySide6.QtCore import Qt

    grille = ecran._tabs[1]
    assert grille._status.textFormat() == Qt.RichText

    for cols, rows in ((2, 2), (5, 5)):          # trop petit, puis à combler
        session.set_layout(cols=cols, rows=rows)
        assert "<b>" in grille._status.text(), (cols, rows)

    session.auto_place_empty_cells()
    assert "<b>" in grille._status.text()


def test_an_empty_cell_is_filled_red_not_merely_outlined(qt_app, session):
    """Un contour rouge sur fond blanc se perdait au milieu des cartes dès que
    la grille passait la centaine de cases."""
    from PySide6.QtGui import QColor

    from pokemon_mosaic.ui.wireframe import CARD_FILL, EMPTY_FILL, WireframeView

    vide = QColor(EMPTY_FILL)
    assert vide.red() > vide.green() + 60 and vide.red() > vide.blue() + 60, \
        "la case vide doit être franchement rouge"
    assert vide != QColor(CARD_FILL)

    session.set_layout(cols=4, rows=6)
    session.toggle_empty_cell(0, 0)
    vue = WireframeView(session, show_paper=False)
    vue.resize(400, 500)
    image = vue.grab().toImage()

    scale, _, _, (card_w, card_h) = vue._geometry
    gx, gy = vue._grid_origin(vue._geometry)
    centre = QColor(image.pixel(int(gx + card_w * scale * 0.5),
                                int(gy + card_h * scale * 0.5)))
    assert centre.red() > centre.green() + 40, \
        f"le centre de la case vide n'est pas rouge : {centre.name()}"


def test_the_cut_line_is_not_the_colour_of_a_hole(qt_app):
    """⚠️ Le trait de coupe valait #c85a5a et le remplissage des trous #d05a5a :
    huit d'écart sur 765, là où une case vide et une carte en ont 315. La coupe
    passait pour une colonne de trous."""
    from pokemon_mosaic.ui.wireframe import CARD_FILL, CUT_LINE, EMPTY_FILL

    def ecart(a, b):
        return (abs(a.red() - b.red()) + abs(a.green() - b.green())
                + abs(a.blue() - b.blue()))

    reference = ecart(EMPTY_FILL, CARD_FILL)
    assert ecart(EMPTY_FILL, CUT_LINE) > reference / 2, \
        "la coupe se confond avec les cases vides"


# --- L'onglet du format : la mosaïque posée dessus --------------------------

def test_the_standard_is_never_covered_by_the_sheet(qt_app, session):
    """⚠️ L'étiquette était centrée sur la seule carte : dès que celle-ci se
    réduisait — un A1, un A0 —, le texte débordait des deux côtés et passait
    sous la feuille."""
    from pokemon_mosaic.layout import PAPER_FORMATS_MM
    from pokemon_mosaic.ui.page_preview import GAP, PagePreview

    vue = PagePreview(session)
    vue.resize(820, 560)
    for nom in PAPER_FORMATS_MM:
        for panneaux in (1, 2):
            session.set_layout(paper=nom, panels=panneaux, cols=4, rows=5)
            vue.grab()
            feuille, carte, etiquette = vue.rects()
            # L'étalon est passé à gauche : la droite revient au bouton
            # d'ajout, et il y aurait été poussé plus loin à chaque feuille.
            assert carte.right() <= feuille.left() - GAP + 0.5, (nom, panneaux)
            assert etiquette.right() <= feuille.left() - GAP + 0.5, (nom, panneaux)
            assert carte.left() >= 0, (nom, panneaux)
            assert etiquette.left() >= 0, (nom, panneaux)
            assert etiquette.top() >= 0, (nom, panneaux)


def test_a_narrow_frame_still_keeps_everything_inside(qt_app, session):
    """Le cadre n'a pas toujours huit cents pixels : la fenêtre se réduit."""
    from pokemon_mosaic.ui.page_preview import GAP, PagePreview

    vue = PagePreview(session)
    vue.resize(420, 300)
    session.set_layout(paper="A0", panels=2)
    vue.grab()
    feuille, _, etiquette = vue.rects()
    assert etiquette.right() <= feuille.left() - GAP + 0.5
    assert etiquette.left() >= 0


def test_the_mosaic_is_drawn_on_the_sheet_when_asked(qt_app, session):
    """Le fond du papier est presque blanc, celui d'une carte franchement
    bleuté : un pixel au centre de la feuille dit lequel est dessiné."""
    from PySide6.QtGui import QColor

    from pokemon_mosaic.ui.page_preview import PagePreview

    session.set_layout(paper="A4", cols=4, rows=5)
    vue = PagePreview(session)
    vue.resize(820, 560)

    vue.set_show_grid(False)
    feuille, _, _ = vue.rects()
    milieu = (int(feuille.center().x()), int(feuille.center().y()))
    nu = QColor(vue.grab().toImage().pixel(*milieu))

    vue.set_show_grid(True)
    garni = QColor(vue.grab().toImage().pixel(*milieu))
    assert garni != nu
    assert garni.blue() > garni.red(), f"la case ne paraît pas une carte : {garni.name()}"


def test_the_mosaic_is_shown_by_the_grid_family_only(session, ecran):
    """⚠️ La bascule « montrer la mosaïque » disparaît : la famille « Grille »
    la montre partout. L'onglet des pages, lui, ne décide que du papier, et une
    grille posée dessus se lisait comme un aperçu du résultat alors qu'elle
    n'était réglée nulle part encore."""
    for position in range(len(ecran._tabs)):
        onglet = ecran._tabs[position]
        assert not hasattr(onglet, "_show_grid"), position
        assert onglet._preview._show_grid is (position > 0), position


def test_only_the_size_tab_lets_you_paint(session, ecran):
    """Un clic qui creuse la mosaïque sans qu'on l'ait demandé serait une
    surprise désagréable : on ne pose des cases vides que là où on les règle."""
    assert ecran._tabs[1]._preview._paintable
    for position in (0, 2, 3):
        assert not ecran._tabs[position]._preview._paintable, position


# --- De gros onglets --------------------------------------------------------

def test_the_tabs_are_big_enough_to_be_aimed_at(ecran):
    from pokemon_mosaic.ui.layout_step import SUB_TAB_HEIGHT, TAB_HEIGHT

    assert ecran._list.property("role") == "tabs"
    for rang, position in enumerate(ecran._rows):
        attendu = SUB_TAB_HEIGHT if position > 0 else TAB_HEIGHT
        assert ecran._list.item(rang).sizeHint().height() >= attendu, rang


def test_no_tab_label_is_cut_off(qt_app, ecran):
    """Un intitulé tronqué en « Orientation, finesse et … » ne dit plus ce que
    la partie contient."""
    from pokemon_mosaic.ui.layout_step import BADGE, TAB_WIDTH

    metrics = ecran._list.fontMetrics()
    dispo = TAB_WIDTH - 8 - 24 - BADGE - 12       # marges, icône, respiration
    for position in range(ecran._list.count()):
        texte = ecran._list.item(position).text()
        assert metrics.horizontalAdvance(texte) <= dispo, texte


def test_the_width_dimension_always_has_room_below_the_sheet(qt_app, session):
    """⚠️ La feuille était centrée dans le cadre entier : la moitié de la
    réserve partait vers le haut, où elle ne sert à rien. Mesuré — 37 px laissés
    sous la feuille pour une cote qui en réclame 42, et le « 42 cm » coupé."""
    from pokemon_mosaic.layout import PAPER_FORMATS_MM
    from pokemon_mosaic.ui.page_preview import BOTTOM_ROOM, PagePreview

    vue = PagePreview(session)
    for largeur, hauteur in ((820, 560), (420, 300), (1000, 300), (700, 280)):
        vue.resize(largeur, hauteur)
        for nom in PAPER_FORMATS_MM:
            for panneaux in (1, 3):
                session.set_layout(paper=nom, panels=panneaux, cols=6, rows=5)
                vue.grab()
                geometrie = vue.rects()
                if geometrie is None:
                    continue
                feuille, _, etiquette = geometrie
                assert vue.height() - feuille.bottom() >= BOTTOM_ROOM - 0.5, \
                    (nom, panneaux, largeur, hauteur)
                assert etiquette.top() >= 0, (nom, panneaux, largeur, hauteur)


def test_the_selected_tab_label_stays_legible(qt_app):
    """Le libellé de l'onglet actif se lit sur un fond que nous posons : il ne
    suit plus la palette de sélection de Qt, donc il se vérifie."""
    from test_ui_theme import contraste

    from pokemon_mosaic.ui import theme

    assert contraste(theme.PALETTE_LIGHT["text"], theme.LIGHT["tab_on_bg"]) >= 4.5
    assert contraste(theme.PALETTE_DARK["text"], theme.DARK["tab_on_bg"]) >= 4.5
    assert contraste(theme.LIGHT["tab_on_border"],
                     theme.PALETTE_LIGHT["window"]) >= 3.0
    assert contraste(theme.DARK["tab_on_border"],
                     theme.PALETTE_DARK["window"]) >= 3.0


# --- Ajouter et retirer des feuilles depuis l'aperçu ------------------------

@pytest.fixture
def papier(session, ecran):
    onglet = ecran._tabs[0]
    onglet.show()
    onglet._preview.resize(760, 460)
    onglet._preview.refresh()
    return onglet


def test_the_plus_adds_a_sheet_and_the_minus_removes_one(session, papier):
    session.set_layout(cols=6, rows=5, panels=1)
    assert papier._preview._minus == [], "une feuille seule ne s'enlève pas"

    papier._preview._plus.click()
    assert session.panels == 2
    assert len(papier._preview._minus) == 2, "un bouton de retrait par feuille"

    papier._preview._minus[0].click()
    assert session.panels == 1


def test_the_sheet_count_stays_between_one_and_five(session, papier):
    """Cinq A2 font déjà deux mètres de large : au-delà, ce n'est plus un poster
    qu'on accroche."""
    session.set_layout(cols=6, rows=5, panels=1)
    for _ in range(10):
        papier._preview._plus.click()
    assert session.panels == 5
    assert not papier._preview._plus.isEnabled()

    for _ in range(10):
        if papier._preview._minus:
            papier._preview._minus[0].click()
    assert session.panels == 1


def test_the_standard_moved_to_the_left_of_the_sheet(session, papier):
    """Les feuilles s'ajoutent à droite : l'étalon y aurait été poussé plus loin
    à chaque clic."""
    from pokemon_mosaic.ui.page_preview import GAP

    session.set_layout(cols=6, rows=5, panels=2)
    feuille, carte, etiquette = papier._preview.rects()
    assert carte.right() <= feuille.left() - GAP + 0.5
    assert etiquette.right() <= feuille.left() - GAP + 0.5
    assert carte.left() >= 0 and etiquette.left() >= 0


def test_the_plus_sits_to_the_right_of_the_sheet(session, papier):
    session.set_layout(cols=6, rows=5, panels=2)
    feuille, _, _ = papier._preview.rects()
    assert papier._preview._plus.x() >= feuille.right()
    assert (papier._preview._plus.x() + papier._preview._plus.width()
            <= papier._preview.width())


def test_the_minus_buttons_fit_in_the_existing_gap(session, papier):
    """⚠️ Leur hauteur entre dans l'écart entre la feuille et sa cote :
    l'agrandir éloignerait la cote de ce qu'elle mesure."""
    from pokemon_mosaic.ui.page_preview import COTE, GUTTER

    session.set_layout(cols=6, rows=5, panels=3)
    feuille, _, _ = papier._preview.rects()
    ligne_de_cote = feuille.bottom() + GUTTER * COTE
    for bouton in papier._preview._minus:
        assert bouton.y() >= feuille.bottom()
        assert bouton.y() + bouton.height() <= ligne_de_cote + 0.5


def test_one_arrow_spans_every_sheet(session, papier):
    """Une seule cote pour l'ensemble, et non une par feuille : c'est la
    largeur du poster qu'on veut lire, pas celle d'un morceau."""
    from pokemon_mosaic.layout import paper_size_mm

    session.set_layout(cols=6, rows=5, panels=3)
    feuille, _, _ = papier._preview.rects()
    largeur_mm, _ = papier._preview._sheet_mm()
    assert largeur_mm == paper_size_mm(session.paper, session.landscape)[0] * 3
    # La flèche est tracée d'un bord à l'autre de ce rectangle unique.
    assert feuille.width() > 0


def test_an_extra_sheet_only_adds_room(session, papier):
    """⚠️ Ajouter une feuille refusait de laisser passer quand les colonnes ne
    s'y divisaient pas, et la mosaïque cessait d'être dessinée. Une feuille de
    plus ne veut plus dire qu'une chose : de la place en plus."""
    session.set_layout(cols=21, rows=21, panels=1)
    assert papier.is_valid()

    papier._preview._plus.click()
    assert session.panels == 2
    assert papier.is_valid(), "21 colonnes sur 2 feuilles reste une mise en page"


def test_the_mosaic_hugs_the_left_edge(qt_app, session):
    """La place en trop est ce qu'apporte la feuille suivante : elle doit se
    voir d'un bloc, du côté où l'on ajoutera la prochaine."""
    from PySide6.QtGui import QColor

    from pokemon_mosaic.ui.page_preview import PagePreview

    session.set_layout(cols=4, rows=5, panels=2)
    vue = PagePreview(session)
    vue.set_show_grid(True)
    vue.resize(760, 460)
    feuille, _, _ = vue.rects()
    image = vue.grab().toImage()

    milieu_y = int(feuille.center().y())
    gauche = QColor(image.pixel(int(feuille.left()) + 3, milieu_y))
    droite = QColor(image.pixel(int(feuille.right()) - 3, milieu_y))
    assert gauche.blue() > gauche.red(), "le bord gauche doit porter des cartes"
    assert droite.red() >= droite.blue(), "le bord droit doit rester du papier nu"


def test_the_hint_says_where_the_card_actually_is(session, papier):
    """L'étalon est passé à gauche : la phrase renvoyait à droite, où il n'y a
    plus qu'un bouton « + »."""
    feuille, carte, _ = papier._preview.rects()
    assert carte.right() < feuille.left()


def test_no_tab_blocks_on_the_sheet_count_any_more(session, ecran):
    """Aucune combinaison de feuilles n'est fautive : c'est la carte qui se plie
    à la feuille, pas les colonnes."""
    session.set_layout(cols=21, rows=21, panels=2)
    ecran._list.setCurrentRow(ecran._row_of(0))
    assert ecran._tabs[0].is_valid()
    assert ecran.can_advance()


def test_the_orientation_moved_to_the_paper_tab(session, ecran):
    """L'orientation décrit la feuille : elle n'avait rien à voir avec la
    finesse d'impression."""
    papier = ecran._tabs[0]
    assert hasattr(papier, "_landscape")
    assert not hasattr(papier, "_panels"), "le nombre de feuilles est passé au « + »"

    papier._landscape.setChecked(True)
    assert session.landscape
    papier._landscape.setChecked(False)
    assert not session.landscape
    assert not hasattr(papier, "_dpi"), "la finesse est passée à l'export"


def test_a_cut_never_falls_on_a_card_whatever_the_grid(session):
    """⚠️ La règle qui tient tout, vue depuis la mise en page de l'écran."""
    from pokemon_mosaic.layout import grid_geometry, mm_to_pixels, paper_size_mm

    for panneaux in range(1, 6):
        for cols, rows in ((7, 3), (21, 21), (5, 4), (13, 9)):
            paper = paper_size_mm("A3")
            g = grid_geometry(paper, panneaux, cols, rows, 713 / 984, 300)
            paper_w = mm_to_pixels(paper[0], 300)
            assert g.span(g.per_panel) <= paper_w, (panneaux, cols, rows)
            assert g.per_panel * panneaux >= cols, "des colonnes sans feuille"


# --- L'écran montre ce que l'imprimante fera --------------------------------

def test_the_previews_use_the_printing_resolution(qt_app, session):
    """⚠️ Le dessin tournait à 72 dpi et l'export à celle des réglages : les
    arrondis en pixels ne donnaient pas le même nombre de cartes par feuille —
    49 161 combinaisons en désaccord sur les sept formats."""
    from pokemon_mosaic.export import PosterSettings, plan_poster
    from pokemon_mosaic.ui.wireframe import WireframeView

    session.set_layout(paper="A6", cols=1, rows=14, panels=1, dpi=300)
    vue = WireframeView(session)
    vue.resize(400, 500)
    vue.grab()

    import numpy as np

    grille = np.zeros((session.rows, session.cols), np.int16)
    plan = plan_poster(grille, session.card_set,
                       PosterSettings(paper=session.paper, dpi=session.dpi,
                                      panels=session.panels))
    assert vue._per_panel == plan.cards_per_panel


def test_the_drawn_columns_restart_on_each_sheet(qt_app, session):
    """⚠️ L'export fait repartir chaque feuille de son bord ; le dessin posait
    les colonnes à la file. Il montrait donc une carte à cheval sur la coupe là
    où le poster n'en a pas."""
    from pokemon_mosaic.ui.wireframe import WireframeView

    session.set_layout(paper="A4", cols=30, rows=4, panels=2, dpi=300)
    vue = WireframeView(session)
    vue.resize(600, 400)
    vue.grab()

    geometrie = vue._geometry
    _, _, (total_w, _), (card_w, _) = geometrie
    feuille_w = total_w / 2
    par_feuille = vue._per_panel

    # La première colonne de la seconde feuille tombe pile sur son bord.
    assert vue.column_offset(par_feuille, geometrie) == pytest.approx(feuille_w)
    # Et aucune colonne ne chevauche la coupe.
    for col in range(session.cols):
        gauche = vue.column_offset(col, geometrie)
        assert not (gauche < feuille_w < gauche + card_w), col


def test_clicks_still_land_on_the_right_cell_across_sheets(qt_app, session):
    """Les colonnes n'étant plus à pas constant, le clic ne peut plus se déduire
    d'une division."""
    from pokemon_mosaic.ui.wireframe import WireframeView

    session.set_layout(paper="A4", cols=30, rows=4, panels=2, dpi=300)
    vue = WireframeView(session)
    vue.resize(600, 400)
    vue.grab()

    scale, _, _, (card_w, card_h) = vue._geometry
    gx, gy = vue._grid_origin(vue._geometry)
    for col in (0, vue._per_panel - 1, vue._per_panel, session.cols - 1):
        x = gx + (vue.column_offset(col, vue._geometry) + card_w / 2) * scale
        y = gy + card_h * scale * 1.5
        assert vue.cell_at(x, y) == (1, col), col


# --- L'onglet de la taille des cartes ---------------------------------------

@pytest.fixture
def cartes(session, ecran):
    onglet = ecran._tabs[2]
    onglet._preview.resize(700, 460)
    return onglet


def test_the_card_size_starts_automatic(session, cartes):
    """La plus grande taille qui fasse tenir la grille, tant qu'on n'y touche
    pas : aucun avertissement avant que l'utilisateur n'ait rien décidé."""
    session.set_layout(cols=4, rows=5)
    assert session.card_width_mm is None
    assert cartes._auto.isChecked()
    assert not cartes._width.isEnabled()
    assert cartes.is_valid()
    assert cartes._status.property("role") == "ok"


def test_leaving_automatic_keeps_what_was_shown(session, cartes):
    """Partir d'autre chose ferait sauter le dessin sous les yeux."""
    session.set_layout(cols=4, rows=5)
    montre = cartes._width.value()
    cartes._auto.setChecked(False)
    assert session.card_width_mm == pytest.approx(montre, abs=0.2)
    assert cartes._width.isEnabled()


def test_the_real_card_button_fixes_the_width(session, cartes):
    from pokemon_mosaic.layout import REAL_CARD_MM

    cartes._real_card.click()
    assert session.card_width_mm == pytest.approx(REAL_CARD_MM[0])
    assert not cartes._auto.isChecked()


def test_a_card_too_big_is_refused_with_its_numbers(session, cartes, ecran):
    """441 cartes à taille réelle ne tiennent pas sur un A2 : on le dit, et on
    ne passe pas."""
    session.set_layout(cols=11, rows=13, paper="A2", panels=1)
    cartes._real_card.click()

    assert not cartes.is_valid()
    assert cartes._status.property("role") == "error"
    assert "63" in cartes._status.text()

    ecran._list.setCurrentRow(ecran._row_of(2))
    assert not ecran.can_advance()


def test_the_paper_tab_only_talks_about_paper(session, ecran):
    """⚠️ Le résumé annonçait la taille des cartes et de la mosaïque : ni l'une
    ni l'autre ne se règle ici, ni ne se voit depuis que la grille n'y est plus
    dessinée, et un format hors catalogue laissait un trou là où le nom devait
    aller. Les pixels, eux, dépendent d'une finesse partie à l'export."""
    session.set_layout(cols=5, rows=4, paper="A4", panels=2)
    resume = ecran._tabs[0]._summary.text()
    assert "px" not in resume and "carte" not in resume.lower()
    assert "21.0 × 29.7 cm" in resume, resume
    assert "42.0 × 29.7 cm" in resume, "la surface totale suit les feuilles"


def test_the_covered_share_counts_the_gaps(session, ecran):
    """La mosaïque n'est pas dessinée ici, mais c'est bien cette surface
    qu'elle couvrira : les écarts en font partie, et le blanc qui reste se
    compte en feuilles achetées."""
    session.set_layout(cols=5, rows=4, paper="A4", panels=2,
                       card_width_mm=30.0, card_gap_mm=0.0)
    serre = ecran._tabs[0]._warnings.text()
    session.set_layout(card_gap_mm=5.0)
    assert ecran._tabs[0]._warnings.text() != serre
    assert "%" in serre


def test_the_shapes_list_only_opens_on_demand(cartes):
    """Vide, elle laissait un rectangle noir sur un quart du panneau."""
    assert not cartes._shapes.isVisibleTo(cartes)
    cartes._show_shapes.click()
    assert cartes._shapes.isVisibleTo(cartes)


def test_a_size_where_nothing_fits_says_so(session, cartes):
    """La liste vide était un rectangle noir sans explication."""
    session.set_layout(cols=5, rows=4, paper="A5", card_width_mm=2000.0)
    cartes._show_shapes.click()
    assert cartes._shapes.count() == 0
    assert not cartes._shapes.isVisibleTo(cartes)
    assert "Aucune" in cartes._shapes_hint.text()


def test_the_shapes_that_would_fit_are_listed_on_demand(session, cartes):
    """⚠️ **La liste reste après qu'on a choisi.** Elle s'effaçait dès que la
    grille tenait — c'est-à-dire juste après un double-clic —, et comparer deux
    propositions demandait de rouvrir la liste entre chacune."""
    session.set_layout(cols=11, rows=13, paper="A2")
    cartes._real_card.click()
    assert cartes._show_shapes.isEnabled()

    cartes._show_shapes.click()
    assert cartes._shapes.count() > 0
    from PySide6.QtCore import Qt

    cols, rows = cartes._shapes.item(0).data(Qt.UserRole)
    combien = cartes._shapes.count()
    cartes._apply_shape(cartes._shapes.item(0))
    assert (session.cols, session.rows) == (cols, rows)
    assert cartes.is_valid(), "la forme proposée doit tenir"
    assert cartes._shapes.count() == combien, "la liste a disparu sous le clic"


def test_the_gap_shrinks_the_cards_in_automatic(session, cartes):
    """L'écart prend de la place : les cartes la cèdent."""
    session.set_layout(cols=5, rows=5, card_gap_mm=0.0)
    sans = cartes._width.value()
    session.set_layout(card_gap_mm=3.0)
    assert cartes._width.value() < sans


def test_the_gap_is_in_millimetres_like_everything_else(cartes):
    """La même unité que la carte et la feuille, seule mesurable sur le poster
    imprimé. L'unité est dans l'intitulé : le champ n'est plus une boîte à
    suffixe mais un grand nombre, comme les dimensions de la grille."""
    assert cartes._gap._title.text().endswith("(mm)")
    assert cartes._width._title.text().endswith("(mm)")


def test_the_card_settings_are_as_big_as_the_grid_dimensions(cartes, ecran):
    """Deux réglages du même ordre : ce qu'on met dans la case, après la taille
    de la grille. Des boîtes de vingt pixels les faisaient passer pour des
    détails de formulaire."""
    from pokemon_mosaic.ui.big_spin import _BigSpinBase

    for champ in (cartes._width, cartes._gap):
        assert isinstance(champ, _BigSpinBase)
    assert cartes._width.height() >= ecran._tabs[1]._cols.height() - 2


def posed(session):
    """Un onglet seul, dimensionné et affiché : dans la pile de l'écran, il ne
    reçoit aucune géométrie tant que l'étape n'est pas montrée."""
    from pokemon_mosaic.ui.layout_tabs import CardSizeTab

    onglet = CardSizeTab(session)
    onglet.resize(900, 600)
    onglet.show()
    return onglet


def test_the_real_card_button_sits_under_the_width(session):
    """Il se lit comme une valeur possible du champ qu'il remplit."""
    onglet = posed(session)
    bouton = onglet._real_card.mapTo(onglet, onglet._real_card.rect().topLeft())
    champ = onglet._width.mapTo(onglet, onglet._width.rect().bottomLeft())
    assert bouton.y() >= champ.y() - 2
    assert abs(bouton.x() - champ.x()) < 20, "sous le champ, pas à côté"


def test_the_shapes_button_is_up_with_the_settings_it_corrects(session):
    """En bas, la liste poussait la grille hors de l'écran au moment précis où
    l'on voulait la regarder changer."""
    onglet = posed(session)
    bouton = onglet._show_shapes.mapTo(onglet, onglet._show_shapes.rect().center())
    dessin = onglet._preview.mapTo(onglet, onglet._preview.rect().topLeft())
    assert bouton.y() < dessin.y()


def test_the_placement_tab_is_a_placeholder(ecran):
    """Le voir vide dit mieux ce qui viendra qu'une absence qu'on prendrait
    pour un oubli."""
    emplacement = ecran._tabs[3]
    assert emplacement.is_valid(), "un jalon ne bloque personne"
    assert "À venir" in emplacement._todo.text()
