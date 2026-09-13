"""Tests des visites de l'étape 2 : une par onglet."""

import pytest
from test_ui_session import card_set_in


@pytest.fixture
def reglages(tmp_path):
    from PySide6.QtCore import QSettings

    return QSettings(str(tmp_path / "reglages.ini"), QSettings.IniFormat)


@pytest.fixture
def fenetre(qt_app, tmp_path, monkeypatch, reglages):
    """La fenêtre sur l'étape 2, cartes chargées, visites de l'étape 1 vues."""
    from pokemon_mosaic.ui.i18n import LanguageManager
    from pokemon_mosaic.ui.main_window import MainWindow
    from pokemon_mosaic.ui.session import Session
    from pokemon_mosaic.ui.tutorial import TutorialStore

    monkeypatch.setattr(MainWindow, "settings", staticmethod(lambda: reglages))
    store = TutorialStore(lambda: reglages)
    for cle in ("cartes", "cartes-galerie"):
        store.mark_seen(cle)
    session = Session()
    session.set_cards(card_set_in(tmp_path, {"s": [str(i) for i in range(12)]}),
                      str(tmp_path))
    ecran = MainWindow(LanguageManager(qt_app), session,
                       presets_directory=str(tmp_path / "presets"),
                       arrangements_directory=str(tmp_path / "agencements"))
    ecran.resize(1000, 700)
    ecran.show()
    ecran._stack.setCurrentIndex(1)
    qt_app.processEvents()
    yield ecran, store
    ecran._tutorial.overlay.stop()
    ecran.close()
    ecran.deleteLater()


def zones_visibles(tutoriel, hote):
    from pokemon_mosaic.ui.tutorial import zone_rect

    return [zone.widget() for zone in tutoriel.zones()
            if not zone_rect(zone.widget(), hote).isEmpty()]


def aller(qt_app, ecran, position):
    etape = ecran._layout_step
    etape.validate_all()
    etape._show(position)
    qt_app.processEvents()
    return etape, etape._tabs[position]


# --- Chaque onglet décrit sa visite ----------------------------------------

def test_the_pages_tab_starts_with_the_list_of_parts(qt_app, fenetre):
    ecran, _ = fenetre
    etape, onglet = aller(qt_app, ecran, 0)

    tutoriel = ecran.current_tutorial()

    assert tutoriel.key == "pages"
    # Sans avertissement de lien, le libellé vide n'a pas de zone.
    assert zones_visibles(tutoriel, ecran) == [
        etape._list, onglet._paper, onglet._landscape, onglet._preview,
        onglet._summary]


def test_the_grid_size_tab(qt_app, fenetre):
    ecran, _ = fenetre
    _, onglet = aller(qt_app, ecran, 1)

    tutoriel = ecran.current_tutorial()

    assert tutoriel.key == "grille-taille"
    attendues = [onglet._cols, onglet._rows, onglet._suggestions_box,
                 onglet._preview, onglet._auto_place, onglet._clear_place,
                 onglet._status]
    assert zones_visibles(tutoriel, ecran) == attendues


def test_the_card_size_tab(qt_app, fenetre):
    ecran, _ = fenetre
    _, onglet = aller(qt_app, ecran, 2)

    tutoriel = ecran.current_tutorial()

    assert tutoriel.key == "grille-cartes"
    assert zones_visibles(tutoriel, ecran) == [
        onglet._width, onglet._real_card, onglet._gap, onglet._show_shapes,
        onglet._preview, onglet._status]


def test_the_placement_tab(qt_app, fenetre):
    ecran, _ = fenetre
    _, onglet = aller(qt_app, ecran, 3)

    tutoriel = ecran.current_tutorial()

    assert tutoriel.key == "grille-emplacement"
    assert zones_visibles(tutoriel, ecran) == [
        onglet._preview, onglet._center, onglet._reset, onglet._status]


def test_the_advanced_tab_outlines_its_sections(qt_app, fenetre):
    ecran, _ = fenetre
    _, onglet = aller(qt_app, ecran, 4)

    tutoriel = ecran.current_tutorial()

    assert tutoriel.key == "avances"
    zones = [zone.widget() for zone in tutoriel.zones()]
    assert zones[0] is onglet._notice and zones[-1] is onglet._projection
    assert zones[1] is onglet._metric_title.parentWidget()
    assert zones[3] is onglet._settings_title.parentWidget()
    assert onglet._notice in zones_visibles(tutoriel, ecran)


def test_a_link_warning_gets_its_zone(qt_app, fenetre):
    ecran, _ = fenetre
    _etape, onglet = aller(qt_app, ecran, 0)

    onglet._warnings.setText("Un lien déborde.")
    qt_app.processEvents()

    assert onglet._warnings in zones_visibles(ecran.current_tutorial(), ecran)


def test_every_text_is_short_and_without_em_dash(qt_app, fenetre):
    ecran, _ = fenetre
    for position in range(5):
        aller(qt_app, ecran, position)
        for zone in ecran.current_tutorial().zones():
            texte = zone.text()
            assert texte.strip()
            assert "—" not in texte and "–" not in texte
            assert len(texte) <= 90, texte


# --- La visite démarre sur chaque onglet -----------------------------------

def test_arriving_on_the_step_guides_the_first_tab(qt_app, fenetre):
    ecran, _ = fenetre

    assert ecran._tutorial.is_guiding()
    assert ecran._tutorial.overlay.tutorial().key == "pages"


def test_moving_to_another_tab_starts_its_guide(qt_app, fenetre):
    ecran, store = fenetre
    ecran._tutorial.overlay.stop()
    store.mark_seen("pages")
    signaux = []
    ecran._layout_step.tutorial_changed.connect(lambda: signaux.append(1))

    aller(qt_app, ecran, 1)
    qt_app.processEvents()

    assert signaux == [1]
    assert ecran._tutorial.is_guiding()
    assert ecran._tutorial.overlay.tutorial().key == "grille-taille"


def test_reselecting_the_same_tab_does_not_announce_a_change(qt_app, fenetre):
    ecran, _ = fenetre
    """Cliquer l'intitulé « Grille » repose la sélection sur l'onglet affiché :
    le même onglet revient, sa visite ne repart pas."""
    etape = ecran._layout_step
    signaux = []
    etape.tutorial_changed.connect(lambda: signaux.append(1))

    etape._list.setCurrentRow(etape._family_rows["grid"])

    assert etape._list.currentRow() == etape._row_of(0)
    assert signaux == []


def test_a_tab_change_on_a_hidden_step_starts_nothing(qt_app, fenetre):
    ecran, store = fenetre
    ecran._tutorial.overlay.stop()
    store.mark_seen("pages")
    ecran._stack.setCurrentIndex(0)
    qt_app.processEvents()

    ecran._layout_step.validate_all()
    ecran._layout_step._show(1)
    qt_app.processEvents()

    assert not ecran._tutorial.is_guiding()
