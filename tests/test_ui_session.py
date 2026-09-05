"""Tests de l'état partagé et de la traduction de l'interface."""

import numpy as np
import pytest

from pokemon_mosaic.cards import Card, CardSet
from pokemon_mosaic.links import Link


def card_set_in(tmp_path, layout):
    """Construit un CardSet dont les chemins reflètent une arborescence réelle."""
    cards = []
    for folder, names in layout.items():
        directory = tmp_path / folder
        directory.mkdir(parents=True, exist_ok=True)
        for name in names:
            path = directory / f"{name}.png"
            path.touch()
            card = Card(path=str(path), index=len(cards),
                        thumbnail=np.zeros((8, 6, 3), np.uint8))
            card.top = card.bottom = card.left = card.right = np.zeros(3)
            cards.append(card)
    return CardSet(cards=cards, full_size=(713, 984), thumb_size=(6, 8))


@pytest.fixture
def session(qt_app):
    from pokemon_mosaic.ui.session import Session

    return Session()


def test_all_cards_selected_after_loading(session, tmp_path):
    session.set_cards(card_set_in(tmp_path, {"a": ["x", "y", "z"]}), str(tmp_path))
    assert session.total_cards == 3
    assert session.selected_count == 3
    assert session.selected_indices() == [0, 1, 2]


def test_toggle_excludes_then_reincludes(session, tmp_path):
    session.set_cards(card_set_in(tmp_path, {"a": ["x", "y"]}), str(tmp_path))
    session.toggle(0)
    assert session.is_excluded(0) and session.selected_count == 1
    session.toggle(0)
    assert not session.is_excluded(0) and session.selected_count == 2


def test_folders_with_the_same_name_stay_distinct(session, tmp_path):
    """Deux séries peuvent avoir un « 0_promo » : les confondre exclurait les deux."""
    session.set_cards(
        card_set_in(tmp_path, {"serie_A/0_promo": ["a", "b"],
                               "serie_B/0_promo": ["c"]}),
        str(tmp_path),
    )
    assert session.folders() == ["serie_A/0_promo", "serie_B/0_promo"]
    assert len(session.indices_in_folder("serie_A/0_promo")) == 2
    assert len(session.indices_in_folder("serie_B/0_promo")) == 1


def test_excluding_one_folder_leaves_its_namesake_untouched(session, tmp_path):
    session.set_cards(
        card_set_in(tmp_path, {"serie_A/0_promo": ["a", "b"],
                               "serie_B/0_promo": ["c"]}),
        str(tmp_path),
    )
    session.set_excluded(session.indices_in_folder("serie_A/0_promo"), True)
    assert session.selected_count == 1
    assert session.selected_indices() == [2]


def test_selection_change_emits_once_per_batch(session, tmp_path):
    session.set_cards(card_set_in(tmp_path, {"a": list("abcdef")}), str(tmp_path))
    calls = []
    session.selection_changed.connect(lambda: calls.append(1))
    session.set_excluded([0, 1, 2], True)
    assert len(calls) == 1


def test_no_signal_when_nothing_actually_changes(session, tmp_path):
    session.set_cards(card_set_in(tmp_path, {"a": ["x", "y"]}), str(tmp_path))
    session.set_excluded([0], True)
    calls = []
    session.selection_changed.connect(lambda: calls.append(1))
    session.set_excluded([0], True)
    assert calls == []


def test_links_referencing_excluded_cards_are_dropped(session, tmp_path):
    session.set_cards(card_set_in(tmp_path, {"a": list("abcd")}), str(tmp_path))
    session.add_link(Link(cards=(0, 1)))
    session.add_link(Link(cards=(2, 3)))
    assert len(session.usable_links()) == 2
    session.set_excluded([1], True)
    assert [l.cards for l in session.usable_links().active] == [(2, 3)]


def test_thumbnail_survives_conversion_to_pixmap(qt_app):
    """QImage ne copie pas son tampon : sans copie, l'image pointerait dans le vide."""
    from pokemon_mosaic.ui.gallery import numpy_to_pixmap

    array = np.random.default_rng(0).integers(0, 255, (12, 9, 3), dtype=np.uint8)
    pixmap = numpy_to_pixmap(array)
    del array
    assert (pixmap.width(), pixmap.height()) == (9, 12)
    assert not pixmap.isNull()


# --- Chargement progressif et filtrage ------------------------------------

def test_cards_arrive_folder_by_folder(session, tmp_path):
    """Les extensions doivent s'afficher les unes après les autres, sans
    attendre les ~3,5 s de décodage complet."""
    card_set = card_set_in(tmp_path, {"s/a": ["1", "2"], "s/b": ["3"]})
    batches = []
    session.cards_added.connect(lambda indices: batches.append(list(indices)))

    session.start_loading(str(tmp_path))
    assert session.total_cards == 0
    session.append_cards(card_set.cards[:2])
    assert session.total_cards == 2
    session.append_cards(card_set.cards[2:])
    session.finish_loading(card_set)

    assert batches == [[0, 1], [2]]
    assert session.total_cards == 3


def test_folders_appear_as_they_load(session, tmp_path):
    card_set = card_set_in(tmp_path, {"s/a": ["1"], "s/b": ["2"]})
    session.start_loading(str(tmp_path))
    session.append_cards(card_set.cards[:1])
    assert session.folders() == ["s/a"]
    session.append_cards(card_set.cards[1:])
    assert session.folders() == ["s/a", "s/b"]


def test_loading_again_clears_the_previous_cards(session, tmp_path):
    session.set_cards(card_set_in(tmp_path, {"a": ["x", "y"]}), str(tmp_path))
    session.start_loading(str(tmp_path))
    assert session.total_cards == 0 and session.folders() == []


@pytest.fixture
def gallery_model(session, tmp_path):
    from pokemon_mosaic.ui.gallery import CardGalleryModel

    session.set_cards(
        card_set_in(tmp_path, {"s/a": ["1", "2", "3"], "s/b": ["4", "5"]}),
        str(tmp_path),
    )
    return CardGalleryModel(session), session


def test_filter_restricts_the_visible_cards(gallery_model):
    model, _ = gallery_model
    assert model.rowCount() == 5
    model.set_folder_filter({"s/b"})
    assert model.rowCount() == 2
    model.set_folder_filter(None)
    assert model.rowCount() == 5


def test_filter_maps_rows_back_to_the_right_cards(gallery_model):
    """Filtrer décale les lignes : sans correspondance, cliquer une carte en
    basculerait une autre."""
    model, _ = gallery_model
    model.set_folder_filter({"s/b"})
    assert [model.card_index_at(row) for row in range(model.rowCount())] == [3, 4]


def test_toggling_while_filtered_hits_the_intended_card(gallery_model):
    model, session = gallery_model
    model.set_folder_filter({"s/b"})
    session.set_excluded([model.card_index_at(0)], True)
    assert session.is_excluded(3)
    assert not session.is_excluded(0)


def test_filter_on_several_folders(gallery_model):
    model, _ = gallery_model
    model.set_folder_filter({"s/a", "s/b"})
    assert model.rowCount() == 5


def test_new_cards_respect_the_active_filter(session, tmp_path):
    """Le filtre de l'utilisateur ne doit pas être perdu quand un dossier arrive."""
    from pokemon_mosaic.ui.gallery import CardGalleryModel

    card_set = card_set_in(tmp_path, {"s/a": ["1", "2"], "s/b": ["3", "4"]})
    session.start_loading(str(tmp_path))
    session.append_cards(card_set.cards[:2])

    model = CardGalleryModel(session)
    model.set_folder_filter({"s/a"})
    assert model.rowCount() == 2

    session.append_cards(card_set.cards[2:])  # dossier s/b, filtré
    assert model.rowCount() == 2
    model.set_folder_filter({"s/b"})
    assert model.rowCount() == 2


def test_include_and_exclude_every_card(session, tmp_path):
    """Les actions globales portent sur tout le jeu, pas sur le filtre affiché."""
    session.set_cards(card_set_in(tmp_path, {"s/a": ["1", "2"], "s/b": ["3"]}),
                      str(tmp_path))
    everything = [card.index for card in session.card_set]

    session.set_excluded(everything, True)
    assert session.selected_count == 0
    session.set_excluded(everything, False)
    assert session.selected_count == 3


def test_loading_another_folder_forgets_the_links(session, tmp_path):
    """Les liens portent des indices : conservés d'un dossier à l'autre, ils
    désigneraient d'autres cartes sans que rien ne le signale."""
    session.set_cards(card_set_in(tmp_path, {"a": ["x", "y", "z"]}), str(tmp_path))
    session.add_link(Link(cards=(0, 1)))
    assert len(session.links) == 1

    other = tmp_path / "autre"
    session.start_loading(str(other))
    assert len(session.links) == 0


@pytest.fixture
def no_background_thread(monkeypatch):
    """Neutralise le fil de chargement.

    `CardsStep.load` démarre un vrai QThread. Laissé en vie, il survit à la fin du
    test et Qt abandonne le processus (« QThread: Destroyed while thread is still
    running ») : une suite qui plante par intermittence. Ces tests n'ont besoin que
    de la logique de bascule, pas du chargement.
    """
    from pokemon_mosaic.ui import cards_step

    monkeypatch.setattr(cards_step, "start_loading",
                        lambda *args, **kwargs: (None, None))


def test_a_failed_load_leaves_the_previous_work_intact(qt_app, tmp_path,
                                                       no_background_thread):
    """Choisir par erreur un dossier sans images effaçait cartes, sélection ET
    liens avant même que le dossier soit lu, alors que le message se contentait
    d'annoncer un échec de chargement. Sans confirmation ni annulation.
    """
    from pokemon_mosaic.ui.cards_step import CardsStep
    from pokemon_mosaic.ui.session import Session

    session = Session()
    session.set_cards(card_set_in(tmp_path, {"a": list("abcdef")}), str(tmp_path))
    session.set_excluded([0, 1], True)
    session.add_link(Link(cards=(2, 3)))

    step = CardsStep(session)
    empty = tmp_path / "sans_images"
    empty.mkdir()
    step.load(str(empty))
    step._on_failed("Aucune image trouvée")

    assert session.total_cards == 6
    assert session.selected_count == 4
    assert len(session.links) == 1


def test_a_successful_load_does_replace_the_previous_work(qt_app, tmp_path,
                                                          no_background_thread):
    """Le pendant : une fois le premier lot acquis, l'ancienne session cède."""
    from pokemon_mosaic.ui.cards_step import CardsStep
    from pokemon_mosaic.ui.session import Session

    session = Session()
    first = card_set_in(tmp_path / "un", {"a": list("abc")})
    session.set_cards(first, str(tmp_path / "un"))
    session.add_link(Link(cards=(0, 1)))

    step = CardsStep(session)
    second = card_set_in(tmp_path / "deux", {"b": list("xy")})
    step.load(str(tmp_path / "deux"))
    step._on_folder_loaded("b", second.cards)

    assert session.total_cards == 2
    assert len(session.links) == 0


def test_closing_during_a_load_stops_the_thread(qt_app, tmp_path):
    """Détruire un QThread encore actif fait abandonner le processus par Qt.
    Fermer la fenêtre pendant les ~4 s de chargement doit donc l'interrompre.
    """
    from pokemon_mosaic.cards import VALID_EXTENSIONS  # noqa: F401
    from pokemon_mosaic.ui.cards_step import CardsStep
    from pokemon_mosaic.ui.session import Session

    folder = tmp_path / "beaucoup"
    folder.mkdir()
    card_set_in(folder, {"a": [str(i) for i in range(3)]})

    step = CardsStep(Session())
    step.load(str(folder))
    step.shutdown()

    assert step._thread is None and step._worker is None


def test_shutdown_is_safe_without_any_load(qt_app):
    from pokemon_mosaic.ui.cards_step import CardsStep
    from pokemon_mosaic.ui.session import Session

    CardsStep(Session()).shutdown()   # ne doit pas lever


def test_the_warnings_reach_the_session_card_set(qt_app, tmp_path):
    """La session tient un `CardSet` à elle, rempli lot par lot, et non celui
    que le chargeur a produit. Sans report, `has_warnings` y serait toujours
    faux alors que le chargement en a relevé."""
    from pokemon_mosaic.cards import SizeWarning
    from pokemon_mosaic.ui.session import Session

    charge = card_set_in(tmp_path, {"s": ["a", "b"]})
    charge.odd_sizes = [SizeWarning(size=(717, 1000), count=1)]
    charge.unreadable = ["casse.webp : illisible"]

    session = Session()
    session.set_cards(charge, str(tmp_path))

    assert session.card_set.has_warnings
    assert session.card_set.odd_sizes[0].size == (717, 1000)
    assert session.card_set.unreadable == ["casse.webp : illisible"]


# --- Agencements mis de côté ------------------------------------------------

def test_saving_fills_the_first_free_slot(session, tmp_path):
    jeu = card_set_in(tmp_path, {"s": ["a", "b"]})
    grille = np.array([[0, 1]])

    assert session.save_grid(grille, jeu, iteration=10, score=1.5) == 0
    assert session.save_grid(grille, jeu, iteration=20, score=1.2) == 1
    session.remove_saved(0)
    assert session.save_grid(grille, jeu, iteration=30, score=1.0) == 0, (
        "la case libérée doit resservir"
    )
    assert session.saved_count() == 2
    assert session.first_saved() == 0


def test_a_slot_keeps_its_rank_when_a_neighbour_is_emptied(session, tmp_path):
    """La case 3 reste la case 3 : une colonne qui se réordonne sous la souris
    ferait cliquer sur autre chose que ce qu'on visait."""
    jeu = card_set_in(tmp_path, {"s": ["a", "b"]})
    grille = np.array([[0, 1]])
    for numero in range(3):
        session.save_grid(grille, jeu, iteration=numero, score=0.0)

    session.remove_saved(1)

    assert session.saved[1] is None
    assert session.saved[2].iteration == 2
    assert session.first_saved() == 0


def test_the_arrangement_beyond_the_last_slot_is_refused(session, tmp_path):
    """Rien n'est écrasé sans qu'on l'ait demandé : l'utilisateur retire
    lui-même la case dont il ne veut plus."""
    from pokemon_mosaic.ui.session import MAX_SAVED

    jeu = card_set_in(tmp_path, {"s": ["a", "b"]})
    grille = np.array([[0, 1]])
    for numero in range(MAX_SAVED):
        assert session.save_grid(grille, jeu, iteration=numero, score=0.0) is not None

    assert session.save_grid(grille, jeu, iteration=99, score=0.0) is None
    assert session.saved_count() == MAX_SAVED
    assert [place.iteration for place in session.saved] == list(range(MAX_SAVED))


def test_the_saved_grid_is_a_copy(session, tmp_path):
    """Celle de la timeline continue de vivre : une reprise de calcul la
    réécrirait sous nos yeux."""
    jeu = card_set_in(tmp_path, {"s": ["a", "b"]})
    grille = np.array([[0, 1]])
    session.save_grid(grille, jeu, iteration=1, score=0.0)

    grille[0, 0] = 42

    assert session.saved[0].grid[0, 0] == 0


def test_saving_and_removing_announce_themselves(session, tmp_path):
    jeu = card_set_in(tmp_path, {"s": ["a", "b"]})
    vus = []
    session.saved_changed.connect(lambda: vus.append(True))

    session.save_grid(np.array([[0, 1]]), jeu, iteration=1, score=0.0)
    session.remove_saved(0)
    session.remove_saved(0)          # déjà vide : rien à annoncer

    assert len(vus) == 2
