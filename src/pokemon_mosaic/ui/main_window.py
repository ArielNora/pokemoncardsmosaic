"""Fenêtre principale : assistant en trois étapes puis vue d'exécution."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from .cards_step import CardsStep
from .i18n import LANGUAGES, LanguageManager
from .layout_step import LayoutStep
from .session import Session
from .settings_step import SettingsStep


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

    def __init__(self, language: LanguageManager, session: Session):
        super().__init__()
        self._language = language
        self._session = session
        self._build()
        language.language_changed.connect(self.retranslate_ui)

    def _build(self) -> None:
        self._steps_bar = QHBoxLayout()
        self._step_labels = []
        for _ in range(self.STEP_COUNT):
            label = QLabel()
            label.setAlignment(Qt.AlignCenter)
            self._step_labels.append(label)
            self._steps_bar.addWidget(label)

        self._stack = QStackedWidget()
        self._cards_step = CardsStep(self._session)
        self._cards_step.status_message.connect(self._show_status)
        self._stack.addWidget(self._cards_step)
        self._layout_step = LayoutStep(self._session)
        self._stack.addWidget(self._layout_step)
        self._settings_step = SettingsStep(self._session)
        self._stack.addWidget(self._settings_step)
        for position in range(3, self.STEP_COUNT):
            self._stack.addWidget(
                PlaceholderStep(lambda i=position: self.step_title(i))
            )
        self._stack.currentChanged.connect(self._update_navigation)

        self._back = QPushButton()
        self._next = QPushButton()
        self._back.clicked.connect(lambda: self._go(self._stack.currentIndex() - 1))
        self._next.clicked.connect(lambda: self._go(self._stack.currentIndex() + 1))

        self._language_label = QLabel()
        self._language_box = QComboBox()
        for code, name in LANGUAGES.items():
            self._language_box.addItem(name, code)
        self._language_box.setCurrentIndex(
            self._language_box.findData(self._language.current)
        )
        self._language_box.currentIndexChanged.connect(self._on_language_picked)

        bottom = QHBoxLayout()
        bottom.addWidget(self._language_label)
        bottom.addWidget(self._language_box)
        bottom.addStretch(1)
        bottom.addWidget(self._back)
        bottom.addWidget(self._next)

        layout = QVBoxLayout()
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

    def _go(self, index: int) -> None:
        if 0 <= index < self._stack.count():
            self._stack.setCurrentIndex(index)

    def _on_language_picked(self, index: int) -> None:
        self._language.set_language(self._language_box.itemData(index))

    def _show_status(self, message: str) -> None:
        self.statusBar().showMessage(message, 8000)

    def _update_navigation(self) -> None:
        current = self._stack.currentIndex()
        self._back.setEnabled(current > 0)
        self._next.setEnabled(current < self._stack.count() - 1)
        for position, label in enumerate(self._step_labels):
            font = label.font()
            font.setBold(position == current)
            label.setFont(font)

    def closeEvent(self, event) -> None:
        """Laisse le chargement s'arrêter avant que les widgets ne disparaissent."""
        self._cards_step.shutdown()
        super().closeEvent(event)

    def retranslate_ui(self) -> None:
        self.setWindowTitle(self.tr("Pokémon Mosaic"))
        for position, label in enumerate(self._step_labels):
            label.setText(f"{position + 1}. {self.step_title(position)}")
        self._back.setText(self.tr("Précédent"))
        self._next.setText(self.tr("Suivant"))
        self._language_label.setText(self.tr("Langue"))
        for widget in (self._stack.widget(i) for i in range(self._stack.count())):
            if hasattr(widget, "retranslate_ui"):
                widget.retranslate_ui()
        self._update_navigation()
