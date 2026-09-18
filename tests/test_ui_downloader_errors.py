"""Un téléchargement qui rencontre une erreur imprévue le dit toujours.

Trouvé par l'audit du 2026-09-18 : une carte déjà présente mais illisible
faisait sortir le travailleur sans aucun signal. Le fil ne s'arrêtait jamais, et
l'étape 1 restait « occupée » jusqu'au redémarrage.
"""

import os
import sys

import pytest

MANIFESTE = {"version": 4,
             "cards": [{"path": "A1/c0.webp", "bytes": 10, "sha256": "ab",
                        "set": "A1"}],
             "mirror": {"sets": {}}}


def travailleur(monkeypatch, dossier):
    from pokemon_mosaic.ui import downloader

    monkeypatch.setattr(downloader, "fetch_manifest", lambda: MANIFESTE)
    worker = downloader.CardDownloader(str(dossier))
    signaux = []
    for nom in ("surveyed", "finished", "failed", "cancelled"):
        getattr(worker, nom).connect(
            lambda *args, nom=nom: signaux.append((nom, args)))
    return worker, signaux


def test_an_unexpected_error_while_surveying_is_reported(qt_app, monkeypatch,
                                                         tmp_path):
    from pokemon_mosaic.ui import downloader

    worker, signaux = travailleur(monkeypatch, tmp_path)

    def illisible(*_):
        raise PermissionError("Permission denied: A1/c0.webp")

    monkeypatch.setattr(downloader, "missing_cards", illisible)
    worker.run()

    assert [nom for nom, _ in signaux] == ["failed"]
    assert "Permission denied" in signaux[0][1][0]


def test_an_unexpected_error_while_fetching_is_reported(qt_app, monkeypatch,
                                                        tmp_path):
    from pokemon_mosaic.ui import downloader

    worker, signaux = travailleur(monkeypatch, tmp_path)

    def en_panne(*_args, **_kwargs):
        raise KeyError("sets")

    monkeypatch.setattr(downloader, "fetch_mirror", en_panne)
    worker.run()

    assert [nom for nom, _ in signaux] == ["surveyed", "failed"]


@pytest.mark.skipif(sys.platform == "win32" or os.geteuid() == 0,
                    reason="les droits POSIX ne s'appliquent pas ici")
def test_an_unreadable_card_already_in_the_folder(qt_app, monkeypatch, tmp_path):
    """Le cas réel : la carte a la bonne taille, mais ne se laisse pas lire."""
    carte = tmp_path / "A1" / "c0.webp"
    carte.parent.mkdir()
    carte.write_bytes(b"x" * 10)
    carte.chmod(0)
    worker, signaux = travailleur(monkeypatch, tmp_path)
    try:
        worker.run()
    finally:
        carte.chmod(0o644)

    assert [nom for nom, _ in signaux] == ["failed"]
