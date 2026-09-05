"""Tests des préréglages : format, identité par chemin, aller-retour complet."""

import itertools
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


@pytest.mark.parametrize("name", ["", "   ", ".", ".."])
def test_an_unusable_name_is_refused(name):
    with pytest.raises(ValueError, match="inutilisable"):
        safe_filename(name)


def test_forbidden_characters_are_encoded_not_dropped():
    """Encodés, « a/b » et « ab » restent distincts ; effacés, ils désigneraient
    le même fichier et l'un écraserait l'autre.

    Le code est **borné** par un second `_` : sa longueur va de un à six
    chiffres, et sans terminateur `_5` suivi d'un « f » littéral se confondrait
    avec `_5f`, le code de `_` lui-même.
    """
    assert safe_filename("a/b") == "a_2f_b.json"


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
    session.set_layout(cols=3, rows=2, paper="A3", dpi=150, panel_rows=2)
    session.set_algorithm(iterations=4242, use_annealing=False)

    preset = session.to_preset("essai")
    assert preset.excluded == (os.path.join("serie_A", "beta.png"),)
    assert preset.active_links == (
        LinkRef(cards=(os.path.join("serie_A", "gamma.png"),
                       os.path.join("serie_A", "delta.png")), shape=(2, 1)),
    )
    assert preset.layout["cols"] == 3 and preset.layout["paper"] == "A3"
    assert preset.layout["panel_rows"] == 2, "les lignes de feuilles aussi"
    assert preset.algorithm["iterations"] == 4242
    assert preset.algorithm["use_annealing"] is False


def test_a_sheet_without_a_name_survives_the_round_trip(session):
    """⚠️ Une feuille hors catalogue n'a pas de nom : le seul « paper » ne
    suffit plus à la décrire, et un préréglage relu aurait rendu un A2."""
    from pokemon_mosaic.presets import Preset

    session.set_layout(paper_size_mm=(300.0, 400.0))
    preset = session.to_preset("essai")
    assert preset.layout["paper"] == ""
    assert preset.layout["paper_size_mm"] == [300.0, 400.0]

    session.set_layout(paper="A5")
    relu = Preset.from_json(preset.to_json())
    assert isinstance(relu, Preset)
    session.apply_preset(relu)
    # Tuple et non liste : une liste ne serait jamais égale à la taille en
    # place, et chaque rechargement rejouerait un changement pour rien.
    assert session.paper_size_mm == (300.0, 400.0)
    assert session.paper == ""


def test_a_hand_written_offset_is_brought_back_onto_its_sheet(session):
    """⚠️ Un préréglage écrit à la main pousserait un morceau hors de sa
    feuille : l'export le ramènerait, l'écran non, et les deux ne montreraient
    plus le même poster."""
    from pokemon_mosaic.presets import Preset

    session.set_layout(paper="A5", cols=4, rows=4, panels=2)
    preset = Preset(name="essai", excluded=(), active_links=(),
                    layout={"paper": "A5", "cols": 4, "rows": 4, "panels": 2,
                            "panel_offsets": [[0, 9999.0, 9999.0],
                                              [42, 1.0, 1.0]]},
                    algorithm={})
    session.apply_preset(preset)

    libre = session.panel_free_mm(0)
    assert session.panel_offsets[0] == pytest.approx(libre)
    assert 42 not in session.panel_offsets, "une feuille qui n'existe pas"


def test_moving_a_piece_survives_the_round_trip(session):
    session.set_layout(paper="A5", cols=4, rows=4, panels=2)
    session.move_panel(1, 5.0, 1.0)
    preset = session.to_preset("essai")
    assert preset.layout["panel_offsets"] == [[1, 5.0, 1.0]]

    session.set_layout(cols=5)                # défait les déplacements
    assert session.panel_offsets == {}
    session.apply_preset(preset)
    assert session.panel_offsets == {1: (5.0, 1.0)}


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


def test_a_preset_without_holes_clears_the_ones_placed(session):
    """Les cases vides ne se posent plus d'office : un préréglage qui n'en
    mémorise aucune décrit une grille où il n'y en a aucune, et le rejouer doit
    retirer celles qui avaient été posées depuis."""
    session.set_layout(cols=4, rows=2)
    preset = session.to_preset("essai")
    assert preset.layout["empty_cells"] is None

    session.toggle_empty_cell(1, 1)
    assert session.empty_cells() == [(1, 1)]
    session.apply_preset(preset)
    assert session.empty_cells() == []


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


# --- Non-régressions de la revue du 2026-08-24 -----------------------------

def test_two_different_names_never_share_a_file():
    """`safe_filename` promet d'être injective. Elle ne l'était pas : un
    `.strip()` final effaçait les espaces de bord sans les coder, et le
    caractère d'échappement `_` n'était pas échappé lui-même."""
    paires = [("a/b", "ab"),               # effacer, au lieu de coder
              ("Essai 1", "Essai 1 "),      # frappe ordinaire
              ("Noel", "  Noel"),
              ("vacances", " vacances"),
              ("a/b", "a_2fb"),            # le caractère d'échappement
              ("a_2f_b", "a/b")]
    for premier, second in paires:
        assert safe_filename(premier) != safe_filename(second), (premier, second)


def test_safe_filename_is_injective_over_tricky_names():
    """Contrôle par force brute : les caractères qui se combinent mal entre eux."""
    alphabet = "a_ /5f2.é"
    vus = {}
    for longueur in (1, 2, 3):
        for combo in itertools.product(alphabet, repeat=longueur):
            nom = "".join(combo)
            try:
                fichier = safe_filename(nom)
            except ValueError:
                continue
            assert vus.setdefault(fichier, nom) == nom, f"{nom!r} entre en collision"


def test_saving_two_close_names_keeps_both(tmp_path):
    """Le défaut visible : le second enregistrement écrasait le premier, sans
    confirmation, et la liste n'affichait qu'une entrée."""
    save_preset(str(tmp_path), Preset(name="Essai 1"))
    save_preset(str(tmp_path), Preset(name="Essai 1 "))
    assert list_presets(str(tmp_path)) == ["Essai 1", "Essai 1 "]
    assert load_preset(str(tmp_path), "Essai 1").name == "Essai 1"
    assert load_preset(str(tmp_path), "Essai 1 ").name == "Essai 1 "


def test_a_preset_saved_under_the_old_name_is_still_readable(tmp_path):
    """Les préréglages écrits avant le changement portent l'ancien nom de
    fichier. Sans recours, tout nom contenant un `_` deviendrait introuvable."""
    ancien = tmp_path / "essai_1.json"
    ancien.write_text(Preset(name="essai_1").to_json(), encoding="utf-8")
    assert list_presets(str(tmp_path)) == ["essai_1"]
    assert load_preset(str(tmp_path), "essai_1").name == "essai_1"
    delete_preset(str(tmp_path), "essai_1")
    assert not ancien.exists()


def test_a_hand_edited_preset_says_what_is_missing():
    """L'en-tête du module présente le JSON comme modifiable à la main. Une
    ligne retirée par mégarde remontait un `KeyError` nu, qui ne nomme ni le
    champ ni le fichier, alors que l'erreur de version, elle, était claire."""
    payload = json.loads(Preset(name="x").to_json())
    del payload["name"]
    with pytest.raises(ValueError, match="champ 'name' manquant"):
        Preset.from_json(json.dumps(payload))

    payload = json.loads(Preset(name="x").to_json())
    payload["active_links"] = [{"ordered": True}]     # « cards » retiré
    with pytest.raises(ValueError, match="champ 'cards' manquant"):
        Preset.from_json(json.dumps(payload))


def test_a_broken_preset_does_not_break_the_whole_list(tmp_path):
    save_preset(str(tmp_path), Preset(name="bon"))
    (tmp_path / "casse.json").write_text('{"version": 1}', encoding="utf-8")
    assert list_presets(str(tmp_path)) == ["bon"]


def test_saving_migrates_a_legacy_named_preset_instead_of_duplicating_it(tmp_path):
    """`load_preset` sait lire l'ancien nom ; laisser le fichier en place faisait
    apparaître le préréglage deux fois dans la liste, celle-ci lisant le nom
    dans le contenu, dont une fois avec la configuration d'avant."""
    ancien = tmp_path / "essai_1.json"
    ancien.write_text(Preset(name="essai_1").to_json(), encoding="utf-8")
    save_preset(str(tmp_path), load_preset(str(tmp_path), "essai_1"))
    assert not ancien.exists()
    assert list_presets(str(tmp_path)) == ["essai_1"]
    assert [p.name for p in tmp_path.iterdir()] == [safe_filename("essai_1")]


def test_migrating_never_deletes_a_neighbours_preset(tmp_path):
    """L'ancien nom de fichier n'est pas injectif, c'est ce qui a motivé le
    changement. Effacer sur sa seule foi détruirait le préréglage du voisin :
    « Essai 1 » et « Essai 1 » s'y ramenaient au même fichier."""
    save_preset(str(tmp_path), Preset(name="Essai 1"))
    save_preset(str(tmp_path), Preset(name="Essai 1 "))
    assert list_presets(str(tmp_path)) == ["Essai 1", "Essai 1 "]


def test_a_preset_written_before_rectangles_still_loads(tmp_path):
    """Les préréglages d'avant ne portent pas de forme. `Link` en déduit alors
    une seule rangée, ce qui reproduit exactement l'ancien comportement, un
    lien y tenait toujours sur une ligne."""
    from pokemon_mosaic.presets import LinkRef

    ancien = LinkRef.from_dict({"cards": ["a.png", "b.png", "c.png"],
                                "ordered": False, "name": "trio"})
    assert ancien.shape == ()

    from pokemon_mosaic.links import Link
    assert Link(cards=(0, 1, 2), shape=ancien.shape).shape == (3, 1)


def test_a_preset_carries_the_shape_of_a_rectangle(tmp_path):
    """Sans elle, un 2×2 rechargé redeviendrait une barre de quatre, une autre
    contrainte, sans que rien ne le signale."""
    from pokemon_mosaic.presets import LinkRef

    carre = LinkRef(cards=("a.png", "b.png", "c.png", "d.png"), shape=(2, 2))
    assert LinkRef.from_dict(carre.to_dict()) == carre


def test_applying_a_preset_restores_the_shape_of_a_link(session):
    """Les mêmes cartes en colonne ou en ligne ne sont pas la même contrainte.
    Garder celle de la bibliothèque rechargeait autre chose que l'enregistré."""
    session.add_link(Link(cards=(2, 3), shape=(1, 2)))     # une colonne
    preset = session.to_preset("colonne")

    # L'utilisateur refait le lien à l'horizontale entre-temps.
    session.remove_link(session.links.links[0])
    session.add_link(Link(cards=(2, 3), shape=(2, 1)))

    session.apply_preset(preset)
    assert session.links.active[0].shape == (1, 2)


def test_applying_an_old_preset_does_not_flatten_a_rectangle(session):
    """Un préréglage d'avant les rectangles ne porte aucune forme : la laisser
    s'appliquer telle quelle ramènerait le lien à une seule rangée."""
    from pokemon_mosaic.presets import LinkRef, Preset

    session.add_link(Link(cards=(2, 3), shape=(1, 2)))
    chemins = tuple(session.relative_path(i) for i in (2, 3))
    ancien = Preset(name="avant", active_links=(LinkRef(cards=chemins),))

    session.apply_preset(ancien)
    assert session.links.active[0].shape == (1, 2)
