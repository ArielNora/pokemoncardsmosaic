#!/bin/sh
# Construit le `.app` macOS.
#
#   paquet/construire.sh
#
# Le paquet embarque le code et les traductions, pas les illustrations : elles
# se récupèrent à l'usage, et l'utilisateur désigne son dossier à l'étape 1.

set -e
cd "$(git rev-parse --show-toplevel)"

uv sync --extra package
uv run pyinstaller paquet/pokemon-mosaic.spec --noconfirm \
    --distpath dist --workpath build

APP="dist/Pokémon Mosaic.app"
echo
echo "Paquet : $APP  ($(du -sh "$APP" | cut -f1))"

# Contrôle de démarrage sans écran : attrape les ressources manquantes et les
# imports oubliés, qui ne se voient pas autrement qu'en lançant.
echo "Contrôle de démarrage…"
QT_QPA_PLATFORM=offscreen "$APP/Contents/MacOS/Pokémon Mosaic" >/dev/null 2>&1 &
PID=$!
sleep 6
if kill -0 $PID 2>/dev/null; then
    kill $PID
    wait $PID 2>/dev/null || true
    echo "  démarre correctement."
else
    echo "  ÉCHEC : l'application s'est arrêtée. Relancez sans QT_QPA_PLATFORM"
    echo "  pour voir la trace."
    exit 1
fi

echo
echo "⚠️ Le paquet n'est pas signé valablement. Il démarre sur cette machine —"
echo "   construit localement, il n'a pas d'attribut de quarantaine — mais"
echo "   Gatekeeper le refusera ailleurs. Voir paquet/README.md."
