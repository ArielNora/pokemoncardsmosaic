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


# --- Les extensions et la sélection ---------------------------------------

def charge(ecran, session, tmp_path, layout):
    """Rejoue le vrai enchaînement de chargement, celui qui remplit la liste
    des dossiers — `set_cards` seul ne l'émet pas."""
    jeu = card_set_in(tmp_path, layout)
    session.start_loading(str(tmp_path))
    session.append_cards(jeu.cards)
    session.finish_loading(jeu)
    return jeu


def test_the_extension_buttons_say_what_they_act_on(step):
    """« Inclure » seul ne disait pas sur quoi : la galerie ou l'extension."""
    ecran, _ = step
    assert "extension" in ecran._include_folder.text()
    assert "extension" in ecran._exclude_folder.text()


def choisir(ecran, *dossiers):
    """Sélectionne des extensions par leur nom, où qu'elles soient dans l'arbre."""
    ecran._folders.clearSelection()
    for nom in dossiers:
        ecran._folder_items[nom].setSelected(True)


def choisir_serie(ecran, lettre):
    """Sélectionne la ligne d'une série, qui vaut toutes ses extensions."""
    ecran._folders.clearSelection()
    ecran._series_items[lettre].setSelected(True)


def test_the_extension_buttons_need_an_extension_selected(step, tmp_path):
    """Actifs sans sélection, ils ne faisaient rien : le clic partait dans le
    vide et l'utilisateur croyait à une panne."""
    ecran, session = step
    charge(ecran, session, tmp_path, {"a1": ["x", "y"], "a2": ["z"]})

    assert not ecran._include_folder.isEnabled()
    assert not ecran._exclude_folder.isEnabled()

    choisir(ecran, "a1")
    assert ecran._include_folder.isEnabled()
    assert ecran._exclude_folder.isEnabled()

    ecran._folders.clearSelection()
    assert not ecran._include_folder.isEnabled()


def test_the_extensions_are_grouped_by_series(step, tmp_path):
    """⚠️ « A1 », « A1a » et la promo A sont la **série A** : c'est ainsi qu'on
    cherche une extension — par série d'abord. Vingt dossiers à plat
    obligeaient à lire chaque nom pour savoir où l'on en était."""
    ecran, session = step
    charge(ecran, session, tmp_path,
           {"a1-puissance-genetique": ["x"], "a3b-la-clairiere-d-evoli": ["y"],
            "promo-a-promo-a": ["z"], "b1-mega-ascension": ["w"]})

    assert set(ecran._series_items) == {"A", "B"}
    serie_a = ecran._series_items["A"]
    assert serie_a.childCount() == 3, "la promo A rejoint la série A"
    assert "3" in serie_a.text(0), "la série compte ses cartes"
    assert ecran._series_items["B"].childCount() == 1


def test_the_series_stay_in_order_whatever_the_loading_order(step):
    """⚠️ Les dossiers arrivent dans l'ordre où le système les rend — `os.walk`
    ne trie pas les répertoires. Une série découverte plus tard se posait alors
    sous une série qui lui succède."""
    ecran, _ = step
    for serie in ("C", "A", "B"):
        ecran._series_item(serie).setText(0, "Série " + serie)
    ecran._folder_item("mes-cartes", None).setText(0, "mes-cartes")
    ecran._series_item("B0").setText(0, "Série B0")

    rangs = [ecran._folders.topLevelItem(i).text(0)
             for i in range(ecran._folders.topLevelItemCount())]
    assert rangs == ["Série A", "Série B", "Série B0", "Série C", "mes-cartes"]


def test_a_hand_picked_folder_joins_no_series(step, tmp_path):
    """Un dossier choisi à la main ne suit aucune convention de nommage : il se
    pose tel quel plutôt que d'inventer un groupe."""
    from PySide6.QtCore import Qt

    ecran, session = step
    charge(ecran, session, tmp_path, {"mes-cartes": ["x"], "a1-truc": ["y"]})

    assert set(ecran._series_items) == {"A"}
    racines = [ecran._folders.topLevelItem(i).data(0, Qt.UserRole)
               for i in range(ecran._folders.topLevelItemCount())]
    assert "mes-cartes" in racines


def test_selecting_a_series_targets_all_its_extensions(step, tmp_path):
    """Une série se clique comme une extension, et vaut toutes les siennes."""
    ecran, session = step
    charge(ecran, session, tmp_path,
           {"a1-truc": ["x", "y"], "promo-a-promo-a": ["z"],
            "b1-machin": ["w"]})

    choisir_serie(ecran, "A")
    assert ecran._selected_folders() == {"a1-truc", "promo-a-promo-a"}
    assert ecran._gallery.visible_count() == 3
    assert ecran._include_folder.isEnabled()

    ecran._exclude_folder.click()
    assert session.selected_count == 1, "seule la carte de la série B reste"


def test_the_folder_list_scrolls_by_pixel(step):
    """Par élément, la liste avance d'une ligne entière à chaque cran : le
    moindre geste au trackpad saute une extension au lieu de la découvrir."""
    from PySide6.QtWidgets import QAbstractItemView

    ecran, _ = step
    assert ecran._folders.verticalScrollMode() == \
        QAbstractItemView.ScrollPerPixel


# --- Les actions globales, posées sur la galerie --------------------------

def test_the_bulk_buttons_sit_on_the_gallery(step, tmp_path):
    """Ils agissent sur la galerie : les laisser dans la barre du haut les
    faisait commander de loin une zone qu'ils ne touchaient pas."""
    ecran, session = step
    charge(ecran, session, tmp_path, {"a1": ["x", "y"]})
    ecran._gallery.resize(400, 300)
    ecran._place_bulk_buttons()

    cadre = ecran._bulk.geometry()
    assert ecran._bulk.parent() is ecran._gallery
    # En bas à droite : les deux bords doivent être proches de ceux de la vue.
    assert cadre.right() <= ecran._gallery.width()
    assert cadre.bottom() <= ecran._gallery.height()
    assert ecran._gallery.height() - cadre.bottom() <= 2 * ecran.BULK_MARGIN


def test_the_bulk_buttons_clear_the_scrollbar(step, tmp_path):
    """Sans contourner sa largeur, ils passent dessous dès que la galerie
    déborde — et le bouton du bas devient inatteignable."""
    ecran, session = step
    charge(ecran, session, tmp_path, {"a1": [str(i) for i in range(60)]})
    ecran._gallery.resize(300, 200)
    ecran._gallery.show()
    ecran._place_bulk_buttons()

    barre = ecran._gallery.verticalScrollBar()
    if barre.isVisible():
        assert ecran._bulk.geometry().right() <= (ecran._gallery.width()
                                                  - barre.width())


def test_the_bulk_buttons_hide_while_no_card_is_loaded(step):
    ecran, _ = step
    assert not ecran._bulk.isVisibleTo(ecran._gallery)


def maintenir(liste, vers_le_bas: int, duree: float = 0.6):
    """Clique le bas de la liste et garde le bouton enfoncé, curseur immobile.

    Le petit mouvement est indispensable : c'est lui qui met la vue en sélection
    glissée et arme la minuterie de défilement automatique. Sans lui, on ne
    reproduit rien — ce qui m'avait fait conclure à tort que le défaut n'existait
    pas.
    """
    import time

    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication

    vue = liste.viewport()
    bas = vue.rect().bottom()
    cible = QPoint(6, bas + vers_le_bas)
    QTest.mousePress(vue, Qt.LeftButton, Qt.NoModifier, QPoint(5, bas - 2))
    QTest.mouseMove(vue, cible)
    debut = time.time()
    while time.time() - debut < duree:
        QApplication.processEvents()
        time.sleep(0.01)
    QTest.mouseRelease(vue, Qt.LeftButton, Qt.NoModifier, cible)
    return liste.verticalScrollBar()


def test_holding_the_click_on_the_last_row_does_not_run_to_the_bottom(step,
                                                                      tmp_path):
    """Le défaut signalé : cliquer l'extension à demi coupée du bas et laisser
    le curseur là faisait dévaler la liste jusqu'au bout. Mesuré avant le
    correctif : 210 crans sur 242."""
    ecran, session = step
    charge(ecran, session, tmp_path,
           {f"jeu{i:02d}": ["x"] for i in range(30)})
    ecran._folders.setFixedHeight(120)
    ecran.show()

    barre = maintenir(ecran._folders, vers_le_bas=-1)
    assert barre.value() <= barre.maximum() // 10


def test_dragging_below_the_list_still_scrolls(step, tmp_path):
    """Le geste volontaire reste : couper le défilement automatique aurait
    supprimé les deux d'un coup."""
    ecran, session = step
    charge(ecran, session, tmp_path,
           {f"jeu{i:02d}": ["x"] for i in range(30)})
    ecran._folders.setFixedHeight(120)
    ecran.show()

    barre = maintenir(ecran._folders, vers_le_bas=20)
    assert barre.value() > 0


def test_the_odd_size_total_matches_what_is_listed(step, tmp_path):
    """Le détail est tronqué à cinq formats mais le total les compte tous :
    sans mention de la troncature, les chiffres se contredisent et on ne peut
    pas savoir s'il manque des lignes ou si le total est faux."""
    from pokemon_mosaic.cards import SizeWarning

    ecran, _ = step
    jeu = card_set_in(tmp_path, {"s": ["a"]})
    jeu.full_size = (734, 1024)
    jeu.odd_sizes = [SizeWarning(size=(700 + i, 1000), count=i + 1)
                     for i in range(7)]
    ecran._show_warnings(jeu)

    texte = ecran._warnings.text()
    assert "28" in texte              # le total, sur les sept formats
    assert "2 autre" in texte         # les deux formats non montrés


def test_a_short_list_of_odd_sizes_says_nothing_more(step, tmp_path):
    from pokemon_mosaic.cards import SizeWarning

    ecran, _ = step
    jeu = card_set_in(tmp_path, {"s": ["a"]})
    jeu.full_size = (734, 1024)
    jeu.odd_sizes = [SizeWarning(size=(717, 1000), count=3)]
    ecran._show_warnings(jeu)

    assert "autre" not in ecran._warnings.text()


# --- La recherche par nom --------------------------------------------------

def test_the_search_field_is_hidden_until_cards_arrive(step, tmp_path):
    """Un champ de recherche au-dessus d'un écran d'accueil ne cherche rien."""
    ecran, session = step
    assert not ecran._search.isVisibleTo(ecran)

    charge(ecran, session, tmp_path, {"a1": ["pikachu"]})
    ecran._update_state()
    assert ecran._search.isVisibleTo(ecran)


def test_typing_a_name_narrows_the_gallery(step, tmp_path):
    ecran, session = step
    charge(ecran, session, tmp_path,
           {"a1": ["a1-004-dracaufeu", "a1-007-carapuce"],
            "a2": ["a2-011-dracofeu-ex", "a2-030-pikachu"]})

    assert ecran._gallery.visible_count() == 4
    ecran._search.setText("draca")
    assert ecran._gallery.visible_count() == 1
    ecran._search.setText("")
    assert ecran._gallery.visible_count() == 4


def test_the_search_ignores_case_and_accents(step, tmp_path):
    """Les noms de fichiers sont normalisés par `artwork.slug()`, pas ce qu'on
    tape : chercher « Mustébouée » au clavier doit trouver `mustebouee`."""
    ecran, session = step
    charge(ecran, session, tmp_path, {"a1": ["a1-055-mustebouee", "a1-056-mew"]})

    ecran._search.setText("Mustébouée")
    assert ecran._gallery.visible_count() == 1


def test_the_search_and_the_folder_filter_add_up(step, tmp_path):
    """Chercher un nom **dans** une extension est le geste attendu ; se
    remplacer l'un l'autre obligerait à défaire la sélection avant de chercher."""
    ecran, session = step
    charge(ecran, session, tmp_path,
           {"a1": ["a1-004-pikachu", "a1-007-carapuce"],
            "a2": ["a2-030-pikachu"]})

    ecran._search.setText("pikachu")
    assert ecran._gallery.visible_count() == 2

    choisir(ecran, "a1")
    assert ecran._gallery.visible_count() == 1


def test_a_fruitless_search_says_so_in_the_counter(step, tmp_path):
    """Une galerie vide sans explication passe pour un chargement raté."""
    ecran, session = step
    charge(ecran, session, tmp_path, {"a1": ["a1-004-pikachu"]})

    ecran._search.setText("zzz")
    assert ecran._gallery.visible_count() == 0
    assert "0" in ecran._count.text()


def test_loading_another_folder_clears_the_search(step, tmp_path):
    """Un nouveau jeu s'ouvre en entier : garder la recherche précédente
    montrerait une galerie presque vide sans dire pourquoi."""
    ecran, session = step
    charge(ecran, session, tmp_path, {"a1": ["a1-004-pikachu", "a1-007-carapuce"]})
    ecran._search.setText("pikachu")
    assert ecran._gallery.visible_count() == 1

    charge(ecran, session, tmp_path / "autre", {"b1": ["b1-001-salameche"]})
    assert ecran._search.text() == ""
    assert ecran._gallery.visible_count() == 1


def test_cards_arriving_during_a_search_respect_it(step, tmp_path):
    """Le chargement se fait par lots : un dossier qui arrive après la frappe
    ne doit pas s'ajouter en bloc sous le filtre en cours."""
    ecran, session = step
    charge(ecran, session, tmp_path, {"a1": ["a1-004-pikachu"]})
    ecran._search.setText("pikachu")

    jeu = card_set_in(tmp_path / "a2", {"a2": ["a2-030-pikachu", "a2-031-mew"]})
    # `append_cards` conserve les indices reçus : le vrai chargeur numérote à la
    # suite d'un dossier à l'autre, on fait de même.
    for rang, carte in enumerate(jeu.cards, start=session.total_cards):
        carte.index = rang
    session.append_cards(jeu.cards)
    assert ecran._gallery.visible_count() == 2


# --- Les boutons de masse portent sur ce qui est affiché -------------------

def test_the_bulk_buttons_act_on_what_the_gallery_shows(step, tmp_path):
    """Chercher « dracaufeu » puis cliquer « Tout exclure » effaçait la
    sélection entière : 40 cartes exclues au lieu des 10 affichées."""
    ecran, session = step
    charge(ecran, session, tmp_path,
           {"a1": ["a1-004-dracaufeu", "a1-007-carapuce", "a1-025-pikachu"]})

    ecran._search.setText("dracaufeu")
    assert ecran._gallery.visible_count() == 1
    ecran._exclude_all.click()

    assert session.selected_count == 2
    assert session.is_excluded(0)


def test_without_a_filter_the_bulk_buttons_still_take_everything(step, tmp_path):
    ecran, session = step
    charge(ecran, session, tmp_path, {"a1": ["x", "y"], "a2": ["z"]})

    ecran._exclude_all.click()
    assert session.selected_count == 0
    ecran._include_all.click()
    assert session.selected_count == 3


def test_the_bulk_labels_name_their_target_once_filtered(step, tmp_path):
    """« Tout exclure » au-dessus de deux résultats se lit « ces deux-là » :
    le libellé chiffré retire l'ambiguïté dans les deux sens."""
    ecran, session = step
    charge(ecran, session, tmp_path,
           {"a1": ["a1-004-pikachu", "a1-030-pikachu-ex", "a1-007-carapuce"]})

    assert ecran._exclude_all.text() == "Tout exclure"

    ecran._search.setText("pikachu")
    assert "2" in ecran._exclude_all.text()
    assert "Tout" not in ecran._exclude_all.text()

    ecran._search.setText("")
    assert ecran._exclude_all.text() == "Tout exclure"


def test_selecting_a_folder_also_narrows_the_bulk_buttons(step, tmp_path):
    ecran, session = step
    charge(ecran, session, tmp_path, {"a1": ["x", "y"], "a2": ["z"]})

    choisir(ecran, "a1")
    assert "2" in ecran._include_all.text()

    ecran._include_all.click()          # a1 seul
    ecran._exclude_all.click()
    assert session.selected_count == 1  # la carte de a2 reste retenue


def test_the_bulk_buttons_stay_inside_the_gallery_once_relabelled(step, tmp_path):
    """Le libellé chiffré est plus long : sans replacement, la barre flottante
    déborde du bord droit."""
    ecran, session = step
    charge(ecran, session, tmp_path, {"a1": ["a1-004-pikachu", "a1-007-carapuce"]})
    ecran._gallery.resize(400, 300)
    ecran._place_bulk_buttons()

    ecran._search.setText("pikachu")
    droite = ecran._bulk.geometry().right()
    assert droite < ecran._gallery.width()


# --- Le surlignage de sélection --------------------------------------------

def test_clicking_a_card_leaves_no_highlight_behind(step, tmp_path):
    """La sélection ne sert qu'à désigner un lot avant de le basculer. Posée,
    elle surlignait la carte en bleu comme du texte attrapé à la souris,
    par-dessus le seul signal qui compte — l'inclusion, dite par l'opacité.

    ⚠️ Un vrai clic, et non l'appel du slot : c'est `mousePressEvent` qui pose
    la sélection, et `clicked` ne part qu'au relâché. Appeler le slot à la main
    ne prouverait rien de ce qui se passe entre les deux.
    """
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    ecran, session = step
    charge(ecran, session, tmp_path, {"a1": ["x", "y", "z"]})
    galerie = ecran._gallery
    galerie.resize(400, 300)
    galerie.show()
    centre = galerie.visualRect(galerie.model().index(1)).center()

    QTest.mousePress(galerie.viewport(), Qt.LeftButton, Qt.NoModifier, centre)
    QTest.mouseRelease(galerie.viewport(), Qt.LeftButton, Qt.NoModifier, centre)

    assert galerie.selectionModel().selectedIndexes() == []
    assert not galerie.selectionModel().currentIndex().isValid()
    assert session.is_excluded(1), "le clic doit tout de même basculer la carte"


def test_a_rubber_band_selection_still_toggles_the_whole_lot(step, tmp_path):
    """Le rectangle de sélection garde son surlignage : il ne passe pas par ce
    slot, `clicked` ne partant pas sur un glissé. Le clic qui suit bascule tout."""
    from PySide6.QtCore import QItemSelection, QItemSelectionModel

    ecran, session = step
    charge(ecran, session, tmp_path, {"a1": ["x", "y", "z", "w"]})
    galerie = ecran._gallery
    modele = galerie.model()

    lot = QItemSelection(modele.index(0), modele.index(2))
    galerie.selectionModel().select(lot, QItemSelectionModel.Select)
    assert len(galerie.selectionModel().selectedIndexes()) == 3

    galerie._on_clicked(modele.index(1))
    assert [session.is_excluded(i) for i in range(4)] == [True, True, True, False]
    assert galerie.selectionModel().selectedIndexes() == []


# --- Inverser la sélection --------------------------------------------------

def test_inverting_swaps_every_card(step, tmp_path):
    ecran, session = step
    charge(ecran, session, tmp_path, {"a1": ["x", "y", "z", "w"]})
    session.set_excluded([0, 1], True)

    ecran._invert.click()
    assert [session.is_excluded(i) for i in range(4)] == [False, False, True, True]


def test_inverting_respects_the_filter(step, tmp_path):
    """Même portée que ses deux voisins : ce que la galerie montre."""
    ecran, session = step
    charge(ecran, session, tmp_path,
           {"a1": ["a1-004-pikachu", "a1-007-carapuce"], "a2": ["a2-030-pikachu"]})
    session.set_excluded([0], True)

    ecran._search.setText("carapuce")          # la carte 1 seule
    ecran._invert.click()
    assert [session.is_excluded(i) for i in range(3)] == [True, True, False]


def test_inverting_repaints_even_when_the_count_is_unchanged(step, tmp_path):
    """Deux `set_excluded`, un par sens, ne préviendraient pas : le signal ne
    part que si le **nombre** d'exclues a changé, et une inversion peut le
    laisser identique — deux cartes dedans, deux dehors."""
    ecran, session = step
    charge(ecran, session, tmp_path, {"a1": ["x", "y", "z", "w"]})
    session.set_excluded([0, 1], True)

    vus = []
    session.selection_changed.connect(lambda: vus.append(session.selected_count))
    ecran._invert.click()

    assert session.selected_count == 2, "le décompte est bien resté le même"
    assert vus, "l'écran n'a pas été prévenu du changement"


def test_the_invert_button_hides_while_no_card_is_loaded(step):
    ecran, _ = step
    assert not ecran._invert.isEnabled()
