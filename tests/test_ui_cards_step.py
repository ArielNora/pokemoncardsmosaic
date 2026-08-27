"""Tests de l'étape 1 : l'écran d'accueil, le téléchargement, les avertissements.

Rien ici ne touche au réseau : `downloader` est nourri par un faux miroir. Les
vignettes sont minuscules — l'écran ne teste ni la taille ni le contenu des
images, seulement ce qu'il en dit.
"""

import pytest
from test_ui_session import card_set_in


@pytest.fixture
def step(qt_app):
    from pokemon_mosaic.ui.cards_step import CardsStep
    from pokemon_mosaic.ui.session import Session

    session = Session()
    return CardsStep(session), session


def depose(racine, layout, taille=(12, 16)):
    """Écrit de vraies images, `load_cards` lisant les en-têtes."""
    from PIL import Image

    for dossier, noms in layout.items():
        cible = racine / dossier
        cible.mkdir(parents=True, exist_ok=True)
        for nom in noms:
            Image.new("RGB", taille, (10, 20, 30)).save(cible / f"{nom}.webp")


# --- L'écran d'accueil -----------------------------------------------------

def test_the_empty_screen_offers_exactly_two_actions(step):
    """Sans carte, la galerie n'a rien à montrer et la barre d'outils rien sur
    quoi agir : on ne laisse cliquables que télécharger et désigner."""
    ecran, _ = step
    assert ecran._pages.currentIndex() == 0
    assert ecran._download.isEnabled()
    assert ecran._locate.isEnabled()
    for bouton in (ecran._include_all, ecran._exclude_all, ecran._show_all):
        assert not bouton.isEnabled()


def test_the_left_column_is_hidden_while_empty(step):
    """Deux listes vides sur trois cents pixels ne disent rien et détournent
    l'œil des deux boutons."""
    ecran, _ = step
    assert not ecran._left_panel.isVisibleTo(ecran)


def test_the_update_button_is_hidden_until_a_folder_is_known(step):
    """Mettre à jour vise un dossier : sans cible, le bouton ment."""
    ecran, _ = step
    assert not ecran._update_catalogue.isVisibleTo(ecran)


def test_loading_cards_reveals_the_gallery(step, tmp_path):
    ecran, session = step
    session.set_cards(card_set_in(tmp_path, {"s": ["a", "b"]}), str(tmp_path))
    ecran._update_state()

    assert ecran._pages.currentIndex() == 1
    assert ecran._left_panel.isVisibleTo(ecran)
    assert ecran._include_all.isEnabled()
    assert ecran._update_catalogue.isEnabled()


# --- Les avertissements ----------------------------------------------------

def test_no_warning_on_a_homogeneous_set(step, tmp_path):
    ecran, _ = step
    ecran._show_warnings(card_set_in(tmp_path, {"s": ["a"]}))
    assert not ecran._warnings.isVisibleTo(ecran)


def test_an_odd_size_says_how_many_which_and_why_it_matters(step, tmp_path):
    """Le nombre seul ne suffit pas : c'est la conséquence — étirement, donc
    couleurs de bord faussées — qui dit à l'utilisateur s'il doit agir."""
    from pokemon_mosaic.cards import SizeWarning

    ecran, _ = step
    jeu = card_set_in(tmp_path, {"s": ["a"]})
    jeu.full_size = (734, 1024)
    jeu.odd_sizes = [SizeWarning(size=(717, 1000), count=3)]
    ecran._show_warnings(jeu)

    texte = ecran._warnings.text()
    assert ecran._warnings.isVisibleTo(ecran)
    assert "3" in texte and "717×1000" in texte and "734×1024" in texte
    assert "bord" in texte


def test_unreadable_files_are_listed_too(step, tmp_path):
    ecran, _ = step
    jeu = card_set_in(tmp_path, {"s": ["a"]})
    jeu.unreadable = ["casse.webp — illisible"]
    ecran._show_warnings(jeu)

    assert "casse.webp" in ecran._warnings.text()


def test_the_warning_hides_again_on_a_clean_reload(step, tmp_path):
    """Sans cela, l'avertissement d'un dossier survivrait au chargement du
    suivant et accuserait des cartes saines."""
    from pokemon_mosaic.cards import SizeWarning

    ecran, _ = step
    sale = card_set_in(tmp_path, {"s": ["a"]})
    sale.odd_sizes = [SizeWarning(size=(1, 1), count=1)]
    ecran._show_warnings(sale)
    assert ecran._warnings.isVisibleTo(ecran)

    ecran._show_warnings(card_set_in(tmp_path, {"t": ["b"]}))
    assert not ecran._warnings.isVisibleTo(ecran)


def test_an_unreadable_file_does_not_repeat_its_full_path(tmp_path):
    """Pillow répète le chemin absolu ; le garder produit une ligne de deux
    cents caractères là où le nom du fichier suffit."""
    from pokemon_mosaic.cards import load_cards

    depose(tmp_path, {"s": ["bonne"]})
    (tmp_path / "s" / "casse.webp").write_bytes(b"pas une image")
    jeu = load_cards(str(tmp_path))

    (message,) = jeu.unreadable
    assert message.startswith("casse.webp")
    assert str(tmp_path) not in message


# --- Le téléchargement -----------------------------------------------------

def test_downloading_disables_the_actions_and_offers_to_cancel(step, tmp_path,
                                                               monkeypatch):
    """Deux téléchargements simultanés écriraient dans le même dossier."""
    ecran, _ = step
    monkeypatch.setattr("pokemon_mosaic.ui.cards_step.start_download",
                        lambda *a, **k: ("fil", "ouvrier"))
    ecran._start_download(str(tmp_path))

    assert ecran._cancel.isVisibleTo(ecran)
    assert not ecran._download.isEnabled()
    assert not ecran._choose_folder.isEnabled()


def test_a_second_download_is_refused_while_one_runs(step, tmp_path, monkeypatch):
    lances = []
    ecran, _ = step
    monkeypatch.setattr("pokemon_mosaic.ui.cards_step.start_download",
                        lambda *a, **k: (lances.append(1), ("f", "o"))[1])
    ecran._start_download(str(tmp_path))
    ecran._start_download(str(tmp_path))

    assert len(lances) == 1


def test_a_complete_folder_says_so_without_downloading(step):
    ecran, _ = step
    messages = []
    ecran.status_message.connect(messages.append)
    ecran._on_surveyed(0, 0)

    assert messages and "complet" in messages[-1]


def test_a_cancelled_download_does_not_claim_to_be_finished(step, tmp_path,
                                                           monkeypatch):
    """Une interruption ressemble trait pour trait à une fin normale : sans
    message distinct, l'utilisateur croirait son dossier complet."""
    ecran, _ = step
    charges = []
    monkeypatch.setattr(ecran, "load", charges.append)
    messages = []
    ecran.status_message.connect(messages.append)
    ecran._download_dir = str(tmp_path)
    ecran._on_download_cancelled(7)

    assert "interrompu" in messages[-1]
    # Ce qui est arrivé a été vérifié avant écriture : on le charge quand même.
    assert charges == [str(tmp_path)]


def test_a_cancelled_download_that_wrote_nothing_loads_nothing(step, tmp_path,
                                                               monkeypatch):
    ecran, _ = step
    charges = []
    monkeypatch.setattr(ecran, "load", charges.append)
    ecran._download_dir = str(tmp_path)
    ecran._on_download_cancelled(0)

    assert charges == []


def test_failures_are_reported_but_what_arrived_is_still_loaded(step, tmp_path,
                                                                monkeypatch):
    """Refuser tout un dossier pour une extension manquante serait
    disproportionné : le reste est vérifié et utilisable."""
    ecran, _ = step
    charges = []
    monkeypatch.setattr(ecran, "load", charges.append)
    messages = []
    ecran.status_message.connect(messages.append)
    ecran._download_dir = str(tmp_path)
    ecran._on_downloaded(30, [("A1 (9 cartes)", "introuvable")])

    assert "introuvable" in messages[-1]
    assert charges == [str(tmp_path)]


def test_a_mirror_failure_re_enables_the_buttons(step, tmp_path):
    """Sans cela, un miroir injoignable laisserait l'écran figé, sans moyen de
    réessayer ni de désigner un dossier à la main."""
    ecran, _ = step
    ecran._download_dir = str(tmp_path)
    ecran._on_download_failed("réseau coupé")

    assert ecran._download.isEnabled()
    assert ecran._locate.isEnabled()
    assert not ecran._cancel.isVisibleTo(ecran)


# --- Le dossier retenu -----------------------------------------------------

def test_the_folder_is_published_once_loaded(step, tmp_path):
    """C'est ce signal que la fenêtre mémorise : sans lui, l'application
    redemanderait le dossier à chaque ouverture."""
    ecran, session = step
    vus = []
    ecran.folder_changed.connect(vus.append)
    session.start_loading(str(tmp_path))
    ecran._on_loaded(card_set_in(tmp_path, {"s": ["a"]}))

    assert vus == [str(tmp_path)]


# --- La fenêtre : mémoire du dossier, verrouillage de la navigation --------

@pytest.fixture
def fenetre(qt_app, tmp_path, monkeypatch):
    # Les réglages sont détournés vers un fichier jetable : un test ne doit
    # jamais écrire dans les préférences réelles de l'utilisateur.
    from PySide6.QtCore import QSettings

    from pokemon_mosaic.ui.i18n import LanguageManager
    from pokemon_mosaic.ui.main_window import MainWindow
    from pokemon_mosaic.ui.session import Session
    reglages = QSettings(str(tmp_path / "reglages.ini"), QSettings.IniFormat)
    monkeypatch.setattr(MainWindow, "settings", staticmethod(lambda: reglages))

    session = Session()
    return MainWindow(LanguageManager(qt_app), session,
                      presets_directory=str(tmp_path / "presets")), session


def test_next_is_locked_while_no_card_is_loaded(fenetre):
    """Les trois écrans suivants n'ont rien à afficher : la grille se dimensionne
    sur le nombre de cartes, les réglages en projettent des chiffres, et
    l'exécution n'a rien à assembler."""
    w, _ = fenetre
    assert not w._next.isEnabled()


def test_next_unlocks_as_soon_as_cards_arrive(fenetre, tmp_path):
    """Il ne se réévaluait qu'au changement d'écran — qu'on ne peut plus faire
    puisqu'il est justement grisé."""
    w, session = fenetre
    session.set_cards(card_set_in(tmp_path, {"s": ["a"]}), str(tmp_path))
    session.cards_loaded.emit()

    assert w._next.isEnabled()


def test_the_folder_is_remembered_across_launches(fenetre, tmp_path):
    from pokemon_mosaic.ui.main_window import MainWindow

    w, _ = fenetre
    jeu = tmp_path / "cartes"
    jeu.mkdir()
    w._cards_step.folder_changed.emit(str(jeu))

    assert MainWindow.remembered_folder() == str(jeu)


def test_a_remembered_folder_that_vanished_is_not_proposed(fenetre, tmp_path):
    """Proposer un chemin mort produirait un « échec du chargement » à
    l'ouverture, là où l'écran d'accueil dit quoi faire."""
    from pokemon_mosaic.ui.main_window import MainWindow

    w, _ = fenetre
    disparu = tmp_path / "envole"
    disparu.mkdir()
    w._cards_step.folder_changed.emit(str(disparu))
    disparu.rmdir()

    assert MainWindow.remembered_folder() == ""
