"""Tests de l'interface des liens : bibliothèque, panneau et dialogue de saisie."""

import numpy as np
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog

from pokemon_mosaic.cards import Card, CardSet
from pokemon_mosaic.links import Link, LinkLibrary


def card_set_in(tmp_path, layout):
    """Arborescence réelle : les liens par défaut se résolvent par chemin."""
    cards = []
    for folder, names in layout.items():
        directory = tmp_path / folder
        directory.mkdir(parents=True, exist_ok=True)
        for name in names:
            path = directory / f"{name}.webp"
            path.touch()
            card = Card(path=str(path), index=len(cards),
                        thumbnail=np.zeros((8, 6, 3), np.uint8))
            card.calculate_features()
            cards.append(card)
    return CardSet(cards=cards, full_size=(713, 984), thumb_size=(6, 8))


@pytest.fixture
def session(qt_app, tmp_path):
    from pokemon_mosaic.ui.session import Session

    session = Session()
    session.set_cards(
        card_set_in(tmp_path, {"a3-gardiens-celestes":
                               ["a3-207-solgaleo-ex", "a3-204-lunala-ex",
                                "a3-206-necrozma-ex"],
                               "a4a-source-secrete":
                               ["a4a-087-entei-ex", "a4a-088-raikou-ex"]}),
        str(tmp_path),
    )
    return session


# --- Bibliothèque ---------------------------------------------------------


def test_replace_keeps_the_link_at_its_place():
    library = LinkLibrary()
    library.add(Link(cards=(0, 1)))
    library.add(Link(cards=(2, 3)))
    library.replace(library.links[0], Link(cards=(0, 1), ordered=False))
    assert library.links[0].cards == (0, 1) and not library.links[0].ordered


def test_a_link_is_not_in_conflict_with_the_version_it_replaces():
    """Sans retrait préalable, modifier un lien serait refusé par sa propre
    réservation de cartes : aucune modification ne passerait jamais."""
    library = LinkLibrary()
    library.add(Link(cards=(0, 1)))
    library.replace(library.links[0], Link(cards=(0, 1), name="duo"))
    assert library.links[0].name == "duo"


def test_a_refused_replacement_leaves_the_library_intact():
    library = LinkLibrary()
    library.add(Link(cards=(0, 1)))
    library.add(Link(cards=(2, 3)))
    with pytest.raises(ValueError, match="appartiennent déjà"):
        library.replace(library.links[0], Link(cards=(0, 2)))
    assert [link.cards for link in library.links] == [(0, 1), (2, 3)]


# --- Session --------------------------------------------------------------


def test_two_identical_disabled_links_stay_distinct():
    """`list.index` compare par égalité : deux liens désactivés portant les mêmes
    cartes sont indiscernables, et modifier le second modifierait le premier."""
    library = LinkLibrary()
    first, second = Link(cards=(0, 1), enabled=False), Link(cards=(0, 1), enabled=False)
    library.add(first)
    library.add(second)   # accepté : un lien désactivé ne réserve rien

    library.replace(second, Link(cards=(0, 1), enabled=True))
    assert [link.enabled for link in library.links] == [False, True]


def test_removing_the_second_of_two_identical_links_keeps_the_first():
    library = LinkLibrary()
    first, second = Link(cards=(0, 1), enabled=False), Link(cards=(0, 1), enabled=False)
    library.add(first)
    library.add(second)
    library.remove(second)
    assert library.links == [first] and library.links[0] is first


def test_removing_a_link_absent_from_the_library_is_refused():
    library = LinkLibrary()
    library.add(Link(cards=(0, 1)))
    with pytest.raises(ValueError, match="absent de la bibliothèque"):
        library.remove(Link(cards=(4, 5)))


def test_default_links_resolve_against_the_loaded_folder(session):
    missing = session.apply_default_links()
    assert missing == []
    # solgaleo=0, lunala=1, necrozma=2, entei=3, raikou=4 — l'ordre de chargement.
    assert [link.cards for link in session.links] == [(0, 1), (3, 4)]


def test_default_links_are_skipped_when_the_cards_are_absent(qt_app, tmp_path):
    from pokemon_mosaic.ui.session import Session

    session = Session()
    session.set_cards(card_set_in(tmp_path, {"autre": ["pikachu", "raichu"]}),
                      str(tmp_path))
    missing = session.apply_default_links()
    assert len(session.links) == 0 and len(missing) == 4


def test_default_links_leave_an_existing_link_alone(session):
    """Rejouer les liens par défaut ne doit pas échouer sur une carte déjà prise."""
    session.add_link(Link(cards=(0, 3)))   # solgaleo + entei, à contre-emploi
    missing = session.apply_default_links()
    assert [link.cards for link in session.links] == [(0, 3)]
    # Seules les cartes déjà engagées sont signalées introuvables ; leurs
    # partenaires restent libres, mais le lien par défaut n'est pas posé.
    assert missing == ["a3-gardiens-celestes/a3-207-solgaleo-ex.webp",
                       "a4a-source-secrete/a4a-087-entei-ex.webp"]


def test_disabling_a_link_keeps_it_in_the_library(session):
    session.add_link(Link(cards=(0, 1)))
    session.set_link_enabled(session.links.links[0], False)
    assert len(session.links) == 1
    assert session.links.active == []


def test_an_excluded_card_makes_its_link_unusable(session):
    session.add_link(Link(cards=(0, 1)))
    assert session.unusable_links() == []
    session.set_excluded([1], True)
    assert len(session.unusable_links()) == 1
    assert len(session.usable_links()) == 0


# --- Panneau --------------------------------------------------------------


@pytest.fixture
def panel(session):
    from pokemon_mosaic.ui.links_panel import LinksPanel

    return LinksPanel(session)


def test_the_panel_names_the_cards_and_shows_the_direction(panel, session):
    session.add_link(Link(cards=(0, 1)))
    session.add_link(Link(cards=(3, 4), ordered=False))
    assert panel._list.item(0).text() == "a3-207-solgaleo-ex → a3-204-lunala-ex"
    assert panel._list.item(1).text() == "a4a-087-entei-ex ↔ a4a-088-raikou-ex"


def test_unchecking_a_row_disables_the_link(panel, session):
    session.add_link(Link(cards=(0, 1)))
    panel._list.item(0).setCheckState(Qt.Unchecked)
    assert session.links.links[0].enabled is False
    panel._list.item(0).setCheckState(Qt.Checked)
    assert session.links.links[0].enabled is True


def test_the_panel_warns_about_a_link_on_an_excluded_card(panel, session):
    session.add_link(Link(cards=(0, 1)))
    assert panel._warning.isHidden()
    session.set_excluded([0], True)
    assert not panel._warning.isHidden()


def test_deleting_removes_the_link(panel, session):
    session.add_link(Link(cards=(0, 1)))
    panel._list.setCurrentRow(0)
    panel._remove()
    assert len(session.links) == 0


# --- Dialogue -------------------------------------------------------------


@pytest.fixture
def dialog_for(session):
    from pokemon_mosaic.ui.link_dialog import LinkDialog

    return lambda link=None: LinkDialog(session, link=link)


def pick(dialog, *names):
    """Sélectionne des cartes par nom dans la liste de gauche, dans cet ordre.

    Rapprochement par fragment : les noms de fichiers portent désormais le code
    et le numéro de la carte (`a4a-087-entei-ex`), et non plus le seul nom.
    """
    for name in names:
        for row in range(dialog._candidates.count()):
            item = dialog._candidates.item(row)
            if name in item.text():
                dialog._candidates.setCurrentItem(item)
                break
        else:
            raise AssertionError(f"{name} absente des cartes disponibles")
        dialog._add_selected()


def test_the_dialog_builds_a_link_in_the_order_chosen(dialog_for):
    dialog = dialog_for()
    pick(dialog, "raikou", "entei")
    assert dialog.link().cards == (4, 3)


def test_a_chosen_card_leaves_the_available_list(dialog_for):
    dialog = dialog_for()
    before = dialog._candidates.count()
    pick(dialog, "entei")
    assert dialog._candidates.count() == before - 1


def test_the_dialog_refuses_a_single_card(dialog_for):
    from PySide6.QtWidgets import QDialogButtonBox

    dialog = dialog_for()
    ok = dialog._buttons.button(QDialogButtonBox.Ok)
    assert not ok.isEnabled()
    pick(dialog, "entei")
    assert not ok.isEnabled()
    pick(dialog, "raikou")
    assert ok.isEnabled()


def test_moving_a_card_changes_the_order(dialog_for):
    dialog = dialog_for()
    pick(dialog, "entei", "raikou")
    dialog._sequence.setCurrentRow(1)
    dialog._move(-1)
    assert dialog.link().cards == (4, 3)


def test_editing_an_existing_link_is_accepted(dialog_for, session):
    """Le lien modifié ne doit pas être jugé en conflit avec lui-même."""
    session.add_link(Link(cards=(0, 1)))
    dialog = dialog_for(session.links.links[0])
    dialog._ordered.setChecked(False)
    dialog._try_accept()
    assert dialog._error.text() == ""
    assert dialog.result() == QDialog.Accepted


def test_a_card_already_linked_elsewhere_is_refused(dialog_for, session):
    session.add_link(Link(cards=(0, 1)))
    dialog = dialog_for()
    pick(dialog, "lunala", "entei")
    dialog._try_accept()
    assert "appartiennent déjà" in dialog._error.text()
    assert dialog.result() != QDialog.Accepted


def test_an_existing_link_opens_with_its_cards_in_order(dialog_for, session):
    session.add_link(Link(cards=(3, 4), ordered=False, name="duo"))
    dialog = dialog_for(session.links.links[0])
    assert dialog.link().cards == (3, 4)
    assert dialog.link().name == "duo"
    assert dialog._ordered.isChecked() is False


def test_an_excluded_card_is_signalled_in_the_dialog(dialog_for, session):
    session.set_excluded([0], True)
    dialog = dialog_for()
    labels = [dialog._candidates.item(r).text()
              for r in range(dialog._candidates.count())]
    assert sum("exclue" in label for label in labels) == 1


# --- Bout en bout ---------------------------------------------------------


def test_a_link_survives_the_renumbering_of_the_selection(qt_app, tmp_path):
    """Le piège central du projet : les cartes retenues sont renumérotées avant
    l'optimisation. Un lien non traduit collerait deux cartes que l'utilisateur
    n'a jamais liées, sans qu'aucune erreur ne le signale."""
    import numpy as np

    from pokemon_mosaic.control import RunControl
    from pokemon_mosaic.optimize import StopConditions, optimize_grid
    from pokemon_mosaic.ui.runner import RunWorker
    from pokemon_mosaic.ui.session import Session

    session = Session()
    names = [f"c{i}" for i in range(9)]
    card_set = card_set_in(tmp_path, {"jeu": names})
    # Des vignettes distinctes : sur des cartes identiques, toutes les positions
    # se valent et le test ne prouverait rien de l'optimisation.
    rng = np.random.default_rng(7)
    for card in card_set:
        card.thumbnail = rng.integers(0, 255, (8, 6, 3), dtype=np.uint8)
        card.calculate_features()
    session.set_cards(card_set, str(tmp_path))

    # On exclut deux cartes situées **avant** les cartes liées : leurs indices
    # descendent de deux rangs au moment de la sélection.
    session.set_excluded([0, 1], True)
    session.add_link(Link(cards=(5, 4)))
    session.set_layout(cols=4, rows=2)

    cards, links, _, grid, distances = RunWorker(
        session, RunControl())._prepare()
    # Les indices du lien ont suivi la renumérotation : 5 et 4 sont devenus 3 et 2.
    assert [link.cards for link in links] == [(3, 2)]
    optimize_grid(grid, distances, links.group_map(),
                  stop=StopConditions(max_iterations=2000))

    positions = {card.source_index: tuple(np.argwhere(grid == card.index)[0])
                 for card in cards}
    (row_a, col_a), (row_b, col_b) = positions[5], positions[4]
    assert row_a == row_b and col_b == col_a + 1


def test_creating_from_the_panel_adds_the_composed_link(panel, session, monkeypatch):
    """Le dialogue est modal : on le court-circuite pour exercer le branchement."""
    from pokemon_mosaic.ui import link_dialog

    def accept(self):
        pick(self, "entei", "raikou")
        return 1

    monkeypatch.setattr(link_dialog.LinkDialog, "exec", accept)
    panel._create()
    assert [link.cards for link in session.links] == [(3, 4)]


def test_cancelling_the_dialog_changes_nothing(panel, session, monkeypatch):
    from pokemon_mosaic.ui import link_dialog

    monkeypatch.setattr(link_dialog.LinkDialog, "exec", lambda self: 0)
    panel._create()
    assert len(session.links) == 0
