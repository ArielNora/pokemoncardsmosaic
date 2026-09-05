"""Aperçu fil de fer de la mise en page.

Montre la disposition et les proportions du résultat, feuille, marges, contours
des cartes, coupes entre panneaux : **sans les images**, comme demandé : on juge
ici de la géométrie, pas du contenu.
"""


from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget

from ..layout import cards_on_panel, grid_geometry

PAPER = QColor(252, 252, 252)
PAPER_EDGE = QColor(120, 120, 120)
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
MARGIN_FILL = QColor(240, 240, 240)
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


class WireframeView(QWidget):
    """Dessine la mise en page à l'échelle et convertit les clics en cases."""

    cell_clicked = Signal(int, int)
    # Tout le trajet parcouru depuis le début du geste, et l'état à y poser.
    cells_painted = Signal(list, bool)

    def __init__(self, session, parent=None, show_paper: bool = True):
        super().__init__(parent)
        self._session = session
        self._geometry: tuple[float, float, float, float] | None = None
        # Sans feuille, la grille occupe tout le cadre : c'est la vue de
        # l'onglet des dimensions, où le format d'impression n'a pas encore été
        # choisi et n'aurait donc rien à dire.
        self._show_paper = show_paper
        # Cases parcourues par le geste en cours, dans l'ordre, et l'état qu'il
        # pose. `None` quand aucun bouton n'est enfoncé.
        self._painted: list[tuple[int, int]] = []
        self._paint_mode: bool | None = None
        # Cartes par feuille du dernier calcul, pour placer les colonnes comme
        # l'export : chaque feuille repart de son bord.
        self._per_panel = 1
        self._rows_per_panel = 1
        self._gap = 0.0
        # Où se pose le morceau de chaque feuille, relevé **une fois par
        # calcul de géométrie**. ⚠️ Le lire case par case coûtait une géométrie
        # de grille complète par case : mesuré, 1,07 s pour dessiner une grille
        # de 200×200 et autant pour y placer un clic.
        self._places: dict[int, tuple[float, float]] = {}
        self.setMinimumSize(320, 380)
        self.setCursor(Qt.PointingHandCursor)

    # --- Géométrie --------------------------------------------------------

    def _card_aspect(self) -> float:
        session = self._session
        if session.card_set and session.card_set.full_size[1]:
            width, height = session.card_set.full_size
            return width / height
        return 713 / 984

    def _grid_only_layout(self):
        """Géométrie quand il n'y a pas de feuille : la grille remplit le cadre.

        On garde la même structure de quadruplet que l'autre cas, feuille et
        grille confondues : pour que le dessin, le clic et le calcul d'origine
        n'aient pas à savoir dans quel mode ils tournent.
        """
        session = self._session
        aspect = self._card_aspect()
        margin = 12
        # Une carte fait 1 de large et 1/aspect de haut : la grille entière tient
        # dans ce rapport, qu'on ajuste au cadre.
        grid_w, grid_h = session.cols * 1.0, session.rows / aspect
        scale = min((self.width() - 2 * margin) / grid_w,
                    (self.height() - 2 * margin) / grid_h)
        if scale <= 0:
            return None
        origin_x = (self.width() - grid_w * scale) / 2
        origin_y = (self.height() - grid_h * scale) / 2
        return scale, (origin_x, origin_y), (grid_w, grid_h), (1.0, 1.0 / aspect)

    def _layout(self):
        """Renvoie (échelle, origine feuille, taille feuille, taille carte) en pixels
        écran, ou None si la mise en page n'a pas de sens."""
        session = self._session
        if session.cols <= 0 or session.rows <= 0:
            return None
        if not self._show_paper:
            return self._grid_only_layout()

        card_aspect = self._card_aspect()
        paper_w, paper_h = _paper_mm(session)
        total_w, total_h = session.sheet_mm()
        # ⚠️ **Un nombre entier de cartes par feuille**, pour qu'une coupe tombe
        # toujours entre deux cartes. La carte se plie à la feuille ; les
        # colonnes, elles, n'ont plus à se diviser par le nombre de feuilles.
        #
        # ⚠️ **À la résolution de la session, jamais à une autre.** Le dessin
        # tournait à 72 dpi et l'export à celle des réglages : les arrondis en
        # pixels ne donnaient pas le même nombre de cartes par feuille, 49 161
        # combinaisons en désaccord sur les sept formats, et l'on jugeait la
        # mise en page sur un dessin qui n'était pas celui du poster.
        geometrie = grid_geometry(
            (paper_w, paper_h), session.panels, session.cols, session.rows,
            card_aspect, session.dpi, session.card_width_mm, session.card_gap_mm,
            session.panel_rows,
        )
        self._per_panel = geometrie.per_panel
        self._rows_per_panel = geometrie.rows_per_panel
        self._places = {index: session.panel_position_mm(index)
                        for index in range(session.panel_count())}
        self._gap = geometrie.gap / session.dpi * 25.4
        # Tout est ramené en millimètres pour le dessin, puis mis à l'échelle.
        card_w = geometrie.card_w / session.dpi * 25.4
        card_h = geometrie.card_h / session.dpi * 25.4

        margin = 12
        scale = min((self.width() - 2 * margin) / total_w,
                    (self.height() - 2 * margin) / total_h)
        if scale <= 0:
            return None

        origin_x = (self.width() - total_w * scale) / 2
        origin_y = (self.height() - total_h * scale) / 2
        return scale, (origin_x, origin_y), (total_w, total_h), (card_w, card_h)

    def cell_origin(self, row: int, col: int, geometry) -> tuple[float, float]:
        """Coin haut-gauche d'une case, en millimètres depuis l'origine.

        ⚠️ **Chaque feuille repart de son propre coin**, comme à l'export : ni
        les colonnes ni les lignes ne sont à pas constant. Posées à la file, le
        dessin montrait une carte à cheval sur une coupe que le poster n'a pas.

        ⚠️ **Et le morceau de chaque feuille se déplace.** Où il se pose, la
        session seule le sait : calé à gauche, centré en hauteur, ou là où
        l'utilisateur l'a tiré. Le fil de fer l'ignorait : après un déplacement,
        la vue d'exécution montrait la mosaïque à sa place d'origine et
        l'imprimante l'écrivait ailleurs.
        """
        _, _, (_, _), (card_w, card_h) = geometry
        session = self._session
        pas_x, pas_y = card_w + self._gap, card_h + self._gap
        if not self._show_paper:
            return col * pas_x, row * pas_y
        paper_w, paper_h = session.paper_mm()
        feuille_c, dans_c = divmod(col, max(1, self._per_panel))
        feuille_l, dans_l = divmod(row, max(1, self._rows_per_panel))
        pose = self._places.get(feuille_l * session.panels + feuille_c,
                                (0.0, 0.0))
        return (feuille_c * paper_w + pose[0] + dans_c * pas_x,
                feuille_l * paper_h + pose[1] + dans_l * pas_y)

    def _grid_origin(self, geometry):
        """Coin haut-gauche du dessin : le papier, ou la grille seule.

        Le calage, à gauche, centré en hauteur ou déplacé à la main, est
        porté par `cell_origin`, qui le lit dans la session. Le recalculer ici
        en donnerait une seconde version, qui finirait par diverger.
        """
        _, (ox, oy), _, _ = geometry
        return ox, oy

    # --- Dessin -----------------------------------------------------------

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), self.palette().window())

        geometry = self._layout()
        self._geometry = geometry
        if geometry is None:
            return

        scale, (ox, oy), (total_w, total_h), (card_w, card_h) = geometry
        session = self._session

        # La feuille, marges comprises.
        if self._show_paper:
            painter.setBrush(QBrush(MARGIN_FILL))
            painter.setPen(QPen(PAPER_EDGE, 1))
            painter.drawRect(QRectF(ox, oy, total_w * scale, total_h * scale))

        gx, gy = self._grid_origin(geometry)
        # ⚠️ **Un fond par morceau, pas un grand rectangle.** La mosaïque n'est
        # plus d'un seul tenant : chaque feuille repart de son coin et son
        # morceau se déplace. Un rectangle englobant peignait du blanc là où il
        # n'y a aucune carte : une bande de papier en travers de la coupe.
        painter.setBrush(QBrush(PAPER))
        painter.setPen(Qt.NoPen)
        if self._show_paper:
            for index in range(session.panel_count()):
                if session.panel_carries_cards(index):
                    painter.drawRect(self._piece_rect(index, geometry, gx, gy))
        else:
            painter.drawRect(QRectF(gx, gy, card_w * session.cols * scale,
                                    card_h * session.rows * scale))

        empty = set(session.empty_cells())
        # Au-delà d'un certain nombre de cases, les contours se confondent : on
        # allège le trait pour que la grille reste lisible.
        pen_width = 1 if session.cols * session.rows <= 900 else 0
        for row in range(session.rows):
            for col in range(session.cols):
                origine = self.cell_origin(row, col, geometry)
                rect = QRectF(gx + origine[0] * scale, gy + origine[1] * scale,
                              card_w * scale, card_h * scale)
                is_empty = (row, col) in empty
                painter.setBrush(QBrush(EMPTY_FILL if is_empty else CARD_FILL))
                painter.setPen(QPen(EMPTY_EDGE if is_empty else CARD_EDGE,
                                    1.5 if is_empty else pen_width))
                painter.drawRect(rect)

        # Coupes entre panneaux : elles tombent toujours sur un bord de carte,
        # dans un sens comme dans l'autre.
        if self._show_paper and session.panel_count() > 1:
            for panel in range(1, session.panels):
                x = ox + (total_w / session.panels) * panel * scale
                draw_cut(painter, QPointF(x, oy),
                         QPointF(x, oy + total_h * scale))
            for ligne in range(1, session.panel_rows):
                y = oy + (total_h / session.panel_rows) * ligne * scale
                draw_cut(painter, QPointF(ox, y),
                         QPointF(ox + total_w * scale, y))
            self._draw_numbers(painter, geometry)
        painter.end()

    def _draw_numbers(self, painter, geometry) -> None:
        """Le numéro de chaque feuille, celui-là même que porte son fichier."""
        scale, (ox, oy), (total_w, total_h), _ = geometry
        session = self._session
        gx, gy = self._grid_origin(geometry)
        largeur = total_w * scale / max(1, session.panels)
        hauteur = total_h * scale / max(1, session.panel_rows)
        encre = self.palette().windowText().color()
        for index in range(session.panel_count()):
            if not session.panel_carries_cards(index):
                continue
            ligne, colonne = divmod(index, max(1, session.panels))
            feuille = QRectF(ox + colonne * largeur, oy + ligne * hauteur,
                             largeur, hauteur)
            morceau = self._piece_rect(index, geometry, gx, gy)
            rect, sur_mosaique = badge_rect(feuille, morceau)
            draw_badge(painter, rect, str(index + 1), encre, sur_mosaique)

    def _piece_rect(self, index: int, geometry, gx: float, gy: float) -> QRectF:
        """Le morceau de mosaïque que porte une feuille, à l'écran."""
        scale, _, _, (card_w, card_h) = geometry
        session = self._session
        ligne, colonne = divmod(index, max(1, session.panels))
        combien_c = cards_on_panel(session.cols, self._per_panel, colonne)
        combien_l = cards_on_panel(session.rows, self._rows_per_panel, ligne)
        origine = self.cell_origin(ligne * max(1, self._rows_per_panel),
                                   colonne * max(1, self._per_panel), geometry)
        return QRectF(
            gx + origine[0] * scale, gy + origine[1] * scale,
            (combien_c * card_w + max(0, combien_c - 1) * self._gap) * scale,
            (combien_l * card_h + max(0, combien_l - 1) * self._gap) * scale)

    # --- Interaction ------------------------------------------------------

    def mousePressEvent(self, event) -> None:
        """Ouvre un geste. Ce qu'il pose est décidé par sa **première** case.

        Basculer case par case ferait clignoter tout ce sur quoi on repasse :
        un aller-retour du curseur défaisait ce que l'aller venait de poser.

        ⚠️ **Le bouton gauche seul.** Sans ce filtre, un clic droit, le réflexe
        pour chercher un menu contextuel, basculait une case, et le moindre
        mouvement en posait toute une rangée. Mesuré : six cases vides posées
        par un glissement au bouton droit que personne n'avait voulu.
        """
        self._painted = []
        self._paint_mode = None
        if event.button() != Qt.LeftButton:
            return
        cell = self.cell_at(event.position().x(), event.position().y())
        if cell is None:
            return
        self._paint_mode = cell not in set(self._session.empty_cells())
        self._painted = [cell]

    def mouseMoveEvent(self, event) -> None:
        if self._paint_mode is None or not (event.buttons() & Qt.LeftButton):
            return
        cell = self.cell_at(event.position().x(), event.position().y())
        if cell is None or cell in self._painted:
            return
        self._painted.append(cell)
        # ⚠️ Le trajet **entier** est renvoyé, pas la seule case atteinte : la
        # session applique alors un lot idempotent, et la vue n'a pas à tenir
        # l'état d'avant le geste pour rester juste si un lot se perd.
        self.cells_painted.emit(list(self._painted), self._paint_mode)

    def mouseReleaseEvent(self, event) -> None:
        """Un geste d'une seule case reste un clic, avec sa bascule.

        C'est ce qui permet de **déplacer** un trou sur une grille déjà
        complète : le clic évince le plus ancien, là où un glissement s'arrête
        au quota. Les deux gestes n'ont pas la même intention.
        """
        if self._paint_mode is not None and len(self._painted) == 1:
            self.cell_clicked.emit(*self._painted[0])
        self._painted = []
        self._paint_mode = None

    def cell_at(self, x: float, y: float):
        """Case de la grille sous ce point de l'écran, ou None en dehors."""
        if self._geometry is None:
            return None
        scale, _, _, (card_w, card_h) = self._geometry
        gx, gy = self._grid_origin(self._geometry)
        # `int()` tronque vers zéro : un clic juste à gauche de la grille
        # donnerait la colonne 0 au lieu d'être rejeté. On écarte d'abord.
        if x < gx or y < gy:
            return None
        # Ni les colonnes ni les lignes ne sont à pas constant, chaque feuille
        # repart de son coin et son morceau se déplace, donc on cherche la
        # case qui contient le point plutôt que de diviser.
        for row in range(self._session.rows):
            for col in range(self._session.cols):
                origine = self.cell_origin(row, col, self._geometry)
                if (0 <= x - gx - origine[0] * scale < card_w * scale
                        and 0 <= y - gy - origine[1] * scale < card_h * scale):
                    return row, col
        return None


def _paper_mm(session):
    return session.paper_mm()
