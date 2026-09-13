"""Tests du moteur des tutoriels : visite guidée, aide au survol, mémoire."""

import pytest


@pytest.fixture
def reglages(tmp_path):
    from PySide6.QtCore import QSettings

    return QSettings(str(tmp_path / "reglages.ini"), QSettings.IniFormat)


@pytest.fixture
def store(reglages):
    from pokemon_mosaic.ui.tutorial import TutorialStore

    return TutorialStore(lambda: reglages)


@pytest.fixture
def page(qt_app):
    """Une page d'essai : trois boutons les uns sous les autres."""
    from PySide6.QtWidgets import QPushButton, QVBoxLayout, QWidget

    hote = QWidget()
    pile = QVBoxLayout(hote)
    boutons = [QPushButton(nom) for nom in ("un", "deux", "trois")]
    for bouton in boutons:
        pile.addWidget(bouton)
    hote.resize(500, 400)
    hote.show()
    qt_app.processEvents()
    yield hote, boutons
    hote.close()


def tutoriel(boutons, key="essai"):
    from pokemon_mosaic.ui.tutorial import Tutorial, Zone

    return Tutorial(key, lambda: [
        Zone(lambda b=bouton: b, lambda n=bouton.text(): f"Explication de {n}")
        for bouton in boutons])


@pytest.fixture
def voile(page):
    from pokemon_mosaic.ui.tutorial import TutorialOverlay

    hote, boutons = page
    return TutorialOverlay(hote), hote, boutons


# --- La mémoire -------------------------------------------------------------

def test_the_store_remembers_what_was_seen(store):
    assert store.should_guide("cartes")

    store.mark_seen("cartes")
    store.mark_seen("pages")

    assert store.seen("cartes") and store.seen("pages")
    assert not store.should_guide("cartes") and store.should_guide("export")


def test_skipping_all_stops_every_future_guide(store):
    store.set_skip_all(True)

    assert not store.should_guide("export")


def test_rearming_brings_every_guide_back(store):
    store.mark_seen("cartes")
    store.set_skip_all(True)

    store.rearm()

    assert store.should_guide("cartes") and not store.skip_all()


# --- La visite guidée -------------------------------------------------------

def test_the_guide_shows_one_zone_at_a_time_in_order(voile):
    overlay, hote, boutons = voile

    assert overlay.start_guide(tutoriel(boutons))

    assert overlay.isVisible() and overlay.geometry() == hote.rect()
    assert overlay._bubble.text() == "Explication de un"
    assert "1 sur 3" in overlay._bubble.progress()


def test_a_click_moves_to_the_next_zone_and_the_last_ends(qt_app, voile):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    overlay, _, boutons = voile
    fins = []
    overlay.guide_ended.connect(lambda *a: fins.append(a))
    overlay.start_guide(tutoriel(boutons))

    QTest.mouseClick(overlay, Qt.LeftButton)
    assert overlay._bubble.text() == "Explication de deux"
    QTest.mouseClick(overlay, Qt.LeftButton)
    QTest.mouseClick(overlay, Qt.LeftButton)

    assert fins == [("essai", False, False)]
    assert not overlay.isVisible()


def test_the_guide_blocks_the_interface_underneath(qt_app, voile):
    """Un clic avance, et rien d'autre ne réagit : on ne lance pas un calcul
    par erreur en voulant passer à la zone suivante."""
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    overlay, hote, boutons = voile
    cliques = []
    boutons[2].clicked.connect(lambda: cliques.append(1))
    overlay.start_guide(tutoriel(boutons))
    centre = boutons[2].mapTo(hote, boutons[2].rect().center())

    # ⚠️ **Ce qui est sous le point**, et non un clic adressé au voile : ce
    # dernier l'atteint même quand le voile laisse passer les clics.
    dessous = hote.childAt(centre)
    assert dessous is overlay or overlay.isAncestorOf(dessous)
    QTest.mouseClick(overlay, Qt.LeftButton, pos=centre)

    assert cliques == []
    assert overlay.current_index() == 1


def test_tab_does_not_take_the_keyboard_out_of_the_guide(voile):
    """Le focus serait passé à un bouton dessous, qu'Espace aurait activé."""
    overlay, _, boutons = voile
    overlay.start_guide(tutoriel(boutons))

    assert overlay.focusNextPrevChild(True) is True


def test_the_guide_stays_above_an_element_raised_after_it(qt_app, voile):
    from PySide6.QtWidgets import QPushButton

    overlay, hote, boutons = voile
    overlay.start_guide(tutoriel(boutons))
    tard = QPushButton("tard", hote)
    tard.show()
    tard.raise_()

    overlay.refresh()

    dessous = hote.childAt(tard.geometry().center())
    assert dessous is overlay or overlay.isAncestorOf(dessous)


def test_enter_moves_on_and_escape_asks_to_skip(qt_app, voile, monkeypatch):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    overlay, _, boutons = voile
    demandes = []
    monkeypatch.setattr(overlay, "_confirm_skip",
                        lambda: demandes.append(1) or (False, False))
    overlay.start_guide(tutoriel(boutons))

    QTest.keyClick(overlay, Qt.Key_Return)
    assert overlay.current_index() == 1
    QTest.keyClick(overlay, Qt.Key_Escape)

    assert demandes == [1]
    assert overlay.isVisible(), "refusé : la visite continue"


def test_skipping_can_skip_every_following_guide(qt_app, voile, monkeypatch):
    overlay, _, boutons = voile
    fins = []
    overlay.guide_ended.connect(lambda *a: fins.append(a))
    monkeypatch.setattr(overlay, "_confirm_skip", lambda: (True, True))
    overlay.start_guide(tutoriel(boutons))

    overlay._skip.click()

    assert fins == [("essai", True, True)]
    assert not overlay.isVisible()


def test_the_skip_button_sits_bottom_right(voile):
    overlay, hote, boutons = voile
    overlay.start_guide(tutoriel(boutons))
    bouton = overlay._skip.geometry()

    assert bouton.right() > hote.width() * 0.7
    assert bouton.bottom() > hote.height() * 0.7


def test_a_hidden_element_has_no_zone(voile):
    overlay, _, boutons = voile
    boutons[1].hide()

    overlay.start_guide(tutoriel(boutons))

    assert len(overlay.zones()) == 2
    assert "1 sur 2" in overlay._bubble.progress()


def test_a_page_without_visible_zones_has_no_guide(voile):
    overlay, _, boutons = voile
    for bouton in boutons:
        bouton.hide()

    assert not overlay.start_guide(tutoriel(boutons))
    assert not overlay.isVisible()


def test_the_zones_follow_the_elements_when_the_window_resizes(qt_app, voile):
    """Les zones se relisent sur leurs éléments : jamais des coordonnées."""
    overlay, hote, boutons = voile
    overlay.start_guide(tutoriel(boutons))

    hote.resize(800, 700)
    qt_app.processEvents()
    overlay.refresh()

    _, rect = overlay.zones()[2]
    attendu = boutons[2].mapTo(hote, boutons[2].rect().topLeft())
    assert overlay.geometry() == hote.rect()
    assert rect.contains(attendu)


def test_a_zone_filling_the_window_holds_its_bubble_inside(qt_app, page):
    """Vu sur une capture : sans place d'aucun côté, la bulle chevauchait le
    bord de la zone, flèche tournée vers elle-même."""
    from PySide6.QtWidgets import QListWidget

    from pokemon_mosaic.ui.tutorial import Tutorial, TutorialOverlay, Zone

    hote, boutons = page
    for bouton in boutons:
        bouton.hide()
    liste = QListWidget()
    hote.layout().addWidget(liste)
    liste.show()
    qt_app.processEvents()
    overlay = TutorialOverlay(hote)

    overlay.start_guide(Tutorial("grand", lambda: [Zone(lambda: liste,
                                                        lambda: "La liste")]))

    _, rect = overlay.zones()[0]
    assert rect.contains(overlay._bubble.geometry())
    assert overlay._arrow is None


def test_the_bubble_stays_inside_the_window(voile):
    overlay, _, boutons = voile
    overlay.start_guide(tutoriel(boutons))
    for _ in range(3):
        assert overlay.rect().contains(overlay._bubble.geometry())
        overlay.next_zone()


# --- Le mode d'aide ---------------------------------------------------------

def test_help_outlines_every_zone_and_lets_clicks_through(qt_app, voile):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    overlay, _hote, boutons = voile
    cliques = []
    boutons[2].clicked.connect(lambda: cliques.append(1))

    overlay.start_help(tutoriel(boutons))

    assert len(overlay.zones()) == 3
    centre = boutons[2].mapTo(_hote, boutons[2].rect().center())
    assert _hote.childAt(centre) is boutons[2], "le clic tombe sur le bouton"
    QTest.mouseClick(boutons[2], Qt.LeftButton)
    assert cliques == [1], "l'aide n'empêche pas d'agir"


def test_help_reads_the_mouse_position_by_itself(voile, monkeypatch):
    """Sans bouton enfoncé, Qt n'envoie pas de mouvement aux boutons : le
    survol se lit sur la position de la souris."""
    from pokemon_mosaic.ui import tutorial as module

    overlay, _hote, boutons = voile
    overlay.start_help(tutoriel(boutons))
    ecran = boutons[1].mapToGlobal(boutons[1].rect().center())
    monkeypatch.setattr(module.QCursor, "pos", staticmethod(lambda: ecran))

    overlay._on_tick()

    assert overlay._bubble.isVisible()
    assert overlay._bubble.text() == "Explication de deux"


def test_hovering_a_zone_shows_its_explanation(voile):
    overlay, hote, boutons = voile
    overlay.start_help(tutoriel(boutons))
    assert not overlay._bubble.isVisible()

    overlay.hover_at(boutons[1].mapTo(hote, boutons[1].rect().center()))

    assert overlay._bubble.isVisible()
    assert overlay._bubble.text() == "Explication de deux"
    overlay.hover_at(overlay.rect().bottomRight() + overlay.rect().topLeft())


# --- Le contrôleur ----------------------------------------------------------

@pytest.fixture
def controleur(page, store):
    from pokemon_mosaic.ui.tutorial import TutorialController

    hote, boutons = page
    courant = {"tutoriel": tutoriel(boutons)}
    return (TutorialController(hote, store, lambda: courant["tutoriel"]),
            courant, store, boutons)


def test_the_first_visit_of_a_page_starts_its_guide_once(qt_app, controleur):
    ctrl, _, store, _ = controleur
    ctrl._apply_page()
    assert ctrl.is_guiding()

    ctrl.overlay.stop()
    ctrl.overlay.guide_ended.emit("essai", False, False)
    ctrl._apply_page()

    assert store.seen("essai")
    assert not ctrl.is_guiding(), "vue une fois, elle ne revient pas"


def test_a_guide_skipped_for_all_is_remembered(controleur):
    """La case « passer aussi tous les tutoriels suivants » est retenue."""
    ctrl, _, store, _ = controleur

    ctrl.overlay.guide_ended.emit("essai", True, True)

    assert store.seen("essai") and store.skip_all()


def test_skip_all_prevents_the_guide(controleur):
    ctrl, _, store, _ = controleur
    store.set_skip_all(True)

    ctrl._apply_page()

    assert not ctrl.is_guiding()


def test_help_follows_the_page_until_switched_off(controleur):
    ctrl, courant, store, boutons = controleur
    store.mark_seen("essai")
    store.mark_seen("autre")
    ctrl.set_help(True)

    courant["tutoriel"] = tutoriel(boutons[:1], key="autre")
    ctrl._apply_page()

    assert ctrl.overlay.mode() == "aide"
    assert ctrl.overlay.tutorial().key == "autre"
    ctrl.set_help(False)
    assert not ctrl.overlay.isVisible()


def test_help_cannot_start_during_a_guide(controleur):
    ctrl, _, _, _ = controleur
    ctrl._apply_page()

    ctrl.set_help(True)

    assert ctrl.is_guiding() and not ctrl.help_active()


# --- Le bouton « ? » --------------------------------------------------------

def test_the_help_button_is_round_checkable_and_glows_blue(qt_app):
    from PySide6.QtGui import QColor

    from pokemon_mosaic.ui.tutorial import HelpButton

    bouton = HelpButton()

    assert bouton.text() == "?" and bouton.isCheckable()
    assert bouton.property("role") == "help"
    couleur = bouton.graphicsEffect().color()
    bleu = QColor(bouton.palette().highlight().color())
    assert (couleur.red(), couleur.green(), couleur.blue()) == (
        bleu.red(), bleu.green(), bleu.blue())


def test_the_help_button_menu_offers_to_replay_the_guides(qt_app):
    from pokemon_mosaic.ui.tutorial import HelpButton

    bouton = HelpButton()
    demandes = []
    bouton.rearm_requested.connect(lambda: demandes.append(1))

    bouton._rearm.trigger()

    assert demandes == [1]
    assert bouton._rearm.text() == "Revoir les visites guidées"


def test_the_main_window_has_the_help_button_greyed_during_a_guide(qt_app,
                                                                   tmp_path,
                                                                   monkeypatch,
                                                                   reglages):
    from pokemon_mosaic.ui.i18n import LanguageManager
    from pokemon_mosaic.ui.main_window import MainWindow
    from pokemon_mosaic.ui.session import Session

    monkeypatch.setattr(MainWindow, "settings", staticmethod(lambda: reglages))
    fenetre = MainWindow(LanguageManager(qt_app), Session(),
                         presets_directory=str(tmp_path / "presets"))

    assert fenetre._help.isEnabled()
    fenetre._tutorial.guide_running.emit(True)
    assert not fenetre._help.isEnabled()
    fenetre._tutorial.guide_running.emit(False)
    assert fenetre._help.isEnabled()

    fenetre._help.click()
    assert fenetre._tutorial.help_active()
    fenetre._help.click()
    assert not fenetre._tutorial.help_active()
    fenetre.deleteLater()
