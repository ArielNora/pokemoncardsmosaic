"""Tests des visites de l'étape 3 : Lancement, Multi-lancement, et ses groupes."""

import pytest
from test_ui_multi_run import card_set, feed_tab


@pytest.fixture
def reglages(tmp_path):
    from PySide6.QtCore import QSettings

    return QSettings(str(tmp_path / "reglages.ini"), QSettings.IniFormat)


@pytest.fixture
def fenetre(qt_app, tmp_path, monkeypatch, reglages):
    """La fenêtre sur l'exécution, cartes chargées, visites d'avant vues."""
    from pokemon_mosaic.ui.i18n import LanguageManager
    from pokemon_mosaic.ui.main_window import MainWindow
    from pokemon_mosaic.ui.session import Session
    from pokemon_mosaic.ui.tutorial import TutorialStore

    monkeypatch.setattr(MainWindow, "settings", staticmethod(lambda: reglages))
    store = TutorialStore(lambda: reglages)
    for cle in ("cartes", "cartes-galerie", "pages", "grille-taille",
                "grille-cartes", "grille-emplacement", "avances"):
        store.mark_seen(cle)
    session = Session()
    session.set_cards(card_set(20), "/fake")
    session.set_layout(cols=5, rows=4)
    session.set_algorithm(iterations=3000, snapshot_every=2, use_annealing=False)
    ecran = MainWindow(LanguageManager(qt_app), session,
                       presets_directory=str(tmp_path / "presets"),
                       arrangements_directory=str(tmp_path / "agencements"))
    ecran.resize(1000, 700)
    ecran.show()
    ecran._stack.setCurrentIndex(2)
    qt_app.processEvents()
    yield ecran, store, session
    ecran._tutorial.overlay.stop()
    ecran.close()
    ecran.deleteLater()


def zones_visibles(tutoriel, hote):
    from pokemon_mosaic.ui.tutorial import zone_rect

    return [zone.widget() for zone in tutoriel.zones()
            if not zone_rect(zone.widget(), hote).isEmpty()]


def vers_multi(qt_app, ecran, store):
    """Passe à l'onglet du multi-lancement, la visite de « Lancement » vue."""
    ecran._tutorial.overlay.stop()
    ecran._tutorial.guide_running.emit(False)
    store.mark_seen("execution")
    etape = ecran._run_step
    etape._tabs.setCurrentWidget(etape._multi)
    qt_app.processEvents()
    return etape, etape._multi


# --- Lancement -------------------------------------------------------------

def test_arriving_on_the_step_guides_the_launch_tab(fenetre):
    ecran, _, _ = fenetre

    assert ecran._tutorial.is_guiding()
    assert ecran._tutorial.overlay.tutorial().key == "execution"


def test_the_launch_tab_before_any_run(fenetre):
    """L'accueil a sa zone, l'image cachée derrière lui n'en a pas."""
    ecran, _, _ = fenetre
    etape = ecran._run_step

    tutoriel = ecran.current_tutorial()

    assert zones_visibles(tutoriel, ecran) == [
        etape._tabs.tabBar(), etape._welcome_start, etape._slider,
        etape._zoom_fit, etape._start, etape._pause, etape._stop,
        etape._extend, etape._resume, etape._keep, etape._saved]


def test_the_image_takes_the_welcome_zone_once_a_run_exists(qt_app, fenetre):
    ecran, _, _ = fenetre
    etape = ecran._run_step

    etape._timeline = [object()]
    etape._update_view()
    qt_app.processEvents()

    zones = zones_visibles(ecran.current_tutorial(), ecran)
    assert etape._scroll in zones and etape._welcome_start not in zones


# --- Multi-lancement -------------------------------------------------------

def test_switching_to_the_multi_run_tab_starts_its_guide(qt_app, fenetre):
    ecran, store, _ = fenetre

    _, onglet = vers_multi(qt_app, ecran, store)

    assert ecran._tutorial.is_guiding()
    assert ecran._tutorial.overlay.tutorial().key == "multi-lancement"
    assert zones_visibles(ecran.current_tutorial(), ecran) == [
        onglet._count_field, onglet._estimate, onglet._start, onglet._pause,
        onglet._stop, onglet._progress, onglet._view]


def test_the_groups_guide_starts_when_the_results_appear(qt_app, fenetre):
    ecran, store, session = fenetre
    _, onglet = vers_multi(qt_app, ecran, store)
    ecran._tutorial.overlay.stop()
    ecran._tutorial.guide_running.emit(False)
    store.mark_seen("multi-lancement")

    feed_tab(onglet, session, 2)
    qt_app.processEvents()

    assert ecran._tutorial.is_guiding()
    tutoriel = ecran._tutorial.overlay.tutorial()
    assert tutoriel.key == "multi-lancement-groupes"
    assert zones_visibles(tutoriel, ecran) == [
        onglet._results_scroll, onglet._choice, onglet._keep, onglet._save]


def test_no_guide_while_the_runs_are_computing(qt_app, fenetre):
    ecran, store, _ = fenetre
    _, onglet = vers_multi(qt_app, ecran, store)
    ecran._tutorial.overlay.stop()
    ecran._tutorial.guide_running.emit(False)
    store.mark_seen("execution")
    store.rearm()

    onglet._thread = object()
    ecran._tutorial._apply_page()
    onglet._thread = None

    assert not ecran._tutorial.is_guiding()


def test_results_on_the_hidden_tab_start_nothing(qt_app, fenetre):
    """Les groupes arrivés pendant qu'on regarde « Lancement » attendent."""
    ecran, store, session = fenetre
    ecran._tutorial.overlay.stop()
    ecran._tutorial.guide_running.emit(False)
    store.mark_seen("execution")
    etape = ecran._run_step
    signaux = []
    etape.tutorial_changed.connect(lambda: signaux.append(1))

    feed_tab(etape._multi, session, 1)
    qt_app.processEvents()

    assert signaux == []
    assert not ecran._tutorial.is_guiding()


def test_every_text_is_short_and_without_em_dash(qt_app, fenetre):
    ecran, store, session = fenetre
    tutoriels = [ecran.current_tutorial()]
    _, onglet = vers_multi(qt_app, ecran, store)
    tutoriels.append(ecran.current_tutorial())
    ecran._tutorial.overlay.stop()
    feed_tab(onglet, session, 1)
    tutoriels.append(ecran.current_tutorial())

    assert [t.key for t in tutoriels] == [
        "execution", "multi-lancement", "multi-lancement-groupes"]
    for tutoriel in tutoriels:
        for zone in tutoriel.zones():
            texte = zone.text()
            assert texte.strip()
            assert "—" not in texte and "–" not in texte
            assert len(texte) <= 90, texte
