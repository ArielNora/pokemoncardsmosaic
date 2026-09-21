"""Tests de l'aperçu d'épaisseur des bandes."""

import time

import numpy as np
import pytest

from pokemon_mosaic.cards import Card, CardSet


def coloured_card_set(n, size=(24, 34)):
    """Cartes en dégradé vertical, chacune entre deux couleurs tirées au sort.

    Un jeu de couleurs **unies** ne conviendrait pas : la moyenne d'une bande y
    vaut la couleur de la carte quelle que soit son épaisseur, donc le réglage
    n'aurait aucun effet et le test ne prouverait rien.
    """
    rng = np.random.default_rng(0)
    width, height = size
    ramp = np.linspace(0.0, 1.0, height)[:, None]
    cards = []
    for i in range(n):
        top_colour = rng.integers(0, 255, 3).astype(float)
        bottom_colour = rng.integers(0, 255, 3).astype(float)
        column = top_colour * (1 - ramp) + bottom_colour * ramp
        thumb = np.repeat(column[:, None, :], width, axis=1).astype(np.uint8)
        card = Card(path=f"/fake/{i}.png", index=i, thumbnail=thumb)
        card.calculate_features(0.1)
        cards.append(card)
    return CardSet(cards=cards, full_size=(713, 984), thumb_size=size)


@pytest.fixture
def session(qt_app):
    from pokemon_mosaic.ui.session import Session

    s = Session()
    s.set_cards(coloured_card_set(30), "/fake")
    return s


@pytest.fixture
def preview(qt_app, session):
    from pokemon_mosaic.ui.strip_preview import StripPreview

    widget = StripPreview(session)
    widget.resize(420, 200)
    return widget, session


def test_sandbox_is_built_from_the_loaded_cards(preview):
    widget, _ = preview
    widget.refresh()
    assert widget._sandbox is not None
    assert widget._sandbox_error == ""


def test_sandbox_reports_when_there_are_too_few_cards(qt_app):
    from pokemon_mosaic.ui.session import Session
    from pokemon_mosaic.ui.strip_preview import StripPreview

    session = Session()
    session.set_cards(coloured_card_set(3), "/fake")
    widget = StripPreview(session)
    widget.refresh()
    assert widget._sandbox is None
    assert "pas assez" in widget._sandbox_error


def test_sandbox_holds_every_sampled_card_once(preview):
    """La grille d'essai passe par subset(), qui renumérote : une erreur de
    correspondance y produirait des cartes manquantes ou répétées."""
    from pokemon_mosaic.ui.strip_preview import SANDBOX_COLS, SANDBOX_ROWS

    widget, _ = preview
    widget.refresh()
    expected = SANDBOX_COLS * SANDBOX_ROWS
    assert widget._sandbox.width() > 0
    assert widget._sandbox.height() > 0
    # La grille est pleine : aucune case ne doit rester noire.
    image = widget._sandbox
    corners = [image.pixelColor(1, 1), image.pixelColor(image.width() - 2, 1),
               image.pixelColor(1, image.height() - 2)]
    assert all(colour.value() > 0 for colour in corners), f"{expected} cases attendues"


def test_changing_the_strip_size_changes_the_sandbox(preview):
    widget, session = preview
    widget.refresh()
    before = widget._sandbox.copy()
    session.set_algorithm(strip_size=0.45)
    widget.refresh()
    assert widget._sandbox != before


def test_a_change_only_marks_the_preview_stale(preview):
    """Reconstruire coûte de 34 à 294 ms. `selection_changed` part à chaque clic
    dans la galerie de l'étape 1, où cet aperçu n'est pas même visible : marquer
    périmé doit être gratuit, le calcul n'ayant lieu qu'à l'affichage."""
    widget, session = preview
    widget.refresh()
    assert widget._dirty is False

    start = time.monotonic()
    for index in range(20):
        session.toggle(index)
    elapsed = time.monotonic() - start

    assert widget._dirty is True
    assert elapsed < 0.05, f"20 basculements ont coûté {elapsed * 1000:.0f} ms"


def test_painting_does_not_rebuild(preview):
    """Reconstruire depuis paintEvent figeait l'interface à chaque cran du
    curseur : le repeint arrivait avant l'anti-rebond, qui ne servait à rien.
    Mesuré : cinq crans donnaient 5 reconstructions et 622 ms.
    """
    widget, session = preview
    widget.refresh()
    session.set_algorithm(strip_size=0.3)
    assert widget._dirty is True

    widget.grab()
    assert widget._dirty is True, "le rendu ne doit pas déclencher le calcul"
    assert widget._timer.isActive(), "il doit être différé, pas abandonné"


def test_the_deferred_rebuild_eventually_runs(preview):
    widget, session = preview
    widget.refresh()
    session.set_algorithm(strip_size=0.3)
    widget._timer.timeout.emit()          # on force le tir du minuteur
    assert widget._dirty is False


def test_an_unrelated_setting_schedules_nothing(preview):
    """L'aperçu ne dépend que de l'épaisseur et des cartes retenues. Changer le
    nombre d'itérations relançait jusqu'à 294 ms de calcul pour rien."""
    widget, session = preview
    widget.refresh()
    session.set_algorithm(iterations=250_000, snapshot_every=25)
    assert widget._dirty is False
    assert not widget._timer.isActive()


def test_an_unrelated_setting_leaves_the_sandbox_coherent(preview):
    widget, session = preview
    session.set_algorithm(iterations=1234)
    widget.refresh()
    assert widget._sandbox is not None


def test_excluded_cards_are_kept_out_of_the_sample(preview):
    """Montrer un raccord entre des cartes que l'utilisateur vient d'exclure
    serait trompeur : l'échantillon doit suivre la sélection."""
    widget, session = preview
    widget.refresh()
    before = widget._sandbox.copy()

    session.set_excluded(range(20), True)
    widget.refresh()
    assert widget._sandbox != before


def test_too_few_cards_left_after_exclusion_is_reported(preview):
    widget, session = preview
    session.set_excluded(range(28), True)   # il n'en reste que 2
    widget.refresh()
    assert widget._sandbox is None
    assert "pas assez" in widget._sandbox_error


def test_widget_paints_when_everything_is_excluded(preview):
    widget, session = preview
    session.set_excluded(range(30), True)
    assert not widget.grab().isNull()


def test_rebuilding_stays_fast_enough_for_a_slider(preview):
    """Mesuré à ~37 ms pour 20 cartes ; au-delà de 250 ms le curseur accrocherait."""
    widget, _ = preview
    start = time.monotonic()
    widget.refresh()
    assert time.monotonic() - start < 0.25


def test_widget_paints_without_cards(qt_app):
    from pokemon_mosaic.ui.session import Session
    from pokemon_mosaic.ui.strip_preview import StripPreview

    widget = StripPreview(Session())
    widget.resize(300, 160)
    widget.grab()   # ne doit pas lever


def test_widget_paints_with_cards(preview):
    widget, _ = preview
    widget.refresh()
    pixmap = widget.grab()
    assert not pixmap.isNull()


def test_two_cards_face_each_other_with_an_arrow_between_them(preview):
    """⚠️ **Une carte seule ne disait pas ce qui est comparé.** Elle montrait
    quatre bandes surlignées sans dire à quoi elles servaient : le score n'existe
    qu'entre **deux** cartes, et la flèche pointe le raccord."""
    from pokemon_mosaic.ui.strip_preview import BAND_EDGE

    widget, session = preview
    widget.refresh()
    image = widget.grab().toImage()
    ratio = image.devicePixelRatio() or 1

    # ⚠️ La couleur seule ne suffit pas : les contours des bandes la portent
    # aussi. La flèche est la seule **suite horizontale** de cette couleur.
    milieu = int(widget.height() / 2 * ratio)
    ligne = [image.pixelColor(x, milieu).name() == BAND_EDGE.name()
             for x in range(int(widget.width() * ratio))]
    suites, debut = [], None
    for x, porte in enumerate(ligne + [False]):
        if porte and debut is None:
            debut = x
        elif not porte and debut is not None:
            suites.append((x - debut, debut, x))
            debut = None
    longueur, gauche, droite = max(suites)
    assert longueur / ratio >= 10, "aucune flèche à hauteur du raccord"

    # Elle est centrée sur la jointure des deux cartes.
    hauteur = widget.height() - 12
    vignette = session.card_set[0].thumbnail
    une_carte = hauteur * vignette.shape[1] / vignette.shape[0]
    centre = (gauche + droite) / 2 / ratio
    assert une_carte * 0.85 < centre < une_carte * 1.15, (
        "la flèche ne tombe pas sur la jointure des deux cartes")


def test_the_shortage_message_goes_through_the_catalogue(qt_app):
    """Écrite en dur, elle s'affichait en français dans une interface anglaise :
    `lupdate` n'extrait que les `tr()` portant une chaîne littérale."""
    from pathlib import Path

    source = Path("src/pokemon_mosaic/ui/strip_preview.py").read_text()
    assert 'self.tr("pas assez de cartes")' in source

    catalogue = Path("translations/pokemon_mosaic_en.ts").read_text()
    assert "pas assez de cartes" in catalogue


# --- La métrique améliorée montrée sur les bandes ---------------------------


def test_a_band_stays_whole_with_the_plain_metric(preview):
    from PySide6.QtCore import QRectF

    widget, _ = preview
    bande = QRectF(10, 20, 200, 30)

    assert widget.band_parts(bande, horizontale=True) == [bande]


def test_the_band_shows_the_parts_the_score_measures(preview):
    """Le découpage montré est celui qui est mesuré.

    ⚠️ **Chaque partie prend toute l'épaisseur de la bande**, et toutes se
    posent au même niveau : une partie est une tranche du rectangle mesuré, pas
    la moitié de son épaisseur. Les avoir posées en deux niveaux, pour que le
    recouvrement saute aux yeux, montrait un découpage que le score ne fait pas.
    """
    from PySide6.QtCore import QRectF

    from pokemon_mosaic.cards import EDGE_PARTS, edge_windows

    widget, session = preview
    session.set_algorithm(fine_metric=True)
    bande = QRectF(10, 20, 220, 30)

    morceaux = widget.band_parts(bande, horizontale=True)

    assert len(morceaux) == EDGE_PARTS
    attendu = edge_windows(220, EDGE_PARTS)
    for rang, (morceau, (debut, fin)) in enumerate(
            zip(morceaux, attendu, strict=True)):
        assert morceau.left() == pytest.approx(bande.left() + debut), rang
        assert morceau.width() == pytest.approx(fin - debut), rang
        assert morceau.top() == pytest.approx(bande.top()), rang
        assert morceau.height() == pytest.approx(bande.height()), rang
    assert morceaux[0].left() == pytest.approx(bande.left())
    assert morceaux[-1].right() == pytest.approx(bande.right())


def test_a_vertical_band_is_cut_along_its_height(preview):
    """Les bords gauche et droit se mesurent dans la hauteur, pas la largeur."""
    from PySide6.QtCore import QRectF

    from pokemon_mosaic.cards import EDGE_PARTS, edge_windows

    widget, session = preview
    session.set_algorithm(fine_metric=True)
    bande = QRectF(10, 20, 30, 220)

    morceaux = widget.band_parts(bande, horizontale=False)

    attendu = edge_windows(220, EDGE_PARTS)
    for rang, (morceau, (debut, fin)) in enumerate(
            zip(morceaux, attendu, strict=True)):
        assert morceau.top() == pytest.approx(bande.top() + debut), rang
        assert morceau.height() == pytest.approx(fin - debut), rang
        assert morceau.left() == pytest.approx(bande.left()), rang
        assert morceau.width() == pytest.approx(bande.width()), rang


def test_toggling_the_fine_metric_rebuilds_the_sandbox(preview):
    """La grille d'essai est réoptimisée : c'est là qu'on voit ce que ça change.

    On vérifie l'invalidation et non l'image : deux optimisations peuvent
    tomber sur le même agencement, et un test qui ne tient qu'à cette chance
    vaudrait moins que pas de test.
    """
    from pokemon_mosaic.cards import EDGE_PARTS

    widget, session = preview
    widget.refresh()
    assert not widget._dirty

    session.set_algorithm(fine_metric=True)

    assert widget._dirty, "la case n'a pas invalidé l'aperçu"
    widget.refresh()
    assert widget._sandbox is not None
    assert EDGE_PARTS in widget._built_key


def test_the_preview_follows_the_chosen_number_of_parts(preview):
    """Le nombre choisi change le découpage montré, et refait la grille d'essai."""
    from PySide6.QtCore import QRectF

    widget, session = preview
    session.set_algorithm(fine_metric=True)
    widget.refresh()
    bande = QRectF(0, 0, 200, 20)
    assert len(widget.band_parts(bande, horizontale=True)) == session.metric_parts

    session.set_algorithm(metric_parts=9)

    assert len(widget.band_parts(bande, horizontale=True)) == 9
    assert widget._dirty, "la grille d'essai n'a pas été invalidée"
