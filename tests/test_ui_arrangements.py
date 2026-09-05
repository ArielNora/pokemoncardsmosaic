"""Tests du menu des agencements enregistrés."""

import numpy as np
import pytest

from pokemon_mosaic.arrangements import Arrangement, list_arrangements, save_arrangement
from pokemon_mosaic.cards import Card, CardSet


def card_set_in(tmp_path, names, size=(6, 8)):
    """Arborescence réelle : un agencement se relit par chemins."""
    width, height = size
    dossier = tmp_path / "cartes" / "a"
    dossier.mkdir(parents=True, exist_ok=True)
    cards = []
    for nom in names:
        chemin = dossier / f"{nom}.webp"
        chemin.touch()
        vignette = np.full((height, width, 3), (len(cards) * 30) % 255, np.uint8)
        card = Card(path=str(chemin), index=len(cards), thumbnail=vignette)
        card.top = card.bottom = card.left = card.right = np.zeros(3)
        cards.append(card)
    return CardSet(cards=cards, full_size=(713, 984), thumb_size=size)


@pytest.fixture
def session(qt_app, tmp_path):
    from pokemon_mosaic.ui.session import Session

    s = Session()
    s.set_cards(card_set_in(tmp_path, ["un", "deux", "trois", "quatre"]),
                str(tmp_path / "cartes"))
    return s


@pytest.fixture
def bibliotheque(tmp_path):
    return str(tmp_path / "agencements")


def range_un(bibliotheque, name="essai", cards=("a/un.webp", "a/deux.webp"),
             grid=((0, 1), (1, 0)), saved_at="2026-09-05T18:00:00", **reste):
    arrangement = Arrangement(name=name, cards=cards, grid=grid,
                              saved_at=saved_at, **reste)
    save_arrangement(bibliotheque, arrangement)
    return arrangement


@pytest.fixture
def menu(session, bibliotheque):
    from pokemon_mosaic.ui.arrangements_dialog import ArrangementsDialog

    range_un(bibliotheque)
    return ArrangementsDialog(session, bibliotheque), session, bibliotheque


def test_the_menu_lists_the_library(menu):
    widget, _, bibliotheque = menu
    range_un(bibliotheque, "second", saved_at="2026-09-06T09:00:00")
    widget.reload()

    assert widget._list.count() == 2
    assert widget.current().name == "second", "le plus récent en tête"


def test_a_missing_card_is_counted_named_and_crossed(menu, bibliotheque):
    """⚠️ Amputé, ce n'est plus l'agencement qu'on a partagé : on le montre, on
    dit ce qui manque, et on ne le laisse pas passer."""
    widget, _, _ = menu
    range_un(bibliotheque, "troué", cards=("a/un.webp", "a/jamais-vue.webp"),
             saved_at="2026-09-07T09:00:00")
    widget.reload(select="troué")

    assert "manquante" in widget._list.item(0).text()
    assert "jamais-vue" in widget._cards.item(0).text()
    assert widget._cards.item(0).text().startswith("✕")
    assert widget._missing.text() != ""
    assert not widget._open.isEnabled(), "il ne doit pas passer à l'export"


def test_a_complete_arrangement_can_be_opened_into_a_slot(menu):
    widget, session, _ = menu

    widget._open_current()

    garde = session.saved[0]
    assert garde is not None
    noms = [[garde.cards[case].name for case in ligne] for ligne in garde.grid]
    assert noms == [["un", "deux"], ["deux", "un"]]


def test_opening_says_when_every_slot_is_taken(menu, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    from pokemon_mosaic.ui.session import MAX_SAVED

    widget, session, _ = menu
    jeu = session.card_set
    for numero in range(MAX_SAVED):
        session.save_grid(np.array([[0, 1]]), jeu, numero, 0.0)
    vus = []
    monkeypatch.setattr(QMessageBox, "information",
                        lambda *a, **k: vus.append(a[2]))

    widget._open_current()

    assert vus, "l'utilisateur doit savoir pourquoi rien ne s'ouvre"


def test_exporting_writes_the_chosen_file(menu, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QFileDialog

    from pokemon_mosaic.arrangements import read_arrangement

    widget, _, _ = menu
    cible = tmp_path / "partage.json"
    monkeypatch.setattr(QFileDialog, "getSaveFileName",
                        lambda *a, **k: (str(cible), ""))

    widget._export_current()

    assert read_arrangement(str(cible)).name == "essai"


def test_importing_never_overwrites_a_namesake(menu, tmp_path, monkeypatch):
    """Deux personnes nomment volontiers leur essai de la même façon."""
    from PySide6.QtWidgets import QFileDialog

    from pokemon_mosaic.arrangements import write_arrangement

    widget, _, bibliotheque = menu
    venu = tmp_path / "venu.json"
    write_arrangement(str(venu), Arrangement(name="essai", cards=("a/un.webp",),
                                             grid=((0,),), score=9.0))
    monkeypatch.setattr(QFileDialog, "getOpenFileName",
                        lambda *a, **k: (str(venu), ""))

    widget._import_file()

    noms = sorted(un.name for un in list_arrangements(bibliotheque))
    assert noms == ["essai", "essai (2)"]


def test_an_unreadable_file_is_reported_not_raised(menu, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QFileDialog, QMessageBox

    widget, _, bibliotheque = menu
    casse = tmp_path / "casse.json"
    casse.write_text("{ pas du json", encoding="utf-8")
    monkeypatch.setattr(QFileDialog, "getOpenFileName",
                        lambda *a, **k: (str(casse), ""))
    vus = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: vus.append(a[1]))

    widget._import_file()

    assert vus
    assert len(list_arrangements(bibliotheque)) == 1


def test_renaming_and_deleting_go_through_the_library(menu, monkeypatch):
    from PySide6.QtWidgets import QInputDialog, QMessageBox

    widget, _, bibliotheque = menu
    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: ("baptisé", True))
    widget._rename_current()
    assert [un.name for un in list_arrangements(bibliotheque)] == ["baptisé"]

    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.Yes)
    widget._delete_current()
    assert list_arrangements(bibliotheque) == []


def test_deleting_asks_first(menu, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    widget, _, bibliotheque = menu
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.No)

    widget._delete_current()

    assert len(list_arrangements(bibliotheque)) == 1


def test_the_preview_crosses_the_missing_cards(session, bibliotheque):
    """La croix rouge se voit dans l'image, pas seulement dans la liste."""
    from pokemon_mosaic.ui.arrangements_dialog import MISSING_FILL, arrangement_image

    arrangement = Arrangement(name="troué", cards=("a/un.webp", "a/perdue.webp"),
                              grid=((0, 1),))
    image = arrangement_image(arrangement, session, (255, 255, 255))

    largeur = image.width() // 2
    couleurs = {image.pixelColor(x, image.height() // 2).name()
                for x in range(largeur, image.width())}
    assert MISSING_FILL.name() in couleurs or any(
        couleur != "#ffffff" for couleur in couleurs)
    assert image.pixelColor(2, image.height() // 2).name() != MISSING_FILL.name()


def test_an_empty_library_says_so(session, bibliotheque):
    from pokemon_mosaic.ui.arrangements_dialog import ArrangementsDialog

    widget = ArrangementsDialog(session, bibliotheque)

    assert widget.current() is None
    assert not widget._open.isEnabled()
    assert "Aucun" in widget._title.text()
