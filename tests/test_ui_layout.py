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
    from pokemon_mosaic.ui.layout_step import READY, state_icon

    attendu = state_icon(READY, ecran.palette()).pixmap(22, 22).toImage()
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

    ecran.advance()                         # « Suivant » ouvre la famille
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


# --- Le parcours se fait dans l'ordre ---------------------------------------

def test_the_tabs_ahead_are_locked_until_suivant_opens_them(session, ecran):
    """⚠️ Sauter d'un clic à l'onglet des écarts sans avoir vu les pages ni la
    grille, c'est régler la taille des cartes pour un papier qu'on n'a pas
    choisi : les onglets qui suivent dépendent de ce que ceux d'avant décident,
    et rien à l'écran ne le disait."""
    from PySide6.QtCore import Qt

    ecran.show()
    session.auto_place_empty_cells()
    assert ecran._list.item(0).flags() & Qt.ItemIsEnabled
    for position in (1, 2, 3):
        assert not ecran._list.item(ecran._row_of(position)).flags() & Qt.ItemIsEnabled
        assert "Suivant" in ecran._list.item(ecran._row_of(position)).toolTip()

    ecran.advance()                       # une partie validée, une d'ouverte
    assert ecran._list.item(ecran._row_of(1)).flags() & Qt.ItemIsEnabled
    assert not ecran._list.item(ecran._row_of(2)).flags() & Qt.ItemIsEnabled


def test_a_locked_tab_does_not_wave_its_badge(session, ecran):
    """Qt éteint le libellé d'une ligne désactivée, mais pas une icône que nous
    dessinons nous-mêmes : à pleine intensité, elle réclamait l'attention pour
    une partie sur laquelle on ne peut rien."""
    from pokemon_mosaic.ui.layout_step import state_icon

    ecran.show()
    verrouille = ecran._list.item(ecran._row_of(2)).icon().pixmap(22, 22).toImage()
    from pokemon_mosaic.ui.layout_step import PENDING

    ouvert = state_icon(PENDING, ecran.palette()).pixmap(22, 22).toImage()
    assert verrouille != ouvert

    ecran.advance()
    session.auto_place_empty_cells()
    ecran.advance()                       # l'onglet 2 s'ouvre
    assert ecran._list.item(ecran._row_of(2)).icon().pixmap(22, 22).toImage() == ouvert


def test_clicking_a_locked_tab_does_nothing(session, ecran):
    """Le verrou tient au clic, pas seulement à l'œil."""
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    ecran.resize(1000, 700)
    ecran.show()
    rect = ecran._list.visualItemRect(ecran._list.item(ecran._row_of(2)))
    QTest.mouseClick(ecran._list.viewport(), Qt.LeftButton, Qt.NoModifier,
                     rect.center())

    assert ecran._current_tab() == 0
    assert ecran._pages.currentIndex() == 0


def test_going_back_and_changing_your_mind_never_locks_again(session, ecran):
    """Une seule visite validée suffit, définitivement : le verrou ne sert
    qu'au premier passage, et c'est la pastille qui dit si la partie tient
    toujours debout."""
    from PySide6.QtCore import Qt

    ecran.show()
    session.auto_place_empty_cells()
    ecran.advance()                       # pages validées
    ecran.advance()                       # taille validée
    assert ecran._list.item(ecran._row_of(2)).flags() & Qt.ItemIsEnabled

    ecran._show(0)
    session.set_layout(paper="A6")        # on change d'avis
    session.set_layout(cols=3, rows=3)    # et la grille ne tient plus
    assert not ecran._ready(1), "la pastille, elle, le dit"
    assert ecran._list.item(ecran._row_of(2)).flags() & Qt.ItemIsEnabled


def test_a_blocked_tab_wears_a_red_cross(session, ecran):
    """⚠️ **La croix est réservée à ce qui bloque.** Une partie qu'on n'a pas
    encore validée est ambre — pas encore fait n'est pas une faute —, et ne
    passe au rouge que si son contenu ne tient pas debout."""
    from PySide6.QtCore import Qt

    from pokemon_mosaic.ui.layout_step import (
        BLOCKED,
        PENDING,
        READY,
        STATE_SIGNS,
    )

    ecran.show()

    def etat_affiche(position):
        return ecran._list.item(ecran._row_of(position)).data(Qt.UserRole + 2)

    # Au premier passage, rien n'est fait mais rien ne bloque.
    session.auto_place_empty_cells()
    assert ecran._state(1) == PENDING and etat_affiche(1) == PENDING

    # Des cases vides à placer : la grille ne laisse pas passer.
    session.set_layout(cols=6, rows=6)
    assert session.missing_empty_cells() > 0
    assert ecran._state(1) == BLOCKED and etat_affiche(1) == BLOCKED

    # Et des cartes qui ne tiennent pas dans les pages, à l'onglet des tailles.
    session.set_layout(paper="A2", cols=11, rows=13, card_width_mm=63.0)
    assert ecran._state(2) == BLOCKED

    session.set_layout(card_width_mm=None)
    session.auto_place_empty_cells()
    ecran.advance()
    assert ecran._state(0) == READY and etat_affiche(0) == READY
    assert STATE_SIGNS[BLOCKED] == "✕"


def test_the_state_colours_the_frame_not_the_words(session, ecran):
    """⚠️ **Le cadre porte la couleur, pas le texte.** Un libellé coloré perdait
    le contraste que le mode lui donne ; le fond et le contour, eux, ne font que
    teinter le gris de départ — et le contour plus fort que le fond."""
    from pokemon_mosaic.ui import theme
    from pokemon_mosaic.ui.layout_step import BLOCKED, PENDING

    palette = ecran.palette()
    ecran.show()
    # Le libellé garde la couleur du mode, quel que soit l'état.
    for position in range(4):
        item = ecran._list.item(ecran._row_of(position))
        assert not item.foreground().color().isValid() or \
            item.foreground().color() == palette.text().color()

    attendu = theme.tab_box(BLOCKED, palette)
    autre = theme.tab_box(PENDING, palette)
    assert attendu[0] != autre[0] and attendu[1] != autre[1]

    # Le contour emprunte plus à l'état que le fond : on compare leur distance
    # au gris de départ.
    from PySide6.QtGui import QColor

    depart = QColor(theme.colours(palette)["button_bg"])
    bord = QColor(theme.colours(palette)["button_border"])
    fond, contour, _ = attendu

    def ecart(a, b):
        return (abs(a.red() - b.red()) + abs(a.green() - b.green())
                + abs(a.blue() - b.blue()))

    teinte = QColor(theme.colours(palette)[BLOCKED])
    assert (ecart(QColor(contour), bord) / max(1, ecart(teinte, bord))
            > ecart(QColor(fond), depart) / max(1, ecart(teinte, depart)))


def test_the_badges_are_repainted_when_the_mode_changes(qt_app, session, ecran):
    """⚠️ Une pastille est une **image posée** : peinte une fois avec la couleur
    du mode d'alors, elle reste ambre foncé sur une fenêtre devenue sombre. Le
    cadre, lui, se relit à chaque dessin et suit tout seul."""
    from pokemon_mosaic.ui import theme

    ecran.show()
    qt_app.setPalette(theme.qt_palette(False))
    qt_app.processEvents()
    clair = ecran._list.item(0).icon().pixmap(22, 22).toImage()

    qt_app.setPalette(theme.qt_palette(True))
    qt_app.processEvents()
    sombre = ecran._list.item(0).icon().pixmap(22, 22).toImage()
    assert clair != sombre, "la pastille est restée dans l'autre mode"


def test_a_locked_tab_stays_grey(session, ecran):
    """Sa couleur dirait un état sur lequel on ne peut rien."""
    from pokemon_mosaic.ui import theme
    from pokemon_mosaic.ui.layout_step import BLOCKED

    palette = ecran.palette()
    couleurs = theme.colours(palette)
    fond, contour, _ = theme.tab_box(BLOCKED, palette, locked=True)
    assert (fond, contour) == (couleurs["button_off_bg"],
                               couleurs["button_off_border"])


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


def test_every_way_of_resizing_the_grid_clears_the_holes(session, ecran):
    """⚠️ Les cases vides sont posées **sur une grille donnée** : sur une autre,
    elles tombent à des endroits qui ne veulent plus rien dire, quand elles n'en
    sortent pas carrément. On vérifie les quatre chemins qui redimensionnent."""
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QListWidgetItem

    grille = ecran._tabs[1]
    ecran.show()

    def pose():
        session.set_layout(cols=6, rows=5)   # 30 cases pour 20 cartes
        session.auto_place_empty_cells()
        assert session.empty_cells(), "il faut des trous pour éprouver la règle"

    # 1. Les champs de l'onglet.
    pose()
    grille._cols.setValue(7)
    assert session.empty_cells() == []

    # 2. Une proposition appliquée au double-clic.
    pose()
    grille._apply_suggestion(grille._suggestions.item(0))
    assert session.empty_cells() == []

    # 3. Une forme proposée par l'onglet des tailles.
    pose()
    item = QListWidgetItem("")
    item.setData(Qt.UserRole, (4, 5))
    ecran._tabs[2]._apply_shape(item)
    assert session.empty_cells() == []

    # 4. La grille proposée d'office au premier passage.
    pose()
    grille._auto_fit_pending = True
    grille._auto_fit()
    assert (session.cols, session.rows) != (6, 5)
    assert session.empty_cells() == []


def test_the_holes_survive_what_does_not_touch_the_grid(session, ecran):
    """Changer de papier, de feuille ou de taille de carte ne déplace aucune
    case : les effacer serait une punition."""
    session.set_layout(cols=6, rows=5)
    session.auto_place_empty_cells()
    poses = session.empty_cells()

    session.set_layout(paper="A3")
    session.set_layout(panels=2)
    session.set_layout(card_width_mm=30.0)
    session.set_layout(card_gap_mm=2.0)
    assert session.empty_cells() == poses


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


def test_the_paper_tab_says_nothing_of_the_white_that_remains(session, ecran):
    """⚠️ Le message donnait la part de papier couverte et prévenait que le
    reste sortirait blanc. Il disait vrai, mais s'affichait dès qu'on ajoutait
    une feuille — au moment précis où l'on demande de la place — et il fallait
    le lire à chaque fois pour n'en rien faire."""
    session.set_layout(panels=3, cols=6, rows=5)
    assert ecran._tabs[0]._warnings.text() == ""


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


def test_the_cut_stands_out_on_everything_it_crosses(qt_app):
    """⚠️ Un seul trait ne pouvait pas convenir partout : tiré dans la couleur
    du texte, il passait en blanc sur une mosaïque bleu très clair. Les deux
    tons sont la convention des repères d'imprimerie — l'un des deux ressort
    quel que soit le fond, cases vides comprises."""
    from pokemon_mosaic.ui.wireframe import (
        CARD_FILL,
        CUT_OVER,
        CUT_UNDER,
        EMPTY_FILL,
        PAPER,
    )

    def ecart(a, b):
        return (abs(a.red() - b.red()) + abs(a.green() - b.green())
                + abs(a.blue() - b.blue()))

    reference = ecart(EMPTY_FILL, CARD_FILL)
    for fond in (CARD_FILL, EMPTY_FILL, PAPER):
        lisible = max(ecart(fond, CUT_UNDER), ecart(fond, CUT_OVER))
        assert lisible > reference, f"la coupe se perd sur {fond.name()}"


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
    suit plus la palette de sélection de Qt, donc il se vérifie.

    Le fond de l'onglet ouvert est maintenant celui de son **état**, teinté à
    partir du gris de départ : c'est `test_ui_theme` qui le mesure pour les
    trois états et les deux modes. Ne reste ici que le rappel du lien.
    """
    from test_ui_theme import contraste

    from pokemon_mosaic.ui import theme

    for mode, palette_table in (("light", theme.PALETTE_LIGHT),
                                ("dark", theme.PALETTE_DARK)):
        palette = theme.qt_palette(mode == "dark")
        fond, _, _ = theme.tab_box("ok", palette, selected=True)
        assert contraste(palette_table["text"], fond) >= 4.5, mode


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
    """⚠️ La règle qui tient tout, vue depuis la mise en page de l'écran —
    **dans les deux sens** depuis que les feuilles se posent aussi en lignes."""
    from pokemon_mosaic.layout import grid_geometry, mm_to_pixels, paper_size_mm

    for panneaux in range(1, 6):
        for lignes in range(1, 4):
            for cols, rows in ((7, 3), (21, 21), (5, 4), (13, 9)):
                paper = paper_size_mm("A3")
                g = grid_geometry(paper, panneaux, cols, rows, 713 / 984, 300,
                                  panel_rows=lignes)
                cas = (panneaux, lignes, cols, rows)
                paper_w = mm_to_pixels(paper[0], 300)
                paper_h = mm_to_pixels(paper[1], 300)
                # Ce qu'une feuille porte tient sur elle, en largeur comme en
                # hauteur : la coupe tombe donc sur un bord de carte.
                assert g.span(g.per_panel) <= paper_w, cas
                hauteur = (g.rows_per_panel * g.card_h
                           + max(0, g.rows_per_panel - 1) * g.gap)
                assert hauteur <= paper_h, cas
                assert g.per_panel * panneaux >= cols, "des colonnes sans feuille"
                assert g.rows_per_panel * lignes >= rows, "des lignes sans feuille"


def test_sheet_rows_make_the_cards_bigger(session):
    """Une ligne de feuilles de plus, c'est de la place en plus : la carte n'a
    plus à rétrécir pour que toute la hauteur tienne sur une seule."""
    from pokemon_mosaic.layout import grid_geometry, paper_size_mm

    paper = paper_size_mm("A4")
    seule = grid_geometry(paper, 1, 4, 20, 713 / 984, 300)
    deux = grid_geometry(paper, 1, 4, 20, 713 / 984, 300, panel_rows=2)
    assert deux.card_h > seule.card_h


def test_a_card_wider_than_the_sheet_never_fits(session):
    """⚠️ Zéro carte par feuille, et surtout pas un plancher à un : une carte de
    deux mètres en logeait « une », et la grille d'une colonne passait pour
    tenable."""
    from pokemon_mosaic.layout import grid_fits, grid_geometry, paper_size_mm

    paper = paper_size_mm("A4")
    g = grid_geometry(paper, 1, 1, 1, 713 / 984, 300, card_width_mm=2000.0)
    assert g.per_panel == 0 and g.rows_per_panel == 0
    assert not grid_fits(1, 1, 1, g)


def test_the_cut_is_drawn_in_two_tones_over_the_mosaic(session, ecran):
    """⚠️ Le trait passait dans la couleur du texte — blanc sur une mosaïque
    bleu très clair. On vérifie qu'il reste, sur la mosaïque elle-même, un ton
    clair **et** un ton sombre le long de la coupe."""
    from PySide6.QtGui import QColor

    papier = ecran._tabs[1]                  # la mosaïque y est dessinée
    papier.resize(700, 560)
    papier.show()
    session.set_layout(paper="A4", cols=8, rows=8, panels=2, panel_rows=1)
    papier._preview.refresh()

    pixmap = papier._preview.grab()
    image, ratio = pixmap.toImage(), pixmap.devicePixelRatio()
    feuille = papier._preview.rects()[0]
    x = feuille.center().x()
    tons = [QColor(image.pixel(int(x * ratio), int(y * ratio))).lightness()
            for y in range(int(feuille.top()) + 8, int(feuille.bottom()) - 8)]
    assert max(tons) > 230, "il manque le ton clair"
    assert min(tons) < 60, "il manque le ton sombre"


def test_each_sheet_carries_its_number(session, ecran):
    """Quinze feuilles étalées sur une table ne disent pas d'elles-mêmes
    laquelle va où : le numéro est celui du nom de fichier."""
    from PySide6.QtGui import QColor

    onglet = ecran._tabs[1]
    onglet.resize(700, 560)
    onglet.show()

    def sombres():
        pixmap = onglet._preview.grab()
        image, ratio = pixmap.toImage(), pixmap.devicePixelRatio()
        feuille = onglet._preview.rects()[0]
        return sum(
            1
            for x in range(int(feuille.left()) + 2, int(feuille.left()) + 40, 2)
            for y in range(int(feuille.top()) + 2, int(feuille.top()) + 30, 2)
            if QColor(image.pixel(int(x * ratio), int(y * ratio))).lightness() < 80
        )

    session.set_layout(paper="A4", cols=8, rows=8, panels=1, panel_rows=1)
    onglet._preview.refresh()
    seule = sombres()

    session.set_layout(panels=2)
    onglet._preview.refresh()
    assert sombres() > seule, "une seule feuille n'a pas de numéro à porter"


def test_the_number_steps_aside_when_the_sheet_has_a_margin(session, ecran):
    """Le morceau ne remplit presque jamais la feuille : le numéro se glisse
    dans ce qui reste plutôt que de couvrir une carte."""
    from PySide6.QtCore import QRectF

    from pokemon_mosaic.ui.wireframe import badge_rect

    feuille = QRectF(0, 0, 300, 400)
    au_large = QRectF(0, 0, 300, 300)        # 100 px libres dessous
    rect, sur_mosaique = badge_rect(feuille, au_large)
    assert not sur_mosaique
    assert not rect.intersects(au_large)

    plein = QRectF(0, 0, 300, 400)           # la feuille est pleine
    rect, sur_mosaique = badge_rect(feuille, plein)
    assert sur_mosaique, "sans marge, le numéro prend un fond"


# --- L'écran montre ce que l'imprimante fera --------------------------------

def test_the_screen_and_the_export_place_each_piece_at_the_same_spot(
        qt_app, session):
    """⚠️ **La leçon déjà payée deux fois** : tout aperçu d'un résultat imprimé
    doit placer ses cartes là où l'export les écrira. L'écran lit
    `panel_position_mm`, l'export son propre plan — on vérifie qu'ils tombent
    d'accord, déplacement ou non, y compris quand la grille déborde de sa
    feuille."""
    import numpy as np

    from pokemon_mosaic.export import PosterSettings, plan_poster
    from pokemon_mosaic.layout import MM_PER_INCH

    def reglages(deplacements):
        return PosterSettings(
            paper=session.paper, paper_size_mm=session.paper_size_mm,
            landscape=session.landscape, dpi=session.dpi,
            panels=session.panels, panel_rows=session.panel_rows,
            card_width_mm=session.card_width_mm,
            card_gap_mm=session.card_gap_mm, panel_offsets=deplacements)

    # Le dernier cas fige la carte pour que la grille **déborde** : c'est là que
    # les deux calculs de marge divergeaient.
    for cols, rows, panneaux, lignes, largeur in (
        (5, 4, 2, 1, None), (8, 8, 2, 2, None),
        (3, 30, 1, 1, None), (7, 5, 3, 2, None), (2, 9, 1, 1, 60.0),
    ):
        session.set_layout(paper="A5", cols=cols, rows=rows, panels=panneaux,
                           panel_rows=lignes, dpi=150, card_width_mm=largeur)
        grille = np.zeros((rows, cols), np.int16)
        paper_w, paper_h = session.paper_mm()
        en_mm = MM_PER_INCH / session.dpi

        # D'abord tel quel — c'est le placement **par défaut** qu'on compare —,
        # puis une feuille déplacée à la main.
        for bouger in (False, True):
            if bouger:
                session.move_panel(0, 3.0, 1.0)
            plan = plan_poster(grille, session.card_set,
                               reglages(dict(session.panel_offsets)))
            for index in range(session.panel_count()):
                ligne, colonne = divmod(index, session.panels)
                premiere_l = ligne * plan.rows_per_panel
                premiere_c = colonne * plan.cards_per_panel
                if premiere_l >= rows or premiere_c >= cols:
                    continue       # feuille sans carte : rien à comparer
                x, y = plan.card_origin(premiere_l, premiere_c)
                attendu = session.panel_position_mm(index)
                cas = (cols, rows, panneaux, lignes, largeur, index, bouger)
                assert x * en_mm - colonne * paper_w == pytest.approx(
                    attendu[0], abs=0.2), cas
                assert y * en_mm - ligne * paper_h == pytest.approx(
                    attendu[1], abs=0.2), cas


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
    assert vue.cell_origin(0, par_feuille, geometrie)[0] == pytest.approx(
        feuille_w)
    # Et aucune colonne ne chevauche la coupe.
    for col in range(session.cols):
        gauche = vue.cell_origin(0, col, geometrie)[0]
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
        origine = vue.cell_origin(1, col, vue._geometry)
        x = gx + (origine[0] + card_w / 2) * scale
        y = gy + (origine[1] + card_h / 2) * scale
        assert vue.cell_at(x, y) == (1, col), col


def test_the_wireframe_follows_a_moved_piece(qt_app, session):
    """⚠️ **Le fil de fer ignorait les déplacements.** Après avoir tiré un
    morceau, la vue d'exécution montrait la mosaïque à sa place d'origine et
    l'imprimante l'écrivait ailleurs — l'aperçu qui ment, une quatrième fois."""
    from pokemon_mosaic.ui.wireframe import WireframeView

    session.set_layout(paper="A4", cols=5, rows=4, panels=2, dpi=300)
    vue = WireframeView(session)
    vue.resize(600, 400)
    vue.grab()
    par_feuille = vue._per_panel
    avant = vue.cell_origin(0, par_feuille, vue._geometry)

    session.move_panel(1, 40.0, 0.0)
    vue.grab()
    apres = vue.cell_origin(0, par_feuille, vue._geometry)
    assert apres[0] - avant[0] == pytest.approx(40.0, abs=0.5)

    # Et le clic suit le dessin, sans quoi on creuserait une autre case.
    scale, _, _, (card_w, card_h) = vue._geometry
    gx, gy = vue._grid_origin(vue._geometry)
    x = gx + (apres[0] + card_w / 2) * scale
    y = gy + (apres[1] + card_h / 2) * scale
    assert vue.cell_at(x, y) == (0, par_feuille)


def test_the_wireframe_reads_each_piece_once_per_paint(qt_app, session):
    """⚠️ Le lire case par case coûtait une géométrie de grille **complète par
    case** : mesuré, 1,07 s pour dessiner une grille de 200×200 et autant pour
    y placer un clic. On relève les places une fois par calcul de géométrie."""
    from pokemon_mosaic.ui.wireframe import WireframeView

    session.set_layout(paper="A4", cols=12, rows=12, panels=2, dpi=300)
    vue = WireframeView(session)
    vue.resize(600, 400)

    appels = []
    vrai = session.panel_position_mm
    session.panel_position_mm = lambda index: appels.append(index) or vrai(index)
    vue.grab()
    vue.cell_at(300, 200)
    session.panel_position_mm = vrai

    assert len(appels) <= session.panel_count(), (
        f"{len(appels)} lectures pour {session.panel_count()} feuilles")


def test_clicks_land_right_across_sheet_rows_too(qt_app, session):
    """⚠️ Les lignes ne sont pas plus à pas constant que les colonnes depuis
    qu'une ligne de feuilles repart de son bord haut."""
    from pokemon_mosaic.ui.wireframe import WireframeView

    session.set_layout(paper="A4", cols=4, rows=20, panels=1, panel_rows=2,
                       dpi=300)
    vue = WireframeView(session)
    vue.resize(600, 500)
    vue.grab()

    scale, _, _, (card_w, card_h) = vue._geometry
    gx, gy = vue._grid_origin(vue._geometry)
    par_feuille = vue._rows_per_panel
    assert 1 <= par_feuille < session.rows, "les lignes se répartissent"
    for row in (0, par_feuille - 1, par_feuille, session.rows - 1):
        origine = vue.cell_origin(row, 1, vue._geometry)
        x = gx + (origine[0] + card_w / 2) * scale
        y = gy + (origine[1] + card_h / 2) * scale
        assert vue.cell_at(x, y) == (row, 1), row


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


def test_a_row_of_sheets_is_added_from_above_the_page(session, ecran):
    """Le « + » du dessus ajoute une ligne, celui de droite une colonne : le
    même geste sur deux axes."""
    from pokemon_mosaic.ui.page_preview import MAX_PANEL_ROWS

    papier = ecran._tabs[0]
    papier.resize(900, 600)
    papier.show()
    apercu = papier._preview

    apercu._plus_row.click()
    assert session.panel_rows == 2
    assert session.panel_count() == 2 * session.panels

    for _ in range(MAX_PANEL_ROWS + 2):
        apercu._plus_row.click()
    assert session.panel_rows == MAX_PANEL_ROWS, "trois A2 superposés font un mur"
    assert not apercu._plus_row.isEnabled()


def test_each_sheet_row_has_its_own_minus_button(session, ecran):
    """Un seul bouton pour l'ensemble ne dirait pas **où** l'on retire."""
    papier = ecran._tabs[0]
    papier.resize(900, 600)
    papier.show()
    apercu = papier._preview
    assert apercu._minus_rows == [], "rien à retirer sur une seule ligne"

    session.set_layout(panel_rows=3)
    apercu.refresh()
    assert len(apercu._minus_rows) == 3
    feuille = apercu.rects()[0]
    for bouton in apercu._minus_rows:
        # ⚠️ Dans la gouttière de la cote, comme les autres entrent dans l'écart
        # sous la feuille : ni sur le papier, ni au-delà de la cote.
        assert bouton.x() + bouton.width() <= feuille.left() + 1
        assert bouton.x() > feuille.left() - 20

    apercu._minus_rows[0].click()
    assert session.panel_rows == 2


def test_the_sheet_rows_show_their_cuts(session, ecran):
    """La feuille dessinée est la somme des feuilles : la coupe entre deux
    lignes s'y voit, faute de quoi on ne saurait pas où l'on colle."""
    papier = ecran._tabs[0]
    papier.resize(900, 600)
    papier.show()
    session.set_layout(panels=1, panel_rows=2)
    papier._preview.refresh()

    pixmap = papier._preview.grab()
    image, ratio = pixmap.toImage(), pixmap.devicePixelRatio()
    feuille = papier._preview.rects()[0]
    interieur = range(int(feuille.left() + 6), int(feuille.right() - 6), 3)

    def encres(y):
        fond = image.pixel(int(feuille.center().x() * ratio),
                           int((feuille.top() + 12) * ratio))
        return sum(1 for x in interieur
                   if image.pixel(int(x * ratio), int(y * ratio)) != fond)

    milieu = feuille.top() + feuille.height() / 2
    assert encres(milieu) > len(interieur) / 3, "la coupe ne se voit pas"
    assert encres(milieu + 12) == 0, "une feuille vide reste vide"


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


# --- L'onglet de l'emplacement ----------------------------------------------

@pytest.fixture
def emplacement(session, ecran):
    onglet = ecran._tabs[3]
    onglet.resize(700, 520)
    onglet.show()
    return onglet


def glisser(onglet, depart, arrivee):
    """Un vrai geste : on saisit la mosaïque, on tire, on lâche."""
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtGui import QMouseEvent

    apercu = onglet._preview

    def evenement(type_, point, boutons):
        return QMouseEvent(type_, QPointF(*point), QPointF(*point),
                           Qt.LeftButton, boutons, Qt.NoModifier)

    apercu.mousePressEvent(evenement(QMouseEvent.Type.MouseButtonPress,
                                     depart, Qt.LeftButton))
    apercu.mouseMoveEvent(evenement(QMouseEvent.Type.MouseMove,
                                    arrivee, Qt.LeftButton))
    apercu.mouseReleaseEvent(evenement(QMouseEvent.Type.MouseButtonRelease,
                                       arrivee, Qt.NoButton))


def test_dragging_moves_the_piece_inside_its_own_sheet(session, emplacement):
    """Le geste : on garde le clic sur la mosaïque et on tire."""
    session.set_layout(paper="A4", cols=4, rows=4, panels=1)
    emplacement.refresh()
    cases = emplacement._preview.grid_cells(emplacement._preview.rects()[0])
    depart = cases[0][2].center()

    glisser(emplacement, (depart.x(), depart.y()), (depart.x() + 30, depart.y()))
    assert session.panel_offsets, "rien n'a bougé"
    assert session.panel_offsets[0][0] > 0


def test_a_piece_never_leaves_its_sheet(session, emplacement):
    """⚠️ Laisser glisser la mosaïque d'une feuille à l'autre remettrait en jeu
    la règle de la coupe à chaque geste."""
    session.set_layout(paper="A4", cols=4, rows=4, panels=2)
    emplacement.refresh()
    cases = emplacement._preview.grid_cells(emplacement._preview.rects()[0])
    depart = cases[0][2].center()

    # On tire très loin à droite : le morceau s'arrête au bord de sa feuille.
    glisser(emplacement, (depart.x(), depart.y()), (depart.x() + 5000, depart.y()))
    libre = session.panel_free_mm(0)
    assert session.panel_offsets[0][0] == pytest.approx(libre[0])

    paper_w = session.paper_mm()[0]
    x, _ = session.panel_position_mm(0)
    assert x <= paper_w, "le morceau est sorti de sa feuille"


def test_clicking_the_blank_of_a_sheet_grabs_nothing(session, emplacement):
    """On ne déplace que ce qu'on voit bouger : le vide d'une feuille
    n'appartient à personne."""
    session.set_layout(paper="A4", cols=2, rows=2, panels=1)
    emplacement.refresh()
    feuille = emplacement._preview.rects()[0]

    glisser(emplacement, (feuille.right() - 4, feuille.bottom() - 4),
            (feuille.left() + 20, feuille.top() + 20))
    assert session.panel_offsets == {}


def test_changing_the_grid_puts_every_piece_back(session, emplacement):
    """⚠️ Une carte plus large, une feuille de plus, un autre format : le
    morceau de chaque feuille n'a plus la même taille, et la place qu'on lui
    avait choisie ne veut plus rien dire."""
    session.set_layout(paper="A4", cols=4, rows=4, panels=1)
    session.move_panel(0, 10.0, 5.0)
    assert session.panel_offsets

    session.set_layout(cols=5)
    assert session.panel_offsets == {}, "les déplacements devaient être défaits"


def test_centring_puts_each_piece_in_the_middle_of_its_sheet(session,
                                                            emplacement):
    """Le geste inverse du glissement : d'un clic, au milieu."""
    session.set_layout(paper="A4", cols=5, rows=4, panels=2)
    emplacement._center.click()

    for index in range(session.panel_count()):
        if not session.panel_carries_cards(index):
            continue
        libre = session.panel_free_mm(index)
        assert session.panel_position_mm(index) == pytest.approx(
            (libre[0] / 2, libre[1] / 2)), index
    assert session.panels_are_centred()


def test_a_sheet_without_cards_is_left_alone(session, emplacement):
    """⚠️ Une feuille qui ne porte aucune carte n'a rien à centrer, et lui
    inventer une position la ferait compter parmi les feuilles déplacées."""
    session.set_layout(paper="A4", cols=2, rows=2, panels=3)
    vides = [index for index in range(session.panel_count())
             if not session.panel_carries_cards(index)]
    assert vides, "il faut une feuille vide pour éprouver la règle"

    emplacement._center.click()
    assert not (set(vides) & set(session.panel_offsets))


def test_the_centring_button_says_when_there_is_nothing_to_do(session,
                                                              emplacement):
    # Deux feuilles : la seconde ne porte qu'une colonne, et a donc de la
    # place à sa droite. Sur une feuille pleine à ras bord, le placement par
    # défaut **est** déjà le centre, et le bouton n'a rien à proposer.
    session.set_layout(paper="A4", cols=5, rows=4, panels=2)
    assert emplacement._center.isEnabled(), "calé à gauche, donc pas centré"

    emplacement._center.click()
    assert not emplacement._center.isEnabled()
    assert "centrés" in emplacement._status.text()

    session.move_panel(1, 0.0, 0.0)
    assert emplacement._center.isEnabled()


def test_the_placement_tab_says_what_it_carries(session, emplacement):
    assert "défaut" in emplacement._status.text()
    assert not emplacement._reset.isEnabled()

    session.move_panel(0, 5.0, 0.0)
    assert "1" in emplacement._status.text()
    assert emplacement._reset.isEnabled()

    emplacement._reset.click()
    assert session.panel_offsets == {}
