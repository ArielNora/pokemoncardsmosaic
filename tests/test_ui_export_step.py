"""Tests de l'étape d'export : ce qui reste réglable, et ce qui ne l'est plus."""

import numpy as np
import pytest

from pokemon_mosaic.cards import Card, CardSet


def card_set(n, size=(12, 16)):
    width, height = size
    cards = []
    for i in range(n):
        thumb = np.full((height, width, 3), 90, np.uint8)
        card = Card(path=f"/fake/{i}.png", index=i, thumbnail=thumb)
        card.top = card.bottom = card.left = card.right = np.zeros(3)
        cards.append(card)
    return CardSet(cards=cards, full_size=(713, 984), thumb_size=size)


@pytest.fixture
def ecran(qt_app):
    from pokemon_mosaic.ui.export_step import ExportStep
    from pokemon_mosaic.ui.session import Session

    session = Session()
    jeu = card_set(20)
    session.set_cards(jeu, "/fake")
    session.set_layout(cols=5, rows=4)
    grille = np.arange(20).reshape(4, 5)
    session.save_grid(grille, jeu, iteration=100, score=12.5)
    widget = ExportStep(session)
    widget.resize(900, 620)
    return widget, session, jeu


def test_the_step_opens_on_the_first_kept_arrangement(ecran):
    """⚠️ **Toujours une case ouverte.** La colonne n'est pas un menu qu'on
    doit penser à ouvrir, et un écran d'habillage sans agencement n'aurait
    rien à montrer."""
    widget, session, _ = ecran
    widget.enter()

    assert widget.current_saved() is session.saved[0]
    assert widget._saved.current() == 0


def test_only_the_selected_slot_is_outlined(ecran):
    """Le cadre vert dit l'agencement affiché, et lui seul."""
    widget, session, jeu = ecran
    session.save_grid(np.arange(20).reshape(4, 5)[:, ::-1].copy(), jeu,
                      iteration=200, score=9.0)
    widget.enter()

    assert widget._saved.current() == 0
    assert widget._saved._slots[0].property("role") == "slot-current"
    assert widget._saved._slots[1].property("role") == "slot"

    widget.show_slot(1)

    assert widget._saved._slots[0].property("role") == "slot"
    assert widget._saved._slots[1].property("role") == "slot-current"
    assert widget.current_saved() is session.saved[1]


def test_the_three_sections_are_there_and_only_one_unfolds(ecran):
    """⚠️ Deux sections dépliées font défiler la colonne, et l'œil ne sait plus
    où regarder."""
    widget, _, _ = ecran
    assert [section.key() for section in widget._sections] == [
        "Présentation", "Couleurs des vides", "Résolution"]
    assert [section.is_open() for section in widget._sections] == [True, False, False]

    widget._toggle_section("Résolution")
    assert [section.is_open() for section in widget._sections] == [False, False, True]

    # Recliquer la même la referme : rien ne reste ouvert par force.
    widget._toggle_section("Résolution")
    assert not any(section.is_open() for section in widget._sections)


def test_a_folded_section_hides_its_settings(ecran):
    widget, _, _ = ecran
    widget.show()
    presentation = widget._sections[0]

    assert presentation.content().isVisibleTo(widget)
    widget._toggle_section("Présentation")
    assert not presentation.content().isVisibleTo(widget)


def test_the_settings_panel_never_widens(ecran):
    """L'image est la seule chose de cet écran qu'on regarde longtemps : un
    champ un peu large la repoussait."""
    from pokemon_mosaic.ui.layout_step import TAB_WIDTH

    widget, _, _ = ecran
    widget.show()
    for section in widget._sections:
        widget._toggle_section(section.key())
        assert section.parentWidget().width() == TAB_WIDTH


def test_the_step_opens_on_its_heading(ecran):
    widget, _, _ = ecran
    assert widget._heading.text() == "Derniers ajustements avant l'export"
    assert widget._heading.font().bold()


def test_the_grid_shape_is_not_offered_anywhere(ecran):
    """⚠️ La changer déferait l'agencement trouvé : les cartes ne seraient plus
    à leur place, et le score n'aurait plus de sens."""
    from pokemon_mosaic.ui.export_step import PresentationTab

    widget, _, _ = ecran
    presentation = widget._tabs[0]
    assert isinstance(presentation, PresentationTab)
    reglages = [nom for nom in vars(presentation) if not nom.startswith("__")]
    assert not any(nom in reglages for nom in ("_cols", "_rows")), (
        "la forme de la grille ne se règle plus ici"
    )


def test_the_gap_and_the_card_width_stay_open(ecran):
    widget, session, _ = ecran
    presentation = widget._tabs[0]

    presentation._gap.setValue(4.0)
    assert session.card_gap_mm == pytest.approx(4.0)
    presentation._width.setValue(30.0)
    assert session.card_width_mm == pytest.approx(30.0)
    presentation._auto_width.click()
    assert session.card_width_mm is None


def test_the_real_size_button_poses_a_real_card(ecran):
    """La mosaïque en taille de collection : une carte fait ses 63 mm."""
    from pokemon_mosaic.layout import REAL_CARD_MM

    widget, session, _ = ecran

    widget._tabs[0]._real_width.click()

    assert session.card_width_mm == pytest.approx(REAL_CARD_MM[0])


def test_the_fields_stay_small_and_each_subject_has_its_block(ecran):
    """⚠️ Les grands compteurs de l'étape 2 prenaient cent cinquante pixels de
    haut chacun : ici on ne pose pas la mise en page, on la retouche. ⚠️ Et tout
    à la file, on cliquait « Au plus grand » en croyant agir sur l'écart au-dessus
    duquel il se trouvait : un trait sépare désormais les sujets."""
    from PySide6.QtWidgets import QFrame

    from pokemon_mosaic.ui.export_step import FIELD_WIDTH

    widget, _, _ = ecran
    widget.show()
    presentation = widget._tabs[0]

    assert presentation._width.width() == FIELD_WIDTH
    assert presentation._gap.width() == FIELD_WIDTH
    assert presentation._width_label.text() == "Largeur de la carte (mm)"
    assert presentation._gap_label.text() == "Écart entre les cartes (mm)"

    traits = [enfant for enfant in presentation.findChildren(QFrame)
              if enfant.frameShape() == QFrame.HLine]
    assert len(traits) == 2, "un trait après la largeur, un après l'écart"

    # L'ordre de haut en bas : largeur, ses boutons, trait, écart, trait, centrer.
    def hauteur(widget_):
        return widget_.mapTo(presentation, widget_.rect().topLeft()).y()

    assert (hauteur(presentation._width_label) < hauteur(presentation._width)
            < hauteur(presentation._real_width) < hauteur(traits[0])
            < hauteur(presentation._gap_label) < hauteur(presentation._gap)
            < hauteur(traits[1]) < hauteur(presentation._centre))


def test_the_automatic_width_is_shown_in_millimetres(ecran):
    """⚠️ **La géométrie compte en pixels.** Posée telle quelle dans un champ en
    millimètres, la largeur automatique s'affichait écrêtée au maximum."""
    from pokemon_mosaic.layout import MM_PER_INCH

    widget, session, _ = ecran
    session.set_layout(card_width_mm=None)
    attendu = session.panel_geometry().card_w * MM_PER_INCH / session.dpi

    assert widget._tabs[0]._width.value() == pytest.approx(attendu, abs=0.1)
    assert widget._tabs[0]._width.value() < session.paper_mm()[0]


def test_the_three_colours_reach_the_session(ecran):
    widget, session, _ = ecran
    couleurs = widget._tabs[1]

    session.set_algorithm(background_colour=(1, 2, 3), gap_colour=(4, 5, 6),
                          empty_colour=(7, 8, 9))
    couleurs.refresh()

    for role, valeur in (("background_colour", (1, 2, 3)),
                         ("gap_colour", (4, 5, 6)),
                         ("empty_colour", (7, 8, 9))):
        assert getattr(session, role) == valeur
        assert f"rgb({valeur[0]}, {valeur[1]}, {valeur[2]})" in (
            couleurs._buttons[role].styleSheet())


def test_the_resolution_tab_writes_the_dpi_and_counts_the_pixels(ecran):
    widget, session, _ = ecran
    resolution = widget._tabs[2]

    resolution._dpi.setValue(150)

    assert session.dpi == 150
    largeur = round(session.paper_mm()[0] / 25.4 * 150)
    assert str(largeur) in resolution._pixels.text()


def test_the_zoom_enlarges_the_preview_inside_its_scroll_area(ecran):
    """L'aperçu se dessine à la taille qu'on lui donne : sans zone défilante,
    l'agrandir le rognerait et le bas de la feuille deviendrait inatteignable."""
    widget, _, _ = ecran
    widget.show()
    avant = widget._preview.minimumHeight()

    widget._zoom_in.click()

    assert widget._zoom > 1.0
    assert widget._preview.minimumHeight() > avant
    assert widget._scroll.widget() is widget._preview

    widget._zoom_fit.click()
    assert widget._zoom == 1.0
    assert widget._preview.minimumHeight() == 0, "ajusté, l'aperçu suit le cadre"


def test_the_wheel_zooms_around_the_cursor(ecran):
    """⚠️ Sans viser un point, chaque cran renvoyait au coin haut-gauche, et il
    fallait retrouver à la main l'endroit qu'on regardait."""
    from PySide6.QtCore import QPointF

    widget, _, _ = ecran
    widget.resize(1100, 700)
    widget.show()
    cadre = widget._scroll.viewport().size()
    coin = QPointF(cadre.width() - 10, cadre.height() - 10)

    widget._zoom_at(2.0, coin)

    assert widget._zoom == 2.0
    barres = (widget._scroll.horizontalScrollBar(),
              widget._scroll.verticalScrollBar())
    assert barres[0].value() > 0 and barres[1].value() > 0, (
        "le coin visé doit rester sous le curseur, pas revenir en haut à gauche")


def test_dragging_the_preview_scrolls_it(ecran):
    """⚠️ **Les gestes se prennent sur l'aperçu, pas sur le cadre.** C'est lui
    que la souris survole : posés sur le cadre, le clic et la molette ne lui
    arrivaient jamais, et rien ne bougeait."""
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest

    widget, _, _ = ecran
    widget.resize(900, 600)
    widget.show()
    widget._zoom_at(3.0, None)
    barre = widget._scroll.horizontalScrollBar()
    barre.setValue(barre.maximum() // 2)
    depart = barre.value()

    # Sur l'aperçu lui-même, là où la main de l'utilisateur se pose.
    QTest.mousePress(widget._preview, Qt.LeftButton, pos=QPoint(200, 150))
    QTest.mouseMove(widget._preview, QPoint(120, 150))
    QTest.mouseRelease(widget._preview, Qt.LeftButton, pos=QPoint(120, 150))

    assert barre.value() > depart, "le glissement n'a pas fait défiler"
    assert not widget._preview._draggable, "déplacer une feuille reste à l'étape 2"


def test_the_preview_wears_the_move_cursor(ecran):
    """La croix directionnelle dit que ça se déplace, comme une fenêtre qu'on
    tire."""
    from PySide6.QtCore import Qt

    widget, _, _ = ecran
    assert widget._preview.cursor().shape() == Qt.SizeAllCursor


def test_the_wheel_over_the_preview_zooms(ecran):
    """Elle aussi arrivait au cadre et jamais à l'image."""
    from PySide6.QtCore import QPoint, QPointF, Qt
    from PySide6.QtGui import QWheelEvent
    from PySide6.QtWidgets import QApplication

    widget, _, _ = ecran
    widget.resize(900, 600)
    widget.show()
    avant = widget._zoom

    place = QPointF(120, 90)
    roue = QWheelEvent(place, widget._preview.mapToGlobal(QPoint(120, 90)),
                       QPoint(0, 0), QPoint(0, 120), Qt.NoButton,
                       Qt.NoModifier, Qt.NoScrollPhase, False)
    # ⚠️ `sendEvent` et non `event()` : appeler la méthode saute les filtres,
    # c'est-à-dire précisément ce qu'on teste.
    QApplication.sendEvent(widget._preview, roue)

    assert widget._zoom > avant


def test_the_preview_paints_the_real_arrangement(ecran):
    """Le fil de fer ne dit rien d'une couleur de fond : la feuille montre le
    poster tel qu'il s'imprimera."""
    widget, session, _jeu = ecran
    session.set_algorithm(background_colour=(250, 0, 0))
    widget.enter()
    widget.show()

    image = widget._preview.grab().toImage()
    rects = widget._preview.rects()
    assert rects is not None
    feuille = rects[0]
    ratio = image.devicePixelRatio() or 1
    coin = image.pixelColor(int((feuille.left() + 3) * ratio),
                            int((feuille.top() + 3) * ratio))

    assert coin.getRgb()[:3] == (250, 0, 0), "le fond de la feuille n'est pas peint"


def test_the_empty_cells_take_their_own_colour(ecran):
    widget, session, jeu = ecran
    session.toggle_empty_cell(0, 0)
    session.set_algorithm(empty_colour=(0, 250, 0))
    grille = np.arange(20).reshape(4, 5)
    grille[0, 0] = -1
    session.remove_saved(0)
    session.save_grid(grille, jeu, iteration=1, score=1.0)
    widget.enter()
    widget.show()

    image = widget._preview.grab().toImage()
    cases = widget._preview.grid_cells(widget._preview.rects()[0])
    rect = next(r for row, col, r in cases if (row, col) == (0, 0))
    ratio = image.devicePixelRatio() or 1
    point = image.pixelColor(int(rect.center().x() * ratio),
                             int(rect.center().y() * ratio))

    assert point.getRgb()[:3] == (0, 250, 0)


def test_the_gap_colour_shows_between_two_cards(ecran):
    """Elle ne se voit que là où aucune carte ne la recouvre, c'est-à-dire
    exactement dans les écarts."""
    widget, session, _ = ecran
    session.set_layout(card_gap_mm=10.0)
    session.set_algorithm(gap_colour=(0, 0, 250))
    widget.enter()
    widget.show()

    image = widget._preview.grab().toImage()
    cases = widget._preview.grid_cells(widget._preview.rects()[0])
    premier = next(r for row, col, r in cases if (row, col) == (0, 0))
    second = next(r for row, col, r in cases if (row, col) == (0, 1))
    ratio = image.devicePixelRatio() or 1
    milieu = (premier.right() + second.left()) / 2
    point = image.pixelColor(int(milieu * ratio),
                             int(premier.center().y() * ratio))

    assert point.getRgb()[:3] == (0, 0, 250)


def test_a_removed_arrangement_hands_the_screen_to_another(ecran):
    widget, session, jeu = ecran
    session.save_grid(np.arange(20).reshape(4, 5), jeu, iteration=2, score=9.0)
    widget.enter()

    session.remove_saved(0)

    assert widget.current_saved() is session.saved[1]
    assert widget._saved.current() == 1


def test_without_any_arrangement_the_export_button_is_dead(qt_app):
    from pokemon_mosaic.ui.export_step import ExportStep
    from pokemon_mosaic.ui.session import Session

    session = Session()
    session.set_cards(card_set(20), "/fake")
    widget = ExportStep(session)
    widget.enter()

    assert widget.current_saved() is None
    assert not widget._export.isEnabled()


# --- Arrêt du fil d'export --------------------------------------------------

class _FilFactice:
    """Un QThread simulé, qui s'arrête ou s'obstine selon `tenace`."""

    def __init__(self, tenace=False):
        self.tenace = tenace
        self.journal = []
        self._actif = True

    def isRunning(self):
        return self._actif

    def quit(self):
        self.journal.append("quit")

    def wait(self, ms):
        self.journal.append("wait")
        if self.tenace:
            return False
        self._actif = False
        return True


class _ExportFactice:
    def __init__(self):
        self.annule = False

    def cancel(self):
        self.annule = True


def test_shutdown_cancels_then_waits_for_the_export(ecran):
    widget, _, _ = ecran
    fil, ouvrier = _FilFactice(), _ExportFactice()
    widget._export_thread, widget._export_worker = fil, ouvrier

    assert widget.shutdown() is True
    assert ouvrier.annule, "l'export doit d'abord être prié de s'arrêter"
    assert fil.journal == ["quit", "wait"], fil.journal
    assert widget._export_thread is None and widget._export_worker is None


def test_a_stubborn_export_keeps_its_reference(ecran):
    """⚠️ Une référence n'est lâchée que si son fil est réellement terminé :
    la lâcher sur un fil actif laisse la fenêtre se fermer dessus, et Qt
    abandonne le processus."""
    widget, _, _ = ecran
    messages = []
    widget.status_message.connect(messages.append)
    fil = _FilFactice(tenace=True)
    widget._export_thread, widget._export_worker = fil, _ExportFactice()

    assert widget.shutdown() is False
    assert widget._export_thread is fil
    assert messages and "export" in messages[0]


def test_shutdown_is_content_when_nothing_is_running(ecran):
    widget, _, _ = ecran
    assert widget.shutdown() is True


# --- Le caméléon et la pipette ----------------------------------------------

def test_the_chameleon_switches_reach_the_session(ecran):
    widget, session, _ = ecran
    couleurs = widget._tabs[1]

    couleurs._chameleon_gaps.setChecked(True)
    assert session.chameleon_gaps
    couleurs._chameleon_border.setChecked(True)
    assert session.chameleon_border

    couleurs._chameleon_gaps.setChecked(False)
    assert not session.chameleon_gaps


def test_the_gap_colour_greys_out_under_the_chameleon(ecran):
    """⚠️ **Grisée, pas retirée.** L'effacer ferait oublier ce qu'on retrouvera
    en éteignant le mode."""
    widget, session, _ = ecran
    couleurs = widget._tabs[1]
    assert couleurs._buttons["gap_colour"].isEnabled()

    session.set_algorithm(chameleon_gaps=True)

    assert not couleurs._buttons["gap_colour"].isEnabled()
    assert not couleurs._droppers["gap_colour"].isEnabled()
    assert couleurs._buttons["background_colour"].isEnabled(), (
        "les autres couleurs restent réglables"
    )

    session.set_algorithm(chameleon_gaps=False)
    assert couleurs._buttons["gap_colour"].isEnabled()


def test_the_eyedropper_takes_the_colour_under_the_click(ecran):
    """On prélève dans le dessin, pas dans un modèle : `grab()` donne
    exactement ce que l'œil voit."""
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest

    widget, session, _ = ecran
    session.set_algorithm(background_colour=(10, 200, 30))
    widget.resize(900, 600)
    widget.show()
    widget.enter()

    widget._tabs[1]._droppers["empty_colour"].click()
    assert widget._picking_role == "empty_colour"
    assert widget._preview.cursor().shape() == Qt.CrossCursor

    # Un coin de l'aperçu : le fond de la feuille, qu'on vient de teinter.
    rects = widget._preview.rects()
    feuille = rects[0]
    point = QPoint(int(feuille.left() + 8), int(feuille.top() + 8))
    QTest.mousePress(widget._preview, Qt.LeftButton, pos=point)

    # ⚠️ À une unité près : le dessin est lissé, et la capture d'un widget peut
    # passer par une mise à l'échelle. C'est la couleur du fond, pas une autre.
    assert all(abs(pris - voulu) <= 2 for pris, voulu
               in zip(session.empty_colour, (10, 200, 30), strict=True)), (
        session.empty_colour)
    assert widget._picking_role == "", "la pipette se referme après un clic"
    assert widget._preview.cursor().shape() == Qt.SizeAllCursor


def test_the_preview_draws_the_chameleon_gaps(ecran):
    """⚠️ L'aperçu passe par la même arithmétique que l'export : un dégradé
    moyenné à l'écran aurait montré autre chose que ce qui s'imprime."""
    widget, session, jeu = ecran
    # Deux aplats francs, un écart large : le dégradé doit se voir.
    for numero, card in enumerate(jeu.cards):
        card.thumbnail[:] = (255, 0, 0) if numero % 2 == 0 else (0, 0, 255)
    session.set_layout(card_gap_mm=8.0)
    session.set_algorithm(gap_colour=(0, 255, 0), chameleon_gaps=True)
    widget.enter()
    widget.show()

    image = widget._preview.grab().toImage()
    cases = widget._preview.grid_cells(widget._preview.rects()[0])
    premier = next(r for row, col, r in cases if (row, col) == (0, 0))
    second = next(r for row, col, r in cases if (row, col) == (0, 1))
    ratio = image.devicePixelRatio() or 1
    y = int(premier.center().y() * ratio)
    couleurs = [image.pixelColor(int(x * ratio), y).getRgb()[:3]
                for x in range(int(premier.right()) + 2, int(second.left()) - 1)]

    assert couleurs, "l'écart est trop étroit pour être mesuré"
    assert all(couleur != (0, 255, 0) for couleur in couleurs), (
        "l'aplat de la couleur d'écart ne doit plus se voir"
    )
    assert couleurs[0][0] > couleurs[-1][0], "le rouge s'efface vers le bleu"
    assert couleurs[0][2] < couleurs[-1][2]


# --- Le zoom au champ, à la molette et au pavé tactile ----------------------

def test_the_zoom_can_be_typed(ecran):
    """⚠️ Atteindre 400 % au bouton demandait sept clics."""
    widget, _, _ = ecran
    widget.resize(900, 600)
    widget.show()

    widget._zoom_field.setValue(400)

    assert widget._zoom == pytest.approx(4.0)
    assert widget._preview.minimumHeight() > 0


def test_the_field_follows_the_buttons_without_looping(ecran):
    """Le champ émet à chaque écriture : sans garde, il rezoomerait sur
    lui-même."""
    widget, _, _ = ecran
    widget.resize(900, 600)
    widget.show()

    widget._zoom_in.click()

    assert widget._zoom_field.value() == round(widget._zoom * 100)
    assert widget._zoom == pytest.approx(1.25)


def test_two_fingers_sliding_scroll_instead_of_zooming(ecran):
    """⚠️ Un pavé tactile envoie aussi des événements de molette : traités comme
    tels, le glissement à deux doigts zoomait au lieu de promener l'image."""
    from PySide6.QtCore import QPoint, QPointF, Qt
    from PySide6.QtGui import QWheelEvent
    from PySide6.QtWidgets import QApplication

    widget, _, _ = ecran
    widget.resize(900, 600)
    widget.show()
    widget._zoom_at(3.0, None)
    avant = widget._zoom

    place = QPointF(120, 90)
    # Un delta **en pixels**, ce qu'une molette crantée ne donne jamais.
    glissement = QWheelEvent(place, widget._preview.mapToGlobal(QPoint(120, 90)),
                             QPoint(0, -40), QPoint(0, -120), Qt.NoButton,
                             Qt.NoModifier, Qt.ScrollUpdate, False)
    QApplication.sendEvent(widget._preview, glissement)

    assert widget._zoom == avant, "le glissement à deux doigts ne zoome pas"


def test_a_pinch_zooms(ecran):
    """Qt remonte le pincement comme un geste natif, jamais comme une molette :
    sans ce cas, écarter les doigts ne faisait rien."""
    from PySide6.QtCore import QPoint, QPointF, Qt
    from PySide6.QtGui import QNativeGestureEvent, QPointingDevice
    from PySide6.QtWidgets import QApplication

    widget, _, _ = ecran
    widget.resize(900, 600)
    widget.show()
    avant = widget._zoom

    geste = QNativeGestureEvent(
        Qt.ZoomNativeGesture, QPointingDevice.primaryPointingDevice(),
        2, QPointF(120, 90), QPointF(120, 90),
        QPointF(widget._preview.mapToGlobal(QPoint(120, 90))), 0.25, QPoint(),
        0)
    QApplication.sendEvent(widget._preview, geste)

    assert widget._zoom > avant


def test_no_hairline_inside_the_mosaic_without_a_gap(ecran):
    """⚠️ `toRect()` arrondit la position et la taille séparément : sans écart,
    des lignes du fond apparaissaient entre les cartes, et changeaient de place
    à chaque cran de zoom. Mesuré : 73 des 74 hauteurs essayées en montraient.
    """
    import numpy as np
    from PySide6.QtGui import QImage

    widget, session, jeu = ecran
    for numero, card in enumerate(jeu.cards):
        card.thumbnail[:] = (255, 0, 0) if numero % 2 == 0 else (0, 0, 255)
    session.set_layout(card_gap_mm=0.0)
    session.set_algorithm(background_colour=(255, 255, 255))
    widget.enter()
    widget.show()

    for hauteur in (483, 517, 561, 604):
        widget.resize(900, hauteur)
        widget._preview.refresh()
        image = widget._preview.grab().toImage().convertToFormat(
            QImage.Format_RGB888)
        ratio = image.devicePixelRatio() or 1
        # ⚠️ Chaque ligne est complétée à un multiple de quatre octets : passer
        # par `bytesPerLine` puis rogner, sinon le tableau ne se reforme pas.
        brut = np.frombuffer(image.constBits(), np.uint8).reshape(
            image.height(), image.bytesPerLine())
        pixels = brut[:, :image.width() * 3].reshape(
            image.height(), image.width(), 3)

        cases = widget._preview.grid_cells(widget._preview.rects()[0])
        boite = cases[0][2]
        for _row, _col, rect in cases:
            boite = boite.united(rect)
        dedans = pixels[int(boite.top() * ratio) + 2:int(boite.bottom() * ratio) - 2,
                        int(boite.left() * ratio) + 2:int(boite.right() * ratio) - 2]

        blancs = int((dedans == 255).all(axis=2).sum())
        assert blancs == 0, f"{blancs} pixels de fond dans la mosaïque à {hauteur}"
