"""Tests de l'état partagé et de la traduction de l'interface."""

import numpy as np
import pytest

from pokemon_mosaic.cards import Card, CardSet
from pokemon_mosaic.links import Link

from test_scoring import make_cards


def card_set_in(tmp_path, layout):
    """Construit un CardSet dont les chemins reflètent une arborescence réelle."""
    cards = []
    for folder, names in layout.items():
        directory = tmp_path / folder
        directory.mkdir(parents=True, exist_ok=True)
        for name in names:
            path = directory / f"{name}.png"
            path.touch()
            card = Card(path=str(path), index=len(cards),
                        thumbnail=np.zeros((8, 6, 3), np.uint8))
            card.top = card.bottom = card.left = card.right = np.zeros(3)
            cards.append(card)
    return CardSet(cards=cards, full_size=(713, 984), thumb_size=(6, 8))


@pytest.fixture
def session(qt_app):
    from pokemon_mosaic.ui.session import Session

    return Session()


def test_all_cards_selected_after_loading(session, tmp_path):
    session.set_cards(card_set_in(tmp_path, {"a": ["x", "y", "z"]}), str(tmp_path))
    assert session.total_cards == 3
    assert session.selected_count == 3
    assert session.selected_indices() == [0, 1, 2]


def test_toggle_excludes_then_reincludes(session, tmp_path):
    session.set_cards(card_set_in(tmp_path, {"a": ["x", "y"]}), str(tmp_path))
    session.toggle(0)
    assert session.is_excluded(0) and session.selected_count == 1
    session.toggle(0)
    assert not session.is_excluded(0) and session.selected_count == 2


def test_folders_with_the_same_name_stay_distinct(session, tmp_path):
    """Deux séries peuvent avoir un « 0_promo » : les confondre exclurait les deux."""
    session.set_cards(
        card_set_in(tmp_path, {"serie_A/0_promo": ["a", "b"],
                               "serie_B/0_promo": ["c"]}),
        str(tmp_path),
    )
    assert session.folders() == ["serie_A/0_promo", "serie_B/0_promo"]
    assert len(session.indices_in_folder("serie_A/0_promo")) == 2
    assert len(session.indices_in_folder("serie_B/0_promo")) == 1


def test_excluding_one_folder_leaves_its_namesake_untouched(session, tmp_path):
    session.set_cards(
        card_set_in(tmp_path, {"serie_A/0_promo": ["a", "b"],
                               "serie_B/0_promo": ["c"]}),
        str(tmp_path),
    )
    session.set_excluded(session.indices_in_folder("serie_A/0_promo"), True)
    assert session.selected_count == 1
    assert session.selected_indices() == [2]


def test_selection_change_emits_once_per_batch(session, tmp_path):
    session.set_cards(card_set_in(tmp_path, {"a": list("abcdef")}), str(tmp_path))
    calls = []
    session.selection_changed.connect(lambda: calls.append(1))
    session.set_excluded([0, 1, 2], True)
    assert len(calls) == 1


def test_no_signal_when_nothing_actually_changes(session, tmp_path):
    session.set_cards(card_set_in(tmp_path, {"a": ["x", "y"]}), str(tmp_path))
    session.set_excluded([0], True)
    calls = []
    session.selection_changed.connect(lambda: calls.append(1))
    session.set_excluded([0], True)
    assert calls == []


def test_links_referencing_excluded_cards_are_dropped(session, tmp_path):
    session.set_cards(card_set_in(tmp_path, {"a": list("abcd")}), str(tmp_path))
    session.add_link(Link(cards=(0, 1)))
    session.add_link(Link(cards=(2, 3)))
    assert len(session.usable_links()) == 2
    session.set_excluded([1], True)
    assert session.usable_links().to_groups() == [(2, 3)]


def test_thumbnail_survives_conversion_to_pixmap(qt_app):
    """QImage ne copie pas son tampon : sans copie, l'image pointerait dans le vide."""
    from pokemon_mosaic.ui.gallery import numpy_to_pixmap

    array = np.random.default_rng(0).integers(0, 255, (12, 9, 3), dtype=np.uint8)
    pixmap = numpy_to_pixmap(array)
    del array
    assert (pixmap.width(), pixmap.height()) == (9, 12)
    assert not pixmap.isNull()
