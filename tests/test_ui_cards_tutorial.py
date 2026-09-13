"""Tests des tutoriels de l'étape 1 : l'écran vide, puis la galerie."""

import pytest
from test_ui_session import card_set_in


@pytest.fixture
def reglages(tmp_path):
    from PySide6.QtCore import QSettings

    return QSettings(str(tmp_path / "reglages.ini"), QSettings.IniFormat)


@pytest.fixture
def fenetre(qt_app, tmp_path, monkeypatch, reglages):
    from pokemon_mosaic.ui.i18n import LanguageManager
    from pokemon_mosaic.ui.main_window import MainWindow
    from pokemon_mosaic.ui.session import Session

    monkeypatch.setattr(MainWindow, "settings", staticmethod(lambda: reglages))
    session = Session()
    ecran = MainWindow(LanguageManager(qt_app), session,
                       presets_directory=str(tmp_path / "presets"),
                       arrangements_directory=str(tmp_path / "agencements"))
    ecran.resize(900, 640)
    yield ecran, session
    ecran._tutorial.overlay.stop()
    ecran.close()
    ecran.deleteLater()


def garnir(ecran, session, tmp_path):
    session.set_cards(card_set_in(tmp_path, {"s": ["a", "b", "c"]}), str(tmp_path))
    ecran._cards_step._update_state()


def zones_visibles(tutoriel, hote):
    from pokemon_mosaic.ui.tutorial import zone_rect

    return [zone.widget() for zone in tutoriel.zones()
            if not zone_rect(zone.widget(), hote).isEmpty()]


# --- L'écran décrit son tutoriel -------------------------------------------

def test_the_empty_screen_explains_its_two_actions(qt_app, fenetre):
    ecran, _ = fenetre
    ecran.show()
    qt_app.processEvents()
    etape = ecran._cards_step

    tutoriel = ecran.current_tutorial()

    assert tutoriel.key == "cartes"
    assert zones_visibles(tutoriel, ecran) == [
        etape._empty_title, etape._download, etape._locate, ecran._help]


def test_the_gallery_has_its_own_tutorial(qt_app, fenetre, tmp_path):
    ecran, session = fenetre
    ecran.show()
    garnir(ecran, session, tmp_path)
    qt_app.processEvents()
    etape = ecran._cards_step

    tutoriel = ecran.current_tutorial()

    assert tutoriel.key == "cartes-galerie"
    # Les avertissements sont cachés sans anomalie : pas de zone.
    assert zones_visibles(tutoriel, ecran) == [
        etape._gallery, etape._folders, etape._search, etape._bulk,
        etape._links, etape._count, etape._update_catalogue,
        ecran._presets, ecran._next, ecran._help]


def test_every_zone_has_a_text_without_em_dash(qt_app, fenetre, tmp_path):
    ecran, session = fenetre
    for tutoriel in (ecran.current_tutorial(),
                     (garnir(ecran, session, tmp_path), ecran.current_tutorial())[1]):
        for zone in tutoriel.zones():
            texte = zone.text()
            assert texte.strip()
            assert "—" not in texte and "–" not in texte


def test_a_step_without_tutorial_has_none(fenetre, tmp_path):
    """L'export n'a pas encore sa visite : pas de voile vide pour autant."""
    ecran, session = fenetre
    garnir(ecran, session, tmp_path)

    ecran._stack.setCurrentIndex(3)

    assert ecran.current_tutorial() is None


# --- La visite guidée démarre au bon moment --------------------------------

def test_the_first_start_guides_through_the_empty_screen(qt_app, fenetre):
    ecran, _ = fenetre

    ecran.show()
    qt_app.processEvents()

    assert ecran._tutorial.is_guiding()
    assert ecran._tutorial.overlay.tutorial().key == "cartes"
    assert not ecran._help.isEnabled()


def test_no_guide_while_cards_are_loading(qt_app, fenetre):
    ecran, _ = fenetre
    ecran._cards_step._loading = True

    ecran.show()
    qt_app.processEvents()

    assert not ecran._tutorial.is_guiding()


def test_the_gallery_guide_starts_when_loading_ends(qt_app, fenetre, tmp_path,
                                                    reglages):
    """La visite complémentaire : la galerie n'existait pas à la première."""
    from pokemon_mosaic.ui.tutorial import TutorialStore

    ecran, session = fenetre
    TutorialStore(lambda: reglages).mark_seen("cartes")
    ecran.show()
    qt_app.processEvents()
    assert not ecran._tutorial.is_guiding()
    etape = ecran._cards_step

    etape._loading = True
    garnir(ecran, session, tmp_path)
    qt_app.processEvents()
    assert not ecran._tutorial.is_guiding(), "pas pendant le chargement"

    etape._loading = False
    etape._update_state()
    qt_app.processEvents()

    assert ecran._tutorial.is_guiding()
    assert ecran._tutorial.overlay.tutorial().key == "cartes-galerie"


def test_a_failed_start_up_load_still_guides_the_empty_screen(qt_app, fenetre,
                                                             tmp_path):
    """Comme `app.py` : la fenêtre s'affiche, puis le dossier retenu se charge.
    Un dossier sans image échoue avant tout lot, et l'écran reste vide."""
    import time

    ecran, _ = fenetre
    vide = tmp_path / "vide"
    vide.mkdir()

    ecran.show()
    ecran.load_cards(str(vide))
    fin = time.monotonic() + 10
    while ecran._cards_step._loading and time.monotonic() < fin:
        qt_app.processEvents()
    qt_app.processEvents()

    assert not ecran._cards_step._loading
    assert ecran._tutorial.is_guiding()
    assert ecran._tutorial.overlay.tutorial().key == "cartes"


def test_the_tutorial_signal_fires_on_state_changes_only(fenetre, tmp_path):
    ecran, session = fenetre
    etape = ecran._cards_step
    signaux = []
    etape.tutorial_changed.connect(lambda: signaux.append(1))

    etape._update_state()
    assert signaux == [], "rien n'a changé"
    garnir(ecran, session, tmp_path)
    etape._update_state()

    assert signaux == [1]


def test_help_follows_the_screen_when_the_gallery_appears(qt_app, fenetre,
                                                         tmp_path, reglages):
    from pokemon_mosaic.ui.tutorial import TutorialStore

    ecran, session = fenetre
    TutorialStore(lambda: reglages).set_skip_all(True)
    ecran.show()
    qt_app.processEvents()
    ecran._help.click()
    assert ecran._tutorial.overlay.tutorial().key == "cartes"

    garnir(ecran, session, tmp_path)
    qt_app.processEvents()

    assert ecran._tutorial.overlay.mode() == "aide"
    assert ecran._tutorial.overlay.tutorial().key == "cartes-galerie"


def test_a_guide_waits_for_its_page_to_be_ready(controleur_pret):
    ctrl, pret = controleur_pret

    ctrl._apply_page()
    assert not ctrl.is_guiding()

    pret["valeur"] = True
    ctrl._apply_page()
    assert ctrl.is_guiding()


@pytest.fixture
def controleur_pret(qt_app, reglages):
    from PySide6.QtWidgets import QPushButton, QVBoxLayout, QWidget

    from pokemon_mosaic.ui.tutorial import (
        Tutorial,
        TutorialController,
        TutorialStore,
        Zone,
    )

    hote = QWidget()
    bouton = QPushButton("un")
    QVBoxLayout(hote).addWidget(bouton)
    hote.resize(300, 200)
    hote.show()
    qt_app.processEvents()
    pret = {"valeur": False}
    tutoriel = Tutorial("essai", lambda: [Zone(lambda: bouton, lambda: "un")],
                        lambda: pret["valeur"])
    ctrl = TutorialController(hote, TutorialStore(lambda: reglages),
                              lambda: tutoriel)
    yield ctrl, pret
    ctrl.overlay.stop()
    hote.close()
