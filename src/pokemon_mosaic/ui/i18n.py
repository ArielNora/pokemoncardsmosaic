"""Bascule de langue français / anglais.

Les textes sont écrits en français dans le code et traduits vers l'anglais par des
fichiers Qt (`translations/*.qm`). Sans fichier de traduction chargé, l'interface
reste donc en français — le comportement voulu par défaut.

Chaque widget expose une méthode `retranslate_ui()` que l'on rappelle après un
changement de langue : Qt ne réévalue pas `tr()` tout seul.
"""

from pathlib import Path
from typing import List

from PySide6.QtCore import QLibraryInfo, QLocale, QObject, QTranslator, Signal

TRANSLATIONS_DIR = Path(__file__).resolve().parents[3] / "translations"

# Langues proposées : code interne -> nom affiché dans son propre alphabet.
LANGUAGES = {"fr": "Français", "en": "English"}
SOURCE_LANGUAGE = "fr"


class LanguageManager(QObject):
    """Installe et retire les traductions sur l'application."""

    language_changed = Signal(str)

    def __init__(self, app):
        super().__init__()
        self._app = app
        self._translators: List[QTranslator] = []
        self._current = SOURCE_LANGUAGE

    @property
    def current(self) -> str:
        return self._current

    @staticmethod
    def system_default() -> str:
        """Langue du système si on la gère, français sinon."""
        code = QLocale.system().name().split("_")[0]
        return code if code in LANGUAGES else SOURCE_LANGUAGE

    def set_language(self, code: str) -> None:
        if code not in LANGUAGES:
            raise ValueError(f"Langue inconnue : {code}. Connues : {list(LANGUAGES)}")
        if code == self._current:
            return

        for translator in self._translators:
            self._app.removeTranslator(translator)
        self._translators.clear()

        # Le français est la langue source : aucun fichier à charger.
        if code != SOURCE_LANGUAGE:
            self._load(TRANSLATIONS_DIR / f"pokemon_mosaic_{code}.qm")
            # Traductions des boutons standards de Qt (OK, Annuler…).
            self._load(
                Path(QLibraryInfo.path(QLibraryInfo.TranslationsPath)) / f"qtbase_{code}.qm"
            )

        self._current = code
        self.language_changed.emit(code)

    def _load(self, path: Path) -> bool:
        translator = QTranslator(self._app)
        if not path.exists() or not translator.load(str(path)):
            return False
        self._app.installTranslator(translator)
        self._translators.append(translator)
        return True
