"""On ne part pas d'un agencement pendant qu'un calcul tourne.

Trouvé par l'audit du 2026-09-18 : revenu à l'étape 1 en plein calcul, le bouton
du haut restait actif, et le départ accepté n'était jamais montré à l'exécution,
qui retrouvait à sa fin le calcul précédent. « Lancer » repartait alors d'une
grille neuve, et non de l'agencement choisi.
"""

import numpy as np
import pytest


@pytest.fixture
def fenetre(qt_app, tmp_path, monkeypatch):
    from PySide6.QtCore import QSettings

    from pokemon_mosaic.cards import Card, CardSet
    from pokemon_mosaic.ui.i18n import LanguageManager
    from pokemon_mosaic.ui.main_window import MainWindow
    from pokemon_mosaic.ui.session import Session

    reglages = QSettings(str(tmp_path / "r.ini"), QSettings.IniFormat)
    monkeypatch.setattr(MainWindow, "settings", staticmethod(lambda: reglages))
    cartes = []
    for i in range(6):
        carte = Card(path=f"/fake/s/{i}.webp", index=i,
                     thumbnail=np.full((16, 12, 3), 30 * i, np.uint8))
        carte.top = carte.bottom = carte.left = carte.right = np.zeros(3)
        cartes.append(carte)
    session = Session()
    session.set_cards(CardSet(cards=cartes, full_size=(713, 984),
                              thumb_size=(12, 16)), "/fake")
    ecran = MainWindow(LanguageManager(qt_app), session,
                       presets_directory=str(tmp_path / "presets"),
                       arrangements_directory=str(tmp_path / "agencements"))
    yield ecran
    ecran.deleteLater()


def bouton(ecran):
    return ecran._presets._arrangements


def test_a_running_calculation_greys_the_start_from_an_arrangement(fenetre):
    etape = fenetre._run_step
    assert bouton(fenetre).isEnabled()

    etape._thread = object()
    etape._update_buttons(running=True)

    assert not bouton(fenetre).isEnabled()
    assert "calcul" in bouton(fenetre).toolTip()


def test_the_button_comes_back_when_the_calculation_ends(fenetre):
    from pokemon_mosaic.optimize import OptimizationResult

    etape = fenetre._run_step
    etape._thread = object()
    etape._update_buttons(running=True)

    etape._on_finished(OptimizationResult(
        accepted=1, attempted=10, initial_score=9.0, final_score=9.0,
        stopped_by="épuisé", elapsed=0.1))

    assert bouton(fenetre).isEnabled()
    assert bouton(fenetre).toolTip() == fenetre._presets.tr(
        "Parcourir les agencements enregistrés.")


def test_a_multi_run_greys_it_too(fenetre):
    multi = fenetre._run_step._multi

    multi._thread = object()
    multi._update_buttons(running=True)
    assert not bouton(fenetre).isEnabled()

    multi._thread = None
    multi._update_buttons(running=False)
    assert bouton(fenetre).isEnabled()


def test_steps_three_and_four_keep_their_own_explanation(fenetre):
    """Aux étapes 3 et 4, l'infobulle renvoie toujours au bouton sous les
    cases, calcul ou non : c'est la raison qui vaut à ces étapes."""
    etape = fenetre._run_step
    fenetre._stack.setCurrentIndex(2)
    etape._thread = object()
    etape._update_buttons(running=True)

    assert not bouton(fenetre).isEnabled()
    assert "sous les cases" in bouton(fenetre).toolTip()
    etape._thread = None
