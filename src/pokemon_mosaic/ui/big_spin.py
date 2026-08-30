"""Un compteur en grand : intitulé, flèche haut, nombre, flèche bas.

Les deux dimensions de la grille sont la décision de l'onglet, et une paire de
`QSpinBox` de vingt pixels de haut ne le disait pas. Ici le nombre occupe la
place qui lui revient, les deux flèches sont assez grandes pour être visées
sans précision, et l'intitulé se lit au-dessus plutôt qu'à côté — deux colonnes
côte à côte se lisent alors de haut en bas, sans chercher quelle étiquette va
avec quel champ.

Le nombre reste **saisissable** : passer de 4 à 21 à la flèche demanderait dix-
sept clics.

Deux variantes, la même présentation : `BigSpin` pour un entier, `BigFloatSpin`
pour une longueur en millimètres. Les réglages qui comptent autant que les
dimensions — largeur d'une carte, écart entre deux — se montrent de la même
façon qu'elles, sous peine de passer pour des détails.
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


class _BigSpinBase(QWidget):
    """La présentation commune : titre, ▲, nombre, ▼.

    Les sous-classes disent seulement comment un nombre s'écrit, se relit et
    s'annonce.
    """

    def __init__(self, minimum, maximum, step, parent=None):
        super().__init__(parent)
        self._min, self._max, self._increment = minimum, maximum, step
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
        self._up.clicked.connect(lambda: self._bump(1))
        self._down.clicked.connect(lambda: self._bump(-1))

        self._field = QLineEdit()
        self._field.setAlignment(Qt.AlignCenter)
        self._field.setFixedHeight(FIELD_HEIGHT)
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

    # --- Ce que les variantes précisent -----------------------------------

    def _clamp(self, value):
        raise NotImplementedError

    def _text(self, value) -> str:
        raise NotImplementedError

    def _parse(self, text):
        """Le nombre écrit, ou `None` si ce n'en est pas un."""
        raise NotImplementedError

    def _emit(self, value) -> None:
        raise NotImplementedError

    # --- Contenu ----------------------------------------------------------

    def setTitle(self, text: str) -> None:
        self._title.setText(text)

    def value(self):
        return self._value

    def setValue(self, value) -> None:
        """Pose une valeur écrêtée. N'émet que si elle change réellement."""
        borne = self._clamp(value)
        if borne == self._value:
            self._show_value()
            return
        self._value = borne
        self._show_value()
        self._emit(borne)

    # --- Réactions --------------------------------------------------------

    def _bump(self, direction: int) -> None:
        self.setValue(self._value + direction * self._increment)

    def _on_typed(self) -> None:
        lu = self._parse(self._field.text().strip())
        if lu is None:
            # Champ vidé ou illisible puis quitté : on remet ce qui était là
            # plutôt que de retomber sur la borne basse, jamais demandée.
            self._show_value()
            return
        self.setValue(lu)

    def _show_value(self) -> None:
        self._field.setText(self._text(self._value))
        self._up.setEnabled(self._value < self._max)
        self._down.setEnabled(self._value > self._min)


class BigSpin(_BigSpinBase):
    """Un entier borné."""

    value_changed = Signal(int)

    def __init__(self, minimum: int, maximum: int, parent=None):
        super().__init__(minimum, maximum, 1, parent)
        self._field.setValidator(QIntValidator(minimum, maximum, self))

    def _clamp(self, value) -> int:
        return max(self._min, min(self._max, int(value)))

    def _text(self, value) -> str:
        return str(value)

    def _parse(self, text: str):
        try:
            return int(text)
        except ValueError:
            return None

    def _emit(self, value: int) -> None:
        self.value_changed.emit(value)


class BigFloatSpin(_BigSpinBase):
    """Une longueur, écrite avec ses décimales.

    Pas de `QDoubleValidator` : il suit la langue du système, et refuserait le
    point décimal sur une machine française — ou la virgule sur une autre. On
    relit soi-même, en acceptant les deux.
    """

    value_changed = Signal(float)

    def __init__(self, minimum: float, maximum: float, step: float = 1.0,
                 decimals: int = 1, parent=None):
        self._decimals = decimals
        super().__init__(float(minimum), float(maximum), float(step), parent)

    def _clamp(self, value) -> float:
        borne = max(self._min, min(self._max, float(value)))
        # Arrondi à l'affiché : sans lui, deux valeurs que l'écran montre
        # identiques se comparent inégales, et chaque pas réémettrait.
        return round(borne, self._decimals)

    def _text(self, value) -> str:
        return f"{value:.{self._decimals}f}"

    def _parse(self, text: str):
        try:
            return float(text.replace(",", "."))
        except ValueError:
            return None

    def _emit(self, value: float) -> None:
        self.value_changed.emit(value)
