"""Tests du mode caméléon : les vides prennent la couleur de ce qui les borde."""

import numpy as np

from pokemon_mosaic.chameleon import (
    border_band,
    crossing,
    gradient_between,
)


def test_a_vertical_gap_joins_two_edges_row_by_row():
    """⚠️ **Pixel par pixel**, et non d'une moyenne à l'autre : le raccord suit
    les motifs, un ciel reste bleu en face du ciel."""
    gauche = np.array([[255, 0, 0], [0, 0, 255]], np.uint8)     # rouge, bleu
    droite = np.array([[255, 0, 0], [0, 0, 255]], np.uint8)

    bande = gradient_between(gauche, droite, 3, horizontal=True)

    assert bande.shape == (2, 3, 3), "deux rangées, trois colonnes d'écart"
    # La rangée du haut reste rouge de bout en bout, celle du bas bleue.
    assert (bande[0] == [255, 0, 0]).all()
    assert (bande[1] == [0, 0, 255]).all()


def test_the_gradient_walks_from_one_colour_to_the_other():
    noir = np.zeros((1, 3), np.uint8)
    blanc = np.full((1, 3), 255, np.uint8)

    bande = gradient_between(noir, blanc, 3, horizontal=True)[0]

    assert list(bande[:, 0]) == [63, 127, 191]
    assert bande[0, 0] < bande[1, 0] < bande[2, 0]


def test_the_first_step_is_not_the_edge_itself():
    """Sinon deux pixels identiques se suivent, et le dégradé paraît décalé."""
    noir = np.zeros((1, 3), np.uint8)
    blanc = np.full((1, 3), 255, np.uint8)

    bande = gradient_between(noir, blanc, 4, horizontal=True)[0]

    assert bande[0, 0] > 0, "le premier pixel de l'écart n'est pas le bord"
    assert bande[-1, 0] < 255


def test_a_horizontal_gap_is_the_same_gradient_turned():
    haut = np.array([[10, 20, 30], [40, 50, 60]], np.uint8)
    bas = np.array([[70, 80, 90], [100, 110, 120]], np.uint8)

    bande = gradient_between(haut, bas, 2, horizontal=False)

    assert bande.shape == (2, 2, 3), "deux rangées d'écart, deux colonnes"
    # La colonne 0 relie bien le premier pixel du haut à celui du bas.
    assert bande[0, 0, 0] < bande[1, 0, 0]


def test_a_crossing_mixes_its_four_corners():
    """⚠️ Quatre cartes s'y touchent : un dégradé à une dimension ferait une
    couture avec l'écart voisin, qui tient compte des deux autres."""
    carre = crossing((0, 0, 0), (255, 0, 0), (0, 255, 0), (255, 255, 0),
                     width=3, height=3)

    assert carre.shape == (3, 3, 3)
    # Le rouge croît vers la droite, le vert vers le bas.
    assert carre[0, 0, 0] < carre[0, -1, 0]
    assert carre[0, 0, 1] < carre[-1, 0, 1]
    # Le coin bas-droit tient des deux.
    assert carre[-1, -1, 0] > carre[0, 0, 0] and carre[-1, -1, 1] > carre[0, 0, 1]


def test_an_empty_cell_is_a_colour_like_any_other():
    """Sa couleur entre dans le dégradé comme celle d'une carte : c'est ce que
    le voisin voit."""
    carte = np.array([[200, 100, 0]], np.uint8)
    vide = np.array([[0, 0, 0]], np.uint8)

    bande = gradient_between(carte, vide, 2, horizontal=True)[0]

    assert bande[0, 0] > bande[1, 0] > 0


def test_a_border_band_goes_to_the_background_and_keeps_its_side():
    bord = np.array([[255, 255, 255]], np.uint8)

    dehors = border_band(bord, (0, 0, 0), 3, horizontal=True, outwards=True)[0]
    dedans = border_band(bord, (0, 0, 0), 3, horizontal=True, outwards=False)[0]

    assert dehors[0, 0] > dehors[-1, 0], "vers la droite, on s'éteint"
    assert dedans[0, 0] < dedans[-1, 0], "vers la gauche, on s'allume"


def test_a_gap_of_zero_pixels_yields_nothing():
    """Sans écart, il n'y a rien à peindre : le cas doit se traverser sans
    lever."""
    bord = np.zeros((4, 3), np.uint8)

    assert gradient_between(bord, bord, 0, horizontal=True).size == 0
    assert crossing((0, 0, 0), (0, 0, 0), (0, 0, 0), (0, 0, 0), 0, 0).size == 0
