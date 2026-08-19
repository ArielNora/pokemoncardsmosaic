"""Tests de l'export : mise en page, panneaux, chevauchement, formats."""

import re

import numpy as np
import pytest
from test_scoring import make_cards

from pokemon_mosaic.cards import CardSet
from pokemon_mosaic.export import PosterSettings, export_poster, plan_poster, render_panels
from pokemon_mosaic.layout import paper_size_mm
from pokemon_mosaic.scoring import EMPTY


def card_set(n, size=(713, 984)):
    cards = make_cards(n)
    thumb = (size[0] // 4, size[1] // 4)
    for card in cards:
        card.thumbnail = np.full((thumb[1], thumb[0], 3), 128, np.uint8)
    return CardSet(cards=cards, full_size=size, thumb_size=thumb)


def small_grid(cols=4, rows=4):
    return np.arange(cols * rows).reshape(rows, cols)


# --- Mise en page ---------------------------------------------------------

def test_columns_must_divide_into_panels():
    """La coupe ne doit jamais traverser une carte."""
    settings = PosterSettings(paper="A4", panels=2, dpi=72)
    with pytest.raises(ValueError, match="ne se divisent pas"):
        plan_poster(small_grid(5, 4), card_set(20), settings)


def test_cards_keep_their_aspect_ratio():
    plan = plan_poster(small_grid(4, 4), card_set(16), PosterSettings(paper="A4", dpi=72))
    card_w, card_h = plan.card_px
    assert card_w / card_h == pytest.approx(713 / 984, abs=0.01)


def test_content_fits_inside_the_paper():
    settings = PosterSettings(paper="A3", dpi=150)
    plan = plan_poster(small_grid(4, 4), card_set(16), settings)
    paper_w, paper_h = settings.paper_px
    assert 4 * plan.card_px[0] <= paper_w
    assert 4 * plan.card_px[1] <= paper_h
    assert plan.margin_px[0] >= 0 and plan.margin_px[1] >= 0


def test_dpi_beyond_the_useful_ceiling_is_flagged():
    settings = PosterSettings(paper="A0", dpi=1200)
    plan = plan_poster(small_grid(4, 4), card_set(16), settings)
    assert any("maximum utile" in w for w in plan.warnings)


def test_reasonable_dpi_raises_no_dpi_warning():
    settings = PosterSettings(paper="A4", dpi=300)
    plan = plan_poster(small_grid(4, 4), card_set(16), settings)
    assert not any("maximum utile" in w for w in plan.warnings)


def test_panel_bounds_cover_the_whole_poster_without_gaps():
    settings = PosterSettings(paper="A4", panels=2, dpi=72)
    plan = plan_poster(small_grid(4, 4), card_set(16), settings)
    paper_w = settings.paper_px[0]
    assert plan.panel_bounds(0) == (0, paper_w)
    assert plan.panel_bounds(1) == (paper_w, 2 * paper_w)


def test_overlap_extends_panels_on_their_inner_edges_only():
    settings = PosterSettings(paper="A4", panels=2, dpi=72, overlap_mm=10)
    plan = plan_poster(small_grid(4, 4), card_set(16), settings)
    overlap = settings.overlap_px
    paper_w = settings.paper_px[0]
    assert plan.panel_bounds(0) == (0, paper_w + overlap)
    assert plan.panel_bounds(1) == (paper_w - overlap, 2 * paper_w)


# --- Rendu ----------------------------------------------------------------

def test_one_image_per_panel_at_paper_size():
    settings = PosterSettings(paper="A6", panels=2, dpi=72)
    images = render_panels(small_grid(4, 4), card_set(16), settings, full_resolution=False)
    assert len(images) == 2
    for image in images:
        assert image.size == settings.paper_px


def test_overlapping_panels_are_wider_than_the_paper():
    settings = PosterSettings(paper="A6", panels=2, dpi=72, overlap_mm=10)
    images = render_panels(small_grid(4, 4), card_set(16), settings, full_resolution=False)
    paper_w = settings.paper_px[0]
    assert all(image.width == paper_w + settings.overlap_px for image in images)


def test_empty_cells_are_painted_in_their_own_colour():
    grid = small_grid(4, 4)
    grid[1, 1] = EMPTY
    settings = PosterSettings(paper="A6", dpi=72, empty_colour=(255, 0, 0))
    plan = plan_poster(grid, card_set(16), settings)
    image = render_panels(grid, card_set(16), settings, full_resolution=False)[0]

    card_w, card_h = plan.card_px
    x = plan.margin_px[0] + card_w + card_w // 2
    y = plan.margin_px[1] + card_h + card_h // 2
    assert image.getpixel((x, y)) == (255, 0, 0)


def test_crop_marks_leave_black_pixels_at_the_corners():
    settings = PosterSettings(paper="A6", dpi=72, crop_marks=True)
    plain = render_panels(small_grid(4, 4), card_set(16),
                          PosterSettings(paper="A6", dpi=72), full_resolution=False)[0]
    marked = render_panels(small_grid(4, 4), card_set(16), settings,
                           full_resolution=False)[0]
    assert list(plain.getdata()) != list(marked.getdata())
    assert marked.getpixel((0, 0)) == (0, 0, 0)


# --- Écriture des fichiers ------------------------------------------------

@pytest.mark.parametrize("extension", [".png", ".jpg", ".pdf"])
def test_each_format_is_written(tmp_path, extension):
    settings = PosterSettings(paper="A6", dpi=72)
    written = export_poster(
        small_grid(4, 4), card_set(16), settings,
        str(tmp_path / f"poster{extension}"), full_resolution=False,
    )
    assert len(written) == 1
    assert written[0].endswith(extension)
    assert (tmp_path / f"poster{extension}").stat().st_size > 0


def test_unknown_format_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="Format non géré"):
        export_poster(small_grid(4, 4), card_set(16), PosterSettings(paper="A6", dpi=72),
                      str(tmp_path / "poster.tiff"), full_resolution=False)


def test_panels_are_written_as_numbered_files(tmp_path):
    settings = PosterSettings(paper="A6", panels=2, dpi=72)
    written = export_poster(
        small_grid(4, 4), card_set(16), settings,
        str(tmp_path / "poster.png"), full_resolution=False,
    )
    assert [w.split("/")[-1] for w in written] == ["poster_1of2.png", "poster_2of2.png"]


@pytest.mark.parametrize("paper,dpi", [("A5", 150), ("A4", 300), ("A6", 72)])
def test_pdf_carries_the_physical_page_size(tmp_path, paper, dpi):
    """C'est tout l'intérêt du PDF : l'imprimeur lit des millimètres, pas des pixels."""
    target = tmp_path / "poster.pdf"
    export_poster(small_grid(4, 4), card_set(16), PosterSettings(paper=paper, dpi=dpi),
                  str(target), full_resolution=False)

    # Le MediaBox d'un PDF s'exprime en points (1/72 pouce).
    box = re.search(rb"/MediaBox\s*\[([^\]]*)\]", target.read_bytes())
    assert box, "aucun MediaBox dans le PDF produit"
    _, _, width_pt, height_pt = (float(v) for v in box.group(1).split())

    expected_w, expected_h = paper_size_mm(paper)
    assert width_pt / 72 * 25.4 == pytest.approx(expected_w, abs=0.5)
    assert height_pt / 72 * 25.4 == pytest.approx(expected_h, abs=0.5)


def test_export_refuses_a_grid_that_cannot_be_split(tmp_path):
    settings = PosterSettings(paper="A6", panels=3, dpi=72)
    with pytest.raises(ValueError, match="ne se divisent pas"):
        export_poster(small_grid(4, 4), card_set(16), settings,
                      str(tmp_path / "poster.png"), full_resolution=False)
