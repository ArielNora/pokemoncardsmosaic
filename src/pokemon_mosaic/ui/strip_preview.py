"""Aperçu de l'épaisseur des bandes de bord.

C'est le réglage qui change le plus le rendu final, et le seul des réglages
« avancés » dont l'effet soit montrable. L'aperçu est double, parce qu'aucune des
deux moitiés ne suffit :

- les bandes surlignées sur une carte disent **quelle zone** est mesurée ;
- une petite grille d'essai réoptimisée en direct dit **ce que ça change** au
  résultat, ce qu'un surlignage ne peut pas montrer.

Faisabilité mesurée : recalculer les signatures des 280 vignettes coûte 25 à
211 ms selon l'épaisseur, et réoptimiser 20 cartes sur 1000 itérations, 37 ms.
Voir SPEC.md §5.
"""

import random

import numpy as np
from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QImage, QPainter, QPen
from PySide6.QtWidgets import QWidget

from ..optimize import build_initial_grid, optimize_grid, select_cards
from ..scoring import EdgeDistances

BAND = QColor(255, 190, 60, 110)
BAND_EDGE = QColor(210, 130, 0)

# Taille de la grille d'essai. Assez grande pour montrer un raccord, assez petite
# pour se réoptimiser sans latence perceptible.
SANDBOX_COLS = 5
SANDBOX_ROWS = 4
SANDBOX_ITERATIONS = 1000

# Délai avant reconstruction. Le curseur d'épaisseur doit pouvoir défiler sans
# payer les 34 à 294 ms d'une réoptimisation à chaque cran.
REBUILD_DELAY_MS = 250


def _to_qimage(array: np.ndarray) -> QImage:
    array = np.ascontiguousarray(array)
    height, width, _ = array.shape
    return QImage(array.data, width, height, 3 * width, QImage.Format_RGB888).copy()


class StripPreview(QWidget):
    """Une carte avec ses bandes surlignées, et une grille d'essai réoptimisée."""

    def __init__(self, session, parent=None):
        super().__init__(parent)
        self._session = session
        self._sandbox: QImage | None = None
        self._sandbox_error = ""
        self._built_key = None
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(REBUILD_DELAY_MS)
        self._timer.timeout.connect(self.refresh)
        self.setMinimumHeight(190)
        for signal in (session.algorithm_changed, session.cards_loaded,
                       session.cards_added, session.selection_changed):
            signal.connect(self.invalidate)

    def _key(self):
        """Ce dont dépend réellement l'aperçu : l'épaisseur et les cartes retenues.

        Comparer cette clé évite de reconstruire pour un réglage sans rapport,
        `algorithm_changed` part aussi pour le nombre d'itérations ou les seuils
        d'arrêt, qui ne changent rien à ce qui est montré.
        """
        return (self._session.strip_size, tuple(self._session.selected_indices()))

    def invalidate(self, *_) -> None:
        """Programme une reconstruction, si tant est qu'elle change quelque chose.

        Le calcul est différé : reconstruire depuis `paintEvent` figerait
        l'interface à chaque cran du curseur, l'anti-rebond ne servant alors à
        rien puisque le repeint arrive avant lui. L'ancienne image reste affichée
        entre-temps, et les bandes surlignées, elles, suivent immédiatement.
        """
        if self._key() == self._built_key:
            return
        self._timer.start()
        self.update()

    def refresh(self) -> None:
        """Reconstruit tout de suite, sans attendre le délai."""
        self._timer.stop()
        key = self._key()
        self._rebuild_sandbox()
        self._built_key = key
        self.update()

    @property
    def _dirty(self) -> bool:
        return self._key() != self._built_key

    # --- Grille d'essai ---------------------------------------------------

    def _rebuild_sandbox(self) -> None:
        """Réoptimise quelques cartes à l'épaisseur courante.

        Sur un échantillon, pas sur tout le jeu : l'intérêt est de montrer l'effet
        du réglage, pas de faire le calcul final.
        """
        self._sandbox = None
        self._sandbox_error = ""
        cards = self._session.card_set
        needed = SANDBOX_COLS * SANDBOX_ROWS
        # On échantillonne parmi les cartes RETENUES : montrer un raccord entre
        # des cartes que l'utilisateur vient d'exclure serait trompeur.
        available = self._session.selected_indices()
        if not cards or len(available) < needed:
            self._sandbox_error = self.tr("pas assez de cartes")
            return

        # Un échantillon régulier plutôt que les premières : les cartes d'un même
        # dossier se ressemblent trop pour que le raccord soit parlant.
        step = max(1, len(available) // needed)
        indices = available[::step][:needed]

        try:
            # `select_cards` plutôt que `subset` seul : c'est le point d'entrée
            # que le code désigne comme le seul sûr, et cet aperçu est le premier
            # usage en production, donc celui qui fera référence.
            subset, _ = select_cards(cards, indices)
            distances = EdgeDistances(subset.cards)
            grid = build_initial_grid(
                subset, shape=(SANDBOX_COLS, SANDBOX_ROWS), rng=random.Random(0)
            )
            optimize_grid(grid, distances, iterations=SANDBOX_ITERATIONS,
                          rng=random.Random(0))
        except Exception as error:  # noqa: BLE001 - voir ci-dessous
            # Volontairement large : ce code tourne dans un slot de `QTimer`, où
            # une exception non rattrapée est simplement imprimée par Qt.
            # L'aperçu resterait alors figé sur l'ancienne image, sans que rien
            # n'explique pourquoi. Ici, le message s'affiche.
            self._sandbox_error = str(error)
            return

        tile_h, tile_w = subset[0].thumbnail.shape[:2]
        canvas = np.zeros((SANDBOX_ROWS * tile_h, SANDBOX_COLS * tile_w, 3), np.uint8)
        for row in range(SANDBOX_ROWS):
            for col in range(SANDBOX_COLS):
                index = int(grid[row, col])
                if index < 0:
                    continue
                canvas[row * tile_h:(row + 1) * tile_h,
                       col * tile_w:(col + 1) * tile_w] = subset[index].thumbnail
        self._sandbox = _to_qimage(canvas)

    # --- Dessin -----------------------------------------------------------

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        painter.fillRect(self.rect(), self.palette().window())

        cards = self._session.card_set
        if not cards:
            painter.drawText(self.rect(), Qt.AlignCenter, self.tr("Aucune carte chargée"))
            painter.end()
            return

        selected = self._session.selected_indices()
        if not selected:
            painter.drawText(self.rect(), Qt.AlignCenter, self.tr("Aucune carte retenue"))
            painter.end()
            return

        margin = 6
        height = self.height() - 2 * margin
        card_width = self._draw_card(painter, cards[selected[0]], margin, margin, height)
        self._draw_sandbox(painter, margin * 2 + card_width, margin, height)
        painter.end()

    def _draw_card(self, painter, card, x, y, height) -> float:
        """Dessine une carte et surligne les quatre bandes mesurées."""
        image = _to_qimage(card.thumbnail)
        width = height * image.width() / image.height()
        target = QRectF(x, y, width, height)
        painter.drawImage(target, image)

        strip = self._session.strip_size
        band_h = height * strip
        band_w = width * strip
        painter.setPen(QPen(BAND_EDGE, 1))
        painter.setBrush(BAND)
        for rect in (
            QRectF(x, y, width, band_h),                     # haut
            QRectF(x, y + height - band_h, width, band_h),   # bas
            QRectF(x, y, band_w, height),                    # gauche
            QRectF(x + width - band_w, y, band_w, height),   # droite
        ):
            painter.drawRect(rect)
        return width

    def _draw_sandbox(self, painter, x, y, height) -> None:
        if self._sandbox is None:
            painter.drawText(QRectF(x, y, self.width() - x, height),
                             Qt.AlignCenter, self._sandbox_error)
            return
        width = height * self._sandbox.width() / self._sandbox.height()
        available = self.width() - x - 6
        if width > available:
            width, height = available, available * self._sandbox.height() / self._sandbox.width()
        painter.drawImage(QRectF(x, y, width, height), self._sandbox)
