"""Les feuilles placées à la main survivent à un changement de finesse.

Trouvé par l'audit du 2026-09-18 : `set_layout` remettait les déplacements à
zéro à tout changement, la finesse comprise. Taper une finesse, ou basculer
« Images d'origine » à l'export, ramenait sans un mot chaque feuille à sa place
par défaut, alors que la place libre en millimètres n'avait bougé que de
quelques centièmes.

La fin du fichier garde l'autre règle des déplacements : ils valent pour la
forme où ils ont été faits, et une autre forme, celle d'un agencement gardé,
les borne à la place libre de ses feuilles, comme l'export le fait en écrivant.
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


# --- Une autre forme borne les déplacements --------------------------------


def test_another_shape_clamps_the_moved_sheet(session):
    """L'aperçu d'un agencement d'une autre forme montrait un morceau dehors.

    Les déplacements valent pour la forme courante. Exporté sur une forme plus
    chargée, le même déplacement dépasse la place libre : l'aperçu le montrait
    à 340 mm quand l'export, qui borne en écrivant, l'aurait ramené à 180.
    """
    s, _ = session
    s.set_layout(cols=4, rows=3, panels=2, panel_rows=1, card_width_mm=20.0)
    s.move_panel(0, 9999.0, 9999.0)
    autre = (5, 12)
    libre = s.panel_free_mm(0, autre)
    assert libre[0] < s.panel_free_mm(0)[0], "la forme choisie doit serrer"

    pose = s.panel_position_mm(0, autre)

    assert pose == pytest.approx(libre)


def test_the_moved_sheet_is_untouched_on_its_own_shape(session):
    """Borner ne doit pas déplacer ce qui tient déjà dans sa feuille."""
    s, _ = session
    s.move_panel(0, 0.0, 12.0)

    assert s.panel_position_mm(0) == s.panel_offsets[0]
