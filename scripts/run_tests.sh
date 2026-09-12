#!/bin/sh
# Lance la suite par lots de tests bornés, un processus par lot, l'un après
# l'autre. Le travail et les mesures sont dans scripts/run_tests.py.
#
# Usage : scripts/run_tests.sh [options pytest supplémentaires]
#         TESTS_PAR_LOT=25 scripts/run_tests.sh -x

set -e
cd "$(git rev-parse --show-toplevel)"

PYTHON=".venv/bin/python"
[ -x "$PYTHON" ] || PYTHON="uv run python"
# Sans guillemets : « uv run python » doit se découper en trois mots.
exec $PYTHON scripts/run_tests.py "$@"
