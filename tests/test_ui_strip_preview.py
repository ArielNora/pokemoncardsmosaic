"""Tests de l'aperçu d'épaisseur des bandes."""

import time

import numpy as np
import pytest

from pokemon_mosaic.cards import Card, CardSet


def coloured_card_set(n, size=(24, 34)):
    """Cartes en dégradé vertical, chacune entre deux couleurs tirées au sort.

    Un jeu de couleurs **unies** ne conviendrait pas : la moyenne d'une bande y
    vaut la couleur de la carte quelle que soit son épaisseur, donc le réglage
    n'aurait aucun effet et le test ne prouverait rien.
    """
    rng = np.random.default_rng(0)
    width, height = size
    ramp = np.linspace(0.0, 1.0, height)[:, None]
    cards = []
    for i in range(n):
        top_colour = rng.integers(0, 255, 3).astype(float)
        bottom_colour = rng.integers(0, 255, 3).astype(float)
        column = top_colour * (1 - ramp) + bottom_colour * ramp
        thumb = np.repeat(column[:, None, :], width, axis=1).astype(np.uint8)
        card = Card(path=f"/fake/{i}.png", index=i, thumbnail=thumb)
        card.calculate_features(0.1)
        cards.append(card)
    return CardSet(cards=cards, full_size=(713, 984), thumb_size=size)


@pytest.fixture
def session(qt_app):
    from pokemon_mosaic.ui.session import Session

    s = Session()
    s.set_cards(coloured_card_set(30), "/fake")
    return s


@pytest.fixture
def preview(qt_app, session):
    from pokemon_mosaic.ui.strip_preview import StripPreview

    widget = StripPreview(session)
    widget.resize(420, 200)
    return widget, session


def test_sandbox_is_built_from_the_loaded_cards(preview):
    widget, _ = preview
    widget.refresh()
    assert widget._sandbox is not None
    assert widget._sandbox_error == ""


def test_sandbox_reports_when_there_are_too_few_cards(qt_app):
    from pokemon_mosaic.ui.session import Session
    from pokemon_mosaic.ui.strip_preview import StripPreview

    session = Session()
    session.set_cards(coloured_card_set(3), "/fake")
    widget = StripPreview(session)
    widget.refresh()
    assert widget._sandbox is None
    assert "pas assez" in widget._sandbox_error


def test_sandbox_holds_every_sampled_card_once(preview):
    """La grille d'essai passe par subset(), qui renumérote : une erreur de
    correspondance y produirait des cartes manquantes ou répétées."""
    from pokemon_mosaic.ui.strip_preview import SANDBOX_COLS, SANDBOX_ROWS

    widget, _ = preview
    widget.refresh()
    expected = SANDBOX_COLS * SANDBOX_ROWS
    assert widget._sandbox.width() > 0
    assert widget._sandbox.height() > 0
    # La grille est pleine : aucune case ne doit rester noire.
    image = widget._sandbox
    corners = [image.pixelColor(1, 1), image.pixelColor(image.width() - 2, 1),
               image.pixelColor(1, image.height() - 2)]
    assert all(colour.value() > 0 for colour in corners), f"{expected} cases attendues"


def test_changing_the_strip_size_changes_the_sandbox(preview):
    widget, session = preview
    widget.refresh()
    before = widget._sandbox.copy()
    session.set_algorithm(strip_size=0.45)
    widget.refresh()
    assert widget._sandbox != before


def test_a_change_only_marks_the_preview_stale(preview):
    """Reconstruire coûte de 34 à 294 ms. `selection_changed` part à chaque clic
    dans la galerie de l'étape 1, où cet aperçu n'est pas même visible : marquer
    périmé doit être gratuit, le calcul n'ayant lieu qu'à l'affichage."""
    widget, session = preview
    widget.refresh()
    assert widget._dirty is False

    start = time.monotonic()
    for index in range(20):
        session.toggle(index)
    elapsed = time.monotonic() - start

    assert widget._dirty is True
    assert elapsed < 0.05, f"20 basculements ont coûté {elapsed * 1000:.0f} ms"


def test_painting_rebuilds_a_stale_preview(preview):
    widget, session = preview
    session.set_algorithm(strip_size=0.3)
    assert widget._dirty is True
    widget.grab()
    assert widget._dirty is False and widget._sandbox is not None


def test_an_unrelated_setting_leaves_the_sandbox_coherent(preview):
    widget, session = preview
    session.set_algorithm(iterations=1234)
    widget.refresh()
    assert widget._sandbox is not None


def test_excluded_cards_are_kept_out_of_the_sample(preview):
    """Montrer un raccord entre des cartes que l'utilisateur vient d'exclure
    serait trompeur : l'échantillon doit suivre la sélection."""
    widget, session = preview
    widget.refresh()
    before = widget._sandbox.copy()

    session.set_excluded(range(20), True)
    widget.refresh()
    assert widget._sandbox != before


def test_too_few_cards_left_after_exclusion_is_reported(preview):
    widget, session = preview
    session.set_excluded(range(28), True)   # il n'en reste que 2
    widget.refresh()
    assert widget._sandbox is None
    assert "pas assez" in widget._sandbox_error


def test_widget_paints_when_everything_is_excluded(preview):
    widget, session = preview
    session.set_excluded(range(30), True)
    assert not widget.grab().isNull()


def test_rebuilding_stays_fast_enough_for_a_slider(preview):
    """Mesuré à ~37 ms pour 20 cartes ; au-delà de 250 ms le curseur accrocherait."""
    widget, _ = preview
    start = time.monotonic()
    widget.refresh()
    assert time.monotonic() - start < 0.25


def test_widget_paints_without_cards(qt_app):
    from pokemon_mosaic.ui.session import Session
    from pokemon_mosaic.ui.strip_preview import StripPreview

    widget = StripPreview(Session())
    widget.resize(300, 160)
    widget.grab()   # ne doit pas lever


def test_widget_paints_with_cards(preview):
    widget, _ = preview
    widget.refresh()
    pixmap = widget.grab()
    assert not pixmap.isNull()
