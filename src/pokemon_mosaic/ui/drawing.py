"""Les pièces communes du dessin d'une mise en page : couleurs, coupe, numéro.

Elles servaient à l'aperçu fil de fer, remplacé le 2026-09-20 par l'aperçu réel
(`page_preview.py`), qui montre les illustrations. Ce qui se dessine pareil
dans les deux reste ici, en un seul endroit : la couleur d'une carte et celle
d'une case vide, le trait de coupe en deux tons, et la pastille qui numérote
une feuille.
"""

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QPen

CARD_EDGE = QColor(150, 165, 190)
CARD_FILL = QColor(225, 233, 245)
# Pleines et non plus seulement cernées : un contour rouge sur fond blanc se
# perdait au milieu des cartes dès que la grille passait la centaine de cases,
# et il fallait chercher les trous au lieu de les voir.
EMPTY_FILL = QColor(208, 90, 90)
EMPTY_EDGE = QColor(150, 45, 45)
# ⚠️ **La coupe se dessine en deux tons.** Un seul trait la rendait invisible :
# tiré dans la couleur du texte, il passait en blanc sur une mosaïque bleu très
# clair, et en sombre sur le papier sombre. Deux traits superposés : un plein
# clair, un pointillé sombre par-dessus, sont la convention des repères
# d'imprimerie, et l'un des deux ressort quel que soit le fond, dans les deux
# modes de l'application.
CUT_UNDER = QColor(255, 255, 255)
CUT_OVER = QColor(20, 20, 20)
CUT_WIDTHS = (4.0, 2.0)
CUT_DASHES = (4, 3)
# La pastille qui numérote une feuille : sa taille, et son fond quand elle doit
# se poser sur la mosaïque faute de marge.
BADGE_SIZE = (26.0, 19.0)
BADGE_GAP = 4.0
BADGE_BG = QColor(20, 20, 20, 200)
BADGE_INK = QColor(245, 245, 245)


def draw_cut(painter, depart, arrivee) -> None:
    """Trace une coupe entre deux feuilles, en deux tons superposés."""
    for rang, (couleur, largeur) in enumerate(
            zip((CUT_UNDER, CUT_OVER), CUT_WIDTHS, strict=True)):
        stylo = QPen(couleur, largeur)
        if rang:                          # le second ton est tireté
            stylo.setDashPattern(list(CUT_DASHES))
        painter.setPen(stylo)
        painter.drawLine(depart, arrivee)


def badge_rect(feuille: QRectF, morceau: QRectF) -> tuple[QRectF, bool]:
    """Où poser le numéro d'une feuille, et s'il faut lui donner un fond.

    ⚠️ **Dans la marge quand il y en a une.** Le morceau de grille ne remplit
    presque jamais toute la feuille : le numéro se glisse dans ce qui reste,
    plutôt que de couvrir une carte. Quand la feuille est pleine à ras bord, il
    ne reste que la mosaïque, et le numéro prend alors un fond, faute de quoi
    il se lirait sur des cartes de toutes les couleurs.
    """
    large, haut = BADGE_SIZE
    dessous = feuille.bottom() - morceau.bottom()
    droite = feuille.right() - morceau.right()
    if dessous >= haut + BADGE_GAP:
        return QRectF(feuille.left() + BADGE_GAP,
                      feuille.bottom() - haut - BADGE_GAP, large, haut), False
    if droite >= large + BADGE_GAP:
        return QRectF(feuille.right() - large - BADGE_GAP,
                      feuille.top() + BADGE_GAP, large, haut), False
    return QRectF(feuille.left() + BADGE_GAP, feuille.top() + BADGE_GAP,
                  large, haut), True


def draw_badge(painter, rect: QRectF, texte: str, encre, sur_mosaique: bool) -> None:
    """Le numéro d'une feuille, tel qu'il apparaît dans le nom du fichier."""
    police = painter.font()
    police.setBold(True)
    painter.save()
    painter.setFont(police)
    if sur_mosaique:
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(BADGE_BG))
        painter.drawRoundedRect(rect, 3, 3)
        painter.setPen(QPen(BADGE_INK))
    else:
        painter.setPen(QPen(encre))
    painter.drawText(rect, Qt.AlignCenter, texte)
    painter.restore()
