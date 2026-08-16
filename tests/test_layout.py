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
