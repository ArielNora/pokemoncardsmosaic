"""Tests de la bascule de langue."""

import pytest


@pytest.fixture
def language(qt_app):
    """Un gestionnaire par test, qui retire ses traducteurs à la sortie.

    La QApplication est partagée par toute la session : sans ce nettoyage, un
    traducteur installé par un test resterait actif pour les suivants, qu'un
    autre gestionnaire ne saurait pas retirer (il ne connaît que les siens).
    """
    from pokemon_mosaic.ui.i18n import LanguageManager

    manager = LanguageManager(qt_app)
    yield manager
    # `set_language("fr")` ne suffit pas : il sort sans rien faire quand la
    # langue est déjà le français, et les traducteurs installés à la
    # construction resteraient en place.
    manager.uninstall()


def test_french_is_the_source_language(language):
    assert language.current == "fr"


def test_unknown_language_is_refused(language):
    with pytest.raises(ValueError, match="Langue inconnue"):
        language.set_language("de")


def test_switching_language_emits_once(language):
    seen = []
    language.language_changed.connect(seen.append)
    language.set_language("en")
    language.set_language("en")  # déjà active : aucun signal
    assert seen == ["en"]


def test_english_translations_are_compiled_and_applied(qt_app, language):
    """Sans .qm compilé, le sélecteur de langue ne ferait rien du tout."""
    from pokemon_mosaic.ui.i18n import TRANSLATIONS_DIR

    if not (TRANSLATIONS_DIR / "pokemon_mosaic_en.qm").exists():
        pytest.skip("traductions non compilées (pyside6-lrelease)")

    language.set_language("en")
    assert qt_app.translate("MainWindow", "Cartes") == "Cards"
    assert qt_app.translate("CardsStep", "Dossiers") == "Folders"

    language.set_language("fr")
    assert qt_app.translate("MainWindow", "Cartes") == "Cartes"


def test_step_titles_are_extractable_not_dynamic():
    """`tr()` sur une variable n'est pas extrait par lupdate : les titres
    resteraient en français. Ils doivent être écrits en toutes lettres."""
    import inspect

    from pokemon_mosaic.ui.main_window import MainWindow

    source = inspect.getsource(MainWindow.step_title)
    for literal in ('self.tr("Cartes")', 'self.tr("Réglages")'):
        assert literal in source


def test_qt_standard_buttons_are_translated_in_french(qt_app, language):
    """Les boutons des dialogues viennent de Qt, pas de nos `tr()`. Sans charger
    `qtbase_fr`, un dialogue affiche « Cancel » en pleine interface française."""
    assert qt_app.translate("QPlatformTheme", "Cancel") == "Annuler"


def test_a_manager_removes_its_translators_on_uninstall(qt_app):
    """Sans cela, chaque gestionnaire créé laisse un traducteur installé sur la
    QApplication partagée : le nettoyage annoncé par les tests ne se ferait pas."""
    from pokemon_mosaic.ui.i18n import LanguageManager

    manager = LanguageManager(qt_app)
    assert manager._translators, "qtbase doit être chargé dès la construction"
    manager.uninstall()
    assert manager._translators == []
