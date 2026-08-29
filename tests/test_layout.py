"""Tests de la mise en page : ajustement au format, cases vides, suggestions."""

import pytest

from pokemon_mosaic.layout import (
    GridFit,
    card_pixel_size,
    distribute_empty_cells,
    max_useful_dpi,
    paper_size_mm,
    suggest_grids,
)

CARD_ASPECT = 713 / 984      # ~0.7246
A_SERIES_PORTRAIT = 1 / 2**0.5   # ~0.7071


def test_paper_orientation():
    assert paper_size_mm("A4") == (210, 297)
    assert paper_size_mm("A4", landscape=True) == (297, 210)


def test_unknown_paper_format_is_rejected():
    with pytest.raises(ValueError, match="Format inconnu"):
        paper_size_mm("B3")


def test_grid_fit_reports_missing_cards():
    fit = GridFit(cols=17, rows=17, card_count=281)
    assert fit.cells == 289
    assert fit.empty_cells == 8
    assert fit.surplus == 0
    assert "8 cartes" in fit.message()


def test_grid_fit_reports_surplus():
    fit = GridFit(cols=16, rows=16, card_count=281)
    assert fit.surplus == 25
    assert fit.empty_cells == 0
    assert "retirez 25" in fit.message().lower()


def test_grid_fit_exact():
    fit = GridFit(cols=17, rows=17, card_count=289)
    assert fit.fits_exactly
    assert "exactement" in fit.message()


def test_square_grids_are_suggested_for_portrait_sheets():
    """Une grille carrée a le rapport d'une carte : c'est l'ajustement de référence."""
    found = suggest_grids(281, CARD_ASPECT, A_SERIES_PORTRAIT)
    shapes = {(s.cols, s.rows) for s in found}
    assert (17, 17) in shapes
    best = next(s for s in found if (s.cols, s.rows) == (17, 17))
    assert best.card_delta == 8
    assert best.aspect_error == pytest.approx(0.0247, abs=1e-3)


def test_rectangular_grids_are_suggested_too():
    """⚠️ Le format en filtre ne laissait passer que des carrés : une carte fait
    0,725 de rapport, une feuille A 0,707, donc la grille idéale a toujours
    autant de lignes que de colonnes à 2,5 % près. Vingt cartes n'avaient alors
    aucune grille de vingt cases."""
    found = suggest_grids(20, CARD_ASPECT, A_SERIES_PORTRAIT)
    assert (found[0].cols, found[0].rows) == (4, 5)
    assert found[0].card_delta == 0
    assert any(s.cols != s.rows for s in found)


def test_no_suggestion_stretches_into_a_strip():
    """Au-delà de trois cases d'écart la mosaïque devient une bande, et l'image
    n'occupe plus qu'un ruban de la feuille."""
    for count in (20, 133, 281, 441):
        found = suggest_grids(count, CARD_ASPECT, A_SERIES_PORTRAIT)
        assert found, f"aucune grille proposée pour {count} cartes"
        assert all(abs(s.cols - s.rows) <= 3 for s in found), count


def test_ten_suggestions_are_offered():
    assert len(suggest_grids(441, CARD_ASPECT, A_SERIES_PORTRAIT)) == 10


def test_the_side_difference_is_adjustable():
    """Le seuil est un paramètre : le durcir doit réellement resserrer la liste."""
    carres = suggest_grids(281, CARD_ASPECT, A_SERIES_PORTRAIT, max_difference=0)
    assert all(s.cols == s.rows for s in carres)


def test_no_suggestion_is_offered_twice():
    found = suggest_grids(441, CARD_ASPECT, A_SERIES_PORTRAIT)
    shapes = [(s.cols, s.rows) for s in found]
    assert len(shapes) == len(set(shapes))


def test_the_aspect_error_breaks_ties_between_equal_grids():
    """20×22 et 22×20 logent le même nombre de cartes ; sur une feuille en
    portrait, c'est celle qui a le plus de lignes qui doit passer devant."""
    found = suggest_grids(441, CARD_ASPECT, A_SERIES_PORTRAIT)
    rang = {(s.cols, s.rows): i for i, s in enumerate(found)}
    assert rang[(20, 22)] < rang[(22, 20)]


def test_panel_split_forces_even_columns():
    """Avec 2 panneaux, la coupe doit tomber sur un bord de carte."""
    found = suggest_grids(281, CARD_ASPECT, 2**0.5, panels=2)
    assert found, "aucune grille proposée"
    assert all(s.cols % 2 == 0 for s in found)


def test_suggestions_prefer_matching_the_card_count():
    found = suggest_grids(281, CARD_ASPECT, A_SERIES_PORTRAIT)
    deltas = [abs(s.card_delta) for s in found]
    assert deltas == sorted(deltas)


def test_empty_cells_are_spread_not_clustered():
    cells = distribute_empty_cells((14, 20), 8)
    assert len(cells) == len(set(cells)) == 8
    rows = {r for r, _ in cells}
    assert len(rows) >= 6, f"les trous se concentrent sur trop peu de lignes : {cells}"


@pytest.mark.parametrize(
    "rows,cols,count",
    [(12, 24, 8), (17, 17, 9), (14, 20, 12), (12, 24, 24), (10, 10, 5)],
)
def test_empty_cells_never_line_up_in_columns(rows, cols, count):
    """Un espacement à pas constant alignait les trous sur deux colonnes.

    Cas typique : 288 cases et 8 trous donnent un pas de 36 = 24 + 12, et tous les
    trous retombent sur les colonnes 6 et 18. Invisible dans un test qui ne regarde
    que les lignes, mais flagrant sur le poster imprimé.
    """
    cells = distribute_empty_cells((rows, cols), count)
    assert len(cells) == len(set(cells)) == count

    # Référence : le nombre de colonnes distinctes qu'on obtiendrait en plaçant les
    # trous au hasard. On ne peut pas exiger mieux — avec 24 trous sur 24 colonnes,
    # les collisions sont inévitables — mais l'aliasing en donnait 4 fois moins.
    expected = cols * (1 - (1 - 1 / cols) ** count)
    distinct_columns = len({c for _, c in cells})
    assert distinct_columns >= 0.6 * expected, (
        f"les trous se concentrent sur {distinct_columns} colonne(s) "
        f"(attendu ~{expected:.1f}) : {cells}"
    )


def test_empty_cells_avoid_the_naive_column_aliasing():
    """Le cas exact qui a produit une colonne de blancs sur un poster réel."""
    cells = distribute_empty_cells((12, 24), 8)
    columns = [c for _, c in cells]
    assert len(set(columns)) >= 6, f"colonnes utilisées : {sorted(set(columns))}"


def test_empty_cells_stay_inside_the_grid():
    cells = distribute_empty_cells((5, 6), 7)
    assert all(0 <= r < 5 and 0 <= c < 6 for r, c in cells)


def test_empty_cells_cannot_exceed_capacity():
    with pytest.raises(ValueError, match="cases vides demandées"):
        distribute_empty_cells((3, 3), 10)


def test_no_empty_cells_requested():
    assert distribute_empty_cells((5, 5), 0) == []


def test_card_pixel_size_preserves_aspect_and_fits():
    paper = paper_size_mm("A2")
    w, h = card_pixel_size(paper, cols=17, rows=17, card_aspect=CARD_ASPECT, dpi=300)
    assert w / h == pytest.approx(CARD_ASPECT, abs=1e-2)
    # L'image doit tenir dans la feuille, sans jamais la déborder.
    assert 17 * w <= round(paper[0] / 25.4 * 300) + 17
    assert 17 * h <= round(paper[1] / 25.4 * 300) + 17


def test_max_useful_dpi_matches_measured_values():
    """Repères calculés dans SPEC.md §4, pour une grille 17x17 de cartes 713 px."""
    assert max_useful_dpi(paper_size_mm("A2"), 17, 713) == pytest.approx(733, abs=2)
    assert max_useful_dpi(paper_size_mm("A0"), 17, 713) == pytest.approx(366, abs=2)


@pytest.mark.parametrize("paper,cols,rows", [
    ("A2", 17, 17), ("A1", 30, 20), ("A3", 17, 17), ("A0", 100, 70), ("A4", 7, 9),
])
def test_the_grid_never_overflows_the_sheet(paper, cols, rows):
    """`round()` pouvait arrondir vers le haut : la largeur totale dépassait celle
    de la feuille, la marge devenait négative et le poster était rogné, alors que
    le module promet « ni déformation ni rognage »."""
    from pokemon_mosaic.layout import mm_to_pixels

    sheet = paper_size_mm(paper)
    card_w, card_h = card_pixel_size(sheet, cols, rows, CARD_ASPECT, dpi=300)
    assert cols * card_w <= mm_to_pixels(sheet[0], 300), "débordement en largeur"
    assert rows * card_h <= mm_to_pixels(sheet[1], 300), "débordement en hauteur"


# --- Sous-ensembles renumérotés -------------------------------------------

def _demo_card_set(n):
    import numpy as np

    from pokemon_mosaic.cards import Card, CardSet

    rng = np.random.default_rng(0)
    cards = []
    for i in range(n):
        card = Card(path=f"/fake/{i}.png", index=i,
                    thumbnail=np.zeros((4, 4, 3), np.uint8))
        card.top, card.bottom, card.left, card.right = (rng.random(3) * 255
                                                        for _ in range(4))
        cards.append(card)
    return CardSet(cards=cards, full_size=(713, 984), thumb_size=(178, 246))


def test_subset_renumbers_from_zero():
    subset = _demo_card_set(6).subset([1, 3, 5])
    assert [card.index for card in subset] == [0, 1, 2]


def test_subset_remembers_the_original_indices():
    """L'export doit pouvoir remonter à la sélection de l'utilisateur."""
    subset = _demo_card_set(6).subset([1, 3, 5])
    assert [card.source_index for card in subset] == [1, 3, 5]


def test_subset_keeps_the_right_cards():
    original = _demo_card_set(6)
    subset = original.subset([4, 1])
    assert [card.path for card in subset] == ["/fake/1.png", "/fake/4.png"]


def test_subset_shares_thumbnails_rather_than_copying_them():
    original = _demo_card_set(4)
    subset = original.subset([2])
    assert subset[0].thumbnail is original.cards[2].thumbnail


def test_a_subset_can_be_scored_and_optimized():
    """Le cas exact que l'étape 4 déclenchera : n'optimiser qu'une sélection."""
    import random

    from pokemon_mosaic.optimize import build_initial_grid, optimize_grid
    from pokemon_mosaic.scoring import EdgeDistances

    subset = _demo_card_set(12).subset([0, 2, 4, 6, 8, 10])
    distances = EdgeDistances(subset.cards)
    grid = build_initial_grid(subset, shape=(3, 2), rng=random.Random(0))
    optimize_grid(grid, distances, iterations=500, rng=random.Random(0))
    assert sorted(int(v) for v in grid.flatten()) == list(range(6))


def test_subset_of_a_subset_keeps_the_first_origin():
    original = _demo_card_set(8)
    once = original.subset([1, 3, 5, 7])
    twice = once.subset([0, 2])
    assert [card.source_index for card in twice] == [1, 5]


# --- Chargement réel depuis le disque --------------------------------------

def _write_png(path, size=(20, 30), colour=(120, 60, 200)):
    from PIL import Image

    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, colour).save(path)


def test_load_cards_reads_a_real_folder(tmp_path):
    """Aucun test n'exerçait load_cards de bout en bout : une régression de
    signature est passée à travers 225 tests avant d'être vue à l'exécution."""
    from pokemon_mosaic.cards import load_cards

    for index in range(3):
        _write_png(tmp_path / "serie" / f"{index}.png")
    cards = load_cards(str(tmp_path))

    assert len(cards) == 3
    assert [card.index for card in cards] == [0, 1, 2]
    assert cards.full_size == (20, 30)
    assert all(card.top is not None for card in cards)


def test_load_cards_accepts_webp(tmp_path):
    """C'est le format du miroir, donc celui de tout jeu récupéré par
    `scripts/fetch_cards.py` : sans lui, le chargement ne trouve aucune carte."""
    from PIL import Image

    from pokemon_mosaic.cards import load_cards

    folder = tmp_path / "a1-jeu"
    folder.mkdir()
    for i in range(3):
        Image.new("RGB", (60, 84), (i * 40, 100, 200)).save(folder / f"c{i}.webp")
    cards = load_cards(str(tmp_path))
    assert len(cards) == 3
    assert cards.full_size == (60, 84)


def test_load_cards_reports_folders_and_progress(tmp_path):
    from pokemon_mosaic.cards import load_cards

    _write_png(tmp_path / "a" / "1.png")
    _write_png(tmp_path / "b" / "2.png")
    folders, steps = [], []
    load_cards(str(tmp_path),
               on_folder=lambda name, cards: folders.append((name, len(cards))),
               progress=lambda done, total: steps.append((done, total)))

    assert [count for _, count in folders] == [1, 1]
    assert steps == [(1, 2), (2, 2)]


def test_load_cards_can_be_cancelled_during_the_header_pass(tmp_path):
    """La première passe est purement séquentielle : sans point d'annulation,
    un chargement lancé sur une grande arborescence serait impossible à arrêter.
    """
    from pokemon_mosaic.cards import load_cards

    for index in range(10):
        _write_png(tmp_path / f"{index}.png")

    seen = []

    def stop():
        seen.append(1)
        if len(seen) > 3:
            raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        load_cards(str(tmp_path), check_cancelled=stop)
    assert len(seen) == 4, "l'arrêt doit survenir dès la lecture des en-têtes"


def test_load_cards_excludes_by_path_fragment(tmp_path):
    from pokemon_mosaic.cards import load_cards

    _write_png(tmp_path / "a" / "garder.png")
    _write_png(tmp_path / "a" / "jeter.png")
    cards = load_cards(str(tmp_path), exclude=("jeter",))
    assert [card.name for card in cards] == ["garder"]


def test_load_cards_settles_on_a_real_card_size(tmp_path):
    """Le format commun est celui **d'une carte réelle**, jamais un couple
    composé de la largeur minimale et de la hauteur minimale prises séparément :
    734×1024 et 717×1050 donnaient 717×1024, que personne ne portait, et toutes
    les cartes s'en trouvaient déformées de 2,3 %.

    À égalité de fréquence — ici une carte de chaque taille — c'est la plus
    petite surface qui l'emporte : mieux vaut réduire qu'agrandir.
    """
    from pokemon_mosaic.cards import load_cards

    _write_png(tmp_path / "grand.png", size=(40, 60))
    _write_png(tmp_path / "petit.png", size=(20, 30))
    cards = load_cards(str(tmp_path), scale=1.0)
    assert cards.full_size == (20, 30)
    assert {card.thumbnail.shape[:2] for card in cards} == {(30, 20)}


def test_load_cards_on_an_empty_folder(tmp_path):
    from pokemon_mosaic.cards import load_cards

    assert len(load_cards(str(tmp_path))) == 0


# --- Chemins : en source comme empaqueté -----------------------------------

def test_paths_resolve_inside_the_repository_when_running_from_source():
    from pokemon_mosaic import paths

    racine = paths.resource_dir()
    assert not paths.frozen()
    assert (racine / "pyproject.toml").is_file(), racine
    assert paths.user_data_dir() == racine / "data"
    assert paths.output_dir() == racine / "output"


def test_paths_follow_the_unpacked_resources_once_frozen(tmp_path, monkeypatch):
    """PyInstaller déplie les ressources dans un dossier temporaire qu'il
    désigne par `sys._MEIPASS`. `Path(sys.executable).parent` pointerait sur
    `Contents/MacOS`, où il n'y a ni traductions ni données."""
    from pokemon_mosaic import paths

    monkeypatch.setattr(paths.sys, "frozen", True, raising=False)
    monkeypatch.setattr(paths.sys, "_MEIPASS", str(tmp_path), raising=False)
    assert paths.frozen()
    assert paths.resource_dir() == tmp_path


def test_frozen_data_never_lands_next_to_the_executable(monkeypatch):
    """Un `.app` vit dans `/Applications`, en lecture seule pour l'utilisateur
    courant : y écrire les cartes échouerait."""
    from pathlib import Path

    from pokemon_mosaic import paths

    monkeypatch.setattr(paths.sys, "frozen", True, raising=False)
    monkeypatch.setattr(paths.sys, "_MEIPASS", "/tmp/deplie", raising=False)
    dossier = paths.user_data_dir()
    assert Path.home() in dossier.parents, dossier
    assert "/tmp/deplie" not in str(dossier)


def test_the_output_folder_is_not_guessed_once_packaged(monkeypatch):
    """`~/Pictures` n'existe qu'en anglais : un Windows ou un Linux en français
    range dans « Images », et le dossier aurait été créé à côté du bon, sans que
    rien ne le signale. On réclame le chemin plutôt que de deviner."""
    from pokemon_mosaic import paths

    assert paths.output_dir() is not None          # depuis le dépôt : `output/`
    monkeypatch.setattr(paths.sys, "frozen", True, raising=False)
    monkeypatch.setattr(paths.sys, "_MEIPASS", "/tmp/deplie", raising=False)
    assert paths.output_dir() is None
