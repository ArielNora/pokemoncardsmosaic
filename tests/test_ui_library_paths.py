"""Un agencement gardé s'écrit avec les chemins de **son** dossier de cartes.

Trouvé par l'audit du 2026-09-18 : les groupes d'un multi-lancement et la
timeline d'un calcul survivent au chargement d'un autre dossier, et les chemins
se calculaient par rapport au dossier chargé ensuite. Le fichier écrit désignait
« ../A/serie/c0.webp », et l'agencement ne retrouvait plus ses cartes.
"""

import json
import os

import numpy as np
import pytest


def jeu(racine, dossier, n=4):
    from pokemon_mosaic.cards import Card, CardSet

    cartes = []
    for i in range(n):
        carte = Card(path=os.path.join(racine, dossier, "serie", f"c{i}.webp"),
                     index=i, thumbnail=np.full((16, 12, 3), 40 * i, np.uint8))
        carte.top = carte.bottom = carte.left = carte.right = np.zeros(3)
        cartes.append(carte)
    return CardSet(cards=cartes, full_size=(713, 984), thumb_size=(12, 16))


@pytest.fixture
def deux_dossiers(qt_app, tmp_path):
    """Une session sur le dossier A, sa bibliothèque, et de quoi charger B."""
    from pokemon_mosaic.ui.session import Session

    racine = str(tmp_path)
    session = Session()
    jeu_a = jeu(racine, "A")
    session.set_cards(jeu_a, os.path.join(racine, "A"))
    session.set_layout(cols=2, rows=2)
    bibliotheque = tmp_path / "biblio"
    bibliotheque.mkdir()

    def charger_b():
        session.set_cards(jeu(racine, "B"), os.path.join(racine, "B"))

    return session, jeu_a, str(bibliotheque), charger_b


def chemins_ecrits(bibliotheque):
    fichiers = os.listdir(bibliotheque)
    assert len(fichiers) == 1
    with open(os.path.join(bibliotheque, fichiers[0]), encoding="utf-8") as flux:
        return json.load(flux)["cards"]


ATTENDUS = [f"serie/c{i}.webp" for i in range(4)]


def groupe_calcule(session, jeu_a, bibliotheque):
    """Un onglet de multi-lancement avec un groupe calculé sur A."""
    from pokemon_mosaic.timeline import Snapshot
    from pokemon_mosaic.ui.multi_run_tab import MultiRunTab

    onglet = MultiRunTab(session, bibliotheque)
    onglet._data_dir = session.data_dir
    onglet._on_run_started(0, jeu_a, None)
    onglet.groups[0].snapshots = [Snapshot(
        grid=np.arange(4).reshape(2, 2), iteration=10, accepted=1, score=5.0,
        elapsed=0.1)]
    return onglet


def test_keeping_a_group_after_loading_another_folder(deux_dossiers):
    session, jeu_a, bibliotheque, charger_b = deux_dossiers
    onglet = groupe_calcule(session, jeu_a, bibliotheque)

    charger_b()
    onglet._show_results()
    onglet.select(0, 0)
    onglet._keep_selected()

    assert chemins_ecrits(bibliotheque) == ATTENDUS


def test_saving_a_group_after_loading_another_folder(deux_dossiers):
    session, jeu_a, bibliotheque, charger_b = deux_dossiers
    onglet = groupe_calcule(session, jeu_a, bibliotheque)

    charger_b()
    onglet._show_results()
    onglet.select(0, 0)
    onglet._save_selected()

    assert chemins_ecrits(bibliotheque) == ATTENDUS


def test_keeping_a_snapshot_after_loading_another_folder(deux_dossiers,
                                                         monkeypatch):
    from pokemon_mosaic.timeline import Timeline
    from pokemon_mosaic.ui import run_step as module
    from pokemon_mosaic.ui.run_step import RunStep

    session, jeu_a, bibliotheque, charger_b = deux_dossiers
    monkeypatch.setattr(module, "start_run",
                        lambda *args, **kwargs: (object(), object()))
    etape = RunStep(session, bibliotheque)
    etape.start_run()
    timeline = Timeline(every=1)
    timeline.record(np.arange(4).reshape(2, 2), 10, 1, 5.0, 0.1)
    etape._on_started(jeu_a, timeline)
    etape._on_snapshot(timeline[-1])
    etape._thread = etape._worker = None

    charger_b()
    etape._keep_current()

    assert chemins_ecrits(bibliotheque) == ATTENDUS


def test_a_kept_arrangement_remembers_the_loaded_folder_by_default(deux_dossiers):
    session, jeu_a, _, _ = deux_dossiers

    rang = session.save_grid(np.arange(4).reshape(2, 2), jeu_a, 1, 1.0)

    assert session.saved[rang].data_dir == session.data_dir
