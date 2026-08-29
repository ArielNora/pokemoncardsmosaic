"""Un compteur en grand : intitulé, flèche haut, nombre, flèche bas.

Les deux dimensions de la grille sont la décision de l'onglet, et une paire de
`QSpinBox` de vingt pixels de haut ne le disait pas. Ici le nombre occupe la
place qui lui revient, les deux flèches sont assez grandes pour être visées
sans précision, et l'intitulé se lit au-dessus plutôt qu'à côté — deux colonnes
côte à côte se lisent alors de haut en bas, sans chercher quelle étiquette va
avec quel champ.

Le nombre reste **saisissable** : passer de 4 à 21 à la flèche demanderait dix-
sept clics.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIntValidator
from PySide6.QtWidgets import (
    QLabel,
    QLineEdit,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

# Hauteur des deux flèches, et du champ. Le nombre est dimensionné par sa police.
ARROW_HEIGHT = 30
FIELD_HEIGHT = 58
# Combien la police du nombre dépasse celle de l'interface.
FONT_BOOST = 16


class BigSpin(QWidget):
    """Un entier borné, présenté en colonne : titre, ▲, nombre, ▼."""

    value_changed = Signal(int)

    def __init__(self, minimum: int, maximum: int, parent=None):
        super().__init__(parent)
        self._min, self._max = minimum, maximum
        self._value = minimum

        self._title = QLabel()
        self._title.setAlignment(Qt.AlignCenter)

        self._up = QToolButton()
        self._up.setText("▲")
        self._up.setAutoRepeat(True)
        self._down = QToolButton()
        self._down.setText("▼")
        self._down.setAutoRepeat(True)
        for bouton in (self._up, self._down):
            bouton.setFixedHeight(ARROW_HEIGHT)
            # Aussi larges que le nombre : réduites à leur texte, elles font
            # deux boutons perdus au-dessus et au-dessous d'un champ trois fois
            # plus large, qu'il faut viser au lieu de simplement cliquer.
            bouton.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._up.clicked.connect(lambda: self._step(1))
        self._down.clicked.connect(lambda: self._step(-1))

        self._field = QLineEdit()
        self._field.setAlignment(Qt.AlignCenter)
        self._field.setFixedHeight(FIELD_HEIGHT)
        self._field.setValidator(QIntValidator(minimum, maximum, self))
        police = self._field.font()
        police.setPointSize(police.pointSize() + FONT_BOOST)
        self._field.setFont(police)
        # `editingFinished` et non `textChanged` : écrêter à chaque frappe
        # transformerait « 21 » en « 2 » puis « 1 » dès que la première chiffre
        # sort des bornes, et l'on ne pourrait plus taper certains nombres.
        self._field.editingFinished.connect(self._on_typed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)
        layout.addWidget(self._title)
        layout.addWidget(self._up)
        layout.addWidget(self._field)
        layout.addWidget(self._down)
        self._show_value()

    # --- Contenu ----------------------------------------------------------

    def setTitle(self, text: str) -> None:
        self._title.setText(text)

    def value(self) -> int:
        return self._value

    def setValue(self, value: int) -> None:
        """Pose une valeur écrêtée. N'émet que si elle change réellement."""
        borne = max(self._min, min(self._max, int(value)))
        if borne == self._value:
            self._show_value()
            return
        self._value = borne
        self._show_value()
        self.value_changed.emit(borne)

    # --- Réactions --------------------------------------------------------

    def _step(self, delta: int) -> None:
        self.setValue(self._value + delta)

    def _on_typed(self) -> None:
        texte = self._field.text().strip()
        if not texte:
            # Champ vidé puis quitté : on remet ce qui était là plutôt que de
            # retomber sur la borne basse, qui n'a jamais été demandée.
            self._show_value()
            return
        self.setValue(int(texte))

    def _show_value(self) -> None:
        self._field.setText(str(self._value))
        self._up.setEnabled(self._value < self._max)
        self._down.setEnabled(self._value > self._min)
