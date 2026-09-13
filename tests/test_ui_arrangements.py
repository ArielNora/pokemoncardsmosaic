"""Tests du menu des agencements enregistrés."""

import numpy as np
import pytest

from pokemon_mosaic.arrangements import Arrangement, list_arrangements, save_arrangement
from pokemon_mosaic.cards import Card, CardSet


def card_set_in(tmp_path, names, size=(6, 8)):
    """Arborescence réelle : un agencement se relit par chemins."""
    width, height = size
    dossier = tmp_path / "cartes" / "a"
    dossier.mkdir(parents=True, exist_ok=True)
    cards = []
    for nom in names:
        chemin = dossier / f"{nom}.webp"
        chemin.touch()
        vignette = np.full((height, width, 3), (len(cards) * 30) % 255, np.uint8)
        card = Card(path=str(chemin), index=len(cards), thumbnail=vignette)
        card.top = card.bottom = card.left = card.right = np.zeros(3)
        cards.append(card)
    return CardSet(cards=cards, full_size=(713, 984), thumb_size=size)


@pytest.fixture
def session(qt_app, tmp_path):
    from pokemon_mosaic.ui.session import Session

    s = Session()
    s.set_cards(card_set_in(tmp_path, ["un", "deux", "trois", "quatre"]),
                str(tmp_path / "cartes"))
    return s


@pytest.fixture
def bibliotheque(tmp_path):
    return str(tmp_path / "agencements")


def range_un(bibliotheque, name="essai", cards=("a/un.webp", "a/deux.webp"),
             grid=((0, 1), (1, 0)), saved_at="2026-09-05T18:00:00", **reste):
    arrangement = Arrangement(name=name, cards=cards, grid=grid,
                              saved_at=saved_at, **reste)
    save_arrangement(bibliotheque, arrangement)
    return arrangement


@pytest.fixture
def menu(session, bibliotheque):
    from pokemon_mosaic.ui.arrangements_dialog import ArrangementsDialog

    range_un(bibliotheque)
    return ArrangementsDialog(session, bibliotheque), session, bibliotheque


def test_the_menu_lists_the_library(menu):
    widget, _, bibliotheque = menu
    range_un(bibliotheque, "second", saved_at="2026-09-06T09:00:00")
    widget.reload()

    assert widget._list.count() == 2
    assert widget.current().name == "second", "le plus récent en tête"


def test_a_missing_card_is_counted_named_and_crossed(menu, bibliotheque):
    """⚠️ Amputé, ce n'est plus l'agencement qu'on a partagé : on le montre, on
    dit ce qui manque, et on ne le laisse pas passer."""
    widget, _, _ = menu
    range_un(bibliotheque, "troué", cards=("a/un.webp", "a/jamais-vue.webp"),
             saved_at="2026-09-07T09:00:00")
    widget.reload(select="troué")

    assert "manquante" in widget._list.item(0).text()
    assert "jamais-vue" in widget._cards.item(0).text()
    assert widget._cards.item(0).text().startswith("✕")
    assert widget._missing.text() != ""
    assert not widget._open.isEnabled(), "il ne doit pas passer à l'export"


def test_without_cards_the_list_asks_to_load_them_first(qt_app, bibliotheque):
    """Premier démarrage ou chargement en cours : toutes les cartes seraient
    « manquantes », et le message laissait croire à un catalogue incomplet."""
    from pokemon_mosaic.ui.arrangements_dialog import ArrangementsDialog
    from pokemon_mosaic.ui.session import Session

    range_un(bibliotheque)
    widget = ArrangementsDialog(Session(), bibliotheque)

    assert widget._list.count() == 1, "la liste reste parcourable"
    assert "manquante" not in widget._list.item(0).text()
    assert "Chargez d'abord les cartes" in widget._missing.text()
    assert not widget._open.isEnabled()


def test_the_missing_card_names_are_red(menu, bibliotheque):
    """Demandé par l'utilisateur : les noms des cartes manquantes en rouge, le
    rouge du thème, lisible en clair comme en sombre."""
    from PySide6.QtGui import QColor

    from pokemon_mosaic.ui import theme

    widget, _, _ = menu
    range_un(bibliotheque, "troué", cards=("a/un.webp", "a/jamais-vue.webp"),
             saved_at="2026-09-07T09:00:00")
    widget.reload(select="troué")
    rouge = QColor(theme.colours(widget.palette())["error"])

    assert widget._cards.item(0).foreground().color() == rouge
    assert widget._cards.item(1).foreground().color() != rouge, "présente"


# --- Partir d'un agencement dès le début ------------------------------------

def carre(bibliotheque, name="départ", **reste):
    """Trois cartes et un trou, en 2×2 : de quoi vérifier cartes, forme et
    cases vides."""
    return range_un(bibliotheque, name, cards=("a/un.webp", "a/deux.webp",
                                               "a/trois.webp"),
                    grid=((0, 1), (2, -1)), **reste)


def test_starting_from_an_arrangement_keeps_only_its_cards(session, bibliotheque):
    arrangement = carre(bibliotheque)

    session.apply_arrangement(arrangement)

    chemins = {session.card_set[i].path.split("cartes/")[1]
               for i in session.selected_indices()}
    assert chemins == {"a/un.webp", "a/deux.webp", "a/trois.webp"}


def test_starting_takes_the_shape_and_the_empty_cells(session, bibliotheque):
    arrangement = carre(bibliotheque)
    session.set_layout(cols=5, rows=4)

    session.apply_arrangement(arrangement)

    assert (session.cols, session.rows) == (2, 2)
    assert session.empty_cells() == [(1, 1)]
    assert session.missing_empty_cells() == 0


def test_starting_takes_the_presentation_and_fills_a_slot(session, bibliotheque):
    arrangement = carre(bibliotheque, presentation={"card_gap_mm": 4.0})

    depart = session.apply_arrangement(arrangement)

    assert session.card_gap_mm == 4.0
    assert depart.slot == 0 and session.saved_count() == 1
    assert np.array_equal(session.saved[0].grid, [[0, 1], [2, -1]])


def test_starting_announces_itself_once(session, bibliotheque):
    arrangement = carre(bibliotheque)
    vus = []
    session.arrangement_applied.connect(lambda: vus.append(1))

    session.apply_arrangement(arrangement)

    assert vus == [1]


def test_starting_is_refused_when_every_slot_is_taken(session, bibliotheque):
    """Décidé par l'utilisateur : refusé, et rien n'est touché."""
    from pokemon_mosaic.ui.session import NoFreeSlot

    arrangement = carre(bibliotheque)
    session.set_layout(cols=5, rows=4)
    for _ in range(4):
        session.save_grid(np.zeros((1, 1), int), session.card_set, 0, 1.0)

    with pytest.raises(NoFreeSlot):
        session.apply_arrangement(arrangement)

    assert session.selected_count == 4
    assert (session.cols, session.rows) == (5, 4)


def test_starting_is_refused_when_a_card_is_missing(session, bibliotheque):
    arrangement = range_un(bibliotheque, "troué",
                           cards=("a/un.webp", "a/jamais-vue.webp"),
                           grid=((0, 1),))

    with pytest.raises(ValueError):
        session.apply_arrangement(arrangement)

    assert session.selected_count == 4 and session.saved_count() == 0


def test_links_broken_in_the_arrangement_are_disabled(session, bibliotheque):
    """Un calcul qui part d'une grille exige chaque lien actif intact :
    « Lancer » échouerait sinon. Désactivés, pas supprimés."""
    from pokemon_mosaic.links import Link

    arrangement = range_un(bibliotheque, "quatre",
                           cards=("a/un.webp", "a/deux.webp", "a/trois.webp",
                                  "a/quatre.webp"),
                           grid=((0, 1), (2, 3)))
    intact = Link(cards=(0, 1), shape=(2, 1))
    # Imposé dans l'ordre 4, 3 : la grille les pose 3, 4.
    rompu = Link(cards=(3, 2), shape=(2, 1), ordered=True)
    session.add_link(intact)
    session.add_link(rompu)

    depart = session.apply_arrangement(arrangement)

    actifs = {link.cards for link in session.links.active}
    assert actifs == {(0, 1)}
    assert [link.cards for link in depart.disabled_links] == [(3, 2)]
    assert len(session.links.links) == 2, "désactivé, pas supprimé"


def test_starting_disarms_the_grid_proposed_on_the_first_visit(session,
                                                               bibliotheque):
    """La grille proposée d'office au premier passage écraserait celle de
    l'agencement."""
    from pokemon_mosaic.ui.layout_tabs import GridSizeTab

    # ⚠️ **La même forme déjà en place** : `set_layout` ne dit alors rien, et
    # seul le signal émis par la reprise désarme la proposition.
    session.set_layout(cols=2, rows=2)
    onglet = GridSizeTab(session)
    assert onglet._auto_fit_pending

    session.apply_arrangement(carre(bibliotheque))

    assert not onglet._auto_fit_pending
    onglet._auto_fit()
    assert (session.cols, session.rows) == (2, 2)


def test_starting_validates_every_part_of_step_two(session, bibliotheque):
    """Décidé par l'utilisateur : « Suivant » traverse l'étape d'un clic."""
    from pokemon_mosaic.ui.layout_step import LayoutStep

    etape = LayoutStep(session)
    assert not etape._validated

    session.apply_arrangement(carre(bibliotheque))

    assert etape._validated == set(range(len(etape._tabs)))


def test_starting_is_refused_while_the_cards_are_still_loading(session,
                                                              bibliotheque):
    """Trouvé par la revue : les lots suivants arrivaient retenus, et la fin du
    chargement réarmait la grille proposée, qui écrasait la forme reprise."""
    arrangement = carre(bibliotheque)
    cartes = list(session.card_set)
    session.start_loading(session.data_dir)
    session.append_cards(cartes[:3])
    assert session.loading

    with pytest.raises(ValueError, match="Chargement"):
        session.apply_arrangement(arrangement)

    assert session.saved_count() == 0 and (session.cols, session.rows) != (2, 2)


def test_the_start_button_waits_for_the_end_of_the_loading(session,
                                                           bibliotheque):
    """Grisé tant que des cartes arrivent, rendu à la fin sans rouvrir la
    fenêtre."""
    from pokemon_mosaic.ui.arrangements_dialog import ArrangementsDialog

    carre(bibliotheque)
    reference = session.card_set
    cartes = list(reference)
    session.start_loading(session.data_dir)
    session.append_cards(cartes[:3])
    widget = ArrangementsDialog(session, bibliotheque, start=True)

    assert not widget._open.isEnabled()
    assert "Chargez d'abord les cartes" in widget._missing.text()

    session.append_cards(cartes[3:])
    session.finish_loading(reference)

    assert widget._open.isEnabled()
    assert widget._missing.text() == ""


def test_the_start_mode_offers_to_start_from_the_arrangement(session,
                                                             bibliotheque):
    from pokemon_mosaic.ui.arrangements_dialog import ArrangementsDialog

    carre(bibliotheque)
    widget = ArrangementsDialog(session, bibliotheque, start=True)

    assert widget._open.text() == "Partir de cet agencement"
    widget._open.click()

    assert (session.cols, session.rows) == (2, 2)
    assert widget.applied == "départ"


def test_the_start_mode_refuses_when_every_slot_is_taken(session, bibliotheque,
                                                         monkeypatch):
    from pokemon_mosaic.ui import arrangements_dialog as module
    from pokemon_mosaic.ui.arrangements_dialog import ArrangementsDialog

    carre(bibliotheque)
    for _ in range(4):
        session.save_grid(np.zeros((1, 1), int), session.card_set, 0, 1.0)
    avis = []
    monkeypatch.setattr(module.QMessageBox, "information",
                        lambda *a, **k: avis.append(a[1]))
    widget = ArrangementsDialog(session, bibliotheque, start=True)

    widget._open.click()

    assert avis and widget.applied == ""
    assert session.selected_count == 4


def test_the_start_mode_names_the_disabled_links(session, bibliotheque,
                                                 monkeypatch):
    from pokemon_mosaic.links import Link
    from pokemon_mosaic.ui import arrangements_dialog as module
    from pokemon_mosaic.ui.arrangements_dialog import ArrangementsDialog

    range_un(bibliotheque, "quatre",
             cards=("a/un.webp", "a/deux.webp", "a/trois.webp", "a/quatre.webp"),
             grid=((0, 1), (2, 3)))
    session.add_link(Link(cards=(3, 2), shape=(2, 1), ordered=True,
                          name="Arcko et Massko"))
    avis = []
    monkeypatch.setattr(module.QMessageBox, "warning",
                        lambda *a, **k: avis.append(a[2]))
    widget = ArrangementsDialog(session, bibliotheque, start=True)

    widget._open.click()

    assert len(avis) == 1 and "Arcko et Massko" in avis[0]
    assert widget.applied == "quatre"


def test_a_complete_arrangement_can_be_opened_into_a_slot(menu):
    widget, session, _ = menu

    widget._open_current()

    garde = session.saved[0]
    assert garde is not None
    noms = [[garde.cards[case].name for case in ligne] for ligne in garde.grid]
    assert noms == [["un", "deux"], ["deux", "un"]]


def test_opening_says_when_every_slot_is_taken(menu, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    from pokemon_mosaic.ui.session import MAX_SAVED

    widget, session, _ = menu
    jeu = session.card_set
    for numero in range(MAX_SAVED):
        session.save_grid(np.array([[0, 1]]), jeu, numero, 0.0)
    vus = []
    monkeypatch.setattr(QMessageBox, "information",
                        lambda *a, **k: vus.append(a[2]))

    widget._open_current()

    assert vus, "l'utilisateur doit savoir pourquoi rien ne s'ouvre"


def test_exporting_writes_the_chosen_file(menu, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QFileDialog

    from pokemon_mosaic.arrangements import read_arrangement

    widget, _, _ = menu
    cible = tmp_path / "partage.json"
    monkeypatch.setattr(QFileDialog, "getSaveFileName",
                        lambda *a, **k: (str(cible), ""))

    widget._export_current()

    assert read_arrangement(str(cible)).name == "essai"


def test_importing_never_overwrites_a_namesake(menu, tmp_path, monkeypatch):
    """Deux personnes nomment volontiers leur essai de la même façon."""
    from PySide6.QtWidgets import QFileDialog

    from pokemon_mosaic.arrangements import write_arrangement

    widget, _, bibliotheque = menu
    venu = tmp_path / "venu.json"
    write_arrangement(str(venu), Arrangement(name="essai", cards=("a/un.webp",),
                                             grid=((0,),), score=9.0))
    monkeypatch.setattr(QFileDialog, "getOpenFileName",
                        lambda *a, **k: (str(venu), ""))

    widget._import_file()

    noms = sorted(un.name for un in list_arrangements(bibliotheque))
    assert noms == ["essai", "essai (2)"]


def test_an_unreadable_file_is_reported_not_raised(menu, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QFileDialog, QMessageBox

    widget, _, bibliotheque = menu
    casse = tmp_path / "casse.json"
    casse.write_text("{ pas du json", encoding="utf-8")
    monkeypatch.setattr(QFileDialog, "getOpenFileName",
                        lambda *a, **k: (str(casse), ""))
    vus = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: vus.append(a[1]))

    widget._import_file()

    assert vus
    assert len(list_arrangements(bibliotheque)) == 1


def test_renaming_and_deleting_go_through_the_library(menu, monkeypatch):
    from PySide6.QtWidgets import QInputDialog, QMessageBox

    widget, _, bibliotheque = menu
    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: ("baptisé", True))
    widget._rename_current()
    assert [un.name for un in list_arrangements(bibliotheque)] == ["baptisé"]

    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.Yes)
    widget._delete_current()
    assert list_arrangements(bibliotheque) == []


def test_deleting_asks_first(menu, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    widget, _, bibliotheque = menu
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.No)

    widget._delete_current()

    assert len(list_arrangements(bibliotheque)) == 1


def test_the_preview_crosses_the_missing_cards(session, bibliotheque):
    """La croix rouge se voit dans l'image, pas seulement dans la liste."""
    from pokemon_mosaic.ui.arrangements_dialog import MISSING_FILL, arrangement_image

    arrangement = Arrangement(name="troué", cards=("a/un.webp", "a/perdue.webp"),
                              grid=((0, 1),))
    image = arrangement_image(arrangement, session, (255, 255, 255))

    largeur = image.width() // 2
    couleurs = {image.pixelColor(x, image.height() // 2).name()
                for x in range(largeur, image.width())}
    assert MISSING_FILL.name() in couleurs or any(
        couleur != "#ffffff" for couleur in couleurs)
    assert image.pixelColor(2, image.height() // 2).name() != MISSING_FILL.name()


def test_an_empty_library_says_so(session, bibliotheque):
    from pokemon_mosaic.ui.arrangements_dialog import ArrangementsDialog

    widget = ArrangementsDialog(session, bibliotheque)

    assert widget.current() is None
    assert not widget._open.isEnabled()
    assert "Aucun" in widget._title.text()


# --- La liste d'abord, l'aperçu ensuite ------------------------------------

def attendre(condition, delai=5.0):
    """Laisse tourner la boucle d'événements jusqu'à ce que la condition tienne."""
    import time

    from PySide6.QtWidgets import QApplication

    fin = time.monotonic() + delai
    while not condition():
        assert time.monotonic() < fin, "rien n'est venu"
        QApplication.processEvents()
        time.sleep(0.005)


def retenu(porte, vrai):
    """Un aperçu qui ne se termine qu'une fois la porte ouverte, ou abandonné.

    Chaque démarrage laisse dans `porte.demarres` sa fonction « périmé ? ».
    """
    import time

    def compose(grid, tiles, tile_shape, empty_colour, fit=None,
                cancelled=lambda: False):
        porte.demarres.append(cancelled)
        while not porte.is_set():
            if cancelled():
                return None
            time.sleep(0.005)
        return vrai(grid, tiles, tile_shape, empty_colour, fit=fit,
                    cancelled=cancelled)
    return compose


@pytest.fixture
def apercu_retenu(monkeypatch):
    """La porte de l'aperçu, ouverte en fin de test quoi qu'il arrive."""
    import threading

    from pokemon_mosaic.ui import arrangements_dialog as module

    porte = threading.Event()
    porte.demarres = []
    monkeypatch.setattr(module, "compose_arrangement",
                        retenu(porte, module.compose_arrangement))
    yield porte
    porte.set()


def test_resolving_paths_reads_the_catalogue_once(session, monkeypatch):
    """⚠️ Une carte cherchée refaisait un `relpath` sur tout le catalogue : le
    menu mettait 34 s à s'ouvrir sur dix agencements de 441 cartes."""
    import os

    vrai, appels = os.path.relpath, []
    monkeypatch.setattr(os.path, "relpath",
                        lambda *a, **k: appels.append(1) or vrai(*a, **k))
    arrangement = Arrangement(
        name="long", grid=((0,),),
        cards=("a/un.webp", "a/deux.webp", "a/trois.webp", "a/quatre.webp") * 25)

    assert session.missing_cards(arrangement) == []
    assert len(appels) <= len(session.card_set)


def test_the_path_table_follows_the_catalogue(session, tmp_path):
    """La table se refait quand le jeu change : un lot qui arrive, ou un autre
    dossier qui remplace le premier."""
    assert session.index_of_path("a/deux.webp") == 1

    cinquieme = card_set_in(tmp_path, ["un", "deux", "trois", "quatre", "cinq"])[4]
    session.append_cards([cinquieme])
    assert session.index_of_path("a/cinq.webp") == 4

    ailleurs = tmp_path / "ailleurs"
    session.set_cards(card_set_in(ailleurs, ["seul"]), str(ailleurs / "cartes"))
    assert session.index_of_path("a/seul.webp") == 0
    assert session.index_of_path("a/deux.webp") is None


def test_the_window_opens_on_the_list_before_any_preview(session, bibliotheque,
                                                         apercu_retenu):
    """⚠️ **La sélection n'attend pas l'image.** Liste, titre et cartes sont là
    tout de suite ; l'aperçu arrive ensuite, l'attente tournant à sa place."""
    from pokemon_mosaic.ui.arrangements_dialog import ArrangementsDialog

    range_un(bibliotheque)
    widget = ArrangementsDialog(session, bibliotheque)
    try:
        assert widget._list.count() == 1
        assert "essai" in widget._title.text()
        assert widget._cards.count() == 2
        assert widget._image.pixmap().isNull()
        assert not widget._spinner.isHidden()

        apercu_retenu.set()
        attendre(lambda: widget._spinner.isHidden())

        assert not widget._image.pixmap().isNull()
    finally:
        apercu_retenu.set()
        widget.done(0)


def test_only_the_last_selection_gets_its_preview(session, bibliotheque,
                                                  apercu_retenu):
    """Parcourir la liste lance une demande par ligne : seule compte la
    dernière. ⚠️ L'image affichée s'efface dès qu'on quitte sa ligne : laissée
    le temps du calcul, elle se lirait sous le titre du nouvel agencement."""
    from pokemon_mosaic.ui.arrangements_dialog import ArrangementsDialog

    # « un » est noir, « quatre » gris : l'image dit laquelle est arrivée.
    range_un(bibliotheque, "sombre", cards=("a/un.webp",), grid=((0,),),
             saved_at="2026-09-05T18:00:00")
    range_un(bibliotheque, "clair", cards=("a/quatre.webp",), grid=((0,),),
             saved_at="2026-09-06T18:00:00")
    widget = ArrangementsDialog(session, bibliotheque)
    try:
        assert widget.current().name == "clair"
        apercu_retenu.set()
        attendre(lambda: widget._spinner.isHidden())
        assert not widget._image.pixmap().isNull()

        apercu_retenu.clear()
        widget._list.setCurrentRow(1)
        assert widget.current().name == "sombre"
        assert widget._image.pixmap().isNull(), "l'image du clair traîne encore"
        assert not widget._spinner.isHidden()

        apercu_retenu.set()
        attendre(lambda: widget._spinner.isHidden())

        image = widget._image.pixmap().toImage()
        assert image.pixelColor(image.width() // 2, image.height() // 2).red() < 15
    finally:
        apercu_retenu.set()
        widget.done(0)

def test_an_image_for_an_older_request_is_ignored(session, bibliotheque,
                                                  apercu_retenu):
    """⚠️ Le calcul peut émettre juste avant qu'on change de ligne : son image
    arrive après la nouvelle demande, et se poserait sous le mauvais titre,
    l'attente éteinte."""
    from PySide6.QtGui import QColor, QImage

    from pokemon_mosaic.ui.arrangements_dialog import ArrangementsDialog

    range_un(bibliotheque)
    widget = ArrangementsDialog(session, bibliotheque)
    try:
        image = QImage(10, 10, QImage.Format_RGB888)
        image.fill(QColor("red"))

        widget._on_preview(widget._preview.token - 1, image)
        assert widget._image.pixmap().isNull()
        assert not widget._spinner.isHidden()

        widget._on_preview(widget._preview.token, image)
        assert not widget._image.pixmap().isNull()
        assert widget._spinner.isHidden()
    finally:
        apercu_retenu.set()
        widget.done(0)


def test_opening_computes_a_single_preview(session, bibliotheque, apercu_retenu):
    """Seul l'agencement sélectionné charge son aperçu, et une seule fois : la
    liste remplie redemandait l'image de la ligne qu'elle venait de choisir, et
    le premier calcul partait pour rien."""
    from pokemon_mosaic.ui.arrangements_dialog import ArrangementsDialog

    range_un(bibliotheque)
    range_un(bibliotheque, "second", saved_at="2026-09-06T09:00:00")
    widget = ArrangementsDialog(session, bibliotheque)
    try:
        apercu_retenu.set()
        attendre(lambda: widget._spinner.isHidden())
        widget._pool.waitForDone()

        assert len(apercu_retenu.demarres) == 1
    finally:
        apercu_retenu.set()
        widget.done(0)


def test_closing_abandons_the_preview_and_waits_for_its_thread(
        session, bibliotheque, apercu_retenu):
    """⚠️ Un fil détruit en plein calcul fait abandonner le processus par Qt :
    la fenêtre attend l'aperçu, qui s'abandonne à sa rangée suivante.

    On attend l'aperçu **en cours**, et non le premier fil venu : un aperçu déjà
    périmé s'arrête de lui-même, et le test passait sans que la fermeture ait
    rien demandé."""
    from pokemon_mosaic.ui.arrangements_dialog import ArrangementsDialog

    range_un(bibliotheque)
    widget = ArrangementsDialog(session, bibliotheque)
    attendre(lambda: widget._pool.activeThreadCount() == 1 and any(
        not perime() for perime in apercu_retenu.demarres))

    widget.done(0)

    assert widget._pool.activeThreadCount() == 0, "l'aperçu en cours tourne encore"
    assert not apercu_retenu.is_set()


# --- Renommer, supprimer : le bon agencement, et les erreurs dites ------------

def test_renaming_selects_the_name_actually_written(menu, monkeypatch):
    """Renommer vers un nom pris donne « B (2) » : sélectionner le nom tapé
    désignait l'autre agencement, que « Supprimer » aurait visé."""
    from PySide6.QtWidgets import QInputDialog

    widget, _, bibliotheque = menu
    range_un(bibliotheque, "B", saved_at="2026-09-04T09:00:00")
    widget.reload(select="essai")
    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: ("B", True))

    widget._rename_current()

    assert widget.current().name == "B (2)"


def test_renaming_by_case_alone_from_the_menu(menu, monkeypatch):
    """⚠️ « essai » en « ESSAI » effaçait l'agencement sur le disque de macOS."""
    from PySide6.QtWidgets import QInputDialog

    widget, _, bibliotheque = menu
    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: ("ESSAI", True))

    widget._rename_current()

    assert [un.name for un in list_arrangements(bibliotheque)] == ["ESSAI"]
    assert widget.current().name == "ESSAI"


@pytest.mark.parametrize("geste, fonction", [
    ("_rename_current", "rename_arrangement"),
    ("_delete_current", "delete_arrangement"),
])
def test_a_disk_error_is_reported_not_raised(menu, monkeypatch, geste, fonction):
    """Une erreur disque sortait du slot sans message : le geste semblait ne rien
    faire, et la trace n'allait nulle part depuis le paquet `.app`."""
    from PySide6.QtWidgets import QInputDialog, QMessageBox

    from pokemon_mosaic.ui import arrangements_dialog as module

    widget, _, _ = menu

    def refus(*a, **k):
        raise OSError("disque plein")

    monkeypatch.setattr(module, fonction, refus)
    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: ("autre", True))
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.Yes)
    vus = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: vus.append(a[2]))

    getattr(widget, geste)()

    assert vus == ["disque plein"]


# --- L'habillage revient avec l'agencement ------------------------------------

HABILLAGE = {"paper": "A3", "dpi": 150, "gap_colour": [10, 20, 30],
             "card_gap_mm": 2.5}


def test_opening_brings_back_its_presentation(session, bibliotheque):
    """Décidé le 2026-09-12 : un agencement partagé redonne le même poster.
    L'habillage enregistré avec lui n'était jamais reposé, `apply_presentation`
    n'étant appelée nulle part."""
    from pokemon_mosaic.ui.arrangements_dialog import ArrangementsDialog

    range_un(bibliotheque, "habillé", presentation=HABILLAGE)
    widget = ArrangementsDialog(session, bibliotheque)
    try:
        widget._open_current()

        assert session.saved[0] is not None
        assert session.paper == "A3"
        assert session.dpi == 150 and session.dpi_chosen
        assert session.gap_colour == (10, 20, 30)
        assert session.card_gap_mm == 2.5
    finally:
        widget.done(0)


def test_a_refused_opening_leaves_the_presentation_alone(session, bibliotheque,
                                                        monkeypatch):
    """Sans case libre, rien ne s'ouvre : l'habillage en place ne doit pas
    changer pour autant."""
    from PySide6.QtWidgets import QMessageBox

    from pokemon_mosaic.ui.arrangements_dialog import ArrangementsDialog
    from pokemon_mosaic.ui.session import MAX_SAVED

    range_un(bibliotheque, "habillé", presentation=HABILLAGE)
    for numero in range(MAX_SAVED):
        session.save_grid(np.array([[0, 1]]), session.card_set, numero, 0.0)
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)
    papier = session.paper
    widget = ArrangementsDialog(session, bibliotheque)
    try:
        widget._open_current()

        assert session.paper == papier and session.dpi != 150
    finally:
        widget.done(0)



def test_a_malformed_presentation_is_sorted_not_trusted(session):
    """⚠️ Un agencement se partage et se modifie à la main : son habillage n'est
    pas digne de foi. Reproduit avant correction : une couleur entière ou un
    chevauchement en texte levaient une exception une fois la case remplie ; une
    finesse « haute » ou -2 feuilles s'installaient dans la session, et faisaient
    tomber le calcul suivant loin de leur cause."""
    ignores = session.apply_presentation({
        "gap_colour": 5, "overlap_mm": "beaucoup", "dpi": "haute", "panels": -2,
        "card_gap_mm": float("nan"), "empty_colour": [300, 0, 0],
        "background_colour": [1, 2, 3], "paper": "A3", "crop_marks": True,
    })

    assert set(ignores) == {"gap_colour", "overlap_mm", "dpi", "panels",
                            "card_gap_mm", "empty_colour"}
    # Ce qui était valide est repris.
    assert session.background_colour == (1, 2, 3)
    assert session.paper == "A3" and session.crop_marks is True
    # Et la session reste calculable.
    assert isinstance(session.dpi, int) and session.dpi > 0
    assert session.panels >= 1
    session.panel_geometry()


def test_opening_names_the_presentation_fields_it_ignored(session, bibliotheque,
                                                         monkeypatch):
    """La grille est valide : l'agencement s'ouvre. Mais ce qui n'a pas été repris
    se dit, par le nom qu'il porte dans le fichier, là où on le corrige."""
    from PySide6.QtWidgets import QMessageBox

    from pokemon_mosaic.ui.arrangements_dialog import ArrangementsDialog

    range_un(bibliotheque, "abîmé", presentation={"gap_colour": 5, "paper": "A3"})
    vus = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: vus.append(a[2]))
    widget = ArrangementsDialog(session, bibliotheque)
    try:
        widget._open_current()

        assert session.saved[0] is not None
        assert session.paper == "A3"
        assert len(vus) == 1 and "gap_colour" in vus[0]
    finally:
        widget.done(0)


def test_the_presentation_bounds_follow_the_interface():
    """Les écrans importent la session, qui ne peut pas lire leurs constantes :
    ses bornes sont recopiées, et ce test empêche qu'elles divergent."""
    from pokemon_mosaic.ui.export_step import DPI_CEILING
    from pokemon_mosaic.ui.page_preview import MAX_PANEL_ROWS, MAX_PANELS
    from pokemon_mosaic.ui.session import PRESENTATION_BOUNDS

    assert PRESENTATION_BOUNDS["dpi"][1] == DPI_CEILING
    assert PRESENTATION_BOUNDS["panels"] == (1, MAX_PANELS)
    assert PRESENTATION_BOUNDS["panel_rows"] == (1, MAX_PANEL_ROWS)


def test_the_presentation_the_app_writes_is_always_read_back(session):
    """La vérification ne doit jamais être plus stricte que l'application :
    un habillage qu'elle a écrit elle-même se relit sans rien écarter."""
    session.set_layout(paper="A3", landscape=True, dpi=1200, panels=5,
                       panel_rows=3, card_gap_mm=100.0, card_width_mm=40.0)
    session.set_algorithm(overlap_mm=50.0, crop_marks=True,
                          gap_colour=(0, 128, 255), chameleon_border=True)
    session.move_panel(0, 3.0, 4.0)
    habillage = session.presentation()

    assert session.apply_presentation(habillage) == []
    assert session.presentation() == habillage


def test_sheet_moves_are_restored_all_or_nothing(session):
    """Un déplacement abîmé fait écarter le champ : reprendre ceux lus avant lui
    aurait bougé des feuilles que l'avertissement dit non reprises."""
    ecartes = session.apply_presentation({"panel_offsets": [[0, 3.0, 4.0], "abîmé"]})

    assert ecartes == ["panel_offsets"]
    assert session.panel_offsets == {}
