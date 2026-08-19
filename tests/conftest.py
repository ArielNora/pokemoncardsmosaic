"""Configuration commune aux tests.

L'interface Qt est testée sans écran : `offscreen` doit être choisi avant tout
import de PySide6, donc avant la collecte des tests.
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="session")
def qt_app():
    """Une seule QApplication pour toute la session : Qt en refuse plusieurs."""
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app
