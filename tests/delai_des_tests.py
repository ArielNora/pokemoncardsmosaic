"""Le délai maximal d'un test, importé par `conftest.py`.

Demandé par l'utilisateur le 2026-09-18 : un test a tourné deux heures sans
s'arrêter pendant un contrôle par mutation, bloqué dans une boucle Qt.

⚠️ **`faulthandler`, et non un signal Python.** Un gestionnaire de signal ne
s'exécute que lorsque l'interpréteur reprend la main : un test coincé dans la
boucle d'événements de Qt, un `exec()` modal par exemple, ne la lui rend jamais,
et le délai ne tomberait pas. `faulthandler` veille depuis un fil à lui, en C :
à l'échéance, il écrit où chaque fil était arrêté, puis **termine le
processus**. Le lanceur des lots y voit un lot en échec, et la trace dit lequel.

À part de `conftest.py` pour pouvoir se charger seul (`-p delai_des_tests`) :
c'est ainsi qu'un test vérifie qu'un test trop long est bien arrêté.
"""

import faulthandler
import os

import pytest

try:
    # ⚠️ **La vraie sortie d'erreur, et non celle du test.** Pytest capture la
    # sortie d'erreur pendant un test : écrite là, la trace partait avec le
    # processus terminé, et le lot échouait sans dire où. Pytest garde une
    # copie de l'originale pour son propre `faulthandler` : on écrit dedans.
    # Interne à pytest, d'où le repli : sans elle, le délai tombe quand même.
    from _pytest.faulthandler import fault_handler_stderr_fd_key
except ImportError:  # pragma: no cover - selon la version de pytest
    fault_handler_stderr_fd_key = None

# Le plus lent des tests prend deux secondes et demie (mesuré le 2026-09-18) :
# une minute ne coupe qu'un test bloqué.
DELAI_PAR_DEFAUT = 60.0


def delai() -> float:
    """Le délai d'un test en secondes, `TESTS_DELAI` pour le changer."""
    return float(os.environ.get("TESTS_DELAI", DELAI_PAR_DEFAUT))


@pytest.fixture(autouse=True)
def delai_maximal(request):
    """Arrête le processus si le test dépasse son délai, trace à l'appui."""
    sortie = 2
    if fault_handler_stderr_fd_key is not None:
        sortie = request.config.stash.get(fault_handler_stderr_fd_key, 2)
    faulthandler.dump_traceback_later(delai(), exit=True, file=sortie)
    yield
    faulthandler.cancel_dump_traceback_later()
