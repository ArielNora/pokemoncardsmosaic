"""Les feuilles placées à la main survivent à un changement de finesse.

Trouvé par l'audit du 2026-09-18 : `set_layout` remettait les déplacements à
zéro à tout changement, la finesse comprise. Taper une finesse, ou basculer
« Images d'origine » à l'export, ramenait sans un mot chaque feuille à sa place
par défaut, alors que la place libre en millimètres n'avait bougé que de
quelques centièmes.
"""

import numpy as np
import pytest


@pytest.fixture
def session(qt_app):
    from pokemon_mosaic.cards import Card, CardSet
    from pokemon_mosaic.ui.session import Session

    cartes = []
    for i in range(20):
        carte = Card(path=f"/fake/s/{i}.webp", index=i,
                     thumbnail=np.full((16, 12, 3), 90, np.uint8))
        carte.top = carte.bottom = carte.left = carte.right = np.zeros(3)
        cartes.append(carte)
    jeu = CardSet(cards=cartes, full_size=(713, 984), thumb_size=(12, 16))
    s = Session()
    s.set_cards(jeu, "/fake")
    s.set_layout(cols=5, rows=4)
    s.move_panel(0, 0.0, 30.0)
    return s, jeu


def test_a_new_dpi_keeps_the_moved_sheets(session):
    s, _ = session
    avant = dict(s.panel_offsets)
    assert avant

    s.set_layout(dpi=s.dpi // 2)

    assert s.panel_offsets == avant


def test_a_real_layout_change_still_resets_them(session):
    """Une carte plus large change la taille de chaque morceau : la place
    choisie ne veut plus rien dire."""
    s, _ = session

    s.set_layout(card_gap_mm=s.card_gap_mm + 2)

    assert s.panel_offsets == {}


def test_dpi_and_something_else_together_reset_them(session):
    s, _ = session

    s.set_layout(dpi=s.dpi // 2, card_gap_mm=s.card_gap_mm + 2)

    assert s.panel_offsets == {}


def test_the_form_sending_every_field_unchanged_but_dpi_keeps_them(session):
    """Les formulaires renvoient tous leurs champs : seuls ceux qui changent
    vraiment comptent."""
    s, _ = session
    avant = dict(s.panel_offsets)

    s.set_layout(cols=s.cols, rows=s.rows, card_gap_mm=s.card_gap_mm,
                 dpi=s.dpi // 2)

    assert s.panel_offsets == avant


def test_the_export_resolution_section_keeps_the_moved_sheets(session):
    from pokemon_mosaic.ui.export_step import ExportStep

    s, jeu = session
    s.save_grid(np.arange(20).reshape(4, 5), jeu, iteration=1, score=1.0)
    etape = ExportStep(s)
    etape.enter()
    s.move_panel(0, 0.0, 30.0)
    avant = dict(s.panel_offsets)
    resolution = etape._tabs[3]

    resolution._full.setChecked(not s.full_resolution)
    assert s.panel_offsets == avant
    resolution._full.setChecked(not s.full_resolution)
    resolution._dpi.setValue(resolution._dpi.value() - 20)

    assert s.panel_offsets == avant
