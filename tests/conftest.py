"""Configuration commune aux tests.

L'interface Qt est testée sans écran : `offscreen` doit être choisi avant tout
import de PySide6, donc avant la collecte des tests.
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(autouse=True)
def reglages_des_tutoriels(tmp_path, monkeypatch):
    """Les réglages des tutoriels des fenêtres, dans un fichier du test.

    ⚠️ **Jamais ceux de la machine** : un test qui ouvre une fenêtre marquerait
    sinon ses visites comme vues chez l'utilisateur. Et **visites passées
    d'office** : une visite démarrée voile la fenêtre et bloque les clics des
    tests qui ne parlent pas des tutoriels. Ceux qui en parlent rallument.
    """
    from PySide6.QtCore import QSettings

    from pokemon_mosaic.ui import tutorial

    reglages = QSettings(str(tmp_path / "tutoriels.ini"), QSettings.IniFormat)
    reglages.setValue(tutorial.SETTINGS_SKIP_ALL, True)
    monkeypatch.setattr(tutorial, "application_settings", lambda: reglages)
    return reglages


@pytest.fixture(scope="session")
def qt_app():
    """Une seule QApplication pour toute la session : Qt en refuse plusieurs."""
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app
