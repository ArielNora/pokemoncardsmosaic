"""Point d'entrée de l'interface graphique."""

import sys

from PySide6.QtWidgets import QApplication

from ..paths import user_data_dir
from .i18n import LanguageManager
from .main_window import MainWindow
from .session import Session

# Dossier de cartes proposé par défaut s'il existe, pour éviter de le chercher
# à chaque lancement. Absent — le cas d'une installation neuve —, l'utilisateur
# le désigne lui-même à l'étape 1.
DEFAULT_DATA_DIR = user_data_dir() / "pokemoncards"


def main(argv=None) -> int:
    app = QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName("Pokémon Mosaic")

    language = LanguageManager(app)
    language.set_language(LanguageManager.system_default())

    session = Session()
    window = MainWindow(language, session)
    window.show()

    if DEFAULT_DATA_DIR.is_dir():
        window._cards_step.load(str(DEFAULT_DATA_DIR))

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
