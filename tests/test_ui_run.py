"""Tests de la vue d'exécution et de son travailleur."""

import numpy as np
import pytest

from pokemon_mosaic.cards import Card, CardSet
from pokemon_mosaic.control import RunControl
from pokemon_mosaic.links import Link


def card_set(n, size=(12, 16)):
    rng = np.random.default_rng(0)
    width, height = size
    ramp = np.linspace(0.0, 1.0, height)[:, None]
    cards = []
    for i in range(n):
        top, bottom = (rng.integers(0, 255, 3).astype(float) for _ in range(2))
        column = top * (1 - ramp) + bottom * ramp
        thumb = np.repeat(column[:, None, :], width, axis=1).astype(np.uint8)
        card = Card(path=f"/fake/{i}.png", index=i, thumbnail=thumb)
        card.calculate_features(0.1)
        cards.append(card)
    return CardSet(cards=cards, full_size=(713, 984), thumb_size=size)


@pytest.fixture
def session(qt_app):
    from pokemon_mosaic.ui.session import Session

    s = Session()
    s.set_cards(card_set(20), "/fake")
    s.set_layout(cols=5, rows=4)
    s.set_algorithm(iterations=4000, snapshot_every=2, use_annealing=False)
    return s


def run_synchronously(session, previous_grid=None):
    """Exécute le travailleur dans le fil courant : déterministe et sans QThread."""
    from pokemon_mosaic.ui.runner import RunWorker

    control = RunControl()
    worker = RunWorker(session, control, previous_grid)
    seen = {"started": [], "snapshots": [], "result": [], "failed": []}
    worker.started_run.connect(lambda c, t: seen["started"].append((c, t)))
    worker.snapshot.connect(seen["snapshots"].append)
    worker.finished_run.connect(seen["result"].append)
    worker.failed.connect(seen["failed"].append)
    worker.run()
    return seen


# --- Le travailleur --------------------------------------------------------

def test_a_run_produces_snapshots_and_a_result(session):
    seen = run_synchronously(session)
    assert seen["failed"] == []
    assert len(seen["snapshots"]) > 1
    assert seen["result"][0].attempted == 4000


def test_the_run_only_uses_the_selected_cards(session):
    session.set_excluded([0, 1, 2, 3, 4], True)
    session.set_layout(cols=5, rows=3)
    seen = run_synchronously(session)
    cards, _ = seen["started"][0]
    assert len(cards) == 15
    assert [card.index for card in cards] == list(range(15))


def test_links_are_translated_for_the_selection(session):
    """Le travailleur doit passer par select_cards : subset seul laisserait les
    liens désigner d'autres cartes après renumérotation."""
    session.add_link(Link(cards=(10, 11)))
    session.set_excluded([0, 1], True)
    session.set_layout(cols=6, rows=3)
    seen = run_synchronously(session)

    cards, timeline = seen["started"][0]
    positions = {}
    final = timeline[-1].grid
    for row in range(final.shape[0]):
        for col in range(final.shape[1]):
            positions[int(final[row, col])] = (row, col)
    # Les cartes d'origine 10 et 11 sont devenues 8 et 9 après renumérotation.
    linked = [index for index, card in enumerate(cards)
              if card.source_index in (10, 11)]
    (r_a, c_a), (r_b, c_b) = (positions[i] for i in linked)
    assert r_a == r_b and abs(c_b - c_a) == 1


def test_a_run_without_cards_fails_cleanly(qt_app):
    from pokemon_mosaic.ui.session import Session

    seen = run_synchronously(Session())
    assert seen["failed"] and "Aucune carte" in seen["failed"][0]
    assert seen["result"] == []


def test_a_run_can_start_from_a_given_grid(session):
    """C'est ce qui permet de prolonger un calcul ou de repartir d'un cliché."""
    first = run_synchronously(session)
    final = first["started"][0][1][-1].grid.astype(int)

    second = run_synchronously(session, previous_grid=final)
    start = second["started"][0][1][0].grid.astype(int)
    np.testing.assert_array_equal(start, final)


def test_empty_cells_stay_put_across_the_run(session):
    from pokemon_mosaic.scoring import EMPTY

    session.set_layout(cols=6, rows=4)      # 24 cases pour 20 cartes
    seen = run_synchronously(session)
    timeline = seen["started"][0][1]
    first = {tuple(cell) for cell in np.argwhere(timeline[0].grid == EMPTY)}
    last = {tuple(cell) for cell in np.argwhere(timeline[-1].grid == EMPTY)}
    assert first == last and len(first) == 4


# --- L'écran ---------------------------------------------------------------

@pytest.fixture
def step(qt_app, session):
    from pokemon_mosaic.ui.run_step import RunStep

    widget = RunStep(session)
    widget.resize(700, 500)
    return widget, session


def feed(step_widget, session):
    """Rejoue une exécution complète dans l'écran, sans fil de fond."""
    seen = run_synchronously(session)
    cards, timeline = seen["started"][0]
    step_widget._on_started(cards, timeline)
    for snapshot in timeline:
        step_widget._on_snapshot(snapshot)
    return timeline


# --- Agencements mis de côté ------------------------------------------------

def test_keeping_is_impossible_before_the_first_snapshot(step):
    widget, session = step
    assert not widget._keep.isEnabled()
    assert not widget.can_advance(), "l'export n'aurait rien à habiller"

    feed(widget, session)

    assert widget._keep.isEnabled()


def test_keeping_stores_the_grid_its_cards_and_its_iteration(step):
    """⚠️ **Le jeu de cartes fait partie de l'agencement.** La grille indexe le
    sous-ensemble retenu au calcul : sans lui, les mêmes nombres désigneraient
    d'autres cartes dès que la sélection change."""
    widget, session = step
    timeline = feed(widget, session)
    widget._slider.setValue(1)

    widget._keep_current()

    garde = session.saved[0]
    assert garde is not None
    assert garde.cards is widget._cards
    assert garde.iteration == timeline[1].iteration
    assert (garde.grid == timeline[1].grid).all()
    assert widget.can_advance()


def test_the_keep_button_dies_once_the_five_slots_are_taken(step):
    from pokemon_mosaic.ui.session import MAX_SAVED

    widget, session = step
    feed(widget, session)
    for _ in range(MAX_SAVED):
        widget._keep_current()

    assert session.saved_count() == MAX_SAVED
    assert not widget._keep.isEnabled()
    # Retirer une case le rallume.
    session.remove_saved(2)
    assert widget._keep.isEnabled()


def test_keeping_wakes_up_on_the_first_snapshot(step):
    """⚠️ Le bouton se réveillait au démarrage du calcul, où la timeline est
    encore **vide** : il restait éteint tout le calcul, et seul un « Prolonger »
    le rallumait."""
    widget, session = step
    seen = run_synchronously(session)
    cards, timeline = seen["started"][0]
    vide = type(timeline)(every=timeline.every)

    widget._on_started(cards, vide)
    assert not widget._keep.isEnabled(), "rien à garder tant qu'il n'y a rien"

    widget._on_started(cards, timeline)
    widget._on_snapshot(timeline[0])
    assert widget._keep.isEnabled()


def test_a_new_run_keeps_the_arrangements_already_set_aside(step):
    """⚠️ Relancer, prolonger ou repartir d'un cliché ne vide pas la colonne :
    ce qu'on a mis de côté est ce qu'on a décidé de garder, et le recalculer
    n'est pas possible."""
    widget, session = step
    timeline = feed(widget, session)
    widget._slider.setValue(0)
    widget._keep_current()
    garde = session.saved[0]

    # Un second calcul repart de zéro : nouveau jeu de cartes, nouvelle timeline.
    seen = run_synchronously(session)
    cards, neuve = seen["started"][0]
    widget._on_started(cards, neuve)
    for cliche in neuve:
        widget._on_snapshot(cliche)

    assert session.saved[0] is garde, "la colonne n'a pas à être vidée"
    # Elle porte toujours la grille d'alors, et non celle du calcul neuf.
    assert (session.saved[0].grid == timeline[0].grid).all()
    assert widget.can_advance()


def test_clicking_a_slot_goes_back_to_its_snapshot(step):
    widget, session = step
    timeline = feed(widget, session)
    widget._slider.setValue(1)
    widget._keep_current()
    widget._slider.setValue(len(timeline) - 1)

    widget._show_saved(0)

    assert widget._slider.value() == 1
    assert widget._saved.current() == 0


def test_an_arrangement_lost_from_the_timeline_opens_in_its_own_window(step):
    """⚠️ **La timeline s'élague, et un nouveau calcul la remplace.** Rejoindre
    un cliché disparu est impossible, et montrer le plus proche donnerait à voir
    autre chose que ce que la case promet : une fenêtre à part le montre pour
    lui-même, et le dit."""
    widget, session = step
    timeline = feed(widget, session)
    widget._slider.setValue(1)
    widget._keep_current()
    dernier = len(timeline) - 1
    widget._slider.setValue(dernier)
    # La timeline oublie le cliché gardé.
    session.saved[0].iteration = -12345
    ouvertes = []
    widget._open_saved_dialog = ouvertes.append

    widget._show_saved(0)

    assert ouvertes == [session.saved[0]]
    assert widget._slider.value() == dernier, "le curseur n'a pas à sauter"


def test_the_dialog_of_a_lost_arrangement_says_so_and_zooms(qt_app, session):
    from pokemon_mosaic.ui.saved_column import SavedDialog
    from pokemon_mosaic.ui.session import SavedGrid

    jeu = card_set(20)
    garde = SavedGrid(np.arange(20).reshape(4, 5), jeu, 42, 1.0)
    dialogue = SavedDialog(garde, (255, 255, 255))
    dialogue.show()

    assert dialogue._notice.property("role") == "warning"
    assert "timeline" in dialogue._notice.text()
    avant = dialogue._view.pixmap().size()

    dialogue._zoom_in.click()

    assert dialogue.zoom() > 1.0
    assert dialogue._view.pixmap().width() > avant.width()


def test_the_green_outline_says_an_open_slot_not_a_kept_one(step):
    """⚠️ **Le cadre vert dit où l'on est**, et l'on n'y « va » pas en mettant
    de côté ce qu'on regarde déjà : allumé par la sauvegarde, il restait allumé
    pour de bon, le cliché gardé étant celui qu'on venait de regarder."""
    widget, session = step
    timeline = feed(widget, session)
    widget._slider.setValue(1)
    widget._keep_current()

    assert widget._saved.current() is None, "garder n'ouvre pas la case"

    widget._show_saved(0)
    assert widget._saved.current() == 0, "y aller l'ouvre"
    assert widget._slider.value() == 1

    widget._slider.setValue(len(timeline) - 1)
    assert widget._saved.current() is None, "on ne la regarde plus"


def test_the_outline_lights_up_while_the_window_of_a_lost_one_is_open(step):
    """Elle n'est plus dans la timeline : c'est la fenêtre qui la montre, et la
    case reste ouverte le temps qu'elle est à l'écran."""
    widget, session = step
    feed(widget, session)
    widget._keep_current()
    session.saved[0].iteration = -12345
    vues = []

    def ouvre(saved):
        vues.append(widget._saved.current())

    widget._open_saved_dialog = ouvre
    widget._show_saved(0)

    assert vues == [0], "la case s'allume avec la fenêtre"
    assert widget._saved.current() is None, "et s'éteint avec elle"


def test_the_screen_offers_the_button_before_anything_has_run(step):
    """⚠️ **Un écran qui n'a rien à montrer offre le geste à faire.** Une phrase
    seule laissait chercher où l'on lance : le bouton du bas se perdait dans une
    rangée de six, tous éteints sauf lui."""
    widget, _ = step
    assert widget._view.currentWidget() is widget._welcome
    assert widget._welcome_start.text()
    # Plus gros que ceux de la barre du bas : c'est le seul geste de l'écran.
    assert (widget._welcome_start.font().pointSize()
            > widget._start.font().pointSize())


def test_pause_and_stop_start_out_dead(step):
    """Ils naissaient actifs : cliquables sans effet tant qu'aucun calcul ne
    tourne, et deux boutons de plus à ignorer sur un écran qui n'en offre qu'un."""
    widget, _ = step
    assert not widget._pause.isEnabled()
    assert not widget._stop.isEnabled()
    assert widget._start.isEnabled()


def test_the_welcome_gives_way_to_the_image(step):
    """Elle n'a plus lieu d'être dès qu'il y a un cliché à regarder."""
    widget, session = step
    feed(widget, session)
    assert widget._view.currentWidget() is widget._scroll


def test_the_central_button_launches_the_run(step):
    """Il fait exactement ce que fait « Lancer » : c'est le même geste, offert
    là où l'œil se pose."""
    widget, _ = step
    lance = []
    widget.start_run = lambda *a, **k: lance.append(True)
    widget._welcome_start.click()
    assert lance


def test_the_slider_follows_the_latest_snapshot(step):
    widget, session = step
    timeline = feed(widget, session)
    assert widget._slider.value() == len(timeline) - 1
    assert widget._following


def test_moving_the_slider_stops_following(step):
    """Sinon l'image échapperait à l'utilisateur pendant qu'il examine un état."""
    widget, session = step
    feed(widget, session)
    widget._slider.setValue(1)
    assert not widget._following

    before = widget._slider.value()
    widget._on_snapshot(widget._timeline[-1])
    assert widget._slider.value() == before


def test_going_to_the_latest_resumes_following(step):
    widget, session = step
    timeline = feed(widget, session)
    widget._slider.setValue(1)
    widget._go_to_latest()
    assert widget._following
    assert widget._slider.value() == len(timeline) - 1


def test_the_position_label_counts_from_one(step):
    widget, session = step
    timeline = feed(widget, session)
    assert f"{len(timeline)}" in widget._position.text()
    widget._slider.setValue(0)
    assert widget._position.text().startswith("cliché 1 ")


def test_a_snapshot_is_rendered(step):
    widget, session = step
    feed(widget, session)
    widget._flush_render()          # le rendu est différé, à cadence bornée
    assert widget._image.pixmap() is not None
    assert not widget._image.pixmap().isNull()


def test_the_empty_colour_is_used_in_the_preview(step):
    widget, session = step
    session.set_layout(cols=6, rows=4)
    session.set_algorithm(empty_colour=(255, 0, 0))
    feed(widget, session)
    image = widget._render(widget._timeline[-1].grid)
    colours = {image.pixelColor(x, y).getRgb()[:3]
               for x in range(0, image.width(), 7)
               for y in range(0, image.height(), 7)}
    assert any(r > 200 and g < 60 and b < 60 for r, g, b in colours)


def test_shutdown_is_safe_without_a_run(step):
    widget, _ = step
    widget.shutdown()


def test_stop_and_pause_do_nothing_before_a_run(step):
    widget, _ = step
    widget._request_stop()
    widget._toggle_pause()      # ne doit pas lever


# --- Non-régressions de la revue -------------------------------------------

def test_clicking_start_passes_no_grid(step):
    """`clicked` transmet l'état coché du bouton : branché directement, il
    faisait recevoir False à previous_grid, et `.copy()` sur un booléen faisait
    échouer la préparation sans qu'aucun signal ne soit émis, interface figée.
    """
    widget, _ = step
    received = {}
    widget.start_run = lambda previous_grid=None: received.update(arg=previous_grid)
    widget._start.click()
    assert received["arg"] is None


def test_an_unexpected_preparation_failure_is_reported(session):
    """Sans cela, l'exception s'échappe du slot : ni finished_run ni failed n'est
    émis, thread.quit() n'est jamais appelé, et l'interface reste bloquée."""
    from pokemon_mosaic.ui.runner import RunWorker

    worker = RunWorker(session, RunControl(), previous_grid=False)
    failures = []
    worker.failed.connect(failures.append)
    worker.run()
    assert failures, "aucun échec remonté"
    assert "copy" in failures[0]


def test_a_run_that_fails_leaves_the_screen_usable(step):
    widget, _ = step
    widget._on_failed("quelque chose a cassé")
    assert widget._start.isEnabled()
    assert not widget._pause.isEnabled() and not widget._stop.isEnabled()


def test_pause_and_resume_drive_the_control_and_the_label(step):
    """La pause et la reprise passent par le contrôle, et le libellé suit.

    Test déterministe : le fait que la pause fige réellement la boucle est
    couvert par test_control.py, sur le vrai mécanisme et sans dépendre du
    minutage d'un fil de fond.
    """
    widget, _ = step
    widget._control = RunControl()
    widget._update_buttons(running=True)
    assert widget._pause.text() == "Pause"

    widget._pause.click()
    assert widget._control.paused
    assert widget._pause.text() == "Reprendre"

    widget._pause.click()
    assert not widget._control.paused
    assert widget._pause.text() == "Pause"


def test_stopping_asks_the_control_to_stop(step):
    widget, _ = step
    widget._control = RunControl()
    widget._update_buttons(running=True)
    widget._stop.click()
    assert widget._control.stop_requested


def test_shutdown_stops_a_real_background_run(qt_app, session):
    """Le seul test qui lance vraiment un fil : il vérifie qu'on sait l'arrêter,
    faute de quoi Qt abandonne le processus à la destruction du widget."""
    from PySide6.QtCore import QDeadlineTimer, QEventLoop

    from pokemon_mosaic.ui.run_step import RunStep

    session.set_algorithm(iterations=50_000_000, snapshot_every=5)
    widget = RunStep(session)
    widget._start.click()

    # Délai large : la boucle sort dès que le calcul a démarré, donc l'attente
    # réelle reste de quelques millisecondes. Un délai serré ne rendait pas le
    # test plus rapide, seulement intermittent sur une machine chargée.
    loop, deadline = QEventLoop(), QDeadlineTimer(10_000)
    while not deadline.hasExpired() and not widget._timeline:
        loop.processEvents(QEventLoop.AllEvents, 10)

    try:
        assert widget._timeline is not None, "le calcul n'a pas démarré"
    finally:
        # Même si l'attente a échoué : sans cet arrêt, un fil lancé pour
        # 50 millions d'itérations continue de tourner jusqu'à la fin de la
        # session de tests, qu'il ralentit et fait échouer en cascade.
        widget.shutdown()
    assert widget._thread is None, "le fil n'a pas été arrêté"


def test_the_preview_render_is_throttled(step):
    """Rendre un cliché coûte 56 ms sur une grille 17×17. Un rendu par cliché
    demanderait 3,9 s de fil principal pour 1,6 s de calcul : l'interface
    accumulerait du retard et le résultat n'apparaîtrait que bien après la fin.
    """
    widget, session = step
    timeline = feed(widget, session)
    assert len(timeline) > 3

    renders = []
    widget._render = lambda grid: renders.append(grid) or None
    for snapshot in timeline:
        widget._on_snapshot(snapshot)
    assert renders == [], "aucun rendu ne doit avoir lieu hors de la cadence"

    widget._flush_render()
    assert len(renders) == 1, "un seul rendu, celui du dernier état demandé"


def test_the_flush_renders_the_latest_requested_state(step):
    widget, session = step
    timeline = feed(widget, session)
    widget._slider.setValue(0)
    widget._slider.setValue(2)
    rendered = []
    widget._render = lambda grid: rendered.append(grid) or None
    widget._flush_render()
    assert len(rendered) == 1
    np.testing.assert_array_equal(rendered[0], timeline[2].grid)


def test_flushing_without_a_run_is_harmless(step):
    widget, _ = step
    widget._flush_render()


def test_the_stop_reason_is_translated(qt_app, session):
    """Le cœur ne dépend pas de Qt et renvoie ses libellés en français : sans
    traduction ici, l'interface anglaise affichait « stopped: itérations
    épuisées »."""
    from pokemon_mosaic.optimize import StopReason
    from pokemon_mosaic.ui.i18n import TRANSLATIONS_DIR, LanguageManager
    from pokemon_mosaic.ui.run_step import RunStep

    if not (TRANSLATIONS_DIR / "pokemon_mosaic_en.qm").exists():
        pytest.skip("traductions non compilées")

    widget = RunStep(session)
    assert widget._stop_reason(StopReason.EXHAUSTED) == "itérations épuisées"

    manager = LanguageManager(qt_app)
    try:
        manager.set_language("en")
        assert widget._stop_reason(StopReason.EXHAUSTED) == "iterations exhausted"
        assert widget._stop_reason(StopReason.REQUESTED) == "stopped by user"
    finally:
        manager.set_language("fr")


def test_an_unknown_stop_reason_is_passed_through(qt_app, session):
    from pokemon_mosaic.ui.run_step import RunStep

    assert RunStep(session)._stop_reason("quelque chose d'inédit") == \
        "quelque chose d'inédit"


# --- Zoom et clavier -------------------------------------------------------

def press(widget, key, modifiers=None):
    from PySide6.QtCore import QEvent, Qt
    from PySide6.QtGui import QKeyEvent

    widget.keyPressEvent(
        QKeyEvent(QEvent.KeyPress, key, modifiers or Qt.NoModifier)
    )


@pytest.fixture
def shown(qt_app):
    """Un écran réellement mis en page, sur des vignettes de taille réaliste.

    Les 12×16 px des autres tests donneraient une mosaïque plus petite que le
    cadre : elle serait déjà agrandie à l'ajustement, le plafond de zoom vaudrait
    1, et les tests de zoom passeraient sans rien vérifier.

    Il suffit que la mosaïque dépasse le cadre : plutôt que de grossir les cartes,
    on rétrécit la fenêtre. Des vignettes de 178×246 dans une fenêtre de 900×600
    faisaient monter le pic mémoire de ce fichier de 109 à 192 Mo, pour la même
    démonstration.
    """
    from pokemon_mosaic.ui.run_step import ZOOM_STEP, RunStep
    from pokemon_mosaic.ui.session import Session

    session = Session()
    session.set_cards(card_set(20, size=(60, 166)), "/fake")
    session.set_layout(cols=5, rows=4)
    session.set_algorithm(iterations=2000, snapshot_every=2, use_annealing=False)

    widget = RunStep(session)
    widget.show()
    widget.resize(420, 320)
    feed(widget, session)
    widget._flush_render()
    # Sans marge au-dessus de 1, les tests de zoom passeraient sans rien
    # vérifier : mieux vaut que la construction échoue franchement.
    assert widget._max_zoom() > ZOOM_STEP, "le fixture ne permet pas de zoomer"
    return widget, session


def test_the_whole_image_fits_by_default(shown):
    """L'aperçu doit montrer le haut et le bas du poster sans défilement :
    borner la seule largeur laissait un poster en portrait dépasser du cadre."""
    widget, _ = shown
    viewport = widget._scroll.viewport()
    assert widget._zoom == 1.0
    assert widget._image.width() <= viewport.width()
    assert widget._image.height() <= viewport.height()
    # Et l'image occupe bien la place disponible dans l'une des deux dimensions.
    assert (widget._image.width() == viewport.width()
            or widget._image.height() == viewport.height())


def test_arrows_move_along_the_timeline(shown):
    from PySide6.QtCore import Qt

    widget, _ = shown
    last = len(widget._timeline) - 1
    press(widget, Qt.Key_Left)
    assert widget._slider.value() == last - 1
    press(widget, Qt.Key_Left)
    assert widget._slider.value() == last - 2
    press(widget, Qt.Key_Right)
    assert widget._slider.value() == last - 1


def test_arrows_stop_at_both_ends(shown):
    from PySide6.QtCore import Qt

    widget, _ = shown
    press(widget, Qt.Key_Home)
    assert widget._slider.value() == 0
    press(widget, Qt.Key_Left)
    assert widget._slider.value() == 0

    press(widget, Qt.Key_End)
    assert widget._slider.value() == len(widget._timeline) - 1
    press(widget, Qt.Key_Right)
    assert widget._slider.value() == len(widget._timeline) - 1


def test_the_zoom_survives_a_move_on_the_timeline(shown):
    """Sinon comparer deux états au même endroit du poster serait impossible."""
    from PySide6.QtCore import Qt

    widget, _ = shown
    widget._zoom_by(2)
    widget._flush_render()      # le rendu du zoom passe par la cadence bornée
    zoomed = widget._zoom
    size = widget._image.size()
    assert zoomed > 1.0

    press(widget, Qt.Key_Left)
    widget._flush_render()
    assert widget._zoom == zoomed
    assert widget._image.size() == size


def test_zooming_out_stops_at_the_full_image(shown):
    """En dessous de l'ajustement, l'image entière est déjà visible : réduire
    encore ne montrerait rien de plus."""
    widget, _ = shown
    for _ in range(10):
        widget._zoom_by(-1)
    assert widget._zoom == 1.0


def test_zooming_in_stops_at_the_thumbnail_resolution(shown):
    """Au-delà, l'agrandissement n'est plus que de l'interpolation."""
    widget, _ = shown
    for _ in range(40):
        widget._zoom_by(1)
    assert widget._zoom == pytest.approx(widget._max_zoom())
    assert not widget._zoom_in.isEnabled()


def test_the_label_follows_the_zoomed_image(shown):
    """Le cadre ne redimensionne pas son contenu : sans cet ajustement, l'image
    zoomée serait rognée sans qu'aucune barre de défilement n'apparaisse."""
    widget, _ = shown
    widget._zoom_by(4)
    widget._flush_render()
    assert widget._image.height() == widget._image.pixmap().height()
    assert widget._scroll.verticalScrollBar().maximum() > 0


def test_reset_zoom_comes_back_to_the_whole_image(shown):
    widget, _ = shown
    widget._zoom_by(3)
    widget._flush_render()
    widget._reset_zoom()
    assert widget._zoom == 1.0
    assert widget._image.height() <= widget._scroll.viewport().height()


def test_control_wheel_zooms_and_a_plain_wheel_scrolls(qt_app):
    """Sans le modificateur, la molette doit continuer à faire défiler."""
    from PySide6.QtCore import QPoint, QPointF, Qt
    from PySide6.QtGui import QWheelEvent

    from pokemon_mosaic.ui.run_step import ImageView

    view = ImageView()
    seen = []
    view.zoom_requested.connect(seen.append)

    def wheel(delta, modifiers):
        return QWheelEvent(QPointF(10, 10), QPointF(10, 10), QPoint(0, 0),
                           QPoint(0, delta), Qt.NoButton, modifiers,
                           Qt.NoScrollPhase, False)

    view.wheelEvent(wheel(120, Qt.ControlModifier))
    view.wheelEvent(wheel(-120, Qt.ControlModifier))
    view.wheelEvent(wheel(120, Qt.NoModifier))
    assert seen == [1, -1]


def test_the_zoom_keeps_the_centre_of_the_view(qt_app, shown):
    """Sinon l'endroit qu'on examinait saute hors du cadre à chaque cran."""
    widget, _ = shown
    widget._zoom_by(1)
    widget._flush_render()
    qt_app.processEvents()
    bar = widget._scroll.verticalScrollBar()
    bar.setValue(bar.maximum() // 2)
    before = widget._relative_centre()

    widget._zoom_by(1)
    # Le rendu est cadencé, et le recentrage différé à la mise en page qui suit.
    widget._flush_render()
    qt_app.processEvents()
    # Le test ne vaut que si le zoom a bougé : au plafond, `_zoom_by` sort sans
    # rien faire et le recentrage serait vérifié à vide.
    from pokemon_mosaic.ui.run_step import ZOOM_STEP

    assert widget._zoom > ZOOM_STEP
    after = widget._relative_centre()
    assert after[0] == pytest.approx(before[0], abs=0.02)
    assert after[1] == pytest.approx(before[1], abs=0.02)


def test_enlarging_the_window_lowers_the_zoom_ceiling(shown):
    """Agrandir la fenêtre augmente l'échelle d'ajustement : le zoom doit
    redescendre avec le plafond, sinon il interpole des pixels inexistants."""
    widget, _ = shown
    for _ in range(40):
        widget._zoom_by(1)
    at_ceiling = widget._zoom

    widget.resize(1400, 1000)
    assert widget._max_zoom() < at_ceiling
    assert widget._zoom == pytest.approx(widget._max_zoom())


def test_a_burst_of_zooms_renders_only_once(shown):
    """Rendre coûte 55 ms quel que soit le zoom, et une rafale de molette
    produit des dizaines de crans par seconde : rendre à chaque cran bloquerait
    le fil principal une seconde entière pour un seul geste."""
    widget, _ = shown
    renders = []
    widget._render = lambda grid: renders.append(grid) or None

    for _ in range(12):
        widget._zoom_by(1)
    assert renders == [], "aucun rendu ne doit avoir lieu hors de la cadence"
    widget._flush_render()
    assert len(renders) == 1


def test_a_new_run_lowers_a_zoom_above_the_new_ceiling(shown):
    """Un zoom hérité d'une grande grille interpolerait des pixels inexistants
    sur une plus petite."""
    widget, session = shown
    for _ in range(40):
        widget._zoom_by(1)
    at_ceiling = widget._zoom
    assert at_ceiling > 1.0

    # Une grille bien plus petite : sa résolution native descend, donc le
    # plafond aussi. On compare au plafond plutôt qu'à une valeur écrite en dur,
    # qui ne tiendrait qu'à la taille des vignettes du fixture.
    session.set_excluded(range(4, 20), True)
    session.set_layout(cols=2, rows=2)
    feed(widget, session)
    assert widget._max_zoom() < at_ceiling
    assert widget._zoom == pytest.approx(widget._max_zoom())


# --- Prolonger et repartir d'un cliché -------------------------------------

@pytest.fixture
def capture_runs(monkeypatch):
    """Remplace le lancement en fond par un enregistrement des arguments."""
    from pokemon_mosaic.ui import run_step as module

    calls = []

    def fake_start_run(parent, session, control, previous_grid=None,
                       timeline=None, **handlers):
        calls.append({"previous_grid": previous_grid, "timeline": timeline})
        return object(), object()      # (thread, worker) factices mais non nuls

    monkeypatch.setattr(module, "start_run", fake_start_run)
    return calls


def test_resuming_is_impossible_before_a_run(qt_app, session):
    from pokemon_mosaic.ui.run_step import RunStep

    widget = RunStep(session)
    assert not widget.can_resume()
    assert not widget._extend.isEnabled() and not widget._resume.isEnabled()
    widget._extend_run()            # ne doit pas lever
    widget._resume_from_snapshot()


def test_a_finished_run_can_be_extended(step, capture_runs):
    widget, session = step
    widget._run_signature = widget._signature()
    feed(widget, session)
    widget._update_buttons(running=False)
    assert widget.can_resume()

    widget._extend.click()
    assert len(capture_runs) == 1
    # Reprend le dernier cliché et poursuit la même timeline.
    np.testing.assert_array_equal(capture_runs[0]["previous_grid"],
                                  widget._timeline[-1].grid)
    assert capture_runs[0]["timeline"] is widget._timeline


def test_resuming_from_a_snapshot_drops_what_came_after(step, capture_runs):
    """L'avenir abandonné ne descend plus de l'état courant : le garder ferait
    une timeline dont la seconde moitié ne suit pas la première."""
    widget, session = step
    widget._run_signature = widget._signature()
    feed(widget, session)
    widget._update_buttons(running=False)
    assert len(widget._timeline) > 2, "il faut des clichés à abandonner"
    kept = widget._timeline[1].grid.copy()

    widget._slider.setValue(1)
    widget._resume.click()
    assert len(widget._timeline) == 2
    np.testing.assert_array_equal(capture_runs[0]["previous_grid"], kept)
    assert widget._slider.value() == 1


def test_restarting_from_the_last_snapshot_is_left_to_extend(step, capture_runs):
    """Deux boutons pour le même geste laisseraient croire qu'ils diffèrent."""
    widget, session = step
    widget._run_signature = widget._signature()
    feed(widget, session)
    widget._update_buttons(running=False)

    widget._slider.setValue(len(widget._timeline) - 1)
    assert not widget._resume.isEnabled()
    widget._slider.setValue(0)
    assert widget._resume.isEnabled()


@pytest.mark.parametrize("change", ["selection", "links", "grid", "strip_size"])
def test_changing_the_inputs_disables_resuming(step, change):
    """Les cartes retenues sont renumérotées de 0 à n-1 : repartir d'un cliché
    après un changement ferait désigner d'autres cartes par les mêmes indices.

    L'épaisseur des bandes compte pour une autre raison : elle recalcule les
    signatures, donc l'échelle du score. Mesuré : la même grille vaut 621,7
    avec une bande de 0,10 et 552,0 avec 0,30. Prolonger sans en tenir compte
    mêlait deux métriques et la courbe chutait sans qu'aucune carte ne bouge.
    """
    widget, session = step
    widget._run_signature = widget._signature()
    feed(widget, session)
    widget._update_buttons(running=False)
    assert widget.can_resume()

    if change == "selection":
        session.set_excluded([0], True)
    elif change == "links":
        session.add_link(Link(cards=(0, 1)))
    elif change == "strip_size":
        session.set_algorithm(strip_size=session.strip_size + 0.2)
    else:
        session.set_layout(cols=4, rows=5)

    assert not widget.can_resume()
    assert not widget._extend.isEnabled() and not widget._resume.isEnabled()


def test_a_grid_of_the_wrong_shape_is_refused_by_the_worker(session):
    """Dernier filet : rien ne planterait, le poster serait simplement composé
    de cartes que l'utilisateur n'a pas choisies."""
    from pokemon_mosaic.ui.runner import RunWorker

    seen = run_synchronously(session)
    grid = seen["started"][0][1][-1].grid
    session.set_layout(cols=4, rows=5)
    worker = RunWorker(session, RunControl(), previous_grid=grid)
    failures = []
    worker.failed.connect(failures.append)
    worker.run()
    assert failures and "mise en page" in failures[0]


# --- Non-régressions du /verif-code de l'interface, 2026-08-24 --------------

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


def test_a_stubborn_run_is_reported_and_its_reference_kept(step):
    """⚠️ Une référence n'est lâchée que si son fil est réellement terminé :
    la lâcher sur un fil actif rouvre le crash que `shutdown` évite. L'export a
    quitté cet écran, il n'y a plus qu'un fil ici."""
    widget, _ = step
    tenace = _FilFactice(tenace=True)
    widget._thread = tenace

    assert widget.shutdown() is False, "un fil tenace doit être signalé"
    assert tenace.journal == ["quit", "wait"], tenace.journal
    assert widget._thread is tenace, "un fil encore actif garde sa référence"


def test_shutdown_reports_success_when_the_run_stops(step):
    widget, _ = step
    widget._thread = _FilFactice()

    assert widget.shutdown() is True
    assert widget._thread is None and widget._worker is None


def test_a_stubborn_thread_keeps_the_window_open(qt_app, session):
    """Fermer sur un fil actif ferait abandonner le processus par Qt : mieux vaut
    refuser la fermeture et laisser une chance de plus."""
    from PySide6.QtGui import QCloseEvent
    from PySide6.QtWidgets import QApplication

    from pokemon_mosaic.ui.i18n import LanguageManager
    from pokemon_mosaic.ui.main_window import MainWindow

    fenetre = MainWindow(LanguageManager(QApplication.instance()), session)
    fenetre._run_step._thread = _FilFactice(tenace=True)

    event = QCloseEvent()
    fenetre.closeEvent(event)
    assert not event.isAccepted(), "la fenêtre ne doit pas se fermer"

    # Le fil rend la main : la fermeture repasse.
    fenetre._run_step._thread = None
    event = QCloseEvent()
    fenetre.closeEvent(event)
    assert event.isAccepted()
    fenetre.deleteLater()


def test_a_thread_that_never_stops_does_not_lock_the_window_shut(qt_app, session):
    """Refuser indéfiniment rendrait la fenêtre infermable dès qu'un fil se
    bloque pour de bon : l'utilisateur cliquerait la croix sans effet, et il ne
    lui resterait qu'à tuer le processus. C'est pire que le plantage évité."""
    from PySide6.QtGui import QCloseEvent
    from PySide6.QtWidgets import QApplication

    from pokemon_mosaic.ui.i18n import LanguageManager
    from pokemon_mosaic.ui.main_window import MainWindow

    fenetre = MainWindow(LanguageManager(QApplication.instance()), session)
    fenetre._run_step._thread = _FilFactice(tenace=True)

    refus = 0
    for _ in range(MainWindow.CLOSE_ATTEMPTS + 2):
        event = QCloseEvent()
        fenetre.closeEvent(event)
        if event.isAccepted():
            break
        refus += 1
    assert event.isAccepted(), "la fenêtre doit finir par se fermer"
    assert refus == MainWindow.CLOSE_ATTEMPTS - 1, refus
    fenetre.deleteLater()


# --- Ce que la reprise doit refuser -----------------------------------------

def prete(step_widget, session):
    """Un écran en état de reprise : une timeline d'un cliché, signature figée."""
    from pokemon_mosaic.optimize import build_initial_grid, select_cards
    from pokemon_mosaic.timeline import Timeline

    sub, links = select_cards(session.card_set, session.selected_indices(),
                              session.usable_links())
    grid = build_initial_grid(sub, shape=(session.cols, session.rows),
                              links=links, empty_cells=session.empty_cells())
    timeline = Timeline(every=1)
    step_widget._on_started(sub, timeline)
    step_widget._run_signature = step_widget._signature()
    timeline.record(grid, 0, 0, 1.0, 0.0)
    step_widget._on_snapshot(timeline.snapshots[-1])
    # C'est la fin du calcul qui ouvre les boutons de reprise ; on ne rejoue
    # que cette partie-là, `_on_finished` demandant un résultat complet.
    step_widget._update_resume_buttons()
    assert step_widget._extend.isEnabled()
    return grid


def test_moving_an_empty_cell_disables_resuming(step):
    """Reprendre saute `build_initial_grid` : les trous resteraient là où ils
    étaient. Mesuré avant correction : trous demandés en (1,2) et (2,3), grille
    reprise gardant (0,0) et (1,2), sans le moindre signe."""
    widget, session = step
    session.set_layout(cols=4, rows=3)          # 12 cases pour 20 cartes… non
    session.set_excluded(range(10, 20), True)   # 10 retenues, 2 trous
    prete(widget, session)

    # Une case qui n'est pas déjà un trou : retirer l'un des deux trous
    # automatiques serait sans effet, `empty_cells()` complétant aussitôt le
    # quota au même endroit.
    assert (2, 3) not in session.empty_cells()
    session.toggle_empty_cell(2, 3)
    assert (2, 3) in session.empty_cells()

    assert not widget._extend.isEnabled()
    assert not widget.can_resume()


def test_reshaping_a_link_disables_resuming(step):
    """Mêmes cartes, autre forme : la signature ne bougeait pas, le bouton
    restait actif, et le calcul échouait au lancement sur un message interne."""
    widget, session = step
    horizontal = Link(cards=(0, 1, 2), shape=(3, 1))
    session.links.add(horizontal)
    prete(widget, session)

    session.links.replace(horizontal, Link(cards=(0, 1, 2), shape=(1, 3)))
    session.links_changed.emit()
    assert not widget._extend.isEnabled()


def test_flipping_the_imposed_order_disables_resuming(step):
    """`_locate_block` n'essaie le bloc retourné que si l'ordre est libre : le
    rendre imposé après coup rend la grille de départ irrecevable."""
    widget, session = step
    libre = Link(cards=(0, 1, 2), shape=(3, 1), ordered=False)
    session.links.add(libre)
    prete(widget, session)

    session.links.replace(libre, Link(cards=(0, 1, 2), shape=(3, 1), ordered=True))
    session.links_changed.emit()
    assert not widget._extend.isEnabled()


def test_a_grid_untouched_still_resumes(step):
    """Le garde ne doit pas éteindre la reprise pour rien : sans modification,
    prolonger reste possible."""
    widget, session = step
    prete(widget, session)
    assert widget.can_resume()


# --- L'élagage de la timeline ------------------------------------------------

def test_thinning_does_not_drag_the_user_back_to_the_live_view(step):
    """L'élagage divise la timeline par deux dès 70 clichés : le maximum baisse,
    Qt écrête la position et émet `valueChanged`. On en déduisait que
    l'utilisateur était revenu en butée, mesuré, curseur 45 ramené à 44 et
    l'image se remettant à défiler pendant qu'il examinait un état antérieur."""
    import numpy as np

    from pokemon_mosaic.timeline import Timeline

    widget, session = step
    timeline = Timeline(every=1, max_snapshots=70)
    widget._on_started(session.card_set, timeline)
    grille = np.zeros((session.rows, session.cols), np.int16)

    def pousse(k):
        timeline.record(grille, k, k, 1.0, 0.0)
        widget._on_snapshot(timeline.snapshots[-1])

    for k in range(60):
        pousse(k)
    widget._slider.setValue(45)
    assert not widget._following

    for k in range(60, 80):             # franchit le seuil d'élagage
        pousse(k)

    assert len(timeline) < 60, "l'élagage ne s'est pas déclenché"
    assert not widget._following, "l'utilisateur a été ramené au direct"


def test_reaching_the_last_snapshot_by_hand_still_follows(step):
    """Le garde ne vaut que pour les réglages que nous provoquons : revenir en
    butée soi-même doit toujours remettre en suivi du direct."""
    widget, session = step
    timeline = feed(widget, session)
    widget._slider.setValue(0)
    assert not widget._following

    widget._slider.setValue(len(timeline) - 1)
    assert widget._following


def test_thinning_refreshes_the_image_under_the_cursor(step):
    """L'élagage renumérote : la case du curseur désigne un autre cliché. Sans
    rendu, l'écran gardait l'image précédente sous une étiquette qui a changé,
    et l'export aurait écrit la grille du nouveau cliché. Mesuré : index 20
    passé de l'itération 20 à l'itération 40, image inchangée."""
    import numpy as np

    from pokemon_mosaic.timeline import Timeline

    widget, session = step
    timeline = Timeline(every=1, max_snapshots=70)
    widget._on_started(session.card_set, timeline)

    def pousse(k):
        grille = np.roll(np.arange(20, dtype=np.int16), k).reshape(
            session.rows, session.cols)
        timeline.record(grille, k, k, 1.0, 0.0)
        widget._on_snapshot(timeline.snapshots[-1])

    for k in range(60):
        pousse(k)
    widget._slider.setValue(20)
    widget._flush_render()
    assert widget._pending_index is None

    avant = timeline[20].iteration
    for k in range(60, 80):
        pousse(k)

    assert timeline[widget._slider.value()].iteration != avant, \
        "l'élagage n'a pas renuméroté"
    assert widget._pending_index == widget._slider.value(), \
        "l'image sous le curseur n'a pas été redemandée"


def test_a_growing_timeline_does_not_re_render_for_nothing(step):
    """Le rendu ne se redemande qu'à un rétrécissement : le déclencher à chaque
    cliché coûterait 56 ms de fil principal pour une image identique."""
    import numpy as np

    from pokemon_mosaic.timeline import Timeline

    widget, session = step
    timeline = Timeline(every=1, max_snapshots=None)
    widget._on_started(session.card_set, timeline)
    grille = np.arange(20, dtype=np.int16).reshape(session.rows, session.cols)

    for k in range(10):
        timeline.record(grille, k, k, 1.0, 0.0)
        widget._on_snapshot(timeline.snapshots[-1])
    widget._slider.setValue(3)
    widget._flush_render()

    timeline.record(grille, 10, 10, 1.0, 0.0)
    widget._on_snapshot(timeline.snapshots[-1])
    assert widget._pending_index is None
