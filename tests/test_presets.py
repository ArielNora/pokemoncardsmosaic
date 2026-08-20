"""Tests des préréglages : format, identité par chemin, aller-retour complet."""

import json
import os

import numpy as np
import pytest

from pokemon_mosaic.cards import Card, CardSet
from pokemon_mosaic.links import Link
from pokemon_mosaic.presets import (
    LinkRef,
    Preset,
    delete_preset,
    list_presets,
    load_preset,
    safe_filename,
    save_preset,
)


def card_set_in(tmp_path, layout):
    cards = []
    for folder, names in layout.items():
        directory = tmp_path / folder
        directory.mkdir(parents=True, exist_ok=True)
        for name in names:
            path = directory / f"{name}.png"
            path.touch()
            card = Card(path=str(path), index=len(cards),
                        thumbnail=np.zeros((8, 6, 3), np.uint8))
            card.calculate_features()
            cards.append(card)
    return CardSet(cards=cards, full_size=(713, 984), thumb_size=(6, 8))


@pytest.fixture
def session(qt_app, tmp_path):
    from pokemon_mosaic.ui.session import Session

    s = Session()
    s.set_cards(
        card_set_in(tmp_path, {"serie_A": ["alpha", "beta", "gamma", "delta"],
                               "serie_B": ["epsilon", "zeta"]}),
        str(tmp_path),
    )
    return s


# --- Format ---------------------------------------------------------------

def test_a_preset_survives_a_round_trip_through_json():
    preset = Preset(name="poster A2", excluded=("a/x.png",),
                    active_links=(LinkRef(cards=("a/y.png", "a/z.png"),
                                          ordered=False, name="duo"),),
                    layout={"cols": 17, "rows": 17},
                    algorithm={"iterations": 5000})
    assert Preset.from_json(preset.to_json()) == preset


def test_an_unknown_version_is_refused():
    payload = json.loads(Preset(name="x").to_json())
    payload["version"] = 99
    with pytest.raises(ValueError, match="version 99"):
        Preset.from_json(json.dumps(payload))


def test_two_different_names_never_share_a_file():
    """Effacer les caractères interdits ferait collisionner « a/b » et « ab »,
    et enregistrer l'un écraserait l'autre sans un mot."""
    assert safe_filename("a/b") != safe_filename("ab")


@pytest.mark.parametrize("name", ["", "   ", ".", ".."])
def test_an_unusable_name_is_refused(name):
    with pytest.raises(ValueError, match="inutilisable"):
        safe_filename(name)


def test_forbidden_characters_are_encoded_not_dropped():
    """Encodés, « a/b » et « ab » restent distincts ; effacés, ils désigneraient
    le même fichier et l'un écraserait l'autre."""
    assert safe_filename("a/b") == "a_2fb.json"


def test_accents_are_kept_in_filenames():
    assert safe_filename("poster été") == "poster été.json"


# --- Le dossier de préréglages --------------------------------------------

def test_saving_then_listing_and_loading(tmp_path):
    directory = str(tmp_path / "presets")
    save_preset(directory, Preset(name="double A3", layout={"panels": 2}))
    save_preset(directory, Preset(name="poster A2", layout={"panels": 1}))
    assert list_presets(directory) == ["double A3", "poster A2"]
    assert load_preset(directory, "double A3").layout == {"panels": 2}


def test_listing_an_absent_directory_is_empty(tmp_path):
    assert list_presets(str(tmp_path / "jamais_créé")) == []


def test_a_damaged_file_does_not_hide_the_others(tmp_path):
    """Un fichier abîmé ne doit pas rendre toute la liste inutilisable."""
    directory = str(tmp_path / "presets")
    save_preset(directory, Preset(name="bon"))
    (tmp_path / "presets" / "abîmé.json").write_text("{ pas du json")
    assert list_presets(directory) == ["bon"]


def test_deleting_removes_only_that_preset(tmp_path):
    directory = str(tmp_path / "presets")
    save_preset(directory, Preset(name="un"))
    save_preset(directory, Preset(name="deux"))
    delete_preset(directory, "un")
    assert list_presets(directory) == ["deux"]


def test_an_interrupted_save_leaves_no_temporary_file(tmp_path):
    directory = str(tmp_path / "presets")
    save_preset(directory, Preset(name="un"))
    assert [f for f in os.listdir(directory) if f.endswith(".tmp")] == []


# --- Aller-retour depuis une session --------------------------------------

def test_a_preset_captures_the_whole_configuration(session):
    session.set_excluded([1], True)
    session.add_link(Link(cards=(2, 3)))
    session.set_layout(cols=3, rows=2, paper="A3", dpi=150)
    session.set_algorithm(iterations=4242, use_annealing=False)

    preset = session.to_preset("essai")
    assert preset.excluded == (os.path.join("serie_A", "beta.png"),)
    assert preset.active_links == (
        LinkRef(cards=(os.path.join("serie_A", "gamma.png"),
                       os.path.join("serie_A", "delta.png"))),
    )
    assert preset.layout["cols"] == 3 and preset.layout["paper"] == "A3"
    assert preset.algorithm["iterations"] == 4242
    assert preset.algorithm["use_annealing"] is False


def test_applying_a_preset_restores_everything(session):
    session.set_excluded([1], True)
    session.add_link(Link(cards=(2, 3)))
    session.set_layout(cols=3, rows=2, dpi=150)
    session.set_algorithm(iterations=4242)
    preset = session.to_preset("essai")

    session.set_excluded([1], False)
    session.set_excluded([0], True)
    session.remove_link(session.links.links[0])
    session.set_layout(cols=6, rows=1, dpi=300)
    session.set_algorithm(iterations=10)

    assert session.apply_preset(preset) == []
    assert session.selected_indices() == [0, 2, 3, 4, 5]
    assert [link.cards for link in session.links.active] == [(2, 3)]
    assert (session.cols, session.rows, session.dpi) == (3, 2, 150)
    assert session.iterations == 4242


def test_a_card_added_since_is_kept_by_default(session, tmp_path):
    """C'est l'usage central : retrouver sa configuration après une extension."""
    session.set_excluded([1], True)
    preset = session.to_preset("essai")

    # Nouvelle extension : les chemins existants gardent leur nom mais leurs
    # indices bougent, « serie_AA » se glissant entre serie_A et serie_B.
    session.set_cards(
        card_set_in(tmp_path, {"serie_A": ["alpha", "beta", "gamma", "delta"],
                               "serie_AA": ["neuf"],
                               "serie_B": ["epsilon", "zeta"]}),
        str(tmp_path),
    )
    assert session.apply_preset(preset) == []
    excluded = [session.relative_path(i) for i in range(session.total_cards)
                if session.is_excluded(i)]
    assert excluded == [os.path.join("serie_A", "beta.png")]
    assert session.index_of_path(os.path.join("serie_AA", "neuf.png")) is not None


def test_a_link_survives_the_renumbering_of_a_new_extension(session, tmp_path):
    session.add_link(Link(cards=(4, 5)))        # epsilon + zeta, en serie_B
    preset = session.to_preset("essai")

    session.set_cards(
        card_set_in(tmp_path, {"serie_A": ["alpha", "beta", "gamma", "delta"],
                               "serie_AA": ["neuf"],
                               "serie_B": ["epsilon", "zeta"]}),
        str(tmp_path),
    )
    session.apply_preset(preset)
    names = [[session.card_set[i].name for i in link.cards]
             for link in session.links.active]
    assert names == [["epsilon", "zeta"]]


def test_a_missing_card_is_reported_without_losing_the_rest(session, tmp_path):
    session.set_excluded([1], True)
    session.add_link(Link(cards=(4, 5)))
    preset = session.to_preset("essai")

    session.set_cards(
        card_set_in(tmp_path, {"serie_A": ["alpha", "gamma", "delta"]}),
        str(tmp_path),
    )
    missing = session.apply_preset(preset)
    assert os.path.join("serie_A", "beta.png") in missing
    assert os.path.join("serie_B", "epsilon.png") in missing
    # Le reste est bien appliqué : rien n'est exclu, aucun lien inapplicable.
    assert session.selected_count == 3
    assert session.links.active == []


def test_applying_a_preset_disables_links_it_does_not_name(session):
    preset = session.to_preset("sans liens")
    session.add_link(Link(cards=(0, 1)))
    session.apply_preset(preset)
    assert session.links.active == []
    # Désactivé, pas supprimé : un lien est un travail durable.
    assert len(session.links) == 1


def test_a_preset_link_absent_from_the_library_is_added(session):
    session.add_link(Link(cards=(0, 1)))
    preset = session.to_preset("avec lien")
    session.remove_link(session.links.links[0])

    session.apply_preset(preset)
    assert [link.cards for link in session.links.active] == [(0, 1)]


def test_pinned_empty_cells_are_restored(session):
    session.set_layout(cols=4, rows=2)       # 8 cases pour 6 cartes
    session.toggle_empty_cell(0, 0)
    pinned = session.empty_cells()
    preset = session.to_preset("essai")

    session.reset_empty_cells()
    session.apply_preset(preset)
    assert session.empty_cells() == pinned


def test_an_automatic_distribution_stays_automatic(session):
    """Figer la répartition automatique l'empêcherait de suivre un changement
    de grille ou de sélection."""
    session.set_layout(cols=4, rows=2)
    preset = session.to_preset("essai")
    assert preset.layout["empty_cells"] is None

    session.toggle_empty_cell(1, 1)
    session.apply_preset(preset)
    assert not session._empty_pinned


def test_a_recreated_link_keeps_its_free_order(session):
    """Hériter des valeurs par défaut ferait revenir un lien à ordre libre en
    lien imposé : l'optimiseur perdrait la moitié de ses placements, sans un mot."""
    session.add_link(Link(cards=(0, 1), ordered=False, name="duo"))
    preset = session.to_preset("essai")
    session.remove_link(session.links.links[0])

    session.apply_preset(preset)
    recreated = session.links.active[0]
    assert recreated.cards == (0, 1)
    assert recreated.ordered is False
    assert recreated.name == "duo"


def test_a_link_already_in_the_library_keeps_its_own_flags(session):
    """Le préréglage dit lesquels sont actifs ; c'est la bibliothèque qui
    détient les liens."""
    session.add_link(Link(cards=(0, 1), ordered=False))
    preset = session.to_preset("essai")
    session.set_link_enabled(session.links.links[0], False)

    session.apply_preset(preset)
    assert session.links.active[0].ordered is False
    assert len(session.links) == 1, "aucun doublon ne doit apparaître"
