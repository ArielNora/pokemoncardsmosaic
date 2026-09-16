"""Tests de la visite de l'export, qui ouvre les sections qu'elle explique."""

import numpy as np
import pytest
from test_ui_export_step import card_set


@pytest.fixture
def reglages(tmp_path):
    from PySide6.QtCore import QSettings

    return QSettings(str(tmp_path / "reglages.ini"), QSettings.IniFormat)


@pytest.fixture
def fenetre(qt_app, tmp_path, monkeypatch, reglages):
    """La fenêtre sur l'export, un agencement gardé, visites d'avant vues."""
    from pokemon_mosaic.ui.i18n import LanguageManager
    from pokemon_mosaic.ui.main_window import MainWindow
    from pokemon_mosaic.ui.session import Session
    from pokemon_mosaic.ui.tutorial import TutorialStore

    monkeypatch.setattr(MainWindow, "settings", staticmethod(lambda: reglages))
    store = TutorialStore(lambda: reglages)
    for cle in ("cartes", "cartes-galerie", "pages", "grille-taille",
                "grille-cartes", "grille-emplacement", "avances", "execution"):
        store.mark_seen(cle)
    session = Session()
    jeu = card_set(20)
    session.set_cards(jeu, "/fake")
    session.set_layout(cols=5, rows=4)
    session.save_grid(np.arange(20).reshape(4, 5), jeu, iteration=100, score=12.5)
    ecran = MainWindow(LanguageManager(qt_app), session,
                       presets_directory=str(tmp_path / "presets"),
                       arrangements_directory=str(tmp_path / "agencements"))
    ecran.resize(1000, 700)
    ecran.show()
    ecran._go(3)
    qt_app.processEvents()
    yield ecran, store
    ecran._tutorial.overlay.stop()
    ecran.close()
    ecran.deleteLater()


def zones_visibles(tutoriel, hote):
    from pokemon_mosaic.ui.tutorial import zone_rect

    return [zone.widget() for zone in tutoriel.zones()
            if not zone_rect(zone.widget(), hote).isEmpty()]


def test_arriving_on_the_export_starts_its_guide(fenetre):
    ecran, _ = fenetre

    assert ecran._tutorial.is_guiding()
    assert ecran._tutorial.overlay.tutorial().key == "export"


def test_the_zones_in_order(fenetre):
    """L'avertissement caché, faute de carte hors des pages, n'a pas de zone."""
    ecran, _ = fenetre
    etape = ecran._export_step

    zones = zones_visibles(ecran.current_tutorial(), ecran)

    assert zones == [etape._scroll, etape._loupe, *etape._sections,
                     etape._saved, etape._summary, etape._export]


def test_the_warning_gets_its_zone_when_shown(qt_app, fenetre):
    ecran, _ = fenetre
    etape = ecran._export_step

    etape._warning.show()
    qt_app.processEvents()

    assert etape._warning in zones_visibles(ecran.current_tutorial(), ecran)


def test_the_guide_opens_each_section_it_explains(qt_app, fenetre):
    ecran, _ = fenetre
    etape = ecran._export_step
    overlay = ecran._tutorial.overlay
    ouvertes = []
    for rang, section in enumerate(etape._sections):
        while overlay.current_index() < 2 + rang:
            overlay.next_zone()
        qt_app.processEvents()
        ouvertes.append([s.is_open() for s in etape._sections])
        # ⚠️ **Le contour que le voile dessine**, relu dès la section ouverte,
        # et non au passage suivant de sa minuterie : il entourait sinon le
        # seul intitulé pendant un instant.
        _zone, contour = overlay.zones()[overlay.current_index()]
        assert contour.height() > (
            section._header.height() + section.content().sizeHint().height() // 2)
    assert ouvertes == [[rang == i for i in range(4)] for rang in range(4)]


def test_help_leaves_the_sections_as_they_are(qt_app, fenetre, reglages):
    ecran, store = fenetre
    etape = ecran._export_step
    ecran._tutorial.overlay.stop()
    ecran._tutorial.guide_running.emit(False)
    store.mark_seen("export")
    avant = [s.is_open() for s in etape._sections]

    ecran._help.click()
    for section in etape._sections:
        ecran._tutorial.overlay.hover_at(
            section.mapTo(ecran, section.rect().center()))
    qt_app.processEvents()

    assert ecran._tutorial.help_active()
    assert [s.is_open() for s in etape._sections] == avant


def test_every_text_is_short_and_without_em_dash(fenetre):
    ecran, _ = fenetre
    for zone in ecran.current_tutorial().zones():
        texte = zone.text()
        assert texte.strip()
        assert "—" not in texte and "–" not in texte
        assert len(texte) <= 90, texte
