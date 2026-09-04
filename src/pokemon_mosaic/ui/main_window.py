"""Fenêtre principale : assistant en trois étapes puis vue d'exécution."""

import os
from pathlib import Path

from PySide6.QtCore import QEvent, QSettings, QStandardPaths, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from ..paths import APP_NAME
from . import theme
from .cards_step import CardsStep
from .i18n import LANGUAGES, LanguageManager
from .layout_step import LayoutStep
from .presets_bar import PresetsBar
from .run_step import RunStep
from .session import Session
from .settings_step import SettingsStep

# L'aura du bouton « Suivant » : son rayon, son opacité, et la place à lui
# laisser autour. ⚠️ **Le rouge est plus discret que le vert** : il accompagne le
# premier passage sur chaque écran, et le voir aussi vif que l'invitation à
# continuer donnerait au parcours l'air d'une suite d'erreurs.
GLOW_RADIUS, GLOW_ALPHA = 26, 220
GLOW_RADIUS_WAITING, GLOW_ALPHA_WAITING = 16, 130
GLOW_ROOM = 10


class PlaceholderStep(QWidget):
    """Étape pas encore construite, pour que la navigation soit déjà testable."""

    def __init__(self, title_provider, parent=None):
        super().__init__(parent)
        # On reçoit une fonction plutôt qu'un texte : le titre doit être relu à
        # chaque changement de langue.
        self._title_provider = title_provider
        self._label = QLabel()
        self._label.setAlignment(Qt.AlignCenter)
        layout = QVBoxLayout(self)
        layout.addWidget(self._label)
        self.retranslate_ui()

    def retranslate_ui(self) -> None:
        self._label.setText(
            self.tr("« %1 » : à construire.").replace("%1", self._title_provider())
        )


class MainWindow(QMainWindow):
    """Coquille de l'application : navigation, langue, barre d'état."""

    STEP_COUNT = 4

    def step_title(self, index: int) -> str:
        """Titres écrits en toutes lettres : `tr()` sur une variable n'est pas
        extractible par lupdate, et la chaîne resterait non traduite."""
        return (
            self.tr("Cartes"),
            self.tr("Grille et format"),
            self.tr("Réglages"),
            self.tr("Exécution"),
        )[index]

    # Clé du dossier de cartes retenu d'un lancement à l'autre. Sans elle,
    # l'application redemandait le dossier à chaque ouverture : un chemin codé en
    # dur ne peut pas convenir à la fois au dépôt et à une application installée,
    # où il n'existe simplement pas.
    SETTINGS_CARDS_DIR = "cartes/dossier"

    @staticmethod
    def settings() -> QSettings:
        """Les réglages de l'application, là où le système les range.

        ⚠️ L'organisation et l'application sont nommées **ici** et non par
        `QApplication.setOrganizationName()`. Poser un nom d'organisation sur
        l'application déplacerait aussi `QStandardPaths.AppConfigLocation`, qui
        vaut `<config>/<organisation>/<application>` : les préréglages déjà
        enregistrés se retrouveraient dans un dossier que plus personne ne lit,
        sans message ni moyen de les retrouver.
        """
        return QSettings(APP_NAME, APP_NAME)

    @classmethod
    def remembered_folder(cls) -> str:
        """Dernier dossier de cartes chargé, ou chaîne vide.

        Rendu vide s'il a disparu depuis : proposer un chemin mort produirait un
        « échec du chargement » à l'ouverture, là où l'écran d'accueil dit quoi
        faire.
        """
        chemin = cls.settings().value(cls.SETTINGS_CARDS_DIR, "", type=str)
        return chemin if chemin and os.path.isdir(chemin) else ""

    @classmethod
    def remember_folder(cls, directory: str) -> None:
        cls.settings().setValue(cls.SETTINGS_CARDS_DIR, directory)

    @staticmethod
    def presets_directory() -> str:
        """Où vivent les préréglages, selon les usages du système.

        Qt sait déjà le dire ; ajouter `platformdirs` pour cela seul alourdirait
        un socle tenu à trois dépendances.
        """
        base = QStandardPaths.writableLocation(QStandardPaths.AppConfigLocation)
        return str(Path(base or ".") / "presets")

    def __init__(self, language: LanguageManager, session: Session,
                 presets_directory: str | None = None):
        super().__init__()
        self._language = language
        self._session = session
        self._presets_directory = presets_directory or self.presets_directory()
        # Tentatives de fermeture déjà refusées, bornées par `CLOSE_ATTEMPTS`.
        self._refus_de_fermeture = 0
        self._build()
        language.language_changed.connect(self.retranslate_ui)

    def _build(self) -> None:
        self._presets = PresetsBar(self._session, self._presets_directory)
        self._presets.status_message.connect(self._show_status)

        self._steps_bar = QHBoxLayout()
        self._step_labels = []
        for _ in range(self.STEP_COUNT):
            label = QLabel()
            label.setAlignment(Qt.AlignCenter)
            self._step_labels.append(label)
            self._steps_bar.addWidget(label)

        self._stack = QStackedWidget()
        self._cards_step = CardsStep(self._session)
        self._cards_step.folder_changed.connect(self.remember_folder)
        self._cards_step.status_message.connect(self._show_status)
        self._stack.addWidget(self._cards_step)
        self._layout_step = LayoutStep(self._session)
        # L'étape 2 se parcourt par parties : « Suivant » les déroule avant de
        # changer d'écran, et se grise tant que la partie affichée n'est pas en
        # état. Sans ce signal, il resterait figé sur son dernier état connu.
        self._layout_step.advance_state_changed.connect(self._update_navigation)
        self._cards_step.advance_state_changed.connect(self._update_navigation)
        self._stack.addWidget(self._layout_step)
        self._settings_step = SettingsStep(self._session)
        self._stack.addWidget(self._settings_step)
        self._run_step = RunStep(self._session)
        self._run_step.status_message.connect(self._show_status)
        self._stack.addWidget(self._run_step)
        self._stack.currentChanged.connect(self._update_navigation)
        # Sans cela, « Suivant » resterait grisé après l'arrivée des cartes :
        # il ne se réévaluait qu'au changement d'écran, qu'on ne peut plus faire.
        self._session.cards_added.connect(self._update_navigation)
        self._session.cards_loaded.connect(self._update_navigation)

        self._back = QPushButton()
        self._next = QPushButton()
        # ⚠️ **Une aura, et non un fond coloré.** Le bouton garde l'apparence
        # d'un bouton : c'est autour de lui que se lit son état, sans quoi il
        # faudrait deux boutons de couleurs différentes selon le moment. Qt ne
        # connaît pas `box-shadow` ; l'effet, lui, se pose sur le widget.
        self._next_glow = QGraphicsDropShadowEffect(self._next)
        self._next_glow.setOffset(0, 0)
        self._next.setGraphicsEffect(self._next_glow)
        self._back.clicked.connect(lambda: self._go(self._stack.currentIndex() - 1))
        self._next.clicked.connect(self._on_next)

        self._language_label = QLabel()
        self._language_box = QComboBox()
        for code, name in LANGUAGES.items():
            self._language_box.addItem(name, code)
        self._language_box.setCurrentIndex(
            self._language_box.findData(self._language.current)
        )
        self._language_box.currentIndexChanged.connect(self._on_language_picked)

        bottom = QHBoxLayout()
        # L'aura déborde du bouton : sans cette marge, elle serait rognée par le
        # bord de la fenêtre et par le bouton voisin.
        bottom.setContentsMargins(0, GLOW_ROOM, 0, GLOW_ROOM)
        bottom.setSpacing(GLOW_ROOM)
        bottom.addWidget(self._language_label)
        bottom.addWidget(self._language_box)
        bottom.addStretch(1)
        bottom.addWidget(self._back)
        bottom.addWidget(self._next)

        layout = QVBoxLayout()
        layout.addWidget(self._presets)
        layout.addLayout(self._steps_bar)
        layout.addWidget(self._stack, 1)
        layout.addLayout(bottom)
        central = QWidget()
        central.setLayout(layout)
        self.setCentralWidget(central)
        self.setStatusBar(QStatusBar())

        self.resize(1100, 760)
        self._update_navigation()
        self.retranslate_ui()

    def load_cards(self, directory: str) -> None:
        """Charge un dossier de cartes. Point d'entrée du lancement.

        Public, là où `app.py` atteignait `_cards_step` : l'écran d'accueil est
        un détail d'organisation interne, pas un contrat.
        """
        self._cards_step.load(directory)

    def _go(self, index: int) -> None:
        if 0 <= index < self._stack.count():
            self._stack.setCurrentIndex(index)

    def _on_next(self) -> None:
        """Un seul bouton pour avancer, y compris **dans** un écran.

        Un écran qui se parcourt par parties consomme le clic tant qu'il lui en
        reste une. Lui donner son propre « Suivant » aurait mis deux boutons du
        même nom à l'écran, sans qu'on sache lequel quitte l'étape.
        """
        courant = self._stack.currentWidget()
        avance = getattr(courant, "advance", None)
        if avance is not None and avance():
            self._update_navigation()
            return
        self._go(self._stack.currentIndex() + 1)

    def _on_language_picked(self, index: int) -> None:
        self._language.set_language(self._language_box.itemData(index))

    def _show_status(self, message: str) -> None:
        self.statusBar().showMessage(message, 8000)

    def _update_navigation(self) -> None:
        current = self._stack.currentIndex()
        self._back.setEnabled(current > 0)
        # Sans carte, les trois écrans suivants n'ont rien à afficher : la grille
        # se dimensionne sur le nombre de cartes, les réglages projettent des
        # chiffres à partir d'elles, et l'exécution n'a rien à assembler.
        avancable = (current < self._stack.count() - 1
                     and self._session.total_cards > 0)
        # Un écran peut refuser de laisser passer : l'étape 2 exige que la partie
        # affichée soit complète — toutes ses cases vides placées, par exemple.
        peut = getattr(self._stack.currentWidget(), "can_advance", None)
        if avancable and peut is not None:
            avancable = peut()
        self._next.setEnabled(avancable)
        self._update_glow(avancable, current < self._stack.count() - 1)
        for position, label in enumerate(self._step_labels):
            font = label.font()
            font.setBold(position == current)
            label.setFont(font)

    def _update_glow(self, ready: bool, has_next: bool) -> None:
        """L'aura du bouton « Suivant » : verte quand il est prêt, rouge sinon.

        ⚠️ **Rien du tout à la dernière étape.** Le bouton y est éteint parce
        qu'il n'y a plus d'écran après, et non parce qu'il manque quelque
        chose : une aura rouge y accuserait un travail qui est fini.

        Le rouge est **moins fort** que le vert. Il dit « il reste à faire »,
        pas « c'est cassé », et il accompagne le premier passage sur chaque
        écran — le voir aussi vif que l'invitation à continuer donnerait à tout
        le parcours l'air d'une suite d'erreurs.
        """
        colours = theme.colours(self.palette())
        if not has_next:
            self._next_glow.setEnabled(False)
            return
        self._next_glow.setEnabled(True)
        couleur = QColor(colours["ok"] if ready else colours["error"])
        couleur.setAlpha(GLOW_ALPHA if ready else GLOW_ALPHA_WAITING)
        self._next_glow.setColor(couleur)
        self._next_glow.setBlurRadius(GLOW_RADIUS if ready
                                      else GLOW_RADIUS_WAITING)

    def changeEvent(self, event) -> None:
        """Suit la bascule clair/sombre du système.

        ⚠️ **Une couleur figée dans un effet ne suit rien.** Tout ce qui se lit
        au moment du dessin change de mode tout seul ; l'aura, elle, garde la
        teinte qu'on lui a posée — verte foncée sur une fenêtre devenue claire.
        """
        super().changeEvent(event)
        if event.type() == QEvent.PaletteChange:
            self._update_navigation()

    # Nombre de tentatives de fermeture avant de passer outre un fil bloqué.
    CLOSE_ATTEMPTS = 2

    def closeEvent(self, event) -> None:
        """Ne ferme que si les fils de fond se sont arrêtés.

        Le `QThread` a pour parent son widget : fermer emporterait un fil encore
        actif, et Qt abandonne alors le processus. Les deux `shutdown()` sont
        appelées avant tout test, pour qu'un refus de la première n'empêche pas
        d'arrêter la seconde.
        """
        arrets = [self._cards_step.shutdown(), self._run_step.shutdown()]
        if all(arrets):
            super().closeEvent(event)
            return

        # ⚠️ Le refus est **borné**. Refuser indéfiniment rendrait la fenêtre
        # infermable dès qu'un fil se bloque pour de bon : l'utilisateur clique
        # la croix, rien ne se passe, et il ne lui reste qu'à tuer le processus.
        # C'est pire que le plantage qu'on cherche à éviter. On accorde donc une
        # seconde tentative — cinq secondes de plus par fil — puis on ferme.
        self._refus_de_fermeture += 1
        if self._refus_de_fermeture >= self.CLOSE_ATTEMPTS:
            # `_show_status` et non un signal : la fenêtre reçoit les messages
            # des écrans, elle n'en émet pas.
            self._show_status(
                self.tr("Fermeture forcée : un traitement de fond n'a pas répondu.")
            )
            super().closeEvent(event)
            return
        event.ignore()

    def retranslate_ui(self) -> None:
        self.setWindowTitle(self.tr("Pokémon Mosaic"))
        for position, label in enumerate(self._step_labels):
            label.setText(f"{position + 1}. {self.step_title(position)}")
        self._back.setText(self.tr("Précédent"))
        self._next.setText(self.tr("Suivant"))
        self._language_label.setText(self.tr("Langue"))
        self._presets.retranslate_ui()
        for widget in (self._stack.widget(i) for i in range(self._stack.count())):
            if hasattr(widget, "retranslate_ui"):
                widget.retranslate_ui()
        self._update_navigation()
