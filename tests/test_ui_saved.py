"""Tests de la colonne des agencements gardés."""

import numpy as np
import pytest

from pokemon_mosaic.cards import Card, CardSet


def card_set(n, size=(6, 8)):
    width, height = size
    cards = []
    for i in range(n):
        thumb = np.full((height, width, 3), (i * 20) % 255, np.uint8)
        card = Card(path=f"/fake/{i}.png", index=i, thumbnail=thumb)
        card.top = card.bottom = card.left = card.right = np.zeros(3)
        cards.append(card)
    return CardSet(cards=cards, full_size=(713, 984), thumb_size=size)


@pytest.fixture
def colonne(qt_app):
    from pokemon_mosaic.ui.saved_column import SavedColumn
    from pokemon_mosaic.ui.session import Session

    session = Session()
    jeu = card_set(6)
    session.set_cards(jeu, "/fake")
    return SavedColumn(session), session, jeu


def garde(session, jeu, iteration=1):
    return session.save_grid(np.array([[0, 1], [2, 3]]), jeu, iteration, 1.0)


def test_the_column_shows_one_box_per_slot(colonne):
    from pokemon_mosaic.ui.session import MAX_SAVED

    widget, _, _ = colonne
    assert len(widget._slots) == MAX_SAVED


def test_an_empty_slot_says_so_and_is_not_a_destination(colonne):
    """Cliquer une case vide laisserait croire à une panne : il n'y a rien à
    montrer."""
    widget, _, _ = colonne
    vus = []
    widget.slot_picked.connect(vus.append)

    widget._slots[0].picked.emit(0)

    assert vus == []
    assert widget._slots[0]._base_role == "slot-empty"


def test_a_filled_slot_carries_the_mosaic_and_can_be_picked(colonne):
    widget, session, jeu = colonne
    garde(session, jeu)
    vus = []
    widget.slot_picked.connect(vus.append)

    widget._slots[0].picked.emit(0)

    assert vus == [0]
    assert widget._slots[0]._base_role == "slot"
    assert not widget._slots[0]._image.pixmap().isNull()


def test_the_cross_only_shows_on_a_filled_slot(colonne):
    widget, session, jeu = colonne
    assert not widget._slots[0]._close.isVisible()

    garde(session, jeu)
    widget._slots[0].show()
    assert widget._slots[0]._close.isVisibleTo(widget._slots[0])


def test_the_cross_asks_before_emptying_its_slot(colonne, monkeypatch):
    """⚠️ **Toujours une confirmation.** La croix est à quelques pixels de la
    vignette, et ce qu'elle efface ne se retrouve pas : le calcul ne redonne
    pas deux fois le même agencement."""
    from PySide6.QtWidgets import QMessageBox

    widget, session, jeu = colonne
    garde(session, jeu, iteration=1)
    garde(session, jeu, iteration=2)

    monkeypatch.setattr(QMessageBox, "question",
                        lambda *a, **k: QMessageBox.No)
    widget._slots[0]._close.click()
    assert session.saved[0] is not None, "un refus ne doit rien effacer"

    monkeypatch.setattr(QMessageBox, "question",
                        lambda *a, **k: QMessageBox.Yes)
    widget._slots[0]._close.click()

    assert session.saved[0] is None
    assert session.saved[1].iteration == 2, "les autres gardent leur rang"
    assert widget._slots[0]._base_role == "slot-empty"


def test_the_column_can_refuse_the_cross(qt_app):
    """À l'export, retirer sous ses propres pieds l'agencement affiché
    n'apporte rien."""
    from pokemon_mosaic.ui.saved_column import SavedColumn
    from pokemon_mosaic.ui.session import Session

    session = Session()
    jeu = card_set(6)
    session.set_cards(jeu, "/fake")
    widget = SavedColumn(session, removable=False)
    garde(session, jeu)

    assert not widget._slots[0]._close.isVisible()


def test_the_current_slot_is_marked_and_only_it(colonne):
    widget, session, jeu = colonne
    garde(session, jeu, iteration=1)
    garde(session, jeu, iteration=2)

    widget.set_current(1)

    assert widget._slots[1].property("role") == "slot-current"
    assert widget._slots[0].property("role") == "slot"
    widget.set_current(None)
    assert widget._slots[1].property("role") == "slot"


def test_the_mosaic_uses_the_empty_colour_for_the_holes(colonne):
    from pokemon_mosaic.ui.saved_column import mosaic_image

    _, _session, jeu = colonne
    grille = np.array([[0, -1]])

    image = mosaic_image(grille, jeu, (10, 200, 30))

    assert image.pixelColor(jeu.thumb_size[0], 0).getRgb()[:3] == (10, 200, 30)


def test_the_mosaic_needs_cards():
    from pokemon_mosaic.ui.saved_column import mosaic_image

    assert mosaic_image(np.array([[0]]), None, (0, 0, 0)) is None
