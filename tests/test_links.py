"""Tests des liens : modèle, bibliothèque, et respect des contraintes à l'optimisation."""

import random

import numpy as np
import pytest

from pokemon_mosaic.links import Link, LinkLibrary
from pokemon_mosaic.optimize import build_initial_grid, optimize_grid
from pokemon_mosaic.scoring import EMPTY, EdgeDistances

from test_scoring import make_cards


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
