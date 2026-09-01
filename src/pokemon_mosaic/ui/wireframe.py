"""Aperçu fil de fer de la mise en page.

Montre la disposition et les proportions du résultat — feuille, marges, contours
des cartes, coupes entre panneaux — **sans les images**, comme demandé : on juge
ici de la géométrie, pas du contenu.
"""


from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget

from ..layout import grid_geometry

PAPER = QColor(252, 252, 252)
PAPER_EDGE = QColor(120, 120, 120)
CARD_EDGE = QColor(150, 165, 190)
CARD_FILL = QColor(225, 233, 245)
# Pleines et non plus seulement cernées : un contour rouge sur fond blanc se
# perdait au milieu des cartes dès que la grille passait la centaine de cases,
# et il fallait chercher les trous au lieu de les voir.
EMPTY_FILL = QColor(208, 90, 90)
EMPTY_EDGE = QColor(150, 45, 45)
# ⚠️ **Plus rouge depuis que les cases vides le sont.** Le trait valait #c85a5a
# et le remplissage des trous #d05a5a : huit d'écart sur 765, là où une case
# vide et une carte en ont 315. La coupe passait pour une colonne de trous. Un
# gris sombre tiré, convention des traits de coupe, ne se confond avec rien.
CUT_LINE = QColor(55, 55, 55)
MARGIN_FILL = QColor(240, 240, 240)


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

        On garde la même structure de quadruplet que l'autre cas — feuille et
        grille confondues — pour que le dessin, le clic et le calcul d'origine
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
        # pixels ne donnaient pas le même nombre de cartes par feuille — 49 161
        # combinaisons en désaccord sur les sept formats —, et l'on jugeait la
        # mise en page sur un dessin qui n'était pas celui du poster.
        geometrie = grid_geometry(
            (paper_w, paper_h), session.panels, session.cols, session.rows,
            card_aspect, session.dpi, session.card_width_mm, session.card_gap_mm,
            session.panel_rows,
        )
        self._per_panel = geometrie.per_panel
        self._rows_per_panel = geometrie.rows_per_panel
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

    def row_offset(self, row: int, geometry) -> float:
        """Décalage d'une ligne depuis le bord haut, en millimètres.

        Même règle que `column_offset` : chaque ligne de feuilles repart de son
        bord haut, sans quoi le dessin montrerait une carte à cheval sur une
        coupe que le poster n'a pas.
        """
        _, _, (_, total_h), (_, card_h) = geometry
        pas = card_h + self._gap
        if self._show_paper:
            par_feuille = max(1, self._rows_per_panel)
            feuille_h = total_h / max(1, self._session.panel_rows)
            return (row // par_feuille) * feuille_h + (row % par_feuille) * pas
        return row * pas

    def column_offset(self, col: int, geometry) -> float:
        """Décalage d'une colonne depuis le bord gauche, en millimètres.

        ⚠️ **Chaque feuille repart de son propre bord**, comme à l'export : les
        colonnes ne sont pas à pas constant. Posées à la file, le dessin
        montrait une carte à cheval sur la coupe là où le poster n'en a pas.
        """
        _, _, (total_w, _), (card_w, _) = geometry
        pas = card_w + self._gap
        if self._show_paper:
            par_feuille = max(1, self._per_panel)
            feuille_w = total_w / max(1, self._session.panels)
            return (col // par_feuille) * feuille_w + (col % par_feuille) * pas
        return col * pas

    def _grid_origin(self, geometry):
        """Coin haut-gauche de la grille.

        ⚠️ **Calée à gauche**, non centrée : la place en trop est ce qu'apporte
        la feuille suivante, et elle doit se voir d'un bloc, du côté où l'on
        ajoutera la prochaine. Répartie de part et d'autre, elle donnait deux
        demi-marges qui ne disaient rien.

        ⚠️ **La marge verticale ne se centre que sur une seule ligne de
        feuilles.** Dès qu'il y en a plusieurs, elle passe à zéro comme à
        l'export : décalée, elle pousserait la dernière ligne de chaque feuille
        au-delà de son bord bas, et la coupe tomberait en pleine carte.
        """
        scale, (ox, oy), (_, total_h), (_card_w, card_h) = geometry
        session = self._session
        if self._show_paper and session.panel_rows > 1:
            return ox, oy
        grid_h = card_h * session.rows + max(0, session.rows - 1) * self._gap
        return ox, oy + (total_h - grid_h) * scale / 2

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
        painter.setBrush(QBrush(PAPER))
        painter.setPen(Qt.NoPen)
        painter.drawRect(QRectF(gx, gy, card_w * session.cols * scale,
                                card_h * session.rows * scale))

        empty = set(session.empty_cells())
        # Au-delà d'un certain nombre de cases, les contours se confondent : on
        # allège le trait pour que la grille reste lisible.
        pen_width = 1 if session.cols * session.rows <= 900 else 0
        for row in range(session.rows):
            for col in range(session.cols):
                rect = QRectF(
                    gx + self.column_offset(col, geometry) * scale,
                    gy + self.row_offset(row, geometry) * scale,
                    card_w * scale, card_h * scale)
                is_empty = (row, col) in empty
                painter.setBrush(QBrush(EMPTY_FILL if is_empty else CARD_FILL))
                painter.setPen(QPen(EMPTY_EDGE if is_empty else CARD_EDGE,
                                    1.5 if is_empty else pen_width))
                painter.drawRect(rect)

        # Coupes entre panneaux : elles tombent toujours sur un bord de carte,
        # dans un sens comme dans l'autre.
        if self._show_paper and (session.panels > 1 or session.panel_rows > 1):
            painter.setPen(QPen(CUT_LINE, 2, Qt.DashLine))
            for panel in range(1, session.panels):
                x = ox + (total_w / session.panels) * panel * scale
                painter.drawLine(x, oy, x, oy + total_h * scale)
            for ligne in range(1, session.panel_rows):
                y = oy + (total_h / session.panel_rows) * ligne * scale
                painter.drawLine(ox, y, ox + total_w * scale, y)
        painter.end()

    # --- Interaction ------------------------------------------------------

    def mousePressEvent(self, event) -> None:
        """Ouvre un geste. Ce qu'il pose est décidé par sa **première** case.

        Basculer case par case ferait clignoter tout ce sur quoi on repasse :
        un aller-retour du curseur défaisait ce que l'aller venait de poser.

        ⚠️ **Le bouton gauche seul.** Sans ce filtre, un clic droit — le réflexe
        pour chercher un menu contextuel — basculait une case, et le moindre
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
        # Ni les colonnes ni les lignes ne sont à pas constant — chaque feuille
        # repart de son bord —, donc on cherche la bande qui contient le point
        # plutôt que de diviser.
        row = next(
            (r for r in range(self._session.rows)
             if 0 <= y - gy - self.row_offset(r, self._geometry) * scale
             < card_h * scale),
            -1,
        )
        col = next(
            (c for c in range(self._session.cols)
             if 0 <= x - gx - self.column_offset(c, self._geometry) * scale
             < card_w * scale),
            -1,
        )
        if 0 <= row < self._session.rows and 0 <= col < self._session.cols:
            return row, col
        return None


def _paper_mm(session):
    return session.paper_mm()
