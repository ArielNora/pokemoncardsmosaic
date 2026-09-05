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


def test_the_three_tabs_are_there_and_never_lock(ecran):
    widget, _, _ = ecran
    titres = [widget._list.item(i).text() for i in range(widget._list.count())]
    assert titres == ["Présentation", "Couleurs des vides", "Résolution"]
    from PySide6.QtCore import Qt

    for rang in range(widget._list.count()):
        drapeaux = widget._list.item(rang).flags()
        assert drapeaux & Qt.ItemIsEnabled, f"onglet {rang} inaccessible"


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
    resolution = widget._tabs[2]
    avant = widget._preview.minimumHeight()

    resolution._zoom_in.click()

    assert resolution.zoom() > 1.0
    assert widget._preview.minimumHeight() > avant
    assert widget._scroll.widget() is widget._preview


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
