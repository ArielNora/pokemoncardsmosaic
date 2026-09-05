"""Étape 2 — les paramètres, une décision par onglet.

Un seul formulaire portait tout : dimensions, format, orientation, finesse,
panneaux, cases vides. Rien ne disait par quoi commencer, ni ce que chaque
réglage changeait aux autres. On reprend la forme des écrans de création de
personnage : une liste de parties à gauche, le détail à droite, et une coche
verte quand la partie est réglée.

Une partie est **prête** quand l'utilisateur l'a validée par « Suivant » **et**
que son contenu tient toujours debout. Revenir en arrière ne défait donc rien,
mais changer un réglage jusqu'à le rendre invalide rallume l'avertissement.

L'étape porte aussi les réglages de l'algorithme, qui formaient une étape à
part : deux décisions du même souffle, séparées par un « Suivant » que rien ne
justifiait.
"""

from PySide6.QtCore import QEvent, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QStackedWidget,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QWidget,
)

from . import theme
from .algorithm_tabs import AdvancedTab, SearchTab
from .layout_tabs import (
    CardSizeTab,
    GridSizeTab,
    LayoutTab,
    PaperTab,
    PlacementTab,
)
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
# Ce que le second rang cède sur sa gauche. Son bord **droit** reste aligné sur
# celui des onglets primaires : décalé des deux côtés, il aurait flotté au
# milieu de la colonne sans se rattacher à rien.
SUB_TAB_INDENT = 26
# Le tronc qui les relie, dans l'espace ainsi libéré, et son épaisseur.
TRUNK_X = 9
TRUNK_WIDTH = 2
# Les marges que la feuille de style pose autour de chaque onglet. Le tronc
# s'arrête au bas du **dessin** du dernier, pas au bas de sa ligne, et le cadre
# se peint dedans.
BOX_BOTTOM_MARGIN = 8
BOX_SIDE_MARGIN = 2
BOX_RADIUS = 7
# Ce que leur libellé gagne sur la police de l'interface. Les seconds rangs n'y
# gagnent rien : c'est ce qui les distingue au premier coup d'œil.
TAB_BOOST = 2
SUB_TAB_BOOST = 0
# Intitulé de la famille, posé sur une ligne qui n'est pas un onglet.
FAMILY_ROW = -1


# Ce qui reste de la pastille sur un onglet encore verrouillé. Qt éteint le
# libellé d'une ligne désactivée, mais pas une icône que nous dessinons
# nous-mêmes : à pleine intensité, elle réclamait l'attention pour une partie
# sur laquelle on ne peut rien.
LOCKED_OPACITY = 0.35


# Les trois états d'une partie, et ce qui les dit : le rôle de couleur du thème
# et le signe dessiné. ⚠️ **La croix rouge est réservée à ce qui bloque** — des
# cartes qui ne tiennent pas dans les pages, des cases vides pas toutes posées.
# L'ambre dit « pas encore fait », ce qui n'est pas une faute : au premier
# passage, tout est ambre, et un écran de croix rouges accueillerait
# l'utilisateur comme un formulaire raté.
BLOCKED, PENDING, READY = "error", "warning", "ok"
STATE_SIGNS = {BLOCKED: "✕", PENDING: "!", READY: "✓"}


def state_icon(state: str, palette, locked: bool = False) -> QIcon:
    """La pastille d'une partie : croix rouge, point ambré ou coche verte.

    Dessinée plutôt que prise à un thème d'icônes : celui-ci n'existe ni sur
    macOS ni sur Windows, et la couleur doit de toute façon venir de nos deux
    palettes pour rester lisible dans les deux modes.
    """
    pixmap = QPixmap(BADGE, BADGE)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    if locked:
        painter.setOpacity(LOCKED_OPACITY)
    painter.setPen(QColor(theme.colours(palette)[state]))
    police = painter.font()
    police.setPointSize(BADGE - 6)
    police.setBold(True)
    painter.setFont(police)
    painter.drawText(pixmap.rect(), Qt.AlignCenter, STATE_SIGNS[state])
    painter.end()
    return QIcon(pixmap)


class TabDelegate(QStyledItemDelegate):
    """Dessine le cadre d'un onglet, et rétrécit ceux du second rang.

    Un `QListView` donne à chaque ligne toute la largeur de sa vue, et une
    feuille de style ne sait pas viser une ligne en particulier : ni le retrait
    du second rang, ni la couleur d'état de chacun ne peuvent venir d'elle.
    C'est donc ici qu'on peint le fond et le contour, et qu'on reprend la place
    à gauche. Le clic, lui, porte toujours sur la ligne entière — viser le
    retrait plutôt que l'onglet ne doit pas rester sans effet.
    """

    def paint(self, painter, option, index) -> None:
        # Copiée : la vue réutilise la sienne d'une ligne à l'autre, et ce
        # qu'on y change déborderait sur les suivantes.
        option = QStyleOptionViewItem(option)
        if index.data(Qt.UserRole + 1):
            option.rect = option.rect.adjusted(SUB_TAB_INDENT, 0, 0, 0)

        etat = index.data(Qt.UserRole + 2)
        if etat:
            selection = bool(option.state & QStyle.State_Selected)
            verrouille = not (option.state & QStyle.State_Enabled)
            fond, contour, epaisseur = theme.tab_box(
                etat, option.palette, selection, verrouille)
            # Le survol reprend le fond de la sélection sans son trait épais :
            # la feuille de style le donnait, et le retirer aurait supprimé le
            # seul signe qu'une ligne est cliquable.
            if option.state & QStyle.State_MouseOver and not selection:
                fond = theme.tab_box(etat, option.palette, True, verrouille)[0]
            cadre = QRectF(option.rect.adjusted(
                BOX_SIDE_MARGIN, 0, -BOX_SIDE_MARGIN, -BOX_BOTTOM_MARGIN))
            painter.save()
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setBrush(QColor(fond))
            painter.setPen(QPen(QColor(contour), epaisseur))
            painter.drawRoundedRect(cadre.adjusted(
                epaisseur / 2, epaisseur / 2, -epaisseur / 2, -epaisseur / 2),
                BOX_RADIUS, BOX_RADIUS)
            painter.restore()
            # ⚠️ **La sélection est déjà dite par le cadre.** Laissée au style,
            # elle repeindrait le fond en bleu par-dessus, et l'onglet ouvert
            # serait le seul à ne plus montrer son état.
            option.state &= ~QStyle.State_Selected
        super().paint(painter, option, index)


class TabList(QListWidget):
    """La colonne d'onglets, et le trait qui rattache le second rang au premier.

    Trois onglets décalés se lisent comme trois onglets décalés ; un trait
    unique qui les longe dit qu'ils sortent tous du même. Il est tracé ici et
    non par un cadre autour d'eux : un cadre les séparerait de leur intitulé,
    qui n'est pas dedans.
    """

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        # ⚠️ **Un trait par famille**, et non un seul du premier au dernier
        # sous-onglet : il y a plusieurs familles, et un trait unique traverserait
        # l'intitulé de la seconde en prétendant que tout descend de la première.
        # On les reconnaît à ce qu'elles sont **contiguës**.
        painter = QPainter(self.viewport())
        painter.setPen(QPen(QColor(theme.colours(self.palette())["button_border"]),
                            TRUNK_WIDTH))
        for groupe in self._sub_tab_runs():
            premier = self.visualItemRect(self.item(groupe[0]))
            dernier = self.visualItemRect(self.item(groupe[-1]))
            x = premier.left() + TRUNK_X
            painter.drawLine(x, premier.top(),
                             x, dernier.bottom() - BOX_BOTTOM_MARGIN)
        painter.end()

    def _sub_tab_runs(self) -> list[list[int]]:
        """Les suites de sous-onglets visibles, une par famille dépliée."""
        groupes: list[list[int]] = []
        for rang in range(self.count()):
            visible = (self.item(rang).data(Qt.UserRole + 1)
                       and not self.isRowHidden(rang))
            if not visible:
                groupes.append([])
            elif groupes and groupes[-1]:
                groupes[-1].append(rang)
            else:
                groupes.append([rang])
        return [groupe for groupe in groupes if groupe]


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
        # Position de l'onglet affiché. La liste ne suffit pas à la donner :
        # cliquer l'intitulé de famille y déplace le rang courant, et il faut
        # savoir où revenir.
        self._position = 0
        # Les familles repliées. On s'ouvre toutes dépliées : cacher au premier
        # regard les trois quarts du parcours le raccourcirait pour de faux.
        self._collapsed: set[str] = set()
        # Vrai le temps d'un retour de sélection que nous provoquons.
        self._navigating = False
        self._build()

    # --- Construction -----------------------------------------------------

    def _build(self) -> None:
        # ⚠️ **L'ordre est celui des décisions** : d'abord le papier, ensuite ce
        # qu'on y pose, enfin comment on l'assemble. Deux familles coiffent
        # chacune leurs onglets ; « Pages » n'en a pas, elle décide seule.
        menu = [
            (None, [PaperTab]),
            ("grid", [GridSizeTab, CardSizeTab, PlacementTab]),
            ("algorithm", [SearchTab, AdvancedTab]),
        ]
        self._tabs: list[LayoutTab] = []
        # Rang de la liste -> onglet, ou `FAMILY_ROW` pour un intitulé.
        self._rows: list[int] = []
        # Clé de famille -> les positions qu'elle chapeaute, et son rang.
        self._families: dict[str, list[int]] = {}
        self._family_rows: dict[str, int] = {}

        self._list = TabList()
        self._list.setItemDelegate(TabDelegate(self._list))
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

        for cle, classes in menu:
            if cle is not None:
                self._family_rows[cle] = len(self._rows)
                self._add_family_row()
                self._families[cle] = []
            for fabrique in classes:
                position = len(self._tabs)
                onglet = fabrique(self._session)
                self._tabs.append(onglet)
                self._pages.addWidget(onglet)
                onglet.state_changed.connect(self._refresh_badges)
                self._add_row(position, sous_onglet=cle is not None)
                if cle is not None:
                    self._families[cle].append(position)

        self._list.currentRowChanged.connect(self._on_tab_picked)
        self._list.itemClicked.connect(self._on_item_clicked)
        self._list.setCurrentRow(0)

        layout = QHBoxLayout(self)
        layout.addWidget(self._list)
        layout.addWidget(self._pages, 1)
        self.retranslate_ui()

    def _add_row(self, position: int, sous_onglet: bool) -> None:
        """Une ligne cliquable pour un onglet. Les seconds rangs sont décalés."""
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
        """L'intitulé « Grille » : il nomme le groupe, et le plie.

        **Cliquable sans être sélectionnable** : il n'a pas de contenu à
        montrer, donc il ne peut pas devenir une destination ; mais un titre de
        groupe qui ne répond pas au clic passe pour un onglet en panne. Il plie
        et déplie les trois lignes qu'il chapeaute, comme n'importe quel
        accordéon.
        """
        item = QListWidgetItem("")
        item.setSizeHint(QSize(TAB_WIDTH - 8, TAB_HEIGHT))
        item.setFlags(Qt.ItemIsEnabled)
        police = self.font()
        police.setPointSize(police.pointSize() + TAB_BOOST)
        police.setBold(True)
        item.setFont(police)
        self._list.addItem(item)
        self._rows.append(FAMILY_ROW)

    def _row_of(self, position: int) -> int:
        return self._rows.index(position)

    def changeEvent(self, event) -> None:
        """Suit la bascule clair/sombre : les pastilles sont des images posées.

        Le cadre d'un onglet se relit à chaque dessin et change de mode tout
        seul ; la pastille, elle, a été peinte une fois avec la couleur du mode
        d'alors.
        """
        super().changeEvent(event)
        if event.type() == QEvent.PaletteChange:
            self._refresh_badges()

    def retranslate_ui(self) -> None:
        for tab in self._tabs:
            tab.retranslate_ui()
        self._refresh_badges()

    # --- État des onglets -------------------------------------------------

    def _ready(self, position: int) -> bool:
        """Validée par l'utilisateur, **et** toujours valide."""
        return position in self._validated and self._tabs[position].is_valid()

    def _state(self, position: int) -> str:
        """L'état d'une partie : bloquée, en attente, ou prête.

        ⚠️ **Bloquée n'est pas « pas encore faite ».** Une partie qu'on n'a pas
        validée est ambre ; elle ne passe au rouge que si son contenu ne tient
        pas debout — des cartes hors des pages, des cases vides pas toutes
        posées. Sans cette distinction, le premier passage montrait un écran
        entier d'alertes pour un travail simplement pas encore fait.
        """
        if not self._tabs[position].is_valid():
            return BLOCKED
        return READY if position in self._validated else PENDING

    def _family_state(self, cle: str) -> str:
        """Ce qu'une famille repliée dit de ses onglets.

        Le pire l'emporte : une croix rouge cachée sous un groupe replié serait
        exactement ce qu'on ne veut pas rater.
        """
        etats = [self._state(position) for position in self._families[cle]]
        for etat in (BLOCKED, PENDING):
            if etat in etats:
                return etat
        return READY

    def _reachable(self, position: int) -> bool:
        """Toutes les parties d'avant ont-elles été validées au moins une fois ?

        ⚠️ **Le parcours se fait dans l'ordre.** Sauter d'un clic à l'onglet des
        écarts sans avoir vu les pages ni la grille, c'est régler la taille des
        cartes pour un papier qu'on n'a pas choisi ; les onglets qui suivent
        dépendent de ce que ceux d'avant décident, et rien à l'écran ne le
        disait.

        Une seule visite validée suffit, **définitivement** : on revient en
        arrière autant qu'on veut, et changer d'avis ne referme rien. C'est
        `_ready` — donc la pastille — qui dit si la partie tient toujours
        debout ; le verrou, lui, ne sert qu'au premier passage.
        """
        return all(rang in self._validated for rang in range(position))

    def _family_of(self, position: int) -> str | None:
        """La famille qui chapeaute cet onglet, s'il en a une."""
        for cle, positions in self._families.items():
            if position in positions:
                return cle
        return None

    def _family_title(self, cle: str) -> str:
        """L'intitulé d'une famille. Littéral : `lupdate` n'extrait que ceux-là."""
        return {"grid": self.tr("Grille"),
                "algorithm": self.tr("Algorithme")}[cle]

    def _family_at_row(self, rang: int) -> str | None:
        for cle, ligne in self._family_rows.items():
            if ligne == rang:
                return cle
        return None

    def _refresh_badges(self) -> None:
        palette = self.palette()
        for rang, position in enumerate(self._rows):
            item = self._list.item(rang)
            if position == FAMILY_ROW:
                cle = self._family_at_row(rang)
                chevron = "▸" if cle in self._collapsed else "▾"
                item.setText(f"{chevron} " + self._family_title(cle))
                # Repliée, la famille répond pour ses trois onglets : sans cela,
                # ce qui reste à faire disparaîtrait avec eux.
                # ⚠️ L'intitulé de famille ne prend **pas** de cadre coloré :
                # il n'est pas une destination, et un cadre en ferait un
                # quatrième onglet. Sa pastille, repliée, dit l'état des siens.
                item.setIcon(state_icon(self._family_state(cle), palette)
                             if cle in self._collapsed else QIcon())
                continue
            # Le retrait est **géométrique** — voir `TabDelegate` — et non
            # quatre espaces dans le libellé, qui décalaient le texte sans
            # décaler l'onglet.
            item.setText(self._tabs[position].title())
            accessible = self._reachable(position)
            etat = self._state(position)
            item.setIcon(state_icon(etat, palette, locked=not accessible))
            # ⚠️ **Le cadre porte la couleur, pas le texte.** La pastille seule
            # tient sur vingt-deux pixels au bord de la colonne, et sur un écran
            # large l'œil est à l'autre bout ; un libellé coloré, lui, perdait
            # le contraste que le mode lui donne. Le délégué lit cet état.
            item.setData(Qt.UserRole + 2, etat)
            item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable if accessible
                          else Qt.NoItemFlags)
            # Un onglet grisé sans un mot laisserait chercher la panne : on dit
            # ce qui l'ouvre.
            item.setToolTip("" if accessible else self.tr(
                "Cliquez « Suivant » sur les parties précédentes pour ouvrir "
                "celle-ci."))
        self.advance_state_changed.emit()

    # --- Navigation -------------------------------------------------------

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        cle = self._family_at_row(self._list.row(item))
        if cle is not None:
            self._toggle_family(cle)

    def _toggle_family(self, cle: str) -> None:
        """Plie ou déplie les onglets d'une famille.

        ⚠️ **Replier depuis l'un d'eux ramène à un onglet sans famille.**
        Garder affiché un onglet dont la ligne vient d'être cachée laisserait un
        écran que plus aucune sélection ne désigne, et un « Suivant » qui avance
        depuis un endroit invisible. Le refuge se cherche : le premier onglet
        hors de toute famille reste visible quoi qu'on plie, alors que la
        position 0 pourrait un jour entrer dans un groupe.
        """
        plie = cle not in self._collapsed
        if plie:
            self._collapsed.add(cle)
        else:
            self._collapsed.discard(cle)
        for position in self._families[cle]:
            self._list.setRowHidden(self._row_of(position), plie)
        if plie and self._position in self._families[cle]:
            self._show(self._refuge())
        self._refresh_badges()

    def _refuge(self) -> int:
        """Premier onglet qui n'appartient à aucune famille, donc toujours
        atteignable. Aucun n'en sortirait : à défaut, le premier onglet tout
        court, quitte à déplier sa famille."""
        groupes = {
            position for onglets in self._families.values() for position in onglets
        }
        for position in range(len(self._tabs)):
            if position not in groupes:
                return position
        return 0

    def _show(self, position: int) -> None:
        """Affiche un onglet, en dépliant la famille s'il s'y trouve.

        ⚠️ Un onglet encore **verrouillé** ne s'affiche pas : `setCurrentRow`
        n'a aucun effet sur une ligne désactivée. Le seul chemin qui y mène,
        `advance`, valide la partie et rafraîchit les pastilles — donc ouvre la
        suivante — avant d'appeler ceci. Un futur « aller à l'onglet X » devra
        faire de même, sous peine de ne rien faire, sans erreur.
        """
        cle = self._family_of(position)
        if cle is not None and cle in self._collapsed:
            self._toggle_family(cle)
        self._list.setCurrentRow(self._row_of(position))

    def _on_tab_picked(self, row: int) -> None:
        if 0 <= row < len(self._rows) and self._rows[row] != FAMILY_ROW:
            self._position = self._rows[row]
            self._pages.setCurrentIndex(self._position)
        elif not self._navigating:
            # Le rang courant s'est posé sur l'intitulé de famille, qui n'est
            # pas une destination : on le remet là où l'écran est resté.
            self._navigating = True
            try:
                self._list.setCurrentRow(self._row_of(self._position))
            finally:
                self._navigating = False
        self.advance_state_changed.emit()

    def _current_tab(self) -> int:
        rang = self._list.currentRow()
        if 0 <= rang < len(self._rows) and self._rows[rang] != FAMILY_ROW:
            return self._rows[rang]
        return -1

    # --- Ce que la fenêtre demande ---------------------------------------

    def can_advance(self) -> bool:
        """Le parcours laisse-t-il passer à la suite ?

        ⚠️ **Pas seulement la partie affichée.** Une partie déjà validée qui
        casse — la grille agrandie déborde des pages, une carte de plus fait
        sauter le compte — bloque le bouton **où qu'on soit**, et sa croix
        rouge dans la colonne dit laquelle. Sans cela, on revenait en arrière,
        on cassait quelque chose, on repartait par un onglet plus loin, et l'on
        quittait l'étape avec une mise en page impossible.

        Les parties **pas encore validées** ne comptent pas : au premier
        passage elles sont toutes en attente, et les exiger fermerait le
        chemin qui mène justement à elles.
        """
        position = self._current_tab()
        if position < 0 or not self._tabs[position].is_valid():
            return False
        return all(self._tabs[rang].is_valid() for rang in self._validated)

    def advance(self) -> bool:
        """Valide la partie affichée et passe à la suivante.

        Rend vrai si l'écran a consommé le clic — il restait une partie à
        traiter —, faux s'il faut maintenant quitter l'étape. C'est ce qui
        permet à la fenêtre de garder un seul bouton « Suivant » : il déroule
        les parties, puis change d'étape.
        """
        position = self._current_tab()
        if not self.can_advance():
            return True                     # rien ne bouge, mais on garde le clic
        self._validated.add(position)
        self._refresh_badges()
        if position + 1 < len(self._tabs):
            self._show(position + 1)
            return True
        return False

    def all_ready(self) -> bool:
        return all(self._ready(position) for position in range(len(self._tabs)))
