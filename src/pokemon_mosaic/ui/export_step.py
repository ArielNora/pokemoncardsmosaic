"""Étape 4 : l'export, où l'on habille un agencement gardé avant de l'écrire.

Le calcul est fini, la grille est arrêtée : **sa forme ne se discute plus**.
Ce qui reste ouvert est tout ce qui n'y touche pas, l'écart entre les cartes,
le nombre de feuilles, les couleurs de ce qui n'est pas une carte, la finesse
d'impression. À gauche, trois sections qui se déplient une à la fois ; à droite,
les quatre agencements gardés, le résumé et le bouton d'export ; au milieu,
**l'image**, qui prend tout ce qui reste, se zoome à la molette et se promène au
glissement. C'est elle qu'on est venu regarder : les réglages se replient pour la
laisser respirer.

⚠️ **Ni les colonnes ni les lignes ne s'y règlent.** Les changer défferait
l'agencement que l'algorithme vient de trouver : les cartes ne seraient plus à
leur place, et le score n'aurait plus de sens.
"""

import os

from PySide6.QtCore import QEvent, QPointF, QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap, QPolygonF
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QDoubleSpinBox,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..layout import MM_PER_INCH, REAL_CARD_MM, grid_fits, max_useful_dpi
from . import theme
from .arrangements_dialog import ArrangementsDialog
from .export_dialog import ExportDialog
from .exporter import start_export
from .layout_step import TAB_WIDTH
from .page_preview import PagePreview
from .saved_column import SavedColumn
from .session import Session

# Le zoom de l'aperçu, ses bornes et son pas multiplicatif. À 1, la feuille
# entière tient dans le cadre.
ZOOM_MIN, ZOOM_MAX, ZOOM_STEP = 1.0, 8.0, 1.25
# Les signes du dépliant, devant l'intitulé d'une section.
OPEN_SIGN, CLOSED_SIGN = "▾", "▸"
# Ce que la phrase d'en-tête gagne sur la police de l'interface.
HEADING_BOOST = 2
# L'écart entre la loupe et le bord de l'aperçu qu'elle surplombe.
ZOOM_BAR_MARGIN = 12
# Le champ du zoom : « 100 % » et ses flèches.
ZOOM_FIELD_WIDTH = 82
# Les champs de la présentation : deux tiennent côte à côte dans la colonne.
FIELD_WIDTH = 96
# Les boutons de cette colonne, plus bas et plus petits que ceux d'un écran :
# ce sont des retouches, pas les décisions de l'étape.
SMALL_BUTTON_HEIGHT = 24
SMALL_BUTTON_BOOST = -1
# Taille de la pastille de couleur d'un bouton.
SWATCH = QSize(28, 18)
# La pipette est **dessinée**, et non prise à une police : ni l'émoji goutte ni
# les caractères de dessin ne sont présents partout, et le bouton sortait vide.
EYEDROPPER_SIZE = 16
# Ce qu'on accorde à un fil d'export pour s'arrêter, avant de le dire bloqué.
SHUTDOWN_TIMEOUT_MS = 5000


def eyedropper_icon(palette) -> QIcon:
    """Une petite pipette : un tube en biais, sa pointe en bas à gauche."""
    pixmap = QPixmap(EYEDROPPER_SIZE, EYEDROPPER_SIZE)
    pixmap.fill(Qt.transparent)
    peintre = QPainter(pixmap)
    peintre.setRenderHint(QPainter.Antialiasing)
    encre = palette.windowText().color()
    peintre.setPen(QPen(encre, 2.2))
    peintre.drawLine(QPointF(5.5, 10.5), QPointF(12.5, 3.5))
    peintre.setPen(Qt.NoPen)
    peintre.setBrush(encre)
    peintre.drawPolygon(QPolygonF([QPointF(2.5, 13.5), QPointF(7.0, 12.0),
                                   QPointF(4.0, 9.0)]))
    peintre.end()
    return QIcon(pixmap)


def _separator() -> QFrame:
    """Un trait horizontal, pour séparer deux sujets d'une même section."""
    trait = QFrame()
    trait.setFrameShape(QFrame.HLine)
    trait.setFrameShadow(QFrame.Sunken)
    return trait


def swatch(colour) -> str:
    """La feuille de style d'un bouton qui montre sa couleur."""
    return (f"background: rgb({colour[0]}, {colour[1]}, {colour[2]});"
            " border: 1px solid palette(mid); border-radius: 3px;")


class ExportTab(QWidget):
    """Un onglet de l'étape, avec son intitulé."""

    def __init__(self, session: Session, parent=None):
        super().__init__(parent)
        self._session = session
        self._updating = False

    def title(self) -> str:
        raise NotImplementedError

    def refresh(self) -> None:
        pass


class PresentationTab(ExportTab):
    """Ce qui se règle encore sans toucher à la forme de la grille."""

    def __init__(self, session: Session, parent=None):
        super().__init__(session, parent)
        # ⚠️ **De petits champs, et sur une seule ligne.** Les grands compteurs
        # de l'étape 2 prenaient chacun cent cinquante pixels de haut : ici on
        # ne pose pas la mise en page, on la retouche, et la place qu'ils
        # prenaient revient à l'image.
        self._gap = QDoubleSpinBox()
        self._gap.setRange(0.0, 50.0)
        self._gap.setSingleStep(0.5)
        self._gap.valueChanged.connect(self._on_gap)
        self._width = QDoubleSpinBox()
        self._width.setRange(1.0, 200.0)
        self._width.setSingleStep(0.5)
        self._width.valueChanged.connect(self._on_width)
        self._width_label = QLabel()
        self._gap_label = QLabel()
        for champ in (self._width, self._gap):
            champ.setFixedWidth(FIELD_WIDTH)

        self._real_width = QPushButton()
        self._real_width.clicked.connect(self._on_real_width)
        self._auto_width = QPushButton()
        self._auto_width.clicked.connect(self._on_auto_width)
        self._centre = QPushButton()
        self._centre.clicked.connect(self._session.center_panels)
        for bouton in (self._real_width, self._auto_width, self._centre):
            bouton.setFixedHeight(SMALL_BUTTON_HEIGHT)
            police = bouton.font()
            police.setPointSize(police.pointSize() + SMALL_BUTTON_BOOST)
            bouton.setFont(police)

        # ⚠️ **Un sujet par bloc, séparés d'un trait.** La largeur et ses deux
        # boutons vont ensemble, l'écart est autre chose, et le centrage ne
        # touche à aucune taille : tout à la file, on cliquait « Au plus grand »
        # en croyant agir sur l'écart au-dessus duquel il se trouvait.
        tailles = QHBoxLayout()
        tailles.setSpacing(6)
        tailles.addWidget(self._real_width)
        tailles.addWidget(self._auto_width)

        centrage = QHBoxLayout()
        centrage.addStretch(1)
        centrage.addWidget(self._centre)
        centrage.addStretch(1)

        pile = QVBoxLayout(self)
        pile.setContentsMargins(6, 4, 6, 6)
        pile.setSpacing(6)
        pile.addWidget(self._width_label)
        pile.addWidget(self._width)
        pile.addLayout(tailles)
        pile.addWidget(_separator())
        pile.addWidget(self._gap_label)
        pile.addWidget(self._gap)
        pile.addWidget(_separator())
        pile.addLayout(centrage)
        self.retranslate_ui()

    def title(self) -> str:
        return self.tr("Présentation")

    def retranslate_ui(self) -> None:
        self._width_label.setText(self.tr("Largeur de la carte (mm)"))
        self._gap_label.setText(self.tr("Écart entre les cartes (mm)"))
        self._real_width.setText(self.tr("Taille réelle"))
        self._auto_width.setText(self.tr("Au plus grand"))
        self._centre.setText(self.tr("Centrer"))
        self._real_width.setToolTip(
            self.tr("Une carte à sa taille réelle, %1 mm de large.")
            .replace("%1", f"{REAL_CARD_MM[0]:.0f}"))
        self.refresh()

    def refresh(self) -> None:
        self._updating = True
        session = self._session
        self._gap.setValue(session.card_gap_mm)
        largeur = session.card_width_mm
        if largeur is None:
            # ⚠️ **La géométrie compte en pixels.** Posée telle quelle dans un
            # champ en millimètres, la largeur automatique s'affichait à 200,
            # c'est-à-dire écrêtée au maximum du champ.
            largeur = (session.panel_geometry().card_w
                       * MM_PER_INCH / session.dpi)
        self._width.setValue(largeur)
        self._updating = False

    def _on_gap(self, valeur: float) -> None:
        if not self._updating:
            self._session.set_layout(card_gap_mm=valeur)

    def _on_width(self, valeur: float) -> None:
        if not self._updating:
            self._session.set_layout(card_width_mm=valeur)

    def _on_real_width(self) -> None:
        """La largeur d'une vraie carte : la mosaïque en taille de collection."""
        self._session.set_layout(card_width_mm=REAL_CARD_MM[0])

    def _on_auto_width(self) -> None:
        """Rend la largeur au calcul : la plus grande qui fasse tenir la grille."""
        self._session.set_layout(card_width_mm=None)


class ColoursTab(ExportTab):
    """Les couleurs de tout ce qui n'est pas une carte, et le mode caméléon."""

    ROLES = ("background_colour", "gap_colour", "empty_colour")
    # Une pipette demandée : l'écran passera en prélèvement, et rendra la
    # couleur au rôle qui l'attend.
    eyedropper_requested = Signal(str)

    def __init__(self, session: Session, parent=None):
        super().__init__(session, parent)
        self._labels: dict[str, QLabel] = {}
        self._buttons: dict[str, QPushButton] = {}
        self._droppers: dict[str, QPushButton] = {}

        pile = QVBoxLayout(self)
        pile.setContentsMargins(6, 4, 6, 6)
        pile.setSpacing(6)
        for role in self.ROLES:
            intitule = QLabel()
            bouton = QPushButton()
            bouton.setFixedSize(SWATCH)
            bouton.clicked.connect(lambda _=False, r=role: self._pick(r))
            # ⚠️ **Une pipette par couleur.** Une seule, pour « la ligne
            # sélectionnée », aurait demandé de choisir la ligne d'abord : un
            # état de plus à retenir pour un geste qui doit être direct.
            pipette = QPushButton()
            pipette.setFixedSize(SWATCH.height() + 6, SWATCH.height())
            pipette.clicked.connect(
                lambda _=False, r=role: self.eyedropper_requested.emit(r))
            self._labels[role] = intitule
            self._buttons[role] = bouton
            self._droppers[role] = pipette
            ligne = QHBoxLayout()
            ligne.setSpacing(6)
            ligne.addWidget(bouton)
            ligne.addWidget(pipette)
            ligne.addWidget(intitule, 1)
            pile.addLayout(ligne)

        pile.addWidget(_separator())
        self._chameleon_title = QLabel()
        gras = self._chameleon_title.font()
        gras.setBold(True)
        self._chameleon_title.setFont(gras)
        self._chameleon_gaps = QCheckBox()
        self._chameleon_gaps.toggled.connect(
            lambda actif: self._session.set_algorithm(chameleon_gaps=actif))
        self._chameleon_border = QCheckBox()
        self._chameleon_border.toggled.connect(
            lambda actif: self._session.set_algorithm(chameleon_border=actif))
        pile.addWidget(self._chameleon_title)
        pile.addWidget(self._chameleon_gaps)
        pile.addWidget(self._chameleon_border)
        self.retranslate_ui()

    def title(self) -> str:
        return self.tr("Couleurs des vides")

    def retranslate_ui(self) -> None:
        self._labels["background_colour"].setText(self.tr("Autour de la grille"))
        self._labels["gap_colour"].setText(self.tr("Entre les cartes"))
        self._labels["empty_colour"].setText(self.tr("Cases vides"))
        for pipette in self._droppers.values():
            pipette.setIcon(eyedropper_icon(self.palette()))
            pipette.setToolTip(self.tr("Prélever une couleur dans l'image"))
        self._chameleon_title.setText(self.tr("Caméléon"))
        self._chameleon_gaps.setText(self.tr("Écarts entre les cartes"))
        self._chameleon_border.setText(self.tr("Pourtour de la grille"))
        self._chameleon_gaps.setToolTip(
            self.tr("Chaque écart passe d'un bord de carte à l'autre en "
                    "dégradé, au lieu d'un aplat."))
        self._chameleon_border.setToolTip(
            self.tr("Une bande large comme l'écart cerne la mosaïque, du bord "
                    "des cartes vers la couleur du fond."))
        self.refresh()

    def refresh(self) -> None:
        session = self._session
        for role, bouton in self._buttons.items():
            bouton.setStyleSheet(swatch(getattr(session, role)))
        self._updating = True
        self._chameleon_gaps.setChecked(session.chameleon_gaps)
        self._chameleon_border.setChecked(session.chameleon_border)
        self._updating = False
        # ⚠️ **Grisée, pas retirée.** Le caméléon remplace la couleur des
        # écarts ; l'effacer ferait oublier ce qu'on retrouvera en éteignant le
        # mode.
        for widget in (self._buttons["gap_colour"], self._droppers["gap_colour"],
                       self._labels["gap_colour"]):
            widget.setEnabled(not session.chameleon_gaps)

    def changeEvent(self, event) -> None:
        """⚠️ Une icône dessinée ne suit pas le mode toute seule : sa couleur
        est figée dans le pixmap, là où tout ce qui se relit au dessin bascule
        de lui-même."""
        super().changeEvent(event)
        if event.type() == QEvent.PaletteChange:
            self.retranslate_ui()

    def _pick(self, role: str) -> None:
        actuelle = QColor(*getattr(self._session, role))
        choisie = QColorDialog.getColor(actuelle, self, self._labels[role].text())
        if choisie.isValid():
            # La session prévient tout le monde, cet onglet compris : un
            # second chemin ferait deux repeints pour un clic.
            self._session.set_algorithm(
                **{role: (choisie.red(), choisie.green(), choisie.blue())})


class ResolutionTab(ExportTab):
    """La finesse d'impression, et ce qu'elle donne en pixels.

    ⚠️ **Le zoom n'est plus ici.** Il porte sur l'image, pas sur le fichier à
    écrire : le ranger dans une section qu'il faut déplier pour s'en servir le
    mettait à trois clics de ce qu'il agrandit.
    """

    def __init__(self, session: Session, parent=None):
        super().__init__(session, parent)
        self._dpi = QSpinBox()
        self._dpi.setRange(50, 1200)
        self._dpi.setSingleStep(50)
        self._dpi.valueChanged.connect(self._on_dpi)
        self._dpi_label = QLabel()
        self._pixels = QLabel()
        self._pixels.setWordWrap(True)

        finesse = QHBoxLayout()
        finesse.setSpacing(8)
        finesse.addWidget(self._dpi_label)
        finesse.addWidget(self._dpi, 1)

        pile = QVBoxLayout(self)
        pile.setContentsMargins(6, 4, 6, 6)
        pile.setSpacing(6)
        pile.addLayout(finesse)
        pile.addWidget(self._pixels)
        self.retranslate_ui()

    def title(self) -> str:
        return self.tr("Résolution")

    def retranslate_ui(self) -> None:
        self._dpi_label.setText(self.tr("Finesse (DPI)"))
        self.refresh()

    def refresh(self) -> None:
        self._updating = True
        session = self._session
        self._dpi.setValue(session.dpi)
        self._updating = False
        largeur, hauteur = session.paper_mm()
        pixels_l = round(largeur / 25.4 * session.dpi)
        pixels_h = round(hauteur / 25.4 * session.dpi)
        texte = (self.tr("Chaque feuille fera %1 × %2 pixels.")
                 .replace("%1", str(pixels_l)).replace("%2", str(pixels_h)))
        cartes = session.card_set
        if cartes is not None and len(cartes):
            utile = max_useful_dpi(session.paper_mm(), session.cols,
                                   cartes.full_size[0])
            if session.dpi > utile:
                texte += " " + (self.tr("Au-delà de %1 DPI, l'impression "
                                        "agrandit sans ajouter de détail.")
                                .replace("%1", f"{utile:.0f}"))
        self._pixels.setText(texte)

    def _on_dpi(self, valeur: int) -> None:
        if not self._updating:
            self._session.set_layout(dpi=valeur)


class Section(QWidget):
    """Un intitulé qu'on déplie, et ses réglages en dessous.

    ⚠️ **Un seul ouvert à la fois**, décidé par le panneau : deux sections
    dépliées font défiler la colonne, et l'œil ne sait plus où regarder.
    """

    toggled = Signal(str)

    def __init__(self, key: str, content: QWidget, parent=None):
        super().__init__(parent)
        self._key = key
        self._content = content
        self._header = QPushButton()
        self._header.setCheckable(True)
        self._header.clicked.connect(lambda: self.toggled.emit(self._key))
        police = self._header.font()
        police.setBold(True)
        self._header.setFont(police)

        cadre = QFrame()
        theme.mark(cadre, "section")
        dedans = QVBoxLayout(cadre)
        dedans.setContentsMargins(0, 0, 0, 0)
        dedans.addWidget(content)
        self._frame = cadre

        pile = QVBoxLayout(self)
        pile.setContentsMargins(0, 0, 0, 0)
        pile.setSpacing(4)
        pile.addWidget(self._header)
        pile.addWidget(cadre)
        self.set_open(False)

    def key(self) -> str:
        return self._key

    def content(self) -> QWidget:
        return self._content

    def set_open(self, ouverte: bool) -> None:
        self._open = ouverte
        self._header.setChecked(ouverte)
        self._frame.setVisible(ouverte)
        self.retranslate_ui()

    def is_open(self) -> bool:
        return self._open

    def retranslate_ui(self) -> None:
        signe = OPEN_SIGN if self._open else CLOSED_SIGN
        self._header.setText(f"{signe}  {self._content.title()}")


class PreviewView(QScrollArea):
    """Le cadre de l'aperçu : molette pour zoomer, glissement pour se déplacer.

    ⚠️ **Les gestes se prennent sur l'aperçu, pas sur le cadre.** C'est lui que
    la souris survole : posés sur le cadre, le clic et la molette ne lui
    arrivaient jamais, et rien ne bougeait. On l'écoute donc directement, par
    un filtre d'événements.

    ⚠️ **Le zoom garde le point sous le curseur.** Sans cela, agrandir renvoyait
    à chaque cran vers le coin haut-gauche, et il fallait retrouver à la main
    l'endroit qu'on regardait.
    """

    zoom_requested = Signal(float, object)   # facteur, point visé dans la vue
    colour_picked = Signal(object)           # QColor prélevée dans l'image

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pan_from = None
        self._bars_at_press = (0, 0)
        # Vrai le temps d'un prélèvement : le prochain clic prend la couleur
        # sous le curseur au lieu de saisir l'image.
        self._picking = False
        # Faux quand la souris appartient à la grille : c'est alors l'aperçu qui
        # reçoit le glissement, pour déplacer la mosaïque dans sa feuille.
        self._panning = True

    def setWidget(self, widget) -> None:
        super().setWidget(widget)
        # La croix directionnelle dit que ça se déplace, comme une fenêtre
        # qu'on tire. Posée sur l'aperçu, elle se voit là où la souris est.
        widget.setCursor(Qt.SizeAllCursor)
        widget.installEventFilter(self)

    def eventFilter(self, objet, event) -> bool:
        if objet is not self.widget():
            return super().eventFilter(objet, event)
        if event.type() == QEvent.Wheel:
            return self._on_wheel(event)
        if event.type() == QEvent.NativeGesture:
            return self._on_gesture(event)
        if event.type() == QEvent.MouseButtonPress:
            return self._on_press(event)
        if event.type() == QEvent.MouseMove:
            return self._on_move(event)
        if event.type() == QEvent.MouseButtonRelease:
            self._pan_from = None
            return False
        return super().eventFilter(objet, event)

    def _on_wheel(self, event) -> bool:
        """La molette zoome ; deux doigts qui glissent déplacent.

        ⚠️ **Un pavé tactile envoie aussi des événements de molette.** Traités
        comme tels, le glissement à deux doigts zoomait au lieu de promener
        l'image : on les reconnaît à leur delta **en pixels**, qu'une molette
        crantée ne donne jamais, et on les laisse au cadre, qui sait défiler.
        Ctrl reste le raccourci du zoom dans les deux cas.
        """
        controle = bool(event.modifiers() & Qt.ControlModifier)
        pave = (not event.pixelDelta().isNull()
                or event.phase() != Qt.NoScrollPhase)
        if pave and not controle:
            return False
        crans = event.angleDelta().y()
        if not crans:
            return False
        facteur = ZOOM_STEP if crans > 0 else 1 / ZOOM_STEP
        self.zoom_requested.emit(facteur, self._aimed(event.position()))
        return True

    def _on_gesture(self, event) -> bool:
        """Le pincement du pavé tactile : deux doigts qui s'écartent zooment.

        Qt le remonte comme un geste natif, jamais comme une molette : sans ce
        cas, écarter les doigts ne faisait rien du tout.
        """
        if event.gestureType() != Qt.ZoomNativeGesture:
            return False
        facteur = 1.0 + event.value()
        if facteur <= 0:
            return False
        self.zoom_requested.emit(facteur, self._aimed(event.position()))
        return True

    def _aimed(self, position) -> QPointF:
        """Le point visé, lu dans le cadre : c'est lui qui défile."""
        return QPointF(self.widget().mapTo(self.viewport(), position.toPoint()))

    def set_panning(self, actif: bool) -> None:
        self._panning = bool(actif)
        if self.widget() is not None and not self._picking:
            self.widget().setCursor(Qt.SizeAllCursor if actif
                                    else Qt.OpenHandCursor)

    def start_picking(self) -> None:
        """Arme la pipette : le prochain clic prélève au lieu de déplacer."""
        self._picking = True
        self.widget().setCursor(Qt.CrossCursor)

    def stop_picking(self) -> None:
        self._picking = False
        if self.widget() is not None:
            self.widget().setCursor(Qt.SizeAllCursor)

    def _on_press(self, event) -> bool:
        if event.button() != Qt.LeftButton:
            return False
        if not self._picking and not self._panning:
            # La grille prend le geste : l'aperçu sait le faire lui-même.
            return False
        if self._picking:
            # ⚠️ **On prélève dans le dessin, pas dans un modèle.** L'aperçu se
            # rend à la demande : `grab()` donne exactement ce que l'œil voit,
            # dégradés du caméléon compris.
            point = event.position().toPoint()
            image = self.widget().grab(
                QRect(point, QSize(1, 1))).toImage()
            if not image.isNull():
                self.colour_picked.emit(image.pixelColor(0, 0))
            self.stop_picking()
            return True
        # ⚠️ **La position se lit à l'écran.** Celle du widget bouge avec lui
        # quand on le fait défiler : l'écart calculé s'annulait au tour suivant,
        # et l'image tremblait sur place au lieu de suivre la souris.
        self._pan_from = event.globalPosition()
        self._bars_at_press = (self.horizontalScrollBar().value(),
                               self.verticalScrollBar().value())
        return True

    def _on_move(self, event) -> bool:
        if self._pan_from is None or not self._panning:
            return False
        ecart = event.globalPosition() - self._pan_from
        x, y = self._bars_at_press
        self.horizontalScrollBar().setValue(int(x - ecart.x()))
        self.verticalScrollBar().setValue(int(y - ecart.y()))
        return True


class ExportStep(QWidget):
    """L'écran d'export : les onglets, l'aperçu, et les agencements gardés."""

    status_message = Signal(str)

    def __init__(self, session: Session, arrangements_directory: str = "",
                 parent=None):
        super().__init__(parent)
        self._session = session
        self._arrangements_directory = arrangements_directory
        self._export_thread = None
        self._export_worker = None
        self._slot: int | None = None
        self._build()
        session.saved_changed.connect(self._on_saved_changed)
        session.layout_changed.connect(self._on_layout_changed)
        # Les couleurs voyagent avec les réglages d'algorithme : l'aperçu, les
        # pastilles des boutons et les vignettes de la colonne en dépendent.
        session.algorithm_changed.connect(self._on_layout_changed)
        session.algorithm_changed.connect(self._saved.refresh)

    # --- Construction -----------------------------------------------------

    def _build(self) -> None:
        self._tabs = [PresentationTab(self._session),
                      ColoursTab(self._session),
                      ResolutionTab(self._session)]

        # ⚠️ **Les réglages se replient.** Trois panneaux ouverts d'un coup
        # prenaient la moitié de l'écran pour des champs qu'on touche une fois :
        # ici on vient regarder le poster, pas les formulaires.
        self._sections = [Section(onglet.title(), onglet) for onglet in self._tabs]
        colonne = QVBoxLayout()
        colonne.setContentsMargins(0, 0, 0, 0)
        colonne.setSpacing(8)
        for section in self._sections:
            section.toggled.connect(self._toggle_section)
            colonne.addWidget(section)
        colonne.addStretch(1)
        gauche = QWidget()
        gauche.setLayout(colonne)
        # ⚠️ **Largeur fixe.** Un champ un peu large repoussait sinon l'image,
        # qui est la seule chose de cet écran qu'on regarde longtemps.
        gauche.setFixedWidth(TAB_WIDTH)
        self._sections[0].set_open(True)

        self._heading = QLabel()
        entete = self._heading.font()
        entete.setBold(True)
        entete.setPointSize(entete.pointSize() + HEADING_BOOST)
        self._heading.setFont(entete)

        # L'aperçu montre le poster tel qu'il s'imprimera, agencement compris.
        self._preview = PagePreview(self._session)
        self._preview.set_show_grid(True)
        self._preview.panels_requested.connect(
            lambda combien: self._session.set_layout(panels=combien))
        self._preview.panel_rows_requested.connect(
            lambda combien: self._session.set_layout(panel_rows=combien))
        # Le glissement sert à se promener dans l'image, sauf en mode
        # « Ajuster », où il rend la souris à la grille.
        self._preview.set_draggable(False)
        self._preview.panel_moved.connect(self._session.move_panel)
        self._zoom = ZOOM_MIN
        # Vrai le temps d'une recopie du zoom dans son champ : le champ émet à
        # chaque écriture, et sans ce garde il rezoomerait sur lui-même.
        self._updating_zoom = False
        self._scroll = PreviewView()
        self._scroll.setWidget(self._preview)
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QScrollArea.NoFrame)
        self._scroll.zoom_requested.connect(self._zoom_at)
        self._scroll.colour_picked.connect(self._on_colour_picked)
        self._scroll.viewport().installEventFilter(self)
        self._tabs[1].eyedropper_requested.connect(self._start_picking)
        # Le rôle qu'une pipette armée remplira.
        self._picking_role = ""

        # La loupe se pose **sur** l'image : une barre en dessous lui aurait
        # repris la hauteur qu'on vient de lui donner.
        self._zoom_out = QPushButton("−")
        self._zoom_in = QPushButton("+")
        # ⚠️ **« Ajuster » est un mode, pas une action.** Enfoncé, il rend le
        # glissement à la grille : on la déplace dans sa feuille, comme à
        # l'onglet « Emplacement de la grille ». Le zoom, lui, se remet à 100 %
        # dans son champ.
        self._adjust = QPushButton()
        self._adjust.setCheckable(True)
        self._adjust.toggled.connect(self._set_adjusting)
        # ⚠️ **Un champ, et non une étiquette.** Atteindre 400 % au bouton
        # demandait sept clics : on écrit le nombre.
        self._zoom_field = QSpinBox()
        self._zoom_field.setRange(int(ZOOM_MIN * 100), int(ZOOM_MAX * 100))
        self._zoom_field.setSingleStep(25)
        self._zoom_field.setSuffix(" %")
        self._zoom_field.setFixedWidth(ZOOM_FIELD_WIDTH)
        self._zoom_field.setAlignment(Qt.AlignCenter)
        self._zoom_field.valueChanged.connect(self._on_zoom_typed)
        for bouton in (self._zoom_out, self._zoom_in):
            bouton.setFixedWidth(32)
        self._zoom_out.clicked.connect(lambda: self._zoom_at(1 / ZOOM_STEP, None))
        self._zoom_in.clicked.connect(lambda: self._zoom_at(ZOOM_STEP, None))
        self._loupe = QWidget(self._scroll)
        theme.mark(self._loupe, "floating-bar")
        loupe = QHBoxLayout(self._loupe)
        loupe.setContentsMargins(6, 4, 6, 4)
        loupe.setSpacing(4)
        for widget in (self._zoom_out, self._zoom_field, self._zoom_in,
                       self._adjust):
            loupe.addWidget(widget)

        self._saved = SavedColumn(self._session, removable=False)
        self._saved.slot_picked.connect(self.show_slot)
        self._saved.library_requested.connect(self._open_library)

        self._export = QPushButton()
        self._export.clicked.connect(self._open_export)
        # Un export de poster prend des minutes : sans annulation ni barre, il
        # n'y a que la croix de la fenêtre pour en sortir, et rien ne dit où il
        # en est.
        self._cancel_export = QPushButton()
        self._cancel_export.clicked.connect(self._request_export_stop)
        self._cancel_export.hide()
        self._export_progress = QProgressBar()
        self._export_progress.hide()
        self._summary = QLabel()
        self._summary.setWordWrap(True)
        # ⚠️ **Ce qui déborde ne s'imprimera pas.** La grille est arrêtée, mais
        # l'écart, la taille des cartes et le nombre de feuilles se règlent
        # encore ici : on peut donc, d'un clic, pousser des cartes hors des
        # pages sans que rien ne le dise.
        self._warning = QLabel()
        self._warning.setWordWrap(True)
        theme.mark(self._warning, "error")
        gras = self._warning.font()
        gras.setBold(True)
        self._warning.setFont(gras)
        self._warning.hide()

        # L'aura du bouton d'export, verte quand il est prêt, rouge quand
        # quelque chose manque : la même que « Suivant » avait sur les autres
        # étapes, et il n'y a plus de « Suivant » ici.
        self._export_glow = QGraphicsDropShadowEffect(self._export)
        self._export_glow.setOffset(0, 0)
        self._export.setGraphicsEffect(self._export_glow)

        droite = QVBoxLayout()
        # L'aura du bouton déborde : sans cette place, elle serait rognée par
        # le bord du panneau.
        droite.setContentsMargins(0, 0, theme.GLOW_ROOM, theme.GLOW_ROOM)
        droite.addWidget(self._saved, 1)
        droite.addWidget(self._warning)
        droite.addWidget(self._summary)
        droite.addWidget(self._export)
        droite.addWidget(self._cancel_export)
        droite.addWidget(self._export_progress)
        panneau_droit = QWidget()
        panneau_droit.setLayout(droite)

        milieu = QHBoxLayout()
        milieu.addWidget(gauche)
        milieu.addWidget(self._scroll, 1)
        milieu.addWidget(panneau_droit)

        layout = QVBoxLayout(self)
        layout.addWidget(self._heading)
        layout.addLayout(milieu, 1)
        self.retranslate_ui()

    def _start_picking(self, role: str) -> None:
        self._picking_role = role
        self._scroll.start_picking()
        self.status_message.emit(
            self.tr("Cliquez dans l'image pour prélever une couleur."))

    def _on_colour_picked(self, couleur) -> None:
        if not self._picking_role:
            return
        self._session.set_algorithm(**{
            self._picking_role: (couleur.red(), couleur.green(), couleur.blue())})
        self._picking_role = ""

    def _toggle_section(self, key: str) -> None:
        """Ouvre la section demandée et referme les autres."""
        for section in self._sections:
            section.set_open(section.key() == key and not section.is_open())

    # --- Le zoom et le déplacement ----------------------------------------

    def _zoom_at(self, facteur: float, point) -> None:
        """Zoome autour d'un point de la vue, ou de son centre.

        ⚠️ Sans viser un point, chaque cran renvoyait au coin haut-gauche, et il
        fallait retrouver à la main l'endroit qu'on regardait.
        """
        voulu = max(ZOOM_MIN, min(ZOOM_MAX, self._zoom * facteur))
        if voulu == self._zoom:
            return
        cadre = self._scroll.viewport().size()
        vise = point if point is not None else QPointF(cadre.width() / 2,
                                                       cadre.height() / 2)
        barres = (self._scroll.horizontalScrollBar(),
                  self._scroll.verticalScrollBar())
        avant = (barres[0].value() + vise.x(), barres[1].value() + vise.y())
        rapport = voulu / self._zoom
        self._zoom = voulu
        self._apply_zoom()
        barres[0].setValue(int(avant[0] * rapport - vise.x()))
        barres[1].setValue(int(avant[1] * rapport - vise.y()))

    def _apply_zoom(self) -> None:
        """Le zoom agrandit le dessin ; la zone défilante fait le reste."""
        cadre = self._scroll.viewport().size()
        if self._zoom <= ZOOM_MIN:
            # Ajusté, l'aperçu suit le cadre : une taille minimale figée
            # laisserait des barres de défilement sur une image qui tient.
            self._preview.setMinimumSize(0, 0)
        else:
            self._preview.setMinimumSize(int(cadre.width() * self._zoom),
                                         int(cadre.height() * self._zoom))
        self._show_zoom()
        self._preview.refresh()

    def _set_adjusting(self, actif: bool) -> None:
        """Passe la souris à la grille, ou la rend au déplacement de la vue.

        Les deux gestes sont le même : cliquer et tirer. Il faut donc dire
        lequel on veut, et le bouton reste enfoncé tant que c'est celui-là.
        """
        theme.mark(self._adjust, "active" if actif else "")
        self._preview.set_draggable(actif)
        self._scroll.set_panning(not actif)
        self.status_message.emit(
            self.tr("Tirez la mosaïque pour la placer sur sa feuille.")
            if actif else "")

    def _show_zoom(self) -> None:
        """Recopie le zoom dans le champ, sans le lui faire réémettre."""
        self._updating_zoom = True
        self._zoom_field.setValue(round(self._zoom * 100))
        self._updating_zoom = False

    def _on_zoom_typed(self, pourcentage: int) -> None:
        if self._updating_zoom:
            return
        self._zoom_at((pourcentage / 100) / self._zoom, None)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._place_zoom_bar()

    def eventFilter(self, objet, event) -> bool:
        """⚠️ **La loupe suit le cadre, pas l'écran.** Placée sur le seul
        `resizeEvent` de l'étape, elle se posait d'après une géométrie que la
        disposition n'avait pas encore arrêtée, et restait en plein milieu de
        l'image."""
        if objet is self._scroll.viewport() and event.type() == QEvent.Resize:
            self._place_zoom_bar()
        return super().eventFilter(objet, event)

    def _place_zoom_bar(self) -> None:
        """La loupe se pose en bas à droite de l'aperçu, par-dessus lui."""
        taille = self._loupe.sizeHint()
        cadre = self._scroll.viewport().geometry()
        self._loupe.resize(taille)
        self._loupe.move(cadre.right() - taille.width() - ZOOM_BAR_MARGIN,
                         cadre.bottom() - taille.height() - ZOOM_BAR_MARGIN)
        self._loupe.raise_()

    def retranslate_ui(self) -> None:
        self._heading.setText(self.tr("Derniers ajustements avant l'export"))
        for onglet, section in zip(self._tabs, self._sections, strict=True):
            onglet.retranslate_ui()
            section.retranslate_ui()
        self._adjust.setText(self.tr("Ajuster"))
        self._adjust.setToolTip(
            self.tr("Déplacer la mosaïque dans sa feuille, à la souris."))
        self._zoom_field.setToolTip(
            self.tr("Molette ou pincement pour zoomer, glissement pour se "
                    "déplacer."))
        self._show_zoom()
        self._export.setText(self.tr("Exporter cet agencement…"))
        self._cancel_export.setText(self.tr("Annuler l'export"))
        self._saved.retranslate_ui()
        self._refresh_preview()

    # --- L'agencement affiché ---------------------------------------------

    def show_slot(self, slot: int) -> None:
        """Montre l'agencement d'une case, et la marque comme courante."""
        saved = self._session.saved[slot]
        if saved is None:
            return
        self._slot = slot
        self._saved.set_current(slot)
        self._preview.set_arrangement(saved.grid, saved.cards)
        self._update_summary()

    def enter(self) -> None:
        """Appelé en arrivant sur l'étape : ouvre la première case gardée.

        ⚠️ **Toujours une case ouverte.** Un écran d'export sans agencement
        n'aurait rien à habiller, et la colonne n'est pas un menu qu'on doit
        penser à ouvrir.
        """
        if self._slot is None or self._session.saved[self._slot] is None:
            premier = self._session.first_saved()
            if premier is not None:
                self.show_slot(premier)
        self._refresh_preview()

    def current_saved(self):
        if self._slot is None:
            return None
        return self._session.saved[self._slot]

    # --- Réactions --------------------------------------------------------

    def _on_saved_changed(self) -> None:
        if self._slot is not None and self._session.saved[self._slot] is None:
            self._slot = None
        self.enter()

    def _on_layout_changed(self) -> None:
        for onglet in self._tabs:
            onglet.refresh()
        self._refresh_preview()

    def _refresh_preview(self) -> None:
        self._preview.refresh()
        self._update_summary()

    def _fits_the_pages(self) -> bool:
        """La mosaïque tient-elle sur les feuilles, à la taille courante ?"""
        session = self._session
        return grid_fits(session.panels, session.cols, session.rows,
                         session.panel_geometry(), session.panel_rows)

    def _update_summary(self) -> None:
        saved = self.current_saved()
        tient = self._fits_the_pages()
        self._warning.setVisible(not tient)
        self._warning.setText(
            "" if tient else
            self.tr("Des cartes sortent des pages : ajoutez une feuille, "
                    "réduisez la taille des cartes ou l'écart."))
        if saved is None:
            self._summary.setText(self.tr("Aucun agencement gardé."))
            self._export.setEnabled(False)
            self._update_glow(False)
            return
        self._export.setEnabled(self._export_thread is None and tient)
        self._update_glow(self._export.isEnabled())
        self._summary.setText(
            self.tr("Agencement %1 sur %2, score %3")
             .replace("%1", str((self._slot or 0) + 1))
             .replace("%2", str(self._session.saved_count()))
             .replace("%3", f"{saved.score:.1f}")
        )

    def _open_library(self) -> None:
        """Le même menu qu'à l'exécution : on y prend l'agencement à habiller."""
        if not self._arrangements_directory:
            return
        dialogue = ArrangementsDialog(self._session,
                                      self._arrangements_directory, parent=self)
        try:
            dialogue.exec()
        finally:
            dialogue.deleteLater()

    # --- Écriture ---------------------------------------------------------

    def _update_glow(self, pret: bool) -> None:
        """Verte quand on peut écrire, rouge quand il manque quelque chose."""
        theme.set_glow(self._export_glow, self.palette(), pret)

    def changeEvent(self, event) -> None:
        """⚠️ Une couleur figée dans un effet ne suit pas le mode : elle garde
        la teinte qu'on lui a posée, verte foncée sur une fenêtre devenue
        claire."""
        super().changeEvent(event)
        if event.type() == QEvent.PaletteChange:
            self._update_summary()

    def _open_export(self) -> None:
        saved = self.current_saved()
        if saved is None or self._export_thread is not None:
            return
        dialog = ExportDialog(self._session, saved.grid, saved.cards, parent=self)
        try:
            if not dialog.exec():
                return
            settings, path = dialog.settings(), dialog.path()
            full_resolution = dialog.full_resolution()
        finally:
            dialog.deleteLater()
        self._start_export(saved, settings, path, full_resolution)

    def _start_export(self, saved, settings, path, full_resolution) -> None:
        self._export.setEnabled(False)
        self._cancel_export.show()
        self._cancel_export.setEnabled(True)
        # Un seul panneau n'a aucune étape intermédiaire à annoncer : une barre
        # figée à 0 % pendant plusieurs secondes se lit comme un export bloqué.
        # Indéterminée, elle dit la seule chose vraie, que ça travaille.
        feuilles = settings.panel_count
        self._export_progress.setRange(0, feuilles if feuilles > 1 else 0)
        self._export_progress.setValue(0)
        self._export_progress.show()
        self.status_message.emit(self.tr("Export en cours…"))
        self._export_thread, self._export_worker = start_export(
            self, saved.grid, saved.cards, settings, path, full_resolution,
            progress=self._on_export_progress,
            exported=self._on_exported,
            cancelled=self._on_export_cancelled,
            failed=self._on_export_failed,
        )

    def _request_export_stop(self) -> None:
        if self._export_worker is not None:
            self._export_worker.cancel()
            self._cancel_export.setEnabled(False)

    def _on_export_progress(self, panel: int, total: int, fichier: str) -> None:
        self._export_progress.setValue(panel)
        if fichier:
            self.status_message.emit(
                self.tr("Panneau %1 / %2 : %3")
                .replace("%1", str(panel + 1)).replace("%2", str(total))
                .replace("%3", os.path.basename(fichier))
            )

    def _end_export(self) -> None:
        self._export_thread = self._export_worker = None
        self._cancel_export.hide()
        self._cancel_export.setEnabled(True)
        self._export_progress.hide()
        self._update_summary()

    def _on_exported(self, written: list) -> None:
        self._end_export()
        self.status_message.emit(
            self.tr("%n fichier(s) écrit(s) : %1", "", len(written))
            .replace("%1", ", ".join(os.path.basename(p) for p in written))
        )

    def _on_export_cancelled(self) -> None:
        self._end_export()
        self.status_message.emit(
            self.tr("Export annulé ; les fichiers partiels ont été effacés.")
        )

    def _on_export_failed(self, message: str) -> None:
        self._end_export()
        self.status_message.emit(
            self.tr("Échec de l'export : %1").replace("%1", message)
        )

    def shutdown(self) -> bool:
        """Arrête l'export en cours. Rend faux s'il résiste.

        ⚠️ **Le résultat compte.** Le `QThread` a pour parent ce widget : la
        fenêtre détruite l'emporte avec elle, référence Python ou non, et Qt
        abandonne alors le processus. Une référence n'est donc lâchée que si son
        fil est réellement terminé.
        """
        if self._export_worker is not None:
            self._export_worker.cancel()
        if self._export_thread is not None and self._export_thread.isRunning():
            self._export_thread.quit()
            if not self._export_thread.wait(SHUTDOWN_TIMEOUT_MS):
                # `status_message` et non `print` : depuis un paquet `.app`, la
                # sortie standard ne va nulle part que l'utilisateur puisse lire.
                self.status_message.emit(
                    self.tr("Arrêt en cours : l'export ne répond pas encore.")
                )
                return False
        self._export_thread = self._export_worker = None
        return True
