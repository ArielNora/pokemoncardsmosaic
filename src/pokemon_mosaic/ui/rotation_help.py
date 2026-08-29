"""Ce que « ordre imposé » autorise, montré plutôt qu'écrit.

Un demi-tour se décrit mal en une ligne, et « retourner le bloc » se lit comme un
effet miroir. Or la rotation est **ponctuelle** : sur un carré, une carte ne passe
pas à côté mais dans le coin opposé. Deux schémas le disent en un coup d'œil là où
un paragraphe laisse un doute.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from . import theme

# Assez grand pour lire une lettre, assez petit pour que les quatre blocs et
# leurs flèches tiennent sur une ligne sans faire déborder le dialogue.
DEMO_WIDTH = 30
DEMO_HEIGHT = 42


def block(letters: str, cols: int) -> QWidget:
    """Un petit rectangle de cases marquées, rempli en ordre de lecture."""
    widget = QWidget()
    grid = QGridLayout(widget)
    grid.setSpacing(3)
    grid.setContentsMargins(0, 0, 0, 0)
    for position, letter in enumerate(letters):
        case = QFrame()
        case.setFixedSize(DEMO_WIDTH, DEMO_HEIGHT)
        theme.mark(case, "cell")
        interieur = QVBoxLayout(case)
        interieur.setContentsMargins(0, 0, 0, 0)
        marque = QLabel(letter)
        marque.setAlignment(Qt.AlignCenter)
        interieur.addWidget(marque)
        grid.addWidget(case, position // cols, position % cols)
    return widget


class RotationHelp(QDialog):
    """Deux exemples : une ligne, puis un carré."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._intro = QLabel()
        self._intro.setWordWrap(True)
        self._shape_note = QLabel()
        self._shape_note.setWordWrap(True)
        self._row_label = QLabel()
        self._square_label = QLabel()

        layout = QVBoxLayout(self)
        layout.addWidget(self._intro)
        layout.addSpacing(8)
        for titre, (lettres, tournees, cols) in (
            (self._row_label, ("ABC", "CBA", 3)),
            (self._square_label, ("ABCD", "DCBA", 2)),
        ):
            layout.addWidget(titre)
            ligne = QHBoxLayout()
            ligne.addWidget(block(lettres, cols))
            fleche = QLabel("→")
            fleche.setAlignment(Qt.AlignCenter)
            ligne.addWidget(fleche)
            ligne.addWidget(block(tournees, cols))
            ligne.addStretch(1)
            layout.addLayout(ligne)
            layout.addSpacing(10)

        layout.addWidget(self._shape_note)
        self._buttons = QDialogButtonBox(QDialogButtonBox.Close)
        self._buttons.rejected.connect(self.reject)
        layout.addWidget(self._buttons)
        self.retranslate_ui()

    def retranslate_ui(self) -> None:
        self.setWindowTitle(self.tr("Ordre libre : le demi-tour"))
        self._intro.setText(self.tr(
            "Ordre imposé décoché, l'optimiseur a le droit d'essayer aussi le "
            "bloc pivoté d'un demi-tour, et garde celui des deux qui s'accorde "
            "le mieux avec ses voisins. Cela lui laisse deux fois plus de "
            "placements possibles."))
        self._row_label.setText(self.tr("Sur une ligne, l'ordre s'inverse :"))
        self._square_label.setText(self.tr(
            "Sur un carré, chaque carte va dans le coin opposé — ce n'est pas "
            "un effet miroir :"))
        self._shape_note.setText(self.tr(
            "La forme ne change jamais : un 3 × 2 pivoté reste un 3 × 2. "
            "Gardez l'ordre imposé quand le sens porte quelque chose — une "
            "lignée d'évolution, ou une paire qui se lit dans un sens."))
