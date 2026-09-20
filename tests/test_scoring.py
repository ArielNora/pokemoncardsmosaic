"""Tests du cœur de calcul : distances, scores, et invariants de l'optimisation."""

import random

import numpy as np
import pytest

from pokemon_mosaic.cards import Card
from pokemon_mosaic.optimize import optimize_grid
from pokemon_mosaic.scoring import (
    EMPTY,
    EdgeDistances,
    _pairwise_distances,
    grid_score,
    local_score,
)


def make_cards(n, seed=0):
    """Cartes synthétiques : seules les signatures de bord comptent pour le score."""
    rng = np.random.default_rng(seed)
    cards = []
    for i in range(n):
        card = Card(path=f"/fake/card{i}.png", index=i, thumbnail=np.zeros((4, 4, 3), np.uint8))
        card.top, card.bottom, card.left, card.right = (rng.random(3) * 255 for _ in range(4))
        cards.append(card)
    return cards


def test_pairwise_distances_matches_scipy():
    """La matrice numpy doit être identique à celle de scipy, qu'on a retiré du socle."""
    scipy_spatial = pytest.importorskip(
        "scipy.spatial.distance", reason="scipy n'est installé qu'avec --extra experiments"
    )
    rng = np.random.default_rng(0)
    a, b = rng.random((40, 3)) * 255, rng.random((40, 3)) * 255
    expected = scipy_spatial.cdist(a, b, "euclidean")
    np.testing.assert_array_equal(_pairwise_distances(a, b), expected)


def test_distance_matrix_orientation():
    """lr[i, j] doit bien opposer le bord DROIT de i au bord GAUCHE de j."""
    cards = make_cards(3)
    d = EdgeDistances(cards)
    expected = np.linalg.norm(cards[0].right - cards[1].left)
    assert d.lr[0, 1] == pytest.approx(expected)
    expected = np.linalg.norm(cards[0].bottom - cards[1].top)
    assert d.tb[0, 1] == pytest.approx(expected)


def test_grid_score_counts_every_seam():
    """Une grille 2x2 a exactement 4 coutures : 2 horizontales, 2 verticales."""
    cards = make_cards(4)
    d = EdgeDistances(cards)
    grid = np.array([[0, 1], [2, 3]])
    expected = d.lr[0, 1] + d.lr[2, 3] + d.tb[0, 2] + d.tb[1, 3]
    assert grid_score(grid, d) == pytest.approx(expected)


def test_empty_cells_contribute_nothing():
    cards = make_cards(4)
    d = EdgeDistances(cards)
    grid = np.array([[0, EMPTY], [2, 3]])
    assert grid_score(grid, d) == pytest.approx(d.tb[0, 2] + d.lr[2, 3])


def test_local_score_counts_shared_seam_once():
    """Deux cases voisines passées ensemble : la couture entre elles compte une fois.

    C'est ce qui justifie de passer les deux zones d'un échange en un seul appel.
    """
    cards = make_cards(4)
    d = EdgeDistances(cards)
    grid = np.array([[0, 1], [2, 3]])
    together = local_score([(0, 0), (0, 1)], grid, d)
    separately = local_score([(0, 0)], grid, d) + local_score([(0, 1)], grid, d)
    assert together == pytest.approx(separately - d.lr[0, 1])


def test_local_score_of_all_cells_equals_grid_score():
    cards = make_cards(9)
    d = EdgeDistances(cards)
    grid = np.arange(9).reshape(3, 3)
    every_cell = [(r, c) for r in range(3) for c in range(3)]
    assert local_score(every_cell, grid, d) == pytest.approx(grid_score(grid, d))


def test_optimization_never_worsens_the_score():
    cards = make_cards(30)
    d = EdgeDistances(cards)
    grid = np.arange(30).reshape(5, 6)
    before = grid_score(grid, d)
    optimize_grid(grid, d, iterations=3000, rng=random.Random(0))
    assert grid_score(grid, d) <= before


def test_optimization_preserves_every_card_exactly_once():
    cards = make_cards(30)
    d = EdgeDistances(cards)
    grid = np.arange(30).reshape(5, 6)
    optimize_grid(grid, d, iterations=3000, rng=random.Random(0))
    assert sorted(grid.flatten()) == list(range(30))


def test_empty_cells_never_move():
    """Les cases vides sont figées : même position avant et après optimisation."""
    cards = make_cards(30)
    d = EdgeDistances(cards)
    grid = np.arange(30).reshape(5, 6)
    grid[1, 2] = EMPTY
    grid[3, 4] = EMPTY
    optimize_grid(grid, d, iterations=5000, rng=random.Random(0))
    assert grid[1, 2] == EMPTY and grid[3, 4] == EMPTY
    assert (grid == EMPTY).sum() == 2


def test_optimization_reports_accepted_swaps():
    """Le compte d'échanges retenus cadencera les snapshots de la timeline."""
    cards = make_cards(30)
    d = EdgeDistances(cards)
    grid = np.arange(30).reshape(5, 6)
    result = optimize_grid(grid, d, iterations=2000, rng=random.Random(0))
    assert 0 < result.accepted < 2000
    assert result.attempted == 2000
    assert 0 < result.acceptance_rate < 1


def test_distances_refuse_a_discontinuous_numbering():
    """Les matrices sont indexées par position, la grille porte des card.index.
    Si les deux divergent, les distances sont lues à la mauvaise ligne et la
    mosaïque est assemblée avec les mauvaises cartes, sans que rien ne lève."""
    cards = make_cards(5)
    selection = [cards[0], cards[2], cards[4]]  # indices 0, 2, 4
    with pytest.raises(ValueError, match="Numérotation discontinue"):
        EdgeDistances(selection)


# --- Non-régressions du /verif-code du 2026-08-24 ---------------------------

def _ecrire(dossier, tailles):
    from PIL import Image
    dossier.mkdir(parents=True, exist_ok=True)
    for nom, taille in tailles.items():
        Image.new("RGB", taille, (10, 20, 30)).save(dossier / f"{nom}.webp")


def test_the_common_size_is_a_real_card_size_not_two_independent_minima(tmp_path):
    """La largeur et la hauteur minimales prises séparément donnaient un couple
    que personne ne portait : 734×1024 et 717×1050 produisaient 717×1024, de
    rapport d'aspect étranger aux deux, et **toutes** les cartes étaient
    déformées de 2,3 % sans un mot. Survenu le 2026-08-22."""
    from pokemon_mosaic.cards import load_cards

    _ecrire(tmp_path / "jeu", {"a": (734, 1024), "b": (717, 1050), "c": (734, 1024)})
    cards = load_cards(str(tmp_path))
    assert cards.full_size == (734, 1024)
    # L'écart est **porté** et non imprimé : depuis un paquet `.app`, la sortie
    # standard ne va nulle part que l'utilisateur puisse lire, et c'est
    # l'étape 1 qui doit pouvoir le dire.
    assert [(e.size, e.count) for e in cards.odd_sizes] == [((717, 1050), 1)]
    assert cards.has_warnings


def test_a_homogeneous_collection_reports_nothing(tmp_path):
    from pokemon_mosaic.cards import load_cards

    _ecrire(tmp_path / "jeu", {"a": (60, 80), "b": (60, 80)})
    cards = load_cards(str(tmp_path))
    assert cards.full_size == (60, 80)
    assert cards.odd_sizes == []
    assert not cards.has_warnings


# --- La métrique améliorée : dix parties recouvrantes par bord --------------


def carte_en_deux(index, un, deux, sens="hauteur", taille=(40, 20)):
    """Une vignette coupée en deux couleurs, dans sa hauteur ou dans sa largeur.

    Coupée en hauteur, ses bords **gauche et droit** varient du haut vers le
    bas ; coupée en largeur, ce sont ses bords **haut et bas** qui varient de
    gauche à droite. Les deux sens se testent : ils ne se découpent pas sur le
    même axe de la vignette.
    """
    hauteur, largeur = taille
    image = np.zeros((hauteur, largeur, 3), np.uint8)
    if sens == "hauteur":
        image[: hauteur // 2], image[hauteur // 2 :] = un, deux
    else:
        image[:, : largeur // 2], image[:, largeur // 2 :] = un, deux
    return Card(path=f"/fake/{index}.webp", index=index, thumbnail=image)


def test_the_parts_overlap_by_half_and_cover_the_whole_edge():
    """Chaque partie commence au milieu de la précédente.

    Celles du bout ne sont donc recouvertes que d'un côté, les autres des deux,
    et les dix parties couvrent le bord entier sans trou.
    """
    from pokemon_mosaic.cards import edge_windows

    bornes = edge_windows(100, 10)

    assert len(bornes) == 10
    assert bornes[0][0] == 0 and bornes[-1][1] == 100
    pas = 100 / 11
    for rang, (debut, fin) in enumerate(bornes):
        assert fin - debut == pytest.approx(2 * pas, abs=1.0), rang
        if rang:
            avant_debut, avant_fin = bornes[rang - 1]
            # Le recouvrement avec la précédente vaut la moitié d'une partie.
            assert avant_fin - debut == pytest.approx(pas, abs=1.0), rang
            assert debut - avant_debut == pytest.approx(pas, abs=1.0), rang
    # Aucun trou : la fin de chaque partie dépasse le début de la suivante.
    assert all(bornes[i][1] >= bornes[i + 1][0] for i in range(9))


def test_two_opposite_edges_stop_passing_for_a_perfect_match():
    """⚠️ **Le défaut que la métrique améliorée corrige.**

    Un bord rouge en haut et bleu en bas a la même moyenne qu'un bord bleu en
    haut et rouge en bas : la métrique d'origine les déclare identiques, score
    nul, alors que la couture saute aux yeux.
    """
    from pokemon_mosaic.cards import EDGE_PARTS

    # Les bords gauche et droit se lisent dans la hauteur, les bords haut et
    # bas dans la largeur : le piège se tend dans les deux sens.
    debout = [carte_en_deux(0, (200, 0, 0), (0, 0, 200)),
              carte_en_deux(1, (0, 0, 200), (200, 0, 0))]
    couche = [carte_en_deux(0, (200, 0, 0), (0, 0, 200), "largeur"),
              carte_en_deux(1, (0, 0, 200), (200, 0, 0), "largeur")]

    for cartes in (debout, couche):
        for carte in cartes:
            carte.calculate_features(0.5)
    assert EdgeDistances(debout).lr[0, 1] == pytest.approx(0.0)
    assert EdgeDistances(couche).tb[0, 1] == pytest.approx(0.0)

    for cartes in (debout, couche):
        for carte in cartes:
            carte.calculate_features(0.5, EDGE_PARTS)
    assert EdgeDistances(debout).lr[0, 1] > 200.0
    assert EdgeDistances(couche).tb[0, 1] > 200.0


def test_an_edge_still_matches_itself_part_by_part():
    """Les parties se comparent dans l'ordre : deux bords identiques valent zéro.

    Rangées à l'envers d'un côté, elles compareraient le haut d'une carte au bas
    de sa voisine, et deux cartes jumelles ne se raccorderaient plus.
    """
    from pokemon_mosaic.cards import EDGE_PARTS

    debout = [carte_en_deux(i, (200, 0, 0), (0, 0, 200)) for i in range(2)]
    couche = [carte_en_deux(i, (200, 0, 0), (0, 0, 200), "largeur")
              for i in range(2)]
    for cartes in (debout, couche):
        for carte in cartes:
            carte.calculate_features(0.5, EDGE_PARTS)

    # Deux cartes identiques : le bord droit de l'une vaut le bord gauche de
    # l'autre, et son bord bas le bord haut de l'autre.
    assert EdgeDistances(debout).lr[0, 1] == pytest.approx(0.0)
    assert EdgeDistances(couche).tb[0, 1] == pytest.approx(0.0)


def test_a_uniform_edge_keeps_the_score_on_the_same_scale():
    """⚠️ **Moyenne des parties, pas somme.** Un score reste comparable.

    Sur des bords unis, les dix parties disent toutes la même chose : le score
    doit alors valoir celui de la métrique d'origine, et non dix fois plus.
    """
    from pokemon_mosaic.cards import EDGE_PARTS

    cartes = [carte_en_deux(0, (10, 20, 30), (10, 20, 30)),
              carte_en_deux(1, (60, 80, 90), (60, 80, 90))]

    for carte in cartes:
        carte.calculate_features(0.5)
    simple = EdgeDistances(cartes).lr[0, 1]
    for carte in cartes:
        carte.calculate_features(0.5, EDGE_PARTS)

    assert EdgeDistances(cartes).lr[0, 1] == pytest.approx(simple)


def test_one_part_measures_exactly_what_it_always_did():
    """La case décochée ne doit rien changer au calcul d'avant."""
    cartes = [carte_en_deux(i, (3 * i, 200 - i, 40), (i, 90, 250 - 2 * i))
              for i in range(6)]
    for carte in cartes:
        carte.calculate_features(0.2)

    attendu = np.linalg.norm(cartes[0].right - cartes[1].left)
    assert EdgeDistances(cartes).lr[0, 1] == attendu


def test_mixing_two_cuttings_is_refused():
    """Des signatures d'une partie et de dix donneraient des distances muettes."""
    from pokemon_mosaic.cards import EDGE_PARTS

    cartes = [carte_en_deux(i, (10, 10, 10), (90, 90, 90)) for i in range(2)]
    cartes[0].calculate_features(0.5, EDGE_PARTS)
    cartes[1].calculate_features(0.5)

    with pytest.raises(ValueError, match="formes différentes"):
        EdgeDistances(cartes)
