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
from .layout_tabs import CardSizeTab, GridSizeTab, PaperTab, PlacementTab
from .session import Session

# Taille de la pastille d'état posée devant chaque onglet.
BADGE = 22
# Largeur de la colonne d'onglets. Assez pour « Orientation, finesse et
# panneaux » sur deux lignes sans rogner la partie utile de l'écran.
TAB_WIDTH = 248
# Hauteur d'un onglet. Il n'y en aura jamais plus de cinq ou six : autant leur
# donner la taille d'un bouton qu'on vise sans réfléchir.
TAB_HEIGHT = 62
# Un onglet de second rang : plus court, décalé, et d'un libellé plus discret.
SUB_TAB_HEIGHT = 44
SUB_TAB_INDENT = 22
# Ce que leur libellé gagne sur la police de l'interface. Les seconds rangs n'y
# gagnent rien : c'est ce qui les distingue au premier coup d'œil.
TAB_BOOST = 2
SUB_TAB_BOOST = 0
# Intitulé de la famille, posé sur une ligne qui n'est pas un onglet.
FAMILY_ROW = -1


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
        # ⚠️ **L'ordre est celui des décisions** : d'abord le papier, ensuite ce
        # qu'on y pose. La grille se règle en trois temps, regroupés sous un même
        # intitulé : sa taille, la taille de ses cartes, puis son emplacement.
        self._tabs = [PaperTab(self._session), GridSizeTab(self._session),
                      CardSizeTab(self._session), PlacementTab(self._session)]
        # Rang de la liste -> onglet, ou `FAMILY_ROW` pour l'intitulé de famille.
        self._rows: list[int] = []

        self._list = QListWidget()
        self._list.setFixedWidth(TAB_WIDTH)
        self._list.setIconSize(QSize(BADGE, BADGE))
        self._list.setWordWrap(True)
        theme.mark(self._list, "tabs")
        self._list.setSpacing(0)      # l'air vient des marges de la feuille
        # Une seule partie à la fois : la liste est une navigation, pas une
        # sélection.
        self._list.setSelectionMode(QAbstractItemView.SingleSelection)
        self._list.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)

        self._pages = QStackedWidget()
        for tab in self._tabs:
            self._pages.addWidget(tab)
            tab.state_changed.connect(self._refresh_badges)

        self._add_row(0)              # les pages
        self._add_family_row()        # « Grille », simple intitulé
        for position in range(1, len(self._tabs)):
            self._add_row(position)

        self._list.currentRowChanged.connect(self._on_tab_picked)
        self._list.setCurrentRow(0)

        layout = QHBoxLayout(self)
        layout.addWidget(self._list)
        layout.addWidget(self._pages, 1)
        self.retranslate_ui()

    def _add_row(self, position: int) -> None:
        """Une ligne cliquable pour un onglet. Les seconds rangs sont décalés."""
        sous_onglet = position > 0
        item = QListWidgetItem("")
        hauteur = SUB_TAB_HEIGHT if sous_onglet else TAB_HEIGHT
        item.setSizeHint(QSize(TAB_WIDTH - 8, hauteur))
        police = self.font()
        police.setPointSize(police.pointSize()
                            + (SUB_TAB_BOOST if sous_onglet else TAB_BOOST))
        police.setBold(not sous_onglet)
        item.setFont(police)
        if sous_onglet:
            item.setData(Qt.UserRole + 1, True)
        self._list.addItem(item)
        self._rows.append(position)

    def _add_family_row(self) -> None:
        """L'intitulé « Grille » : une ligne qui nomme, et qu'on ne sélectionne pas.

        Cliquable, elle aurait fait un quatrième onglet sans contenu ; muette,
        elle laisse voir que les trois lignes suivantes vont ensemble.
        """
        item = QListWidgetItem("")
        item.setSizeHint(QSize(TAB_WIDTH - 8, TAB_HEIGHT))
        item.setFlags(Qt.NoItemFlags)
        police = self.font()
        police.setPointSize(police.pointSize() + TAB_BOOST)
        police.setBold(True)
        item.setFont(police)
        self._list.addItem(item)
        self._rows.append(FAMILY_ROW)

    def _row_of(self, position: int) -> int:
        return self._rows.index(position)

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
        for rang, position in enumerate(self._rows):
            item = self._list.item(rang)
            if position == FAMILY_ROW:
                item.setText(self.tr("Grille"))
                continue
            marge = "    " if item.data(Qt.UserRole + 1) else ""
            item.setText(marge + self._tabs[position].title())
            item.setIcon(state_icon(self._ready(position), palette))
        self.advance_state_changed.emit()

    def _on_tab_picked(self, row: int) -> None:
        if 0 <= row < len(self._rows) and self._rows[row] != FAMILY_ROW:
            self._pages.setCurrentIndex(self._rows[row])
        self.advance_state_changed.emit()

    def _current_tab(self) -> int:
        rang = self._list.currentRow()
        if 0 <= rang < len(self._rows) and self._rows[rang] != FAMILY_ROW:
            return self._rows[rang]
        return -1

    # --- Ce que la fenêtre demande ---------------------------------------

    def can_advance(self) -> bool:
        """La partie affichée laisse-t-elle passer à la suivante ?"""
        position = self._current_tab()
        return position >= 0 and self._tabs[position].is_valid()

    def advance(self) -> bool:
        """Valide la partie affichée et passe à la suivante.

        Rend vrai si l'écran a consommé le clic — il restait une partie à
        traiter —, faux s'il faut maintenant quitter l'étape. C'est ce qui
        permet à la fenêtre de garder un seul bouton « Suivant » : il déroule
        les parties, puis change d'étape.
        """
        position = self._current_tab()
        if position < 0 or not self._tabs[position].is_valid():
            return True                     # rien ne bouge, mais on garde le clic
        self._validated.add(position)
        self._refresh_badges()
        if position + 1 < len(self._tabs):
            self._list.setCurrentRow(self._row_of(position + 1))
            return True
        return False

    def all_ready(self) -> bool:
        return all(self._ready(position) for position in range(len(self._tabs)))
