"""Tests des liens : modèle, bibliothèque, et respect des contraintes à l'optimisation."""

import random

import numpy as np
import pytest
from test_scoring import make_cards

from pokemon_mosaic.links import Link, LinkLibrary
from pokemon_mosaic.optimize import build_initial_grid, optimize_grid
from pokemon_mosaic.scoring import EMPTY, EdgeDistances


def positions(grid, *indices):
    return [tuple(np.argwhere(grid == i)[0]) for i in indices]


def test_link_needs_at_least_two_cards():
    with pytest.raises(ValueError, match="au moins deux cartes"):
        Link(cards=(3,))


def test_link_rejects_a_repeated_card():
    with pytest.raises(ValueError, match="répétée"):
        Link(cards=(3, 3))


def test_library_refuses_a_card_in_two_active_links():
    library = LinkLibrary()
    library.add(Link(cards=(1, 2)))
    with pytest.raises(ValueError, match="appartiennent déjà"):
        library.add(Link(cards=(2, 5)))


def test_disabled_links_free_their_cards():
    library = LinkLibrary()
    library.add(Link(cards=(1, 2), enabled=False))
    library.add(Link(cards=(2, 5)))
    assert len(library.active) == 1


def test_links_referencing_removed_cards_are_dropped():
    library = LinkLibrary()
    library.add(Link(cards=(1, 2)))
    library.add(Link(cards=(7, 8)))
    kept = library.for_cards({1, 2, 3, 4})
    assert kept.to_groups() == [(1, 2)]


def test_ordered_link_keeps_its_direction():
    cards = make_cards(30)
    distances = EdgeDistances(cards)
    grid = np.arange(30).reshape(5, 6)
    link = Link(cards=(7, 8), ordered=True)
    optimize_grid(grid, distances, {7: link, 8: link}, 8000, random.Random(0))
    (r7, c7), (r8, c8) = positions(grid, 7, 8)
    assert r7 == r8 and c8 == c7 + 1


def test_unordered_link_stays_adjacent_but_may_flip():
    """Sans ordre imposé, les deux cartes restent voisines dans un sens ou l'autre."""
    cards = make_cards(30)
    distances = EdgeDistances(cards)
    grid = np.arange(30).reshape(5, 6)
    link = Link(cards=(7, 8), ordered=False)
    optimize_grid(grid, distances, {7: link, 8: link}, 8000, random.Random(0))
    (r7, c7), (r8, c8) = positions(grid, 7, 8)
    assert r7 == r8 and abs(c8 - c7) == 1


def test_a_link_can_hold_more_than_two_cards():
    cards_set = _card_set(30)
    library = LinkLibrary()
    library.add(Link(cards=(4, 5, 6), ordered=True))
    grid = build_initial_grid(cards_set, (6, 5), library, rng=random.Random(1))
    distances = EdgeDistances(cards_set.cards)
    optimize_grid(grid, distances, library.group_map(), 8000, random.Random(1))
    (r4, c4), (r5, c5), (r6, c6) = positions(grid, 4, 5, 6)
    assert r4 == r5 == r6
    assert (c5, c6) == (c4 + 1, c4 + 2)


def test_optimizer_refuses_a_grid_where_a_link_is_already_broken():
    """L'optimiseur préserve un bloc mais ne sait pas le reconstituer.

    Sans cette garde, la contrainte serait violée en silence jusqu'à l'image finale.
    """
    cards = make_cards(30)
    distances = EdgeDistances(cards)
    grid = np.arange(30).reshape(5, 6)  # coupe le trio 4-5-6 entre deux lignes
    link = Link(cards=(4, 5, 6))
    with pytest.raises(ValueError, match="ne sont pas contiguës"):
        optimize_grid(grid, distances, {i: link for i in (4, 5, 6)}, 100)


def test_unordered_link_is_flipped_when_that_scores_better():
    """Cas construit pour que le sens inverse soit nettement meilleur."""
    from pokemon_mosaic.cards import Card
    from pokemon_mosaic.scoring import grid_score

    def card(index, left, right):
        c = Card(path=f"/fake/{index}.png", index=index,
                 thumbnail=np.zeros((4, 4, 3), np.uint8))
        c.left = np.array(left, float)
        c.right = np.array(right, float)
        c.top = c.bottom = np.zeros(3)
        return c

    # Rangée [X, a, b, Y] : dans ce sens les deux coutures extérieures sont
    # mauvaises ; en inversant a et b, les trois coutures deviennent bonnes.
    cards = [
        card(0, [0, 0, 0], [0, 0, 0]),            # X
        card(1, [255, 255, 255], [10, 10, 10]),   # a
        card(2, [5, 5, 5], [250, 250, 250]),      # b
        card(3, [0, 0, 0], [0, 0, 0]),            # Y
    ]
    distances = EdgeDistances(cards)
    grid = np.array([[0, 1, 2, 3]])
    before = grid_score(grid, distances)

    link = Link(cards=(1, 2), ordered=False)
    optimize_grid(grid, distances, {1: link, 2: link}, 200, random.Random(0))

    assert grid.tolist() == [[0, 2, 1, 3]], "le bloc aurait dû être retourné"
    assert grid_score(grid, distances) < before


def test_ordered_link_is_never_flipped_even_when_worse():
    """Le pendant du test précédent : l'ordre imposé prime sur le score."""
    from pokemon_mosaic.cards import Card

    def card(index, left, right):
        c = Card(path=f"/fake/{index}.png", index=index,
                 thumbnail=np.zeros((4, 4, 3), np.uint8))
        c.left, c.right = np.array(left, float), np.array(right, float)
        c.top = c.bottom = np.zeros(3)
        return c

    cards = [
        card(0, [0, 0, 0], [0, 0, 0]),
        card(1, [255, 255, 255], [10, 10, 10]),
        card(2, [5, 5, 5], [250, 250, 250]),
        card(3, [0, 0, 0], [0, 0, 0]),
    ]
    distances = EdgeDistances(cards)
    grid = np.array([[0, 1, 2, 3]])
    link = Link(cards=(1, 2), ordered=True)
    optimize_grid(grid, distances, {1: link, 2: link}, 200, random.Random(0))
    assert grid.tolist() == [[0, 1, 2, 3]]


def test_build_initial_grid_places_links_and_empty_cells():
    cards_set = _card_set(20)
    library = LinkLibrary()
    library.add(Link(cards=(3, 4)))
    grid = build_initial_grid(
        cards_set, shape=(5, 5), links=library,
        empty_cells=[(0, 0), (4, 4)], rng=random.Random(0),
    )
    assert grid[0, 0] == EMPTY and grid[4, 4] == EMPTY
    assert (grid == EMPTY).sum() == 5  # 25 cases - 20 cartes
    (r3, c3), (r4, c4) = positions(grid, 3, 4)
    assert r3 == r4 and c4 == c3 + 1
    assert sorted(v for v in grid.flatten() if v != EMPTY) == list(range(20))


def test_build_initial_grid_rejects_an_impossible_layout():
    cards_set = _card_set(20)
    with pytest.raises(ValueError, match="cases disponibles"):
        build_initial_grid(cards_set, shape=(4, 4), rng=random.Random(0))


def test_empty_cells_survive_optimization_with_links():
    cards_set = _card_set(20)
    library = LinkLibrary()
    library.add(Link(cards=(3, 4), ordered=False))
    empty = [(0, 0), (2, 2), (4, 4)]
    grid = build_initial_grid(cards_set, (5, 5), library, empty, random.Random(0))
    distances = EdgeDistances(cards_set.cards)
    optimize_grid(grid, distances, library.group_map(), 10000, random.Random(0))
    for cell in empty:
        assert grid[cell] == EMPTY
    assert sorted(v for v in grid.flatten() if v != EMPTY) == list(range(20))


def _card_set(n):
    from pokemon_mosaic.cards import CardSet

    return CardSet(cards=make_cards(n), full_size=(713, 984), thumb_size=(178, 246))


def test_a_link_wider_than_the_grid_is_reported_at_construction():
    """Le bloc était abandonné en silence : ses cartes repartaient libres, le lien
    était rompu, et l'échec ne refaisait surface qu'au contrôle d'intégrité — avec
    un message conseillant d'appeler build_initial_grid, qu'on venait d'appeler."""
    cards_set = _card_set(6)
    library = LinkLibrary()
    library.add(Link(cards=(0, 1, 2)))
    with pytest.raises(ValueError, match="3 colonne|3 cases de large|ne trouve pas"):
        build_initial_grid(cards_set, shape=(2, 3), links=library, rng=random.Random(0))


def test_links_fit_check_can_be_called_upfront():
    """Exposée pour que l'interface refuse une grille trop étroite en amont."""
    from pokemon_mosaic.optimize import check_links_fit

    check_links_fit([(0, 1)], cols=2)
    with pytest.raises(ValueError, match="colonne"):
        check_links_fit([(0, 1, 2)], cols=2)


def test_a_link_that_fits_exactly_is_accepted():
    cards_set = _card_set(6)
    library = LinkLibrary()
    library.add(Link(cards=(0, 1, 2)))
    grid = build_initial_grid(cards_set, shape=(3, 2), links=library,
                              rng=random.Random(0))
    row = [int(v) for v in grid[0]]
    assert row == [0, 1, 2]


# --- Renumérotation des liens ---------------------------------------------

def _named_card_set(n):
    from pokemon_mosaic.cards import CardSet

    cards = make_cards(n)
    for card in cards:
        card.path = f"/fake/carte_{card.index}.png"
    return CardSet(cards=cards, full_size=(713, 984), thumb_size=(178, 246))


def test_remapping_translates_link_indices():
    library = LinkLibrary()
    library.add(Link(cards=(2, 3)))
    remapped = library.remapped({2: 0, 3: 1, 5: 2})
    assert remapped.to_groups() == [(0, 1)]


def test_remapping_keeps_the_order_flag():
    library = LinkLibrary()
    library.add(Link(cards=(4, 5), ordered=False, name="soleil-lune"))
    link = remapped_first(library, {4: 1, 5: 0})
    assert link.cards == (1, 0)
    assert link.ordered is False and link.name == "soleil-lune"


def remapped_first(library, mapping):
    return library.remapped(mapping).links[0]


def test_remapping_drops_links_whose_cards_left_the_selection():
    library = LinkLibrary()
    library.add(Link(cards=(0, 1)))
    library.add(Link(cards=(7, 8)))
    assert library.remapped({0: 0, 1: 1}).to_groups() == [(0, 1)]


def test_subset_provides_the_mapping_needed_to_remap():
    cards_set = _named_card_set(10)
    subset = cards_set.subset([2, 3, 5, 6, 7, 9])
    assert subset.index_mapping() == {2: 0, 3: 1, 5: 2, 6: 3, 7: 4, 9: 5}


def test_remapped_links_stick_the_cards_the_user_actually_chose():
    """Le cas silencieux : sans traduction, le lien (2, 3) désignait après
    renumérotation les cartes 5 et 6 — score plausible, image plausible, et les
    deux cartes voulues ailleurs."""
    cards_set = _named_card_set(10)
    library = LinkLibrary()
    library.add(Link(cards=(2, 3)))

    subset = cards_set.subset([2, 3, 5, 6, 7, 9])
    translated = library.remapped(subset.index_mapping())
    grid = build_initial_grid(subset, shape=(3, 2), links=translated,
                              rng=random.Random(0))
    (r_a, c_a), (r_b, c_b) = positions(grid, *translated.to_groups()[0])
    assert r_a == r_b and c_b == c_a + 1

    linked = {subset[int(grid[r_a, c_a])].path, subset[int(grid[r_b, c_b])].path}
    assert linked == {"/fake/carte_2.png", "/fake/carte_3.png"}


def test_a_link_pointing_outside_the_selection_is_refused():
    """Variante bruyante : l'indice sort des bornes après renumérotation."""
    cards_set = _named_card_set(6)
    library = LinkLibrary()
    library.add(Link(cards=(4, 5)))
    subset = cards_set.subset([1, 3, 4, 5])   # renumérotées 0..3
    with pytest.raises(ValueError, match="absentes de la sélection"):
        build_initial_grid(subset, shape=(2, 2), links=library, rng=random.Random(0))


def test_select_cards_translates_links_so_the_right_pair_is_stuck():
    """Variante silencieuse : les indices fautifs restent dans les bornes, donc
    aucune vérification ne peut les détecter. select_cards fait les deux gestes
    ensemble, ce qui est la seule garantie."""
    from pokemon_mosaic.optimize import select_cards

    cards_set = _named_card_set(10)
    library = LinkLibrary()
    library.add(Link(cards=(2, 3)))

    subset, translated = select_cards(cards_set, [2, 3, 5, 6, 7, 9], library)
    grid = build_initial_grid(subset, shape=(3, 2), links=translated,
                              rng=random.Random(0))
    pair = translated.to_groups()[0]
    (r_a, c_a), (r_b, c_b) = positions(grid, *pair)
    assert r_a == r_b and c_b == c_a + 1
    linked = {subset[int(grid[r_a, c_a])].path, subset[int(grid[r_b, c_b])].path}
    assert linked == {"/fake/carte_2.png", "/fake/carte_3.png"}


def test_select_cards_drops_links_whose_cards_are_deselected():
    from pokemon_mosaic.optimize import select_cards

    library = LinkLibrary()
    library.add(Link(cards=(0, 1)))
    library.add(Link(cards=(8, 9)))
    _, translated = select_cards(_named_card_set(10), [0, 1, 2, 3], library)
    assert translated.to_groups() == [(0, 1)]


def test_select_cards_without_links_returns_an_empty_library():
    from pokemon_mosaic.optimize import select_cards

    subset, translated = select_cards(_named_card_set(6), [1, 2, 3])
    assert len(subset) == 3 and len(translated) == 0
