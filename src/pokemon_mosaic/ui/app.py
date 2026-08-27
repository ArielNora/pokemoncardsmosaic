"""Point d'entrée de l'interface graphique."""

import sys

from PySide6.QtWidgets import QApplication

from ..paths import APP_NAME, user_data_dir
from .i18n import LanguageManager
from .main_window import MainWindow
from .session import Session

# Dossier proposé en dernier recours, s'il existe : c'est `data/pokemoncards`
# quand on tourne depuis le dépôt. Une application installée ne le trouve jamais,
# et c'est bien ainsi — l'étape 1 propose alors de télécharger les cartes.
FALLBACK_DATA_DIR = user_data_dir() / "pokemoncards"


def initial_folder() -> str:
    """Dossier de cartes à ouvrir au lancement, ou chaîne vide.

    Le dernier dossier chargé d'abord : c'est la seule valeur qui vaille pour
    les deux modes d'exécution. Le repli n'existe que pour le dépôt, où le jeu
    de cartes est à un emplacement connu.
    """
    return (MainWindow.remembered_folder()
            or (str(FALLBACK_DATA_DIR) if FALLBACK_DATA_DIR.is_dir() else ""))


def main(argv=None) -> int:
    app = QApplication(argv if argv is not None else sys.argv)
    # ⚠️ Le nom d'application seul, sans nom d'organisation : en poser un
    # déplacerait `QStandardPaths.AppConfigLocation`, donc les préréglages déjà
    # enregistrés. Les réglages nomment leur emplacement eux-mêmes, voir
    # `MainWindow.settings()`.
    app.setApplicationName(APP_NAME)

    language = LanguageManager(app)
    language.set_language(LanguageManager.system_default())

    session = Session()
    window = MainWindow(language, session)
    window.show()

    depart = initial_folder()
    if depart:
        window.load_cards(depart)

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
