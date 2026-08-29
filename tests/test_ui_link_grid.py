"""Tests de l'éditeur de rectangle : croissance, suppression, glisser-déposer.

La logique est éprouvée par les méthodes plutôt qu'en synthétisant des
événements Qt, sauf pour le transport du glisser lui-même : c'est là que le
format des données compte, et un test qui le contourne ne prouverait rien.
"""

import numpy as np
import pytest


@pytest.fixture
def grille(qt_app):
    from pokemon_mosaic.ui.link_grid import LinkGrid

    editeur = LinkGrid()
    # Des vignettes minuscules : la grille ne regarde ni leur taille ni leur
    # contenu, seulement leur présence.
    editeur.set_thumbnails({i: np.zeros((4, 3, 3), np.uint8) for i in range(9)})
    return editeur


# --- Croissance et réduction ----------------------------------------------

def test_a_new_grid_is_one_empty_cell(grille):
    assert grille.shape == (1, 1)
    assert grille.cards() == [None]
    assert not grille.complete
    assert grille.empty_count() == 1


def test_adding_a_column_then_a_row_gives_a_square(grille):
    grille.add_col()
    grille.add_row()
    assert grille.shape == (2, 2)
    assert grille.cards() == [None] * 4


def test_growth_stops_at_three(grille):
    """Trois cases de côté au plus : au-delà, le bloc devient trop gros devant
    la grille de la mosaïque."""
    for _ in range(5):
        grille.add_col()
        grille.add_row()
    assert grille.shape == (3, 3)


def test_the_last_row_and_column_cannot_be_removed(grille):
    """Sinon la grille n'aurait plus de case du tout, et le dialogue plus rien
    à montrer."""
    grille.remove_row(0)
    grille.remove_col(0)
    assert grille.shape == (1, 1)


def test_removing_a_row_drops_its_cards(grille):
    grille.add_col()
    grille.add_row()
    for position, index in enumerate((0, 1, 2, 3)):
        grille.place(position // 2, position % 2, index)

    grille.remove_row(0)
    assert grille.shape == (2, 1)
    assert grille.cards() == [2, 3]


def test_removing_a_column_drops_its_cards(grille):
    grille.add_col()
    grille.add_row()
    for position, index in enumerate((0, 1, 2, 3)):
        grille.place(position // 2, position % 2, index)

    grille.remove_col(1)
    assert grille.shape == (1, 2)
    assert grille.cards() == [0, 2]


def test_a_removal_button_exists_only_beyond_one(grille):
    """Les « − » n'apparaissent qu'à partir de deux lignes ou deux colonnes."""
    from PySide6.QtWidgets import QPushButton

    def moins():
        return [b for b in grille.findChildren(QPushButton) if b.text() == "－"]

    assert moins() == []
    grille.add_col()
    assert len(moins()) == 2            # un sous chaque colonne
    grille.add_row()
    assert len(moins()) == 4            # deux colonnes + deux lignes


def test_the_add_buttons_disappear_at_three(grille):
    from PySide6.QtWidgets import QPushButton

    def plus():
        return [b for b in grille.findChildren(QPushButton) if b.text() == "＋"]

    assert len(plus()) == 2
    grille.add_col()
    grille.add_col()                     # trois colonnes : plus de « + » à droite
    assert len(plus()) == 1
    grille.add_row()
    grille.add_row()
    assert plus() == []


# --- Contenu ---------------------------------------------------------------

def test_placing_a_card_fills_the_cell(grille):
    grille.add_col()
    grille.place(0, 1, 7)
    assert grille.cards() == [None, 7]
    assert grille.placed_cards() == {7}


def test_a_card_cannot_occupy_two_cells(grille):
    """`Link` refuse une carte répétée : sans ce retrait, déplacer une carte
    la laisserait des deux côtés et la validation lèverait une exception."""
    grille.add_col()
    grille.place(0, 0, 5)
    grille.place(0, 1, 5)
    assert grille.cards() == [None, 5]


def test_dropping_onto_an_occupied_cell_replaces(grille):
    grille.place(0, 0, 1)
    grille.place(0, 0, 2)
    assert grille.cards() == [2]


def test_clearing_a_cell_empties_it(grille):
    grille.place(0, 0, 3)
    grille.clear_cell(0, 0)
    assert grille.cards() == [None]


def test_completeness_needs_every_cell(grille):
    grille.add_col()
    grille.place(0, 0, 1)
    assert not grille.complete
    grille.place(0, 1, 2)
    assert grille.complete


def test_loading_an_existing_link_restores_its_layout(grille):
    grille.load((0, 1, 2, 3, 4, 5), (3, 2))
    assert grille.shape == (3, 2)
    assert grille.cards() == [0, 1, 2, 3, 4, 5]


def test_a_change_is_announced(grille):
    """Le dialogue s'y raccroche pour rafraîchir la palette et le bouton OK."""
    vus = []
    grille.changed.connect(lambda: vus.append(1))
    grille.add_col()
    grille.place(0, 0, 4)
    grille.clear_cell(0, 0)
    assert len(vus) == 3


# --- Le transport du glisser ----------------------------------------------

def test_the_mime_payload_round_trips():
    from pokemon_mosaic.ui.link_grid import card_from_mime, card_mime

    assert card_from_mime(card_mime(42)) == 42


def test_a_foreign_payload_is_not_taken_for_a_card():
    """Un nom de fichier lâché depuis le Finder ne doit pas passer pour un
    indice : d'où un format propre au projet plutôt que du texte brut."""
    from PySide6.QtCore import QMimeData

    from pokemon_mosaic.ui.link_grid import card_from_mime

    etranger = QMimeData()
    etranger.setText("7")
    assert card_from_mime(etranger) is None


def test_a_malformed_payload_is_refused():
    from PySide6.QtCore import QMimeData

    from pokemon_mosaic.ui.link_grid import CARD_MIME, card_from_mime

    abime = QMimeData()
    abime.setData(CARD_MIME, b"pas un nombre")
    assert card_from_mime(abime) is None


def test_the_palette_hands_over_the_card_index(qt_app):
    """C'est ce que la case reçoit : sans cet indice, le dépôt ne saurait pas
    quelle carte poser."""
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QListWidgetItem

    from pokemon_mosaic.ui.link_grid import CardPalette, card_from_mime

    palette = CardPalette()
    item = QListWidgetItem("une carte")
    item.setData(Qt.UserRole, 12)
    palette.addItem(item)

    assert card_from_mime(palette.mimeData([item])) == 12


def test_a_cell_reports_the_drop_with_its_own_coordinates(qt_app):
    """La case connaît sa place ; c'est elle qui la donne à la grille, plutôt
    que la grille de la retrouver par la géométrie."""
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtGui import QDropEvent

    from pokemon_mosaic.ui.link_grid import CardCell, card_mime

    case = CardCell(1, 2)
    recus = []
    case.dropped.connect(lambda r, c, i: recus.append((r, c, i)))
    # ⚠️ La charge est gardée dans une variable : `QDropEvent` n'en prend qu'un
    # pointeur, et un `QMimeData` temporaire est collecté avant que Qt ne le
    # lise — segmentation fault, pas exception.
    charge = card_mime(8)
    case.dropEvent(QDropEvent(QPoint(1, 1), Qt.CopyAction, charge,
                              Qt.LeftButton, Qt.NoModifier))

    assert recus == [(1, 2, 8)]


def test_a_cell_ignores_a_drop_it_cannot_read(qt_app):
    from PySide6.QtCore import QMimeData, QPoint, Qt
    from PySide6.QtGui import QDropEvent

    from pokemon_mosaic.ui.link_grid import CardCell

    case = CardCell(0, 0)
    recus = []
    case.dropped.connect(lambda *a: recus.append(a))
    etranger = QMimeData()
    etranger.setText("/Users/x/photo.png")
    case.dropEvent(QDropEvent(QPoint(1, 1), Qt.CopyAction, etranger,
                              Qt.LeftButton, Qt.NoModifier))

    assert recus == []


def test_double_clicking_a_filled_cell_asks_to_clear_it(qt_app):
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtGui import QMouseEvent

    from pokemon_mosaic.ui.link_grid import CardCell

    case = CardCell(2, 1)
    case.set_card(4, np.zeros((4, 3, 3), np.uint8))
    vus = []
    case.cleared.connect(lambda r, c: vus.append((r, c)))
    case.mouseDoubleClickEvent(QMouseEvent(
        QMouseEvent.MouseButtonDblClick, QPointF(1, 1), QPointF(1, 1),
        Qt.LeftButton, Qt.LeftButton, Qt.NoModifier))

    assert vus == [(2, 1)]


def test_double_clicking_an_empty_cell_does_nothing(qt_app):
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtGui import QMouseEvent

    from pokemon_mosaic.ui.link_grid import CardCell

    case = CardCell(0, 0)
    vus = []
    case.cleared.connect(lambda r, c: vus.append((r, c)))
    case.mouseDoubleClickEvent(QMouseEvent(
        QMouseEvent.MouseButtonDblClick, QPointF(1, 1), QPointF(1, 1),
        Qt.LeftButton, Qt.LeftButton, Qt.NoModifier))

    assert vus == []


def test_clicking_a_removal_button_does_not_crash(grille):
    """Le bouton « − » déclenche la reconstruction qui le détruit : c'est le cas
    classique du widget supprimé depuis son propre gestionnaire de signal.
    `deleteLater` diffère la destruction à la boucle d'événements, ce qui le rend
    sûr — mais rien ne le prouve tant qu'on appelle `remove_row` directement.
    """
    from PySide6.QtWidgets import QApplication, QPushButton

    grille.add_col()
    grille.add_row()
    for position in range(4):
        grille.place(position // 2, position % 2, position)

    moins = [b for b in grille.findChildren(QPushButton) if b.text() == "－"]
    assert len(moins) == 4
    moins[0].click()
    QApplication.processEvents()        # laisse les deleteLater s'exécuter

    assert grille.shape in ((2, 1), (1, 2))


def test_clicking_an_add_button_grows_the_grid(grille):
    from PySide6.QtWidgets import QApplication, QPushButton

    plus = [b for b in grille.findChildren(QPushButton) if b.text() == "＋"]
    plus[0].click()                      # celui du haut : ajouter une ligne
    QApplication.processEvents()

    assert grille.shape == (1, 2)


def test_a_fresh_cell_looks_like_a_cleared_one(qt_app):
    """Une case doit porter son texte d'attente dès sa construction. Sans cela
    elle reste blanche jusqu'au premier `set_card`, et une case vidée paraît
    différente d'une case qui n'a jamais rien reçu."""
    from pokemon_mosaic.ui import theme
    from pokemon_mosaic.ui.link_grid import CardCell

    theme.apply(qt_app)
    neuve = CardCell(0, 0)
    videe = CardCell(0, 0)
    videe.set_card(1, np.zeros((4, 3, 3), np.uint8))
    videe.set_card(None, None)
    for case in (neuve, videe):
        case.show()
    qt_app.processEvents()

    assert neuve.grab().toImage() == videe.grab().toImage()


def test_the_palette_is_a_grid_that_only_hands_cards_out(qt_app):
    """Une grille, et non une liste : quatre cent quarante et une cartes une par
    ligne obligent à faire défiler sans fin. `DragOnly` et `Static` parce qu'on
    tire **vers** l'éditeur — la palette n'a pas d'ordre propre à réarranger."""
    from PySide6.QtWidgets import QListWidget

    from pokemon_mosaic.ui.link_grid import CardPalette

    palette = CardPalette()
    assert palette.viewMode() == QListWidget.IconMode
    assert palette.dragDropMode() == QListWidget.DragOnly
    assert palette.movement() == QListWidget.Static
    assert palette.isWrapping()


def test_a_card_keeps_its_size_from_the_palette_to_the_grid(qt_app):
    """Une carte glissée doit avoir dans le rectangle exactement l'aspect
    qu'elle avait dans la palette : la voir rapetisser en la déposant fait
    douter d'avoir pris la bonne."""
    from pokemon_mosaic.ui.link_grid import CELL_HEIGHT, CELL_WIDTH, CardCell, CardPalette

    case = CardCell(0, 0)
    palette = CardPalette()

    assert case.size().toTuple() == (CELL_WIDTH, CELL_HEIGHT)
    assert palette.iconSize().toTuple() == (CELL_WIDTH, CELL_HEIGHT)


# --- Le seuil de glissement ------------------------------------------------

def gestes(case, depart, arrivee, qt_app):
    """Presse, bouge, et dit si un glissement a démarré.

    `QDrag.exec` ouvre une boucle imbriquée : on l'observe sans le jouer.
    """
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    from pokemon_mosaic.ui import link_grid

    lances = []

    class FauxDrag:
        def __init__(self, source):
            pass

        def setMimeData(self, data):
            pass

        def setPixmap(self, pixmap):
            pass

        def exec(self, action):
            lances.append(action)

    vrai = link_grid.QDrag
    link_grid.QDrag = FauxDrag
    try:
        QTest.mousePress(case, Qt.LeftButton, Qt.NoModifier, depart)
        QTest.mouseMove(case, arrivee)
        qt_app.processEvents()
    finally:
        link_grid.QDrag = vrai
    return bool(lances)


def test_a_trembling_hand_does_not_start_a_drag(qt_app):
    """`drag.exec` ouvre une boucle imbriquée qui avale la suite du geste : le
    double-clic n'arrivait jamais, et la case ne se vidait pas. Comme c'est le
    seul moyen de la vider, le geste échouait une fois sur deux."""
    from PySide6.QtCore import QPoint
    from PySide6.QtWidgets import QApplication

    from pokemon_mosaic.ui.link_grid import CardCell

    case = CardCell(0, 0)
    case.set_card(3, np.zeros((4, 3, 3), np.uint8))
    case.show()

    seuil = QApplication.startDragDistance()
    assert seuil >= 4, "seuil trop bas pour que le test ait un sens"
    assert not gestes(case, QPoint(39, 54), QPoint(41, 55), qt_app)


def test_a_real_drag_still_starts(qt_app):
    """Le seuil ne doit pas empêcher le geste volontaire."""
    from PySide6.QtCore import QPoint
    from PySide6.QtWidgets import QApplication

    from pokemon_mosaic.ui.link_grid import CardCell

    case = CardCell(0, 0)
    case.set_card(3, np.zeros((4, 3, 3), np.uint8))
    case.show()

    loin = QApplication.startDragDistance() + 20
    assert gestes(case, QPoint(10, 10), QPoint(10 + loin, 10 + loin), qt_app)


def test_an_empty_cell_never_starts_a_drag(qt_app):
    from PySide6.QtCore import QPoint

    from pokemon_mosaic.ui.link_grid import CardCell

    case = CardCell(0, 0)
    case.show()
    assert not gestes(case, QPoint(10, 10), QPoint(90, 90), qt_app)


def test_a_filled_cell_captures_the_mouse(qt_app):
    """`QWidget::mousePressEvent` ignore l'événement par défaut : la case ne
    capturerait pas la souris et les mouvements suivants iraient au parent, si
    bien que le glissement d'une case à l'autre ne partirait jamais d'une vraie
    souris. `QTest.mouseMove` ne le montre pas — il livre l'événement au widget
    visé, en court-circuitant la capture."""
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtGui import QMouseEvent

    from pokemon_mosaic.ui.link_grid import CardCell

    case = CardCell(0, 0)
    case.set_card(1, np.zeros((4, 3, 3), np.uint8))
    presse = QMouseEvent(QMouseEvent.MouseButtonPress, QPointF(10, 10),
                         QPointF(10, 10), Qt.LeftButton, Qt.LeftButton,
                         Qt.NoModifier)
    case.mousePressEvent(presse)
    assert presse.isAccepted()


def test_an_empty_cell_lets_the_click_through(qt_app):
    """Rien à faire glisser : la case n'a aucune raison de retenir la souris."""
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtGui import QMouseEvent

    from pokemon_mosaic.ui.link_grid import CardCell

    case = CardCell(0, 0)
    presse = QMouseEvent(QMouseEvent.MouseButtonPress, QPointF(10, 10),
                         QPointF(10, 10), Qt.LeftButton, Qt.LeftButton,
                         Qt.NoModifier)
    case.mousePressEvent(presse)
    assert not presse.isAccepted()
