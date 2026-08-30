"""Tests de l'export depuis la vue d'exécution : dialogue, travailleur, écran."""

import os

import numpy as np
import pytest
from test_ui_run import card_set, feed


@pytest.fixture
def session(qt_app):
    from pokemon_mosaic.ui.session import Session

    s = Session()
    s.set_cards(card_set(20), "/fake")
    s.set_layout(cols=5, rows=4, paper="A5", dpi=72)
    s.set_algorithm(iterations=2000, snapshot_every=2, use_annealing=False)
    return s


@pytest.fixture
def step(session):
    from pokemon_mosaic.ui.run_step import RunStep

    widget = RunStep(session)
    feed(widget, session)
    return widget, session


def grid_of(step_widget):
    return step_widget.current_grid()


# --- L'écran --------------------------------------------------------------

def test_export_is_refused_before_a_run(session):
    """Il n'y a rien à exporter tant qu'aucun cliché n'existe."""
    from pokemon_mosaic.ui.run_step import RunStep

    widget = RunStep(session)
    assert not widget._export.isEnabled()
    assert widget.current_grid() is None
    widget._open_export()       # ne doit pas lever


def test_export_becomes_available_once_the_run_has_started(step):
    widget, _ = step
    assert widget._export.isEnabled()


def test_the_exported_grid_is_the_one_displayed(step):
    """« Exporter ce cliché » : celui qu'on regarde, pas le dernier calculé."""
    widget, _ = step
    latest = widget.current_grid().copy()
    widget._slider.setValue(0)
    first = widget.current_grid()
    np.testing.assert_array_equal(first, widget._timeline[0].grid)
    assert not np.array_equal(first, latest)


# --- Le dialogue ----------------------------------------------------------

@pytest.fixture
def dialog(step):
    from pokemon_mosaic.ui.export_dialog import ExportDialog

    widget, session = step
    return ExportDialog(session, grid_of(widget), widget._cards)


def test_the_settings_come_from_the_layout_step(dialog, session):
    """Format, orientation et panneaux appartiennent à l'étape 2 : les ressaisir
    ici les laisserait diverger sans que rien ne le signale."""
    session.set_layout(paper="A3", landscape=True, panels=1)
    settings = dialog.settings()
    assert (settings.paper, settings.landscape, settings.panels) == ("A3", True, 1)


def test_a_sheet_without_a_name_still_exports(step):
    """⚠️ Une feuille hors catalogue n'a pas de nom : le seul « paper » aurait
    fait échouer la traduction, ou pire, imprimé un A2 à la place de ce que
    l'écran montrait. Le rappel de mise en page la dit alors en centimètres,
    faute de nom à citer."""
    from pokemon_mosaic.ui.export_dialog import ExportDialog

    widget, session = step
    session.set_layout(paper_size_mm=(300.0, 400.0), landscape=True)
    dialog = ExportDialog(session, grid_of(widget), widget._cards)

    settings = dialog.settings()
    assert settings.paper == ""
    assert settings.paper_mm == (400.0, 300.0)
    assert "40.0 × 30.0 cm" in dialog._layout_recap.text()


def test_the_resolution_is_chosen_here_and_written_to_the_session(dialog, session):
    """⚠️ La finesse était demandée à l'étape 2, avant que la mosaïque n'existe :
    elle n'y changeait rien de visible, et il fallait deviner le poids d'un
    fichier qu'on n'avait pas encore décrit. Elle se choisit devant lui."""
    dialog._dpi.setValue(300)
    assert dialog.settings().dpi == 300
    # Écrite dans la session : les aperçus arrondissent leurs pixels comme
    # l'export, et un préréglage la retrouve.
    assert session.dpi == 300


def test_a_resolution_outside_the_field_bounds_comes_back_corrected(step):
    """Un préréglage écrit à la main peut porter n'importe quoi."""
    from pokemon_mosaic.ui.export_dialog import ExportDialog

    widget, session = step
    session.set_layout(dpi=5000)
    dialog = ExportDialog(session, grid_of(widget), widget._cards)
    assert dialog._dpi.value() == 1200
    assert session.dpi == 1200
    assert dialog.settings().dpi == 1200


def test_the_dialog_owns_the_printing_choices(dialog):
    dialog._overlap.setValue(7.5)
    dialog._crop_marks.setChecked(True)
    settings = dialog.settings()
    assert settings.overlap_mm == 7.5 and settings.crop_marks


def test_changing_the_format_rewrites_the_extension(dialog, tmp_path):
    """Laisser « poster.png » alors que JPEG est choisi écrirait un PNG sans
    le dire : c'est l'extension qui décide du format à l'écriture."""
    dialog._path.setText(str(tmp_path / "poster.png"))
    dialog._format.setCurrentIndex(1)       # JPEG
    assert dialog.path().endswith(".jpg")
    dialog._format.setCurrentIndex(2)       # PDF
    assert dialog.path().endswith(".pdf")


def test_the_dialog_names_the_files_that_will_be_written(step, session, tmp_path):
    """Avec plusieurs panneaux, « poster.png » écrit en réalité deux fichiers
    dont aucun sélecteur ne prononce le nom."""
    from pokemon_mosaic.ui.export_dialog import ExportDialog

    widget, _ = step
    # La géométrie vient de la grille du cliché, pas des réglages de session :
    # une grille de 5 colonnes ne se couperait pas en deux.
    session.set_layout(panels=2)
    dialog = ExportDialog(session, grid_of(widget)[:, :4], widget._cards)
    dialog._path.setText(str(tmp_path / "poster.png"))
    assert "poster_1of2.png" in dialog._files.text()
    assert "poster_2of2.png" in dialog._files.text()


def test_the_dialog_warns_about_an_existing_file(dialog, tmp_path):
    target = tmp_path / "poster.png"
    dialog._path.setText(str(target))
    assert "écrasé" not in dialog._files.text()
    target.write_bytes(b"")
    dialog._path.setText("")                # force un rafraîchissement
    dialog._path.setText(str(target))
    assert "écrasé" in dialog._files.text()


def test_an_odd_column_count_across_panels_is_planned_normally(dialog, session):
    """5 colonnes sur 2 feuilles : la coupe traverse une carte, et c'est admis
    depuis que plusieurs feuilles ne veulent dire que « plus de place »."""
    session.set_layout(cols=5, rows=4, panels=2)
    dialog._update_plan()
    assert "ne se divisent pas" not in dialog._plan_label.text()
    assert dialog._plan is not None


def test_an_impossible_plan_cannot_be_validated(dialog, session, tmp_path,
                                                monkeypatch):
    """Accepter lancerait un fil de fond pour qu'il échoue aussitôt sur l'erreur
    déjà affichée, et l'utilisateur n'en verrait qu'un message fugace.

    Plus aucun réglage de l'écran ne rend le plan impossible depuis que la coupe
    n'est plus contrainte : on fait échouer `plan_poster` à la main pour que le
    garde reste couvert."""
    from PySide6.QtWidgets import QDialog, QDialogButtonBox

    from pokemon_mosaic.ui import export_dialog as module

    dialog._path.setText(str(tmp_path / "poster.png"))
    assert dialog._buttons.button(QDialogButtonBox.Ok).isEnabled()

    def refuse(*_a, **_k):
        raise ValueError("plan impossible")

    monkeypatch.setattr(module, "plan_poster", refuse)
    dialog._update_plan()
    assert "plan impossible" in dialog._plan_label.text()
    assert not dialog._buttons.button(QDialogButtonBox.Ok).isEnabled()
    dialog._try_accept()
    assert dialog.result() != QDialog.Accepted

    # Le plan redevenu calculable rouvre la validation.
    monkeypatch.undo()
    dialog._update_plan()
    assert dialog._buttons.button(QDialogButtonBox.Ok).isEnabled()


def test_an_empty_destination_is_refused(dialog):
    from PySide6.QtWidgets import QDialog

    dialog._path.setText("")
    dialog._try_accept()
    assert dialog.result() != QDialog.Accepted
    assert dialog._warnings.text()


def test_the_jpeg_quality_only_shows_for_jpeg(dialog):
    dialog._format.setCurrentIndex(0)
    assert not dialog._quality.isVisible()
    dialog._format.setCurrentIndex(1)
    dialog.show()
    assert dialog._quality.isVisible()


# --- Le travailleur -------------------------------------------------------

def run_worker(step_widget, path, **kwargs):
    """Exécute l'export dans le fil courant : déterministe et sans QThread."""
    from pokemon_mosaic.export import PosterSettings
    from pokemon_mosaic.ui.exporter import ExportWorker

    worker = ExportWorker(
        grid_of(step_widget), step_widget._cards,
        PosterSettings(paper="A5", dpi=72, **kwargs), path,
        full_resolution=False,
    )
    seen = {"exported": [], "cancelled": [], "failed": [], "progress": []}
    worker.exported.connect(seen["exported"].append)
    worker.cancelled.connect(lambda: seen["cancelled"].append(True))
    worker.failed.connect(seen["failed"].append)
    worker.progress.connect(lambda *args: seen["progress"].append(args))
    return worker, seen


def test_a_single_panel_shows_an_indeterminate_progress(step, tmp_path):
    """Une barre figée à 0 % pendant sept secondes se lit comme un export bloqué."""
    from pokemon_mosaic.export import PosterSettings

    widget, _ = step
    widget._start_export(grid_of(widget), PosterSettings(paper="A5", dpi=72),
                         str(tmp_path / "poster.png"), False)
    assert widget._export_progress.maximum() == 0
    widget.shutdown()

    widget._start_export(grid_of(widget)[:, :4],
                         PosterSettings(paper="A5", dpi=72, panels=2),
                         str(tmp_path / "deux.png"), False)
    assert widget._export_progress.maximum() == 2
    widget.shutdown()


def test_the_worker_writes_the_poster(step, tmp_path):
    widget, _ = step
    worker, seen = run_worker(widget, str(tmp_path / "poster.png"))
    worker.run()
    assert seen["failed"] == [] and seen["cancelled"] == []
    assert [os.path.basename(p) for p in seen["exported"][0]] == ["poster.png"]
    assert (tmp_path / "poster.png").exists()


def test_a_cancelled_worker_reports_it_and_writes_nothing(step, tmp_path):
    widget, _ = step
    worker, seen = run_worker(widget, str(tmp_path / "poster.png"))
    worker.cancel()
    worker.run()
    assert seen["cancelled"] == [True]
    assert seen["exported"] == []
    assert list(tmp_path.glob("*.png")) == []


def test_a_bad_format_is_reported_not_raised(step, tmp_path):
    """Une exception qui s'échappe du slot n'émettrait aucun signal, et
    l'interface attendrait indéfiniment un export qui n'existe plus."""
    widget, _ = step
    worker, seen = run_worker(widget, str(tmp_path / "poster.tiff"))
    worker.run()
    assert seen["exported"] == []
    assert "Format non géré" in seen["failed"][0]


def test_the_screen_returns_to_its_resting_state_after_an_export(step, tmp_path):
    widget, _ = step
    widget._on_exported([str(tmp_path / "poster.png")])
    assert widget._export.isEnabled()
    assert widget._cancel_export.isHidden()
    assert widget._export_progress.isHidden()
    assert widget._export_thread is None


def test_resuming_comes_back_after_the_export(step, tmp_path, monkeypatch):
    """Griser les boutons à part de `can_resume` les laissait éteints après un
    export : plus moyen de prolonger sans toucher au curseur."""
    from pokemon_mosaic.export import PosterSettings
    from pokemon_mosaic.ui import run_step as module

    widget, _ = step
    widget._run_signature = widget._signature()
    widget._update_buttons(running=False)
    widget._slider.setValue(0)
    assert widget._extend.isEnabled() and widget._resume.isEnabled()

    monkeypatch.setattr(module, "start_export",
                        lambda *args, **kwargs: (object(), object()))
    widget._start_export(grid_of(widget), PosterSettings(paper="A5", dpi=72),
                         str(tmp_path / "poster.png"), False)
    assert not widget._extend.isEnabled(), "un export en cours occupe l'écran"
    assert not widget.can_resume()

    widget._on_exported([str(tmp_path / "poster.png")])
    assert widget._extend.isEnabled() and widget._resume.isEnabled()
    assert widget.can_resume()


def test_the_card_size_and_gap_reach_the_export(dialog, session):
    """⚠️ Oubliés, l'export repassait en taille automatique et sans écart : le
    fichier écrit n'avait rien à voir avec l'aperçu qu'on venait de régler."""
    session.set_layout(card_width_mm=63.0, card_gap_mm=2.5)
    reglages = dialog.settings()
    assert reglages.card_width_mm == 63.0
    assert reglages.card_gap_mm == 2.5
