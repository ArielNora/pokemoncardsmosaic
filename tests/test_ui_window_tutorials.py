"""Tests des visites des fenêtres ouvertes par-dessus, chacune avec son « ? »."""

import numpy as np
import pytest
from test_ui_export_step import card_set


@pytest.fixture
def visites(reglages_des_tutoriels):
    """Les visites rallumées : la fixture commune les passe d'office."""
    reglages_des_tutoriels.setValue("tutoriels/passer_tous", False)
    return reglages_des_tutoriels


@pytest.fixture
def session(qt_app):
    from pokemon_mosaic.ui.session import Session

    s = Session()
    jeu = card_set(20)
    s.set_cards(jeu, "/fake")
    s.set_layout(cols=5, rows=4)
    s.save_grid(np.arange(20).reshape(4, 5), jeu, iteration=100, score=12.5)
    return s


def zones_visibles(tutoriel, hote):
    from pokemon_mosaic.ui.tutorial import zone_rect

    return [zone.widget() for zone in tutoriel.zones()
            if not zone_rect(zone.widget(), hote).isEmpty()]


def ouvrir(qt_app, fenetre, largeur=900, hauteur=640):
    fenetre.resize(largeur, hauteur)
    fenetre.show()
    qt_app.processEvents()
    return fenetre._tutorial


def fermer(fenetre):
    fenetre._tutorial.controller.overlay.stop()
    fenetre.close()
    fenetre.deleteLater()


def verifier_textes(tutoriel):
    for zone in tutoriel.zones():
        texte = zone.text()
        assert texte.strip()
        assert "—" not in texte and "–" not in texte
        assert len(texte) <= 90, texte


# --- Le socle -------------------------------------------------------------

def test_tests_never_touch_the_machine_settings(reglages_des_tutoriels):
    from pokemon_mosaic.ui import tutorial

    assert tutorial.application_settings() is reglages_des_tutoriels


def test_a_window_guides_on_first_show_only(qt_app, visites):
    from PySide6.QtWidgets import QDialog, QPushButton, QVBoxLayout

    from pokemon_mosaic.ui.tutorial import Tutorial, WindowTutorial, Zone

    fenetre = QDialog()
    bouton = QPushButton("un")
    QVBoxLayout(fenetre).addWidget(bouton)
    tutoriel = WindowTutorial(fenetre, lambda: Tutorial("essai-fenetre", lambda: [
        Zone(lambda: bouton, lambda: "un")]))
    fenetre.layout().addWidget(tutoriel.help_button)
    fenetre.show()

    tutoriel.window_shown()
    qt_app.processEvents()
    assert tutoriel.controller.is_guiding()
    assert not tutoriel.help_button.isEnabled()

    tutoriel.controller.overlay.next_zone()
    assert tutoriel.help_button.isEnabled()
    assert "essai-fenetre" in visites.value("tutoriels/vus", "", type=str)

    tutoriel.help_button.click()
    assert tutoriel.controller.help_active() and tutoriel.help_button.isChecked()
    tutoriel.help_button.click()
    assert not tutoriel.controller.help_active()

    # Allumée sans passer par le bouton, l'aide se lit quand même sur lui.
    tutoriel.controller.set_help(True)
    assert tutoriel.help_button.isChecked()
    tutoriel.controller.set_help(False)

    # Rouverte, la fenêtre ne rejoue pas une visite déjà vue.
    fenetre.hide()
    fenetre.show()
    tutoriel.window_shown()
    qt_app.processEvents()
    assert not tutoriel.controller.is_guiding()
    fenetre.close()


def test_the_help_menu_rearms_every_guide(qt_app, visites):
    from PySide6.QtWidgets import QDialog

    from pokemon_mosaic.ui.tutorial import WindowTutorial

    visites.setValue("tutoriels/vus", "cartes,fenetre-lien")
    fenetre = QDialog()
    tutoriel = WindowTutorial(fenetre, lambda: None)

    tutoriel.help_button._rearm.trigger()

    assert visites.value("tutoriels/vus", "", type=str) == ""
    fenetre.close()


def test_skip_all_keeps_the_windows_quiet(qt_app, session, tmp_path):
    """La fixture commune passe les visites : les tests des fenêtres cliquent."""
    from pokemon_mosaic.ui.arrangements_dialog import ArrangementsDialog

    fenetre = ArrangementsDialog(session, str(tmp_path))
    tutoriel = ouvrir(qt_app, fenetre)

    assert not tutoriel.controller.is_guiding()
    fermer(fenetre)


# --- Les quatre fenêtres ---------------------------------------------------

def test_the_library_window(qt_app, session, tmp_path, visites):
    from pokemon_mosaic.ui.arrangements_dialog import ArrangementsDialog

    fenetre = ArrangementsDialog(session, str(tmp_path))
    tutoriel = ouvrir(qt_app, fenetre)

    assert tutoriel.help_button.window() is fenetre
    assert tutoriel.controller.is_guiding()
    visite = tutoriel.controller.overlay.tutorial()
    assert visite.key == "fenetre-agencements"
    assert zones_visibles(visite, fenetre) == [
        fenetre._list, fenetre._image, fenetre._cards, fenetre._open,
        fenetre._export, fenetre._import, fenetre._rename, fenetre._delete]
    verifier_textes(visite)
    assert visite.zones()[3].text() == fenetre._texts.library_slot()
    fermer(fenetre)


def test_the_library_explains_starting_from_an_arrangement(qt_app, session,
                                                         tmp_path, visites):
    from pokemon_mosaic.ui.arrangements_dialog import ArrangementsDialog

    fenetre = ArrangementsDialog(session, str(tmp_path), start=True)

    assert fenetre.tutorial().zones()[3].text() == fenetre._texts.library_start()
    fenetre.deleteLater()


def test_the_link_editor(qt_app, session, visites):
    from pokemon_mosaic.ui.link_dialog import LinkDialog

    fenetre = LinkDialog(session)
    tutoriel = ouvrir(qt_app, fenetre, 1040, 700)

    assert tutoriel.help_button.window() is fenetre
    visite = tutoriel.controller.overlay.tutorial()
    assert visite.key == "fenetre-lien"
    assert zones_visibles(visite, fenetre) == [
        fenetre._panel, fenetre._palette, fenetre._search, fenetre._folder,
        fenetre._ordered, fenetre._name, fenetre._buttons]
    verifier_textes(visite)
    fermer(fenetre)


def test_the_export_window(qt_app, session, visites):
    from pokemon_mosaic.ui.export_dialog import ExportDialog

    garde = session.saved[0]
    fenetre = ExportDialog(session, garde.grid, garde.cards)
    tutoriel = ouvrir(qt_app, fenetre, 560, 420)

    assert tutoriel.help_button.window() is fenetre
    visite = tutoriel.controller.overlay.tutorial()
    assert visite.key == "fenetre-export"
    attendues = [fenetre._layout_recap, fenetre._format, fenetre._quality,
                 fenetre._folder, fenetre._basename, fenetre._plan_label,
                 fenetre._files, fenetre._buttons]
    assert zones_visibles(visite, fenetre) == [
        w for w in attendues if w.isVisible()]
    assert fenetre._format in zones_visibles(visite, fenetre)
    verifier_textes(visite)
    fermer(fenetre)


def test_the_kept_arrangement_window(qt_app, session, visites):
    from pokemon_mosaic.ui.saved_column import SavedDialog

    fenetre = SavedDialog(session.saved[0], (255, 255, 255))
    tutoriel = ouvrir(qt_app, fenetre, 600, 500)

    assert tutoriel.help_button.window() is fenetre
    visite = tutoriel.controller.overlay.tutorial()
    assert visite.key == "fenetre-agencement-garde"
    assert zones_visibles(visite, fenetre) == [
        fenetre._notice, fenetre._scroll, fenetre._zoom_in]
    verifier_textes(visite)
    fermer(fenetre)
