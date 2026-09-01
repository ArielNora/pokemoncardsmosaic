"""Tests de l'export : mise en page, panneaux, chevauchement, formats."""

import os
import re

import numpy as np
import pytest
from test_scoring import make_cards

from pokemon_mosaic.cards import CardSet
from pokemon_mosaic.export import (
    ExportCancelled,
    PosterSettings,
    export_poster,
    panel_paths,
    plan_poster,
    render_panels,
)
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

def test_columns_need_not_divide_into_panels():
    """⚠️ Plusieurs feuilles, c'est **une seule surface**. Le calcul découpait la
    grille par feuille et exigeait que les colonnes s'y divisent, pour que la
    coupe tombe sur un bord de carte. Des feuilles côte à côte ne sont qu'une
    façon d'avoir plus de place : la coupe tombe où elle tombe."""
    settings = PosterSettings(paper="A4", panels=2, dpi=72)
    plan = plan_poster(small_grid(5, 4), card_set(20), settings)
    assert plan.cols == 5


def test_a_second_sheet_lets_the_cards_grow():
    """Une grille large et courte est bornée par la largeur : lui donner une
    feuille de plus, c'est en mettre moins par feuille, donc de plus grandes."""
    seule = plan_poster(small_grid(10, 2), card_set(20),
                        PosterSettings(paper="A4", panels=1, dpi=72))
    deux = plan_poster(small_grid(10, 2), card_set(20),
                       PosterSettings(paper="A4", panels=2, dpi=72))
    assert deux.cards_per_panel < seule.cards_per_panel
    assert deux.card_px[0] > seule.card_px[0]


def test_a_cut_never_falls_on_a_card():
    """⚠️ **La règle qui tient tout.** Chaque feuille repart de son propre bord :
    les cartes ne se suivent pas d'une feuille à l'autre en ignorant la coupe."""
    for panneaux in (1, 2, 3, 4, 5):
        for cols, rows in ((7, 3), (21, 21), (5, 4), (13, 9)):
            reglages = PosterSettings(paper="A5", panels=panneaux, dpi=72)
            plan = plan_poster(small_grid(cols, rows), card_set(cols * rows),
                               reglages)
            card_w = plan.card_px[0]
            paper_w = reglages.paper_px[0]
            for feuille in range(1, panneaux):
                coupe = feuille * paper_w
                for col in range(cols):
                    gauche = plan.column_x(col)
                    assert not (gauche < coupe < gauche + card_w), (
                        f"la coupe {coupe} traverse la colonne {col} "
                        f"({panneaux} feuilles, {cols}×{rows})")


def test_every_column_stays_on_the_paper():
    """Une colonne poussée hors des feuilles disponibles sortirait du poster."""
    for panneaux in (1, 2, 3):
        reglages = PosterSettings(paper="A5", panels=panneaux, dpi=72)
        plan = plan_poster(small_grid(11, 4), card_set(44), reglages)
        dernier = plan.column_x(plan.cols - 1) + plan.card_px[0]
        assert dernier <= plan.total_px[0], (panneaux, dernier, plan.total_px)


def test_the_grid_is_flush_with_the_left_edge():
    """La place en trop est ce qu'apporte la feuille suivante : elle doit se
    voir d'un bloc, du côté où l'on ajoutera la prochaine."""
    plan = plan_poster(small_grid(4, 4), card_set(16),
                       PosterSettings(paper="A4", panels=2, dpi=72))
    assert plan.margin_px[0] == 0
    assert plan.margin_px[1] >= 0, "la marge verticale, elle, reste centrée"


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
    settings = PosterSettings(paper="A4", panels=2, panel_rows=2, dpi=72)
    plan = plan_poster(small_grid(4, 4), card_set(16), settings)
    paper_w, paper_h = settings.paper_px
    assert plan.panel_bounds(0) == (0, 0, paper_w, paper_h)
    assert plan.panel_bounds(1) == (paper_w, 0, 2 * paper_w, paper_h)
    # Les feuilles se lisent de gauche à droite, ligne par ligne.
    assert plan.panel_bounds(2) == (0, paper_h, paper_w, 2 * paper_h)
    assert plan.panel_bounds(3) == (paper_w, paper_h, 2 * paper_w, 2 * paper_h)


def test_overlap_extends_panels_on_their_inner_edges_only():
    settings = PosterSettings(paper="A4", panels=2, panel_rows=2, dpi=72,
                              overlap_mm=10)
    plan = plan_poster(small_grid(4, 4), card_set(16), settings)
    overlap = settings.overlap_px
    paper_w, paper_h = settings.paper_px
    assert plan.panel_bounds(0) == (0, 0, paper_w + overlap, paper_h + overlap)
    assert plan.panel_bounds(3) == (paper_w - overlap, paper_h - overlap,
                                    2 * paper_w, 2 * paper_h)


def test_each_sheet_row_restarts_at_its_own_top_edge():
    """⚠️ La règle des colonnes vaut pour les lignes : une coupe horizontale ne
    coupe pas plus une carte qu'une coupe verticale."""
    settings = PosterSettings(paper="A4", panels=1, panel_rows=2, dpi=72)
    plan = plan_poster(small_grid(2, 8), card_set(16), settings)
    paper_h = settings.paper_px[1]
    par_feuille = plan.rows_per_panel
    assert 1 <= par_feuille < 8, "les huit lignes se répartissent"

    # La dernière ligne d'une feuille tient sur elle ; la suivante recommence
    # au bord haut de la feuille d'en dessous.
    derniere = plan.row_y(par_feuille - 1) + plan.card_px[1]
    assert derniere <= paper_h
    assert plan.row_y(par_feuille) == paper_h


def test_no_card_ever_straddles_a_sheet_edge():
    """⚠️ **La règle qui tient tout**, vérifiée sur le plan lui-même et dans les
    deux sens : une carte posée à `column_x` / `row_y` tient tout entière sur la
    feuille où elle commence."""
    for panneaux in (1, 3, 5):
        for lignes in (1, 2, 3):
            for cols, rows in ((7, 3), (13, 9), (4, 20)):
                settings = PosterSettings(paper="A5", panels=panneaux,
                                          panel_rows=lignes, dpi=150)
                plan = plan_poster(small_grid(cols, rows),
                                   card_set(cols * rows), settings)
                paper_w, paper_h = settings.paper_px
                card_w, card_h = plan.card_px
                cas = (panneaux, lignes, cols, rows)
                for col in range(cols):
                    assert plan.column_x(col) % paper_w + card_w <= paper_w, cas
                for row in range(rows):
                    debut = plan.margin_px[1] + plan.row_y(row)
                    assert debut % paper_h + card_h <= paper_h, cas


def test_the_files_say_which_sheet_goes_where():
    """Sur plusieurs lignes, un numéro seul ne dirait plus où coller quoi."""
    assert panel_paths("/x/poster.png", 1, 1) == ["/x/poster.png"]
    assert panel_paths("/x/poster.png", 2) == ["/x/poster_1of2.png",
                                               "/x/poster_2of2.png"]
    noms = panel_paths("/x/poster.png", 2, 2)
    assert noms == ["/x/poster_l1c1sur2x2.png", "/x/poster_l1c2sur2x2.png",
                    "/x/poster_l2c1sur2x2.png", "/x/poster_l2c2sur2x2.png"]


def test_the_poster_is_as_tall_as_its_sheet_rows():
    settings = PosterSettings(paper="A5", panels=3, panel_rows=2, dpi=72)
    plan = plan_poster(small_grid(4, 4), card_set(16), settings)
    paper_w, paper_h = settings.paper_px
    assert plan.total_px == (paper_w * 3, paper_h * 2)
    assert settings.panel_count == 6


# --- Rendu ----------------------------------------------------------------

def test_one_image_per_sheet_including_rows():
    settings = PosterSettings(paper="A6", panels=2, panel_rows=2, dpi=72)
    images = render_panels(small_grid(4, 4), card_set(16), settings,
                           full_resolution=False)
    assert len(images) == 4
    for image in images:
        assert image.size == settings.paper_px


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


def test_a_grid_of_sheets_writes_one_file_per_sheet(tmp_path):
    """Six feuilles, six fichiers, chacun nommé par sa place dans le mur."""
    settings = PosterSettings(paper="A6", panels=3, panel_rows=2, dpi=72)
    written = export_poster(
        small_grid(6, 6), card_set(36), settings,
        str(tmp_path / "poster.png"), full_resolution=False,
    )
    assert len(written) == 6
    assert [os.path.basename(w) for w in written][:2] == [
        "poster_l1c1sur2x3.png", "poster_l1c2sur2x3.png"]
    from PIL import Image

    for chemin in written:
        with Image.open(chemin) as image:
            assert image.size == settings.paper_px


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


def test_a_card_straddling_the_cut_is_written_on_both_panels(tmp_path):
    """La coupe peut désormais traverser une carte : chaque panneau doit en
    porter sa part, sans trou ni doublon."""
    settings = PosterSettings(paper="A6", panels=3, dpi=72)
    ecrits = export_poster(small_grid(4, 4), card_set(16), settings,
                           str(tmp_path / "poster.png"), full_resolution=False)
    assert len(ecrits) == 3

    from PIL import Image

    plan = plan_poster(small_grid(4, 4), card_set(16), settings)
    largeurs = [Image.open(chemin).width for chemin in ecrits]
    assert sum(largeurs) == plan.total_px[0], "les panneaux doivent recouvrir tout"


# --- Progression, annulation, écriture panneau par panneau -----------------

def test_panel_paths_names_each_panel():
    assert panel_paths("/tmp/poster.png", 1) == ["/tmp/poster.png"]
    assert panel_paths("/tmp/poster.png", 2) == ["/tmp/poster_1of2.png",
                                                 "/tmp/poster_2of2.png"]


def test_panel_paths_refuses_an_unknown_format():
    with pytest.raises(ValueError, match="Format non géré"):
        panel_paths("/tmp/poster.tiff", 1)


def test_each_panel_is_written_before_the_next_is_rendered(tmp_path):
    """Le module promet de ne jamais tenir le poster entier en mémoire : rendre
    les deux panneaux avant d'écrire quoi que ce soit trahirait cette promesse."""
    seen = []
    export_poster(
        small_grid(4, 4), card_set(16), PosterSettings(paper="A5", dpi=72, panels=2),
        str(tmp_path / "poster.png"), full_resolution=False,
        on_progress=lambda panel, total, target: seen.append(
            (panel, sorted(p.name for p in tmp_path.glob("*.png")))
        ),
    )
    # Au démarrage du second panneau, le premier est déjà sur le disque.
    assert seen[0] == (0, [])
    assert seen[1] == (1, ["poster_1of2.png"])
    assert seen[2][0] == 2 and len(seen[2][1]) == 2


def test_a_cancelled_export_leaves_no_file_behind(tmp_path):
    """Un poster à moitié rendu ne se distingue pas d'un poster fini au moment
    de l'envoyer à l'imprimeur."""
    written_before_cancelling = []
    calls = []

    def cancel_during_the_second_panel():
        calls.append(1)
        # Le contrôle a lieu à chaque ligne : 4 lignes pour le premier panneau,
        # donc le 6e appel tombe au milieu du second, le premier étant écrit.
        if len(calls) == 6:
            written_before_cancelling.extend(p.name for p in tmp_path.glob("*.png"))
            return True
        return False

    with pytest.raises(ExportCancelled):
        export_poster(
            small_grid(4, 4), card_set(16),
            PosterSettings(paper="A5", dpi=72, panels=2),
            str(tmp_path / "poster.png"), full_resolution=False,
            check_cancelled=cancel_during_the_second_panel,
        )
    # Le test ne vaut que si un fichier existait bel et bien au moment de l'arrêt.
    assert written_before_cancelling == ["poster_1of2.png"]
    assert list(tmp_path.glob("*.png")) == []


def test_an_export_that_is_never_cancelled_writes_everything(tmp_path):
    written = export_poster(
        small_grid(4, 4), card_set(16), PosterSettings(paper="A5", dpi=72, panels=2),
        str(tmp_path / "poster.png"), full_resolution=False,
        check_cancelled=lambda: False,
    )
    assert len(written) == 2
    assert all(os.path.exists(path) for path in written)
