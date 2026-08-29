"""Étape 2 — la mise en page, une décision par onglet.

Un seul formulaire portait tout : dimensions, format, orientation, finesse,
panneaux, cases vides. Rien ne disait par quoi commencer, ni ce que chaque
réglage changeait aux autres. On reprend la forme des écrans de création de
personnage : une liste de parties à gauche, le détail à droite, et une coche
verte quand la partie est réglée.

Une partie est **prête** quand l'utilisateur l'a validée par « Suivant » **et**
que son contenu tient toujours debout. Revenir en arrière ne défait donc rien,
mais changer un réglage jusqu'à le rendre invalide rallume l'avertissement.
"""

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QStackedWidget,
    QWidget,
)

from . import theme
from .layout_tabs import GridTab, PaperTab, PrintingTab
from .session import Session

# Taille de la pastille d'état posée devant chaque onglet.
BADGE = 22
# Largeur de la colonne d'onglets. Assez pour « Orientation, finesse et
# panneaux » sur deux lignes sans rogner la partie utile de l'écran.
TAB_WIDTH = 248
# Hauteur d'un onglet. Il n'y en aura jamais plus de cinq ou six : autant leur
# donner la taille d'un bouton qu'on vise sans réfléchir.
TAB_HEIGHT = 62
# Ce que leur libellé gagne sur la police de l'interface.
TAB_BOOST = 2


def state_icon(ready: bool, palette) -> QIcon:
    """Une coche verte, ou un point d'exclamation ambré.

    Dessinée plutôt que prise à un thème d'icônes : celui-ci n'existe ni sur
    macOS ni sur Windows, et la couleur doit de toute façon venir de nos deux
    palettes pour rester lisible dans les deux modes.
    """
    colours = theme.colours(palette)
    pixmap = QPixmap(BADGE, BADGE)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(QColor(colours["ok"] if ready else colours["warning"]))
    police = painter.font()
    police.setPointSize(BADGE - 6)
    police.setBold(True)
    painter.setFont(police)
    painter.drawText(pixmap.rect(), Qt.AlignCenter, "✓" if ready else "!")
    painter.end()
    return QIcon(pixmap)


class LayoutStep(QWidget):
    """Les parties de la mise en page, et la navigation entre elles."""

    # Émis quand « Suivant » doit être réévalué par la fenêtre.
    advance_state_changed = Signal()

    def __init__(self, session: Session, parent=None):
        super().__init__(parent)
        self._session = session
        # Parties que l'utilisateur a validées en cliquant « Suivant » dessus.
        # ⚠️ Cet ensemble **survit** à un aller-retour vers l'étape 1 : revalider
        # trois écrans pour avoir changé une carte serait une punition.
        self._validated: set[int] = set()
        self._build()

    # --- Construction -----------------------------------------------------

    def _build(self) -> None:
        self._tabs = [GridTab(self._session), PaperTab(self._session),
                      PrintingTab(self._session)]

        self._list = QListWidget()
        self._list.setFixedWidth(TAB_WIDTH)
        self._list.setIconSize(QSize(BADGE, BADGE))
        self._list.setWordWrap(True)
        theme.mark(self._list, "tabs")
        police = self._list.font()
        police.setPointSize(police.pointSize() + TAB_BOOST)
        self._list.setFont(police)
        self._list.setSpacing(0)      # l'air vient des marges de la feuille
        # Une seule partie à la fois : la liste est une navigation, pas une
        # sélection.
        self._list.setSelectionMode(QAbstractItemView.SingleSelection)
        self._list.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)

        self._pages = QStackedWidget()
        for tab in self._tabs:
            item = QListWidgetItem("")
            item.setSizeHint(QSize(TAB_WIDTH - 8, TAB_HEIGHT))
            self._list.addItem(item)
            self._pages.addWidget(tab)
            tab.state_changed.connect(self._refresh_badges)

        self._list.currentRowChanged.connect(self._on_tab_picked)
        self._list.setCurrentRow(0)

        layout = QHBoxLayout(self)
        layout.addWidget(self._list)
        layout.addWidget(self._pages, 1)
        self.retranslate_ui()

    def retranslate_ui(self) -> None:
        for tab in self._tabs:
            tab.retranslate_ui()
        self._refresh_badges()

    # --- État des onglets -------------------------------------------------

    def _ready(self, position: int) -> bool:
        """Validée par l'utilisateur, **et** toujours valide."""
        return position in self._validated and self._tabs[position].is_valid()

    def _refresh_badges(self) -> None:
        palette = self.palette()
        for position, tab in enumerate(self._tabs):
            item = self._list.item(position)
            item.setText(tab.title())
            item.setIcon(state_icon(self._ready(position), palette))
        self.advance_state_changed.emit()

    def _on_tab_picked(self, row: int) -> None:
        if 0 <= row < len(self._tabs):
            self._pages.setCurrentIndex(row)
        self.advance_state_changed.emit()

    # --- Ce que la fenêtre demande ---------------------------------------

    def can_advance(self) -> bool:
        """La partie affichée laisse-t-elle passer à la suivante ?"""
        row = self._list.currentRow()
        return 0 <= row < len(self._tabs) and self._tabs[row].is_valid()

    def advance(self) -> bool:
        """Valide la partie affichée et passe à la suivante.

        Rend vrai si l'écran a consommé le clic — il restait une partie à
        traiter —, faux s'il faut maintenant quitter l'étape. C'est ce qui
        permet à la fenêtre de garder un seul bouton « Suivant » : il déroule
        les parties, puis change d'étape.
        """
        row = self._list.currentRow()
        if not (0 <= row < len(self._tabs)) or not self._tabs[row].is_valid():
            return True                     # rien ne bouge, mais on garde le clic
        self._validated.add(row)
        self._refresh_badges()
        if row + 1 < len(self._tabs):
            self._list.setCurrentRow(row + 1)
            return True
        return False

    def all_ready(self) -> bool:
        return all(self._ready(position) for position in range(len(self._tabs)))
