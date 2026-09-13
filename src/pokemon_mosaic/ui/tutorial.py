"""Les tutoriels : une visite guidée à la première visite, une aide au survol.

Décidé par l'utilisateur le 2026-09-13, voir `SPEC.md` §10. Chaque page, onglet
ou fenêtre décrit ses **zones** : un élément de l'interface et son explication.

- **La visite guidée** assombrit et bloque l'interface, entoure une zone à la
  fois dans l'ordre, et l'explique dans une bulle ; un clic, Entrée ou la flèche
  droite passe à la suivante. « Passer le tutoriel » demande confirmation, avec
  une case pour passer toutes les visites suivantes.
- **Le mode d'aide**, allumé par le bouton « ? », entoure toutes les zones sans
  rien bloquer, et montre l'explication de celle qu'on survole.

⚠️ **Les zones sont des éléments, jamais des coordonnées.** La fenêtre change de
taille, des sections se replient, des listes défilent : le contour se relit sur
l'élément à chaque rafraîchissement, et un élément caché n'a pas de zone.
"""

from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtCore import QEvent, QObject, QPoint, QPointF, QRect, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QCursor, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QGraphicsDropShadowEffect,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from . import theme

# Le voile de la visite guidée : assez sombre pour isoler la zone, assez clair
# pour qu'on devine encore l'écran autour.
DIM_ALPHA = 150
OUTLINE_WIDTH = 2.5
# L'air laissé entre l'élément et son contour.
ZONE_MARGIN = 4
BUBBLE_WIDTH = 300
# L'écart entre la zone et sa bulle, où se loge la flèche.
BUBBLE_GAP = 12
ARROW = 7
# La relecture des zones, et de la souris en mode d'aide : les éléments bougent
# sans prévenir le voile, et la souris n'envoie rien qu'on puisse écouter.
REFRESH_MS = 120
SKIP_MARGIN = 16

SETTINGS_SEEN = "tutoriels/vus"
SETTINGS_SKIP_ALL = "tutoriels/passer_tous"

GUIDE, HELP = "guide", "aide"


@dataclass
class Zone:
    """Un élément de l'interface et son explication.

    Deux fonctions, et non des valeurs : l'élément peut être recréé, et le texte
    doit suivre la langue choisie au moment où il s'affiche.
    """

    widget: Callable[[], QWidget | None]
    text: Callable[[], str]


@dataclass
class Tutorial:
    """Le tutoriel d'une page : sa clé, retenue une fois vue, et ses zones dans
    l'ordre où il faut les comprendre."""

    key: str
    zones: Callable[[], list[Zone]]


def zone_rect(widget: QWidget | None, host: QWidget) -> QRect:
    """Le rectangle **visible** d'un élément, dans les coordonnées de `host`.

    Vide si l'élément manque, est caché, appartient à une autre fenêtre ou
    défile hors de son cadre : une zone qu'on ne voit pas n'a rien à montrer.
    """
    if widget is None or not widget.isVisible() or widget.window() is not host.window():
        return QRect()
    visible = widget.visibleRegion().boundingRect()
    if visible.isEmpty():
        return QRect()
    haut_gauche = widget.mapTo(host, visible.topLeft())
    rect = QRect(haut_gauche, visible.size()).adjusted(
        -ZONE_MARGIN, -ZONE_MARGIN, ZONE_MARGIN, ZONE_MARGIN)
    return rect.intersected(host.rect())


class TutorialStore:
    """Ce qui a déjà été vu, retenu dans les réglages de la machine.

    Les clés vues tiennent dans une chaîne séparée par des virgules : une liste
    d'un seul élément revient en chaîne selon le format des réglages.
    """

    def __init__(self, settings: Callable[[], object]):
        self._settings = settings

    def _seen(self) -> set[str]:
        valeur = self._settings().value(SETTINGS_SEEN, "", type=str)
        return {cle for cle in valeur.split(",") if cle}

    def seen(self, key: str) -> bool:
        return key in self._seen()

    def mark_seen(self, key: str) -> None:
        self._settings().setValue(SETTINGS_SEEN,
                                  ",".join(sorted(self._seen() | {key})))

    def skip_all(self) -> bool:
        return self._settings().value(SETTINGS_SKIP_ALL, False, type=bool)

    def set_skip_all(self, skip: bool) -> None:
        self._settings().setValue(SETTINGS_SKIP_ALL, bool(skip))

    def should_guide(self, key: str) -> bool:
        return not self.skip_all() and not self.seen(key)

    def rearm(self) -> None:
        """Toutes les visites guidées reviendront à leur prochaine ouverture."""
        self._settings().setValue(SETTINGS_SEEN, "")
        self._settings().setValue(SETTINGS_SKIP_ALL, False)


class TutorialBubble(QFrame):
    """La bulle d'explication, et en visite guidée, où l'on en est."""

    def __init__(self, parent=None):
        super().__init__(parent)
        theme.mark(self, "tutorial-bubble")
        self.setFixedWidth(BUBBLE_WIDTH)
        self._text = QLabel()
        self._text.setWordWrap(True)
        self._progress = QLabel()
        theme.mark(self._progress, "status")
        pile = QVBoxLayout(self)
        pile.setContentsMargins(12, 10, 12, 10)
        pile.setSpacing(6)
        pile.addWidget(self._text)
        pile.addWidget(self._progress)
        self.hide()

    def show_text(self, text: str, progress: str = "") -> None:
        self._text.setText(text)
        self._progress.setText(progress)
        self._progress.setVisible(bool(progress))
        self.adjustSize()

    def text(self) -> str:
        return self._text.text()

    def progress(self) -> str:
        return self._progress.text()


class TutorialOverlay(QWidget):
    """Le voile posé sur une fenêtre : contours, bulle, et la visite en cours."""

    # (clé, passée, passer toutes les suivantes) : une visite guidée finie.
    guide_ended = Signal(str, bool, bool)

    def __init__(self, host: QWidget):
        super().__init__(host)
        self._host = host
        self._mode: str | None = None
        self._tutorial: Tutorial | None = None
        self._index = 0
        self._zones: list[tuple[Zone, QRect]] = []
        self._hovered: int | None = None
        # Où la flèche de la bulle part, et vers quel point elle pointe.
        self._arrow: QPolygonF | None = None
        self._bubble = TutorialBubble(self)
        self._skip = QPushButton(self)
        self._skip.clicked.connect(self.request_skip)
        self._skip.hide()
        self._timer = QTimer(self)
        self._timer.setInterval(REFRESH_MS)
        self._timer.timeout.connect(self._on_tick)
        self.setFocusPolicy(Qt.StrongFocus)
        # ⚠️ **Aucun filtre d'événements**, ni sur l'application ni sur la
        # fenêtre. Un voile dont Python a perdu l'objet continuait d'y recevoir
        # des événements, et Qt appelait un objet vide : l'erreur tombait dans
        # un tout autre écran. Le voile se recale sur sa fenêtre à chaque
        # rafraîchissement, voir `refresh`.
        self.hide()
        self.retranslate_ui()

    def retranslate_ui(self) -> None:
        self._skip.setText(self.tr("Passer le tutoriel"))
        self._skip.adjustSize()
        self.refresh()

    # --- Les deux modes ---------------------------------------------------

    def mode(self) -> str | None:
        return self._mode

    def tutorial(self) -> Tutorial | None:
        return self._tutorial

    def current_index(self) -> int:
        return self._index

    def zones(self) -> list[tuple[Zone, QRect]]:
        return list(self._zones)

    def start_guide(self, tutorial: Tutorial) -> bool:
        """Lance la visite guidée. Rend faux s'il n'y a aucune zone à montrer."""
        self._mode, self._tutorial, self._index = GUIDE, tutorial, 0
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self._show_over_host()
        if not self._zones:
            self.stop()
            return False
        self._skip.show()
        self.setFocus()
        self.refresh()
        return True

    def start_help(self, tutorial: Tutorial | None) -> None:
        """Allume l'aide : les contours de toutes les zones, rien de bloqué."""
        self._mode, self._tutorial, self._hovered = HELP, tutorial, None
        # ⚠️ **Transparent aux clics** : l'aide explique sans empêcher d'agir.
        # Le survol se lit alors sur la position de la souris, voir `_on_tick`.
        # ⚠️ **Jamais de filtre sur l'application entière** : un voile détruit
        # l'aide allumée y restait inscrit, et l'application appelait ensuite un
        # objet à moitié détruit.
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self._skip.hide()
        self._show_over_host()

    def stop(self) -> None:
        self._mode, self._tutorial, self._hovered = None, None, None
        self._zones = []
        self._timer.stop()
        self._bubble.hide()
        self._skip.hide()
        self.hide()

    def _show_over_host(self) -> None:
        self.setGeometry(self._host.rect())
        self.show()
        self.raise_()
        self._timer.start()
        self.refresh()

    # --- La visite guidée -------------------------------------------------

    def next_zone(self) -> None:
        if self._mode != GUIDE:
            return
        self._index += 1
        if self._index >= len(self._zones):
            cle = self._tutorial.key
            self.stop()
            self.guide_ended.emit(cle, False, False)
            return
        self.refresh()

    def request_skip(self) -> None:
        if self._mode != GUIDE:
            return
        passer, toutes = self._confirm_skip()
        if not passer:
            self.setFocus()
            return
        cle = self._tutorial.key
        self.stop()
        self.guide_ended.emit(cle, True, toutes)

    def _confirm_skip(self) -> tuple[bool, bool]:
        """Demande s'il faut passer, et s'il faut passer toutes les suivantes.

        À part pour que les tests le remplacent : une boîte modale n'a pas de
        fin dans une suite qui ne clique sur rien.
        """
        boite = QMessageBox(self._host)
        boite.setWindowTitle(self.tr("Passer le tutoriel"))
        boite.setText(self.tr("Passer le tutoriel de cette page ?"))
        case = QCheckBox(self.tr("Passer aussi tous les tutoriels suivants"))
        boite.setCheckBox(case)
        boite.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        boite.setDefaultButton(QMessageBox.No)
        passer = boite.exec() == QMessageBox.Yes
        return passer, passer and case.isChecked()

    def mousePressEvent(self, event) -> None:
        # ⚠️ **Tout clic avance, et rien d'autre ne réagit** : on ne lance pas
        # un calcul par erreur en voulant passer à la zone suivante.
        if self._mode == GUIDE and event.button() == Qt.LeftButton:
            self.next_zone()
        event.accept()

    def keyPressEvent(self, event) -> None:
        if self._mode != GUIDE:
            super().keyPressEvent(event)
            return
        if event.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Right, Qt.Key_Space):
            self.next_zone()
        elif event.key() == Qt.Key_Escape:
            self.request_skip()
        event.accept()

    # --- Le mode d'aide ---------------------------------------------------

    def _on_tick(self) -> None:
        """Relit la souris en mode d'aide, puis les zones.

        ⚠️ **La position est lue, pas attendue.** Sans bouton enfoncé, Qt
        n'envoie de mouvement qu'aux éléments qui suivent la souris, et aucun
        bouton ni aucune liste ne le fait : écouter les mouvements laissait le
        survol muet dans l'application, alors que les tests passaient.
        """
        if self._mode == HELP:
            point = self.mapFromGlobal(QCursor.pos())
            self.hover_at(point if self.rect().contains(point) else QPoint(-1, -1))
        self.refresh()

    def focusNextPrevChild(self, next_child: bool) -> bool:
        """⚠️ **Tab ne sort pas du voile pendant la visite.** Le focus serait
        passé à un bouton dessous, qu'Espace aurait activé : le blocage n'aurait
        bloqué que la souris."""
        if self._mode == GUIDE:
            return True
        return super().focusNextPrevChild(next_child)

    def hover_at(self, point: QPoint) -> None:
        """Montre la bulle de la zone sous ce point, en coordonnées du voile."""
        survolee = next((rang for rang, (_zone, rect) in enumerate(self._zones)
                         if rect.contains(point)), None)
        if survolee != self._hovered:
            self._hovered = survolee
            self.refresh()

    def hovered_index(self) -> int | None:
        return self._hovered

    # --- Le dessin --------------------------------------------------------

    def refresh(self) -> None:
        """Relit les zones sur leurs éléments, et replace la bulle."""
        if self._mode is None or self._tutorial is None:
            self._zones = []
            self._bubble.hide()
            self.update()
            return
        # La fenêtre a pu changer de taille depuis le dernier passage.
        if self.geometry() != self._host.rect():
            self.setGeometry(self._host.rect())
        # ⚠️ **Toujours au premier plan.** Un élément montré ou relevé après le
        # début de la visite passait au-dessus du voile, et restait cliquable.
        self.raise_()
        self._zones = [(zone, rect) for zone in self._tutorial.zones()
                       if not (rect := zone_rect(zone.widget(), self._host)).isEmpty()]
        if self._mode == GUIDE:
            if not self._zones:
                self._bubble.hide()
            else:
                self._index = min(self._index, len(self._zones) - 1)
                zone, rect = self._zones[self._index]
                self._bubble.show_text(
                    zone.text(),
                    self.tr("Cliquez pour continuer (%1 sur %2)")
                    .replace("%1", str(self._index + 1))
                    .replace("%2", str(len(self._zones))))
                self._place_bubble(rect)
            self._skip.adjustSize()
            self._skip.move(self.width() - self._skip.width() - SKIP_MARGIN,
                            self.height() - self._skip.height() - SKIP_MARGIN)
            self._skip.raise_()
        else:
            if self._hovered is not None and self._hovered < len(self._zones):
                zone, rect = self._zones[self._hovered]
                self._bubble.show_text(zone.text())
                self._place_bubble(rect)
            else:
                self._hovered = None
                self._bubble.hide()
                self._arrow = None
        self.update()

    def _place_bubble(self, rect: QRect) -> None:
        """Pose la bulle du côté de la zone où elle tient : dessous, dessus, à
        droite, puis à gauche, et toujours dans le voile."""
        taille = self._bubble.sizeHint()
        largeur, hauteur = BUBBLE_WIDTH, taille.height()
        cadre = self.rect()
        centre = rect.center()
        cotes = [
            ("bas", QPoint(centre.x() - largeur // 2, rect.bottom() + BUBBLE_GAP),
             cadre.bottom() - rect.bottom() >= hauteur + BUBBLE_GAP),
            ("haut", QPoint(centre.x() - largeur // 2, rect.top() - BUBBLE_GAP - hauteur),
             rect.top() >= hauteur + BUBBLE_GAP),
            ("droite", QPoint(rect.right() + BUBBLE_GAP, centre.y() - hauteur // 2),
             cadre.right() - rect.right() >= largeur + BUBBLE_GAP),
            ("gauche", QPoint(rect.left() - BUBBLE_GAP - largeur, centre.y() - hauteur // 2),
             rect.left() >= largeur + BUBBLE_GAP),
        ]
        # ⚠️ **Une zone qui prend presque tout l'écran** ne laisse la place
        # d'aucun côté : la bulle se pose alors en bas **dans** la zone, sans
        # flèche. Posée dessous par défaut, elle chevauchait le bord de la zone,
        # avec une flèche qui pointait vers l'intérieur de la bulle.
        cote, coin, _tient = next(
            (c for c in cotes if c[2]),
            ("dedans", QPoint(centre.x() - largeur // 2,
                              rect.bottom() - BUBBLE_GAP - hauteur), True))
        x = max(cadre.left(), min(coin.x(), cadre.right() - largeur))
        y = max(cadre.top(), min(coin.y(), cadre.bottom() - hauteur))
        self._bubble.setGeometry(x, y, largeur, hauteur)
        self._bubble.show()
        self._bubble.raise_()
        bulle = QRectF(self._bubble.geometry())
        if cote == "dedans":
            self._arrow = None
        elif cote == "bas":
            base = QPointF(max(bulle.left() + 12, min(centre.x(), bulle.right() - 12)), bulle.top())
            pointe = QPointF(base.x(), rect.bottom() + 2)
            self._arrow = QPolygonF([base + QPointF(-ARROW, 1), pointe, base + QPointF(ARROW, 1)])
        elif cote == "haut":
            base = QPointF(max(bulle.left() + 12, min(centre.x(), bulle.right() - 12)), bulle.bottom())
            pointe = QPointF(base.x(), rect.top() - 2)
            self._arrow = QPolygonF([base + QPointF(-ARROW, -1), pointe, base + QPointF(ARROW, -1)])
        elif cote == "droite":
            base = QPointF(bulle.left(), max(bulle.top() + 12, min(centre.y(), bulle.bottom() - 12)))
            pointe = QPointF(rect.right() + 2, base.y())
            self._arrow = QPolygonF([base + QPointF(1, -ARROW), pointe, base + QPointF(1, ARROW)])
        else:
            base = QPointF(bulle.right(), max(bulle.top() + 12, min(centre.y(), bulle.bottom() - 12)))
            pointe = QPointF(rect.left() - 2, base.y())
            self._arrow = QPolygonF([base + QPointF(-1, -ARROW), pointe, base + QPointF(-1, ARROW)])

    def paintEvent(self, event) -> None:
        if self._mode is None:
            return
        peintre = QPainter(self)
        peintre.setRenderHint(QPainter.Antialiasing)
        palette = self.palette()
        trait = QColor(palette.highlight().color())
        if self._mode == GUIDE and self._zones:
            _zone, rect = self._zones[self._index]
            voile = QPainterPath()
            voile.addRect(QRectF(self.rect()))
            trou = QPainterPath()
            trou.addRoundedRect(QRectF(rect), 6, 6)
            peintre.fillPath(voile.subtracted(trou), QColor(0, 0, 0, DIM_ALPHA))
            peintre.setPen(QPen(trait, OUTLINE_WIDTH))
            peintre.drawRoundedRect(QRectF(rect), 6, 6)
        elif self._mode == HELP:
            for rang, (_zone, rect) in enumerate(self._zones):
                epaisseur = OUTLINE_WIDTH * (1.6 if rang == self._hovered else 1.0)
                peintre.setPen(QPen(trait, epaisseur))
                peintre.drawRoundedRect(QRectF(rect), 6, 6)
        if self._bubble.isVisible() and self._arrow is not None:
            peintre.setPen(QPen(trait, 1))
            peintre.setBrush(palette.base())
            peintre.drawPolygon(self._arrow)
        peintre.end()


class HelpButton(QPushButton):
    """Le bouton rond « ? » : allume et éteint l'aide, et se voit de loin.

    Un clic droit propose de revoir les visites guidées.
    """

    rearm_requested = Signal()

    def __init__(self, parent=None):
        super().__init__("?", parent)
        theme.mark(self, "help")
        self.setCheckable(True)
        # ⚠️ **Une aura bleue**, demandée par l'utilisateur : le bouton est petit
        # et rond, et c'est la porte d'entrée de toute l'aide.
        self._glow = QGraphicsDropShadowEffect(self)
        self._glow.setOffset(0, 0)
        self.setGraphicsEffect(self._glow)
        self._menu = QMenu(self)
        self._rearm = self._menu.addAction("")
        self._rearm.triggered.connect(self.rearm_requested.emit)
        self.retranslate_ui()

    def retranslate_ui(self) -> None:
        self.setToolTip(self.tr("Afficher ou masquer l'aide de cette page. "
                                "Clic droit : revoir les visites guidées."))
        self._rearm.setText(self.tr("Revoir les visites guidées"))
        self.update_glow()

    def update_glow(self) -> None:
        theme.set_help_glow(self._glow, self.palette())

    def contextMenuEvent(self, event) -> None:
        self._menu.exec(event.globalPos())

    def changeEvent(self, event) -> None:
        super().changeEvent(event)
        if event.type() == QEvent.PaletteChange:
            self.update_glow()


class TutorialController(QObject):
    """Décide, pour une fenêtre, entre la visite guidée et l'aide.

    `current` rend le tutoriel de la page affichée, ou `None`.
    """

    help_changed = Signal(bool)
    guide_running = Signal(bool)

    def __init__(self, host: QWidget, store: TutorialStore,
                 current: Callable[[], Tutorial | None]):
        super().__init__(host)
        self._store = store
        self._current = current
        self._help = False
        self.overlay = TutorialOverlay(host)
        self.overlay.guide_ended.connect(self._on_guide_ended)

    def is_guiding(self) -> bool:
        return self.overlay.mode() == GUIDE

    def help_active(self) -> bool:
        return self._help

    def page_shown(self) -> None:
        """La page affichée a changé : l'aide la suit, ou sa visite démarre.

        ⚠️ **Au tour suivant de la boucle** : la page vient d'être montrée, et
        ses éléments n'ont pas encore leur place ni leur taille.
        """
        QTimer.singleShot(0, self, self._apply_page)

    def _apply_page(self) -> None:
        if self.is_guiding():
            return
        tutoriel = self._current()
        if self._help:
            self.overlay.start_help(tutoriel)
            return
        if (tutoriel is not None and self._store.should_guide(tutoriel.key)
                and self.overlay.start_guide(tutoriel)):
            self.guide_running.emit(True)

    def set_help(self, active: bool) -> None:
        if self.is_guiding():
            return
        self._help = bool(active)
        if self._help:
            self.overlay.start_help(self._current())
        else:
            self.overlay.stop()
        self.help_changed.emit(self._help)

    def _on_guide_ended(self, key: str, _skipped: bool, skip_all: bool) -> None:
        self._store.mark_seen(key)
        if skip_all:
            self._store.set_skip_all(True)
        self.guide_running.emit(False)

    def rearm(self) -> None:
        self._store.rearm()
