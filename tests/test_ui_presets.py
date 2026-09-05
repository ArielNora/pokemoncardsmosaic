"""Tests de la barre des préréglages."""

import pytest
from PySide6.QtWidgets import QMessageBox
from test_presets import card_set_in

from pokemon_mosaic.links import Link
from pokemon_mosaic.presets import Preset, list_presets, save_preset


@pytest.fixture
def session(qt_app, tmp_path):
    from pokemon_mosaic.ui.session import Session

    s = Session()
    s.set_cards(card_set_in(tmp_path / "cartes", {"a": ["un", "deux", "trois"]}),
                str(tmp_path / "cartes"))
    return s


@pytest.fixture
def bar(session, tmp_path):
    from pokemon_mosaic.ui.presets_bar import PresetsBar

    return PresetsBar(session, str(tmp_path / "presets"))


@pytest.fixture
def yes(monkeypatch):
    """Répond « oui » à toute demande de confirmation."""
    monkeypatch.setattr(QMessageBox, "question",
                        staticmethod(lambda *a, **k: QMessageBox.Yes))


@pytest.fixture
def no(monkeypatch):
    monkeypatch.setattr(QMessageBox, "question",
                        staticmethod(lambda *a, **k: QMessageBox.No))


def test_the_list_starts_empty(bar):
    assert bar._names.count() == 0
    assert not bar._load.isEnabled() and not bar._delete.isEnabled()


def test_saving_adds_the_preset_and_selects_it(bar, tmp_path):
    bar.save_current("poster A2")
    assert list_presets(str(tmp_path / "presets")) == ["poster A2"]
    assert bar._names.currentText() == "poster A2"
    assert bar._load.isEnabled()


def test_an_empty_name_saves_nothing(bar, tmp_path):
    bar.save_current("   ")
    assert list_presets(str(tmp_path / "presets")) == []


def test_saving_over_an_existing_name_asks_first(bar, no, tmp_path):
    bar.save_current("essai")
    bar._session.set_layout(cols=1, rows=3)
    bar.save_current("essai")       # refusé par le fixture `no`
    from pokemon_mosaic.presets import load_preset
    assert load_preset(str(tmp_path / "presets"), "essai").layout["cols"] != 1


def test_confirming_the_overwrite_replaces_it(bar, yes, tmp_path):
    from pokemon_mosaic.presets import load_preset

    bar.save_current("essai")
    bar._session.set_layout(cols=1, rows=3)
    bar.save_current("essai")
    assert load_preset(str(tmp_path / "presets"), "essai").layout["cols"] == 1


def test_loading_restores_the_configuration(bar, session):
    session.set_layout(cols=1, rows=3)
    session.set_algorithm(iterations=1234)
    bar.save_current("essai")

    session.set_layout(cols=3, rows=1)
    session.set_algorithm(iterations=99)
    bar.load_selected()
    assert (session.cols, session.rows) == (1, 3)
    assert session.iterations == 1234


def test_loading_reports_a_missing_card(bar, session, tmp_path):
    """Un préréglage doit survivre à la disparition d'une carte, et le dire."""
    session.set_excluded([1], True)
    bar.save_current("essai")

    session.set_cards(card_set_in(tmp_path / "cartes2", {"a": ["un", "trois"]}),
                      str(tmp_path / "cartes2"))
    messages = []
    bar.status_message.connect(messages.append)
    bar.load_selected()
    assert "introuvable" in messages[-1]
    assert session.selected_count == 2


def test_deleting_asks_first(bar, no, tmp_path):
    bar.save_current("essai")
    bar.delete_selected()
    assert list_presets(str(tmp_path / "presets")) == ["essai"]


def test_confirming_the_deletion_removes_it(bar, yes, tmp_path):
    bar.save_current("essai")
    bar.delete_selected()
    assert list_presets(str(tmp_path / "presets")) == []
    assert bar._names.count() == 0


def test_deleting_leaves_the_link_library_alone(bar, session, yes):
    """Un lien est un travail durable ; un préréglage un essai jetable."""
    session.add_link(Link(cards=(0, 1)))
    bar.save_current("essai")
    bar.delete_selected()
    assert len(session.links) == 1


def test_an_unreadable_preset_is_reported_not_raised(bar, tmp_path):
    directory = tmp_path / "presets"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "cassé.json").write_text('{"version": 99, "name": "cassé"}')
    # Il n'apparaît pas dans la liste : on force son chargement par le nom.
    bar._names.addItem("cassé")
    bar._names.setCurrentText("cassé")
    messages = []
    bar.status_message.connect(messages.append)
    bar.load_selected()
    assert "illisible" in messages[-1]


def test_a_preset_saved_elsewhere_appears_after_a_refresh(bar, tmp_path):
    save_preset(str(tmp_path / "presets"), Preset(name="venu d'ailleurs"))
    assert bar._names.count() == 0
    bar.refresh()
    assert bar._names.currentText() == "venu d'ailleurs"


def test_the_window_offers_the_bar_and_a_directory(qt_app, tmp_path, session):
    from pokemon_mosaic.ui.i18n import LanguageManager
    from pokemon_mosaic.ui.main_window import MainWindow

    window = MainWindow(LanguageManager(qt_app), session,
                        presets_directory=str(tmp_path / "presets"))
    window._presets.save_current("depuis la fenêtre")
    assert list_presets(str(tmp_path / "presets")) == ["depuis la fenêtre"]
    assert MainWindow.presets_directory().endswith("presets")


def test_saving_unlocks_as_soon_as_cards_arrive(qt_app, tmp_path):
    """« Enregistrer… » ne se réévaluait qu'au changement de préréglage dans la
    liste : geste impossible tant qu'on n'en a aucun. Le tout premier préréglage
    était donc définitivement impossible à créer."""
    from pokemon_mosaic.ui.presets_bar import PresetsBar
    from pokemon_mosaic.ui.session import Session

    session = Session()
    barre = PresetsBar(session, str(tmp_path / "presets"))
    assert not barre._save.isEnabled()

    session.set_cards(card_set_in(tmp_path / "cartes", {"a": ["un", "deux"]}),
                      str(tmp_path / "cartes"))
    assert barre._save.isEnabled()


def test_saving_unlocks_on_the_very_first_batch(qt_app, tmp_path):
    """Le chargement se fait par lots : on n'attend pas le dernier."""
    from pokemon_mosaic.ui.presets_bar import PresetsBar
    from pokemon_mosaic.ui.session import Session

    session = Session()
    barre = PresetsBar(session, str(tmp_path / "presets"))
    jeu = card_set_in(tmp_path / "cartes", {"a": ["un", "deux"]})

    session.start_loading(str(tmp_path / "cartes"))
    session.append_cards(jeu.cards)
    assert barre._save.isEnabled()
