#!/bin/sh
# Lance la suite **fichier par fichier**, dans un processus par fichier.
#
# En un seul processus, tout s'accumule : la QApplication partagée, les widgets,
# les vignettes et les images d'export. Mesuré sur cette suite, le pic mémoire
# passe de 177 Mo d'un bloc à 142 Mo au plus, chaque fichier rendant sa mémoire
# avant le suivant. Le coût est le démarrage répété de l'interpréteur : 12,4 s
# contre 10,3 s.
#
# Usage : scripts/run_tests.sh [arguments pytest supplémentaires]
#         scripts/run_tests.sh -x -q

set -e
cd "$(git rev-parse --show-toplevel)"

PYTEST=".venv/bin/pytest"
[ -x "$PYTEST" ] || PYTEST="uv run pytest"

total=0
failed=""
for file in tests/test_*.py; do
    printf '%-36s' "$file"
    if output=$($PYTEST "$file" -q --no-header "$@" 2>&1); then
        count=$(printf '%s' "$output" | grep -oE '[0-9]+ passed' | head -1)
        printf '%s\n' "${count:-ok}"
        n=$(printf '%s' "${count:-0}" | cut -d' ' -f1)
        total=$((total + n))
    else
        printf 'ÉCHEC\n'
        printf '%s\n' "$output" | tail -30
        failed="$failed $file"
    fi
done

if [ -n "$failed" ]; then
    echo
    echo "Fichiers en échec :$failed"
    exit 1
fi
echo
echo "$total tests passés."
