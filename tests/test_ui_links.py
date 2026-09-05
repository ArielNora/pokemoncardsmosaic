"""Tests de l'interface des liens : bibliothèque, panneau et dialogue de saisie."""

import numpy as np
import pytest
from PySide6.QtCore import Qt

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
                               ["a4a-087-entei-ex", "a4a-088-raikou-ex"],
                               "b3-aura-palpitante":
                               ["b3-194-mega-jungko-ex", "b3-157-massko",
                                "b3-156-arcko"]}),
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
    # solgaleo=0, lunala=1, necrozma=2, entei=3, raikou=4, puis la lignée
    # jungko=5, massko=6, arcko=7 : l'ordre de chargement.
    assert [link.cards for link in session.links] == [(0, 1), (3, 4), (5, 6, 7)]


def test_the_default_lineage_is_a_column_read_from_the_top(session):
    """Arcko en bas, Massko au milieu, Méga-Jungko-ex en haut : la plus évoluée
    domine, comme sur un arbre généalogique. L'ordre de lecture d'une colonne
    allant de haut en bas, c'est Jungko qui vient en premier."""
    session.apply_default_links()
    lignee = session.links.links[2]

    assert lignee.shape == (1, 3)
    noms = [session.card_set[index].name for index in lignee.cards]
    assert noms == ["b3-194-mega-jungko-ex", "b3-157-massko", "b3-156-arcko"]
    assert lignee.ordered, "le sens porte quelque chose : pas de demi-tour"


def test_default_links_are_skipped_when_the_cards_are_absent(qt_app, tmp_path):
    from pokemon_mosaic.ui.session import Session

    session = Session()
    session.set_cards(card_set_in(tmp_path, {"autre": ["pikachu", "raichu"]}),
                      str(tmp_path))
    missing = session.apply_default_links()
    assert len(session.links) == 0 and len(missing) == 7


def test_default_links_leave_an_existing_link_alone(session):
    """Rejouer les liens par défaut ne doit pas échouer sur une carte déjà prise."""
    session.add_link(Link(cards=(0, 3)))   # solgaleo + entei, à contre-emploi
    missing = session.apply_default_links()
    # Les deux paires butent sur une carte prise ; la lignée, libre, se pose.
    assert [link.cards for link in session.links] == [(0, 3), (5, 6, 7)]
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
    assert panel._list.item(0).text() == \
        "2 × 1  a3-207-solgaleo-ex → a3-204-lunala-ex"
    assert panel._list.item(1).text() == \
        "2 × 1  a4a-087-entei-ex ↔ a4a-088-raikou-ex"


def test_the_panel_does_not_draw_a_chain_across_a_rectangle(panel, session):
    """Sur un 2×2, « A → B → C → D » décrirait une chaîne là où les cartes
    forment un carré. Au-delà d'une rangée, seule la forme dit la disposition."""
    session.add_link(Link(cards=(0, 1, 2, 3), shape=(2, 2)))
    texte = panel._list.item(0).text()
    assert texte.startswith("2 × 2")
    assert "→" not in texte and "↔" not in texte


def test_the_panel_tells_a_row_from_a_column(panel, session):
    session.add_link(Link(cards=(0, 1, 2), shape=(1, 3)))
    assert panel._list.item(0).text().startswith("1 × 3")


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


# --- Dialogue : la grille -------------------------------------------------


@pytest.fixture
def dialog_for(session):
    from pokemon_mosaic.ui.link_dialog import LinkDialog

    return lambda link=None: LinkDialog(session, link=link)


def index_of(session, fragment):
    """Indice de la carte dont le nom contient ce fragment."""
    for card in session.card_set:
        if fragment in card.name:
            return card.index
    raise AssertionError(f"{fragment} absente du jeu de cartes")


def pose(dialog, session, *noms):
    """Remplit la grille en ordre de lecture, comme le ferait un glisser."""
    for position, nom in enumerate(noms):
        row, col = divmod(position, dialog._grid.cols)
        dialog._grid.place(row, col, index_of(session, nom))


def palette_names(dialog):
    """Les noms vivent en **infobulle** : la vignette occupe la cellule seule."""
    return [dialog._palette.item(row).toolTip()
            for row in range(dialog._palette.count())]


def test_the_grid_starts_as_a_single_empty_cell(dialog_for):
    """Un lien commence par une case : la forme se construit ensuite, par ses
    bords, plutôt que d'être choisie dans une liste abstraite."""
    dialog = dialog_for()
    assert dialog._grid.shape == (1, 1)
    assert dialog._grid.cards() == [None]


def test_the_dialog_builds_a_link_in_reading_order(dialog_for, session):
    dialog = dialog_for()
    dialog._grid.add_col()
    pose(dialog, session, "raikou", "entei")

    link = dialog.link()
    assert link.shape == (2, 1)
    assert link.cards == (index_of(session, "raikou"), index_of(session, "entei"))


def test_a_placed_card_leaves_the_palette(dialog_for, session):
    """Elle ne peut figurer qu'une fois dans un lien : la laisser proposée
    inviterait à un doublon que `Link` refuserait ensuite."""
    dialog = dialog_for()
    dialog._grid.add_col()
    pose(dialog, session, "raikou")

    assert not any("raikou" in nom for nom in palette_names(dialog))
    assert any("entei" in nom for nom in palette_names(dialog))


def test_clearing_a_cell_returns_the_card_to_the_palette(dialog_for, session):
    dialog = dialog_for()
    dialog._grid.add_col()
    pose(dialog, session, "raikou", "entei")
    dialog._grid.clear_cell(0, 0)

    assert any("raikou" in nom for nom in palette_names(dialog))
    assert dialog._grid.cards()[0] is None


def test_an_incomplete_rectangle_cannot_be_validated(dialog_for, session):
    """Un lien est un rectangle **plein** : une case vide n'a rien à donner à
    l'optimiseur, et `Link` refuserait le compte."""
    from PySide6.QtWidgets import QDialogButtonBox

    dialog = dialog_for()
    dialog._grid.add_col()
    dialog._grid.add_row()          # 2×2, quatre cases
    pose(dialog, session, "raikou", "entei")

    assert not dialog._buttons.button(QDialogButtonBox.Ok).isEnabled()
    assert "2" in dialog._panel.hint.text()


def test_a_single_cell_cannot_be_validated_even_when_filled(dialog_for, session):
    """Une carte seule ne contraint rien."""
    from PySide6.QtWidgets import QDialogButtonBox

    dialog = dialog_for()
    dialog._grid.place(0, 0, index_of(session, "entei"))

    assert dialog._grid.complete
    assert not dialog._buttons.button(QDialogButtonBox.Ok).isEnabled()
    assert "deux cartes" in dialog._panel.hint.text()


def test_a_full_rectangle_can_be_validated(dialog_for, session):
    from PySide6.QtWidgets import QDialogButtonBox

    dialog = dialog_for()
    dialog._grid.add_col()
    pose(dialog, session, "raikou", "entei")

    assert dialog._buttons.button(QDialogButtonBox.Ok).isEnabled()
    assert "2 × 1" in dialog._panel.hint.text()


def test_moving_a_card_to_another_cell_leaves_no_duplicate(dialog_for, session):
    """Sans le retrait de l'ancienne case, la carte figurerait deux fois et
    `Link` lèverait « une carte est répétée » à la validation."""
    dialog = dialog_for()
    dialog._grid.add_col()
    raikou = index_of(session, "raikou")
    dialog._grid.place(0, 0, raikou)
    dialog._grid.place(0, 1, raikou)

    assert dialog._grid.cards() == [None, raikou]


def test_editing_an_existing_link_is_accepted(dialog_for, session):
    from pokemon_mosaic.links import Link

    existing = Link(cards=(3, 4))
    session.links.add(existing)
    dialog = dialog_for(existing)
    dialog._name.setText("renommé")
    dialog._try_accept()

    assert dialog._error.text() == ""


def test_a_card_already_linked_elsewhere_is_refused(dialog_for, session):
    from pokemon_mosaic.links import Link

    session.links.add(Link(cards=(3, 4)))
    dialog = dialog_for()
    dialog._grid.add_col()
    dialog._grid.place(0, 0, 3)
    dialog._grid.place(0, 1, 0)
    dialog._try_accept()

    assert "appartiennent déjà" in dialog._error.text()


def test_an_existing_link_reopens_on_its_rectangle(dialog_for, session):
    """Sans cela, modifier le nom d'une colonne la renverrait en ligne."""
    from pokemon_mosaic.links import Link

    colonne = Link(cards=(0, 1, 2), shape=(1, 3), name="lignée")
    dialog = dialog_for(colonne)

    assert dialog._grid.shape == (1, 3)
    assert dialog._grid.cards() == [0, 1, 2]
    assert dialog.link().shape == (1, 3)


def test_an_excluded_card_is_signalled_in_the_dialog(dialog_for, session):
    """Un lien sur une carte retirée ne s'appliquera jamais : mieux vaut le voir
    en composant qu'après une exécution entière."""
    session.set_excluded([0], True)
    dialog = dialog_for()

    assert any("exclue" in nom for nom in palette_names(dialog))


# --- Le filtre de la palette ----------------------------------------------

def test_the_palette_can_be_filtered_by_extension(dialog_for, session):
    dialog = dialog_for()
    position = dialog._folder.findData("a4a-source-secrete")
    assert position > 0
    dialog._folder.setCurrentIndex(position)

    noms = palette_names(dialog)
    assert noms and all("a4a-source-secrete" in nom for nom in noms)


def test_the_palette_can_be_filtered_by_name(dialog_for, session):
    dialog = dialog_for()
    dialog._search.setText("entei")

    assert [nom for nom in palette_names(dialog) if "entei" in nom] \
        == palette_names(dialog)


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
        self._grid.add_col()
        pose(self, session, "entei", "raikou")
        return 1

    monkeypatch.setattr(link_dialog.LinkDialog, "exec", accept)
    panel._create()
    assert [link.cards for link in session.links] == [(3, 4)]


def test_cancelling_the_dialog_changes_nothing(panel, session, monkeypatch):
    from pokemon_mosaic.ui import link_dialog

    monkeypatch.setattr(link_dialog.LinkDialog, "exec", lambda self: 0)
    panel._create()
    assert len(session.links) == 0


def test_the_palette_shows_only_the_artwork(dialog_for):
    """Sur 441 cartes, un nom par ligne oblige à faire défiler sans fin et prend
    la place de ce qu'on cherche à reconnaître. Le nom reste en infobulle."""
    dialog = dialog_for()
    premier = dialog._palette.item(0)

    assert premier.text() == ""
    assert premier.toolTip()
    assert not premier.icon().isNull()


def test_the_error_line_stays_hidden_until_there_is_an_error(dialog_for, session):
    """Visible et vide, elle réservait une ligne entre le nom et les boutons,
    qui se lisait comme un trou."""
    from pokemon_mosaic.links import Link

    dialog = dialog_for()
    assert not dialog._error.isVisibleTo(dialog)

    session.links.add(Link(cards=(3, 4)))
    dialog._grid.add_col()
    dialog._grid.place(0, 0, 3)
    dialog._grid.place(0, 1, 0)
    dialog._try_accept()

    assert dialog._error.isVisibleTo(dialog)
