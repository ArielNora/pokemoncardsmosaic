"""Tests du format des agencements gardés et de leur bibliothèque."""

import json

import pytest

from pokemon_mosaic.arrangements import (
    Arrangement,
    default_name,
    delete_arrangement,
    list_arrangements,
    read_arrangement,
    rename_arrangement,
    save_arrangement,
    unique_name,
    write_arrangement,
)


def un_agencement(name="essai", **changes):
    base = {
        "name": name,
        "cards": ("a/un.webp", "a/deux.webp", "b/trois.webp"),
        "grid": ((0, 1), (2, -1)),
        "presentation": {"paper": "A3", "dpi": 300},
        "score": 12.5,
        "saved_at": "2026-09-05T18:40:00+02:00",
    }
    base.update(changes)
    return Arrangement(**base)


def test_a_round_trip_keeps_everything():
    lu = Arrangement.from_json(un_agencement().to_json())
    assert lu == un_agencement()
    assert lu.shape == (2, 2), "(colonnes, lignes), la convention du projet"


def test_the_cards_are_listed_once_and_the_grid_points_at_them():
    """441 cartes en 21×21 tiennent ainsi en 25 Ko au lieu d'une centaine."""
    payload = json.loads(un_agencement().to_json())
    assert payload["cards"] == ["a/un.webp", "a/deux.webp", "b/trois.webp"]
    assert payload["grid"] == [[0, 1], [2, -1]]


def test_another_version_is_refused():
    texte = un_agencement().to_json().replace('"version": 1', '"version": 7')
    with pytest.raises(ValueError, match="version 7"):
        Arrangement.from_json(texte)


def test_a_missing_field_names_itself():
    """Le fichier est présenté comme modifiable à la main : un `KeyError` nu ne
    dirait ni le champ ni le fichier."""
    texte = json.dumps({"version": 1, "name": "x", "cards": []})
    with pytest.raises(ValueError, match="grid"):
        Arrangement.from_json(texte)


def test_a_cell_pointing_nowhere_is_refused():
    """Sans ce contrôle, la relecture montrerait une carte au hasard, ou
    planterait bien plus loin."""
    contenu = json.loads(un_agencement().to_json())
    contenu["grid"] = [[0, 1], [9, -1]]
    with pytest.raises(ValueError, match="ne désigne"):
        Arrangement.from_json(json.dumps(contenu))


def test_rows_of_different_lengths_are_refused():
    contenu = json.loads(un_agencement().to_json())
    contenu["grid"] = [[0, 1], [2]]
    with pytest.raises(ValueError, match="même longueur"):
        Arrangement.from_json(json.dumps(contenu))


def test_the_default_name_says_the_shape_the_date_and_the_score():
    from datetime import UTC, datetime

    nom = default_name((21, 21), 57658.4,
                       datetime(2026, 9, 5, 18, 40, tzinfo=UTC))
    assert nom == "21 × 21, 2026-09-05 18:40, score 57658"


def test_the_library_lists_the_newest_first(tmp_path):
    save_arrangement(str(tmp_path), un_agencement("vieux", saved_at="2026-01-01T00:00:00"))
    save_arrangement(str(tmp_path), un_agencement("neuf", saved_at="2026-09-05T00:00:00"))

    assert [un.name for un in list_arrangements(str(tmp_path))] == ["neuf", "vieux"]


def test_a_broken_file_does_not_break_the_whole_library(tmp_path):
    save_arrangement(str(tmp_path), un_agencement("bon"))
    (tmp_path / "casse.json").write_text("{ pas du json", encoding="utf-8")

    assert [un.name for un in list_arrangements(str(tmp_path))] == ["bon"]


def test_a_taken_name_is_suffixed(tmp_path):
    """Deux calculs peuvent tomber dans la même minute sur la même forme et le
    même score arrondi : sans cela le second écraserait le premier."""
    save_arrangement(str(tmp_path), un_agencement("essai"))
    assert unique_name(str(tmp_path), "essai") == "essai (2)"

    save_arrangement(str(tmp_path), un_agencement("essai (2)"))
    assert unique_name(str(tmp_path), "essai") == "essai (3)"
    assert unique_name(str(tmp_path), "autre") == "autre"


def test_renaming_moves_the_file_with_the_name(tmp_path):
    """Le nom vit dans le contenu **et** donne le nom du fichier : les changer
    séparément laisserait un agencement introuvable par son fichier."""
    save_arrangement(str(tmp_path), un_agencement("avant"))

    rename_arrangement(str(tmp_path), "avant", "après")

    noms = [un.name for un in list_arrangements(str(tmp_path))]
    assert noms == ["après"]
    assert len(list(tmp_path.glob("*.json"))) == 1


def test_deleting_removes_the_file(tmp_path):
    save_arrangement(str(tmp_path), un_agencement("jetable"))
    delete_arrangement(str(tmp_path), "jetable")
    assert list_arrangements(str(tmp_path)) == []


def test_an_export_writes_where_it_is_told(tmp_path):
    cible = tmp_path / "partage.json"
    write_arrangement(str(cible), un_agencement("à envoyer"))

    assert read_arrangement(str(cible)).name == "à envoyer"


def test_an_interrupted_write_leaves_the_previous_file_intact(tmp_path, monkeypatch):
    """Écriture puis remplacement : un fichier tronqué ne se rechargerait plus."""
    import os

    save_arrangement(str(tmp_path), un_agencement("essai"))
    monkeypatch.setattr(os, "replace",
                        lambda *a: (_ for _ in ()).throw(OSError("disque plein")))

    with pytest.raises(OSError):
        save_arrangement(str(tmp_path), un_agencement("essai", score=999.0))

    assert list_arrangements(str(tmp_path))[0].score == 12.5


def test_the_library_of_a_folder_that_does_not_exist_is_empty(tmp_path):
    assert list_arrangements(str(tmp_path / "jamais")) == []
