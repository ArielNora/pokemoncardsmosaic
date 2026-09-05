"""Le menu des agencements gardés : tout ce qui est enregistré, en un endroit.

Chaque agencement s'y voit en petit, avec une **croix rouge** sur les cartes que
le catalogue n'a pas, et la liste des cartes qu'il emploie, les manquantes
nommées. De là, on l'ouvre dans une case pour l'exporter, on l'envoie en JSON,
on en importe un, on le renomme ou on le jette.

⚠️ **Un agencement à qui il manque une carte ne s'ouvre pas.** Amputé, ce n'est
plus celui qu'on a partagé : la fenêtre le montre et dit ce qui manque, mais
elle ne le laisse pas passer à l'export.
"""

import os

import numpy as np
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..arrangements import (
    Arrangement,
    delete_arrangement,
    list_arrangements,
    read_arrangement,
    rename_arrangement,
    save_arrangement,
    unique_name,
    write_arrangement,
)
from ..scoring import EMPTY
from . import theme
from .session import MAX_SAVED, Session

DIALOG_SIZE = QSize(1000, 660)
# L'aperçu d'un agencement dans la fenêtre. Assez grand pour reconnaître une
# mosaïque et voir où sont les trous.
PREVIEW = QSize(360, 460)
# La croix des cartes absentes, dessinée par-dessus la case qu'elles occupaient.
MISSING_FILL = QColor(120, 30, 30)
MISSING_CROSS = QColor(255, 90, 90)


def arrangement_image(arrangement: Arrangement, session: Session,
                      empty_colour) -> QImage | None:
    """La mosaïque d'un agencement, croix rouge là où une carte manque.

    Dessinée depuis le catalogue de celui qui regarde, et non depuis des images
    enregistrées : un agencement ne transporte pas les cartes, il les nomme.
    """
    if not arrangement.grid:
        return None
    cartes = session.card_set
    if cartes is None or not len(cartes):
        return None
    tile_h, tile_w = cartes[0].thumbnail.shape[:2]
    rows, cols = len(arrangement.grid), len(arrangement.grid[0])
    canvas = np.full((rows * tile_h, cols * tile_w, 3), empty_colour, np.uint8)
    manquantes = []
    for row, ligne in enumerate(arrangement.grid):
        for col, case in enumerate(ligne):
            if case == EMPTY:
                continue
            index = session.index_of_path(arrangement.cards[case])
            if index is None:
                manquantes.append((row, col))
                continue
            canvas[row * tile_h:(row + 1) * tile_h,
                   col * tile_w:(col + 1) * tile_w] = cartes[index].thumbnail

    canvas = np.ascontiguousarray(canvas)
    hauteur, largeur, _ = canvas.shape
    image = QImage(canvas.data, largeur, hauteur, 3 * largeur,
                   QImage.Format_RGB888).copy()
    if manquantes:
        peintre = QPainter(image)
        peintre.setPen(QPen(MISSING_CROSS, max(1, tile_w // 8)))
        for row, col in manquantes:
            x, y = col * tile_w, row * tile_h
            peintre.fillRect(x, y, tile_w, tile_h, MISSING_FILL)
            peintre.drawLine(x, y, x + tile_w, y + tile_h)
            peintre.drawLine(x + tile_w, y, x, y + tile_h)
        peintre.end()
    return image


class ArrangementsDialog(QDialog):
    """La bibliothèque : la liste à gauche, l'agencement choisi à droite."""

    def __init__(self, session: Session, directory: str, parent=None):
        super().__init__(parent)
        self._session = session
        self._directory = directory
        self._arrangements: list[Arrangement] = []
        self._build()
        self.reload()

    # --- Construction -----------------------------------------------------

    def _build(self) -> None:
        self._list = QListWidget()
        self._list.currentRowChanged.connect(lambda _: self._show_current())
        self._list.setMinimumWidth(280)

        self._title = QLabel()
        gras = self._title.font()
        gras.setBold(True)
        self._title.setFont(gras)
        self._title.setWordWrap(True)
        self._image = QLabel()
        self._image.setAlignment(Qt.AlignCenter)
        self._image.setFixedSize(PREVIEW)
        self._missing = QLabel()
        self._missing.setWordWrap(True)
        theme.mark(self._missing, "warning")
        alerte = self._missing.font()
        alerte.setBold(True)
        self._missing.setFont(alerte)
        # La liste des cartes employées, les absentes en tête et signalées.
        self._cards = QListWidget()

        droite = QVBoxLayout()
        droite.addWidget(self._title)
        droite.addWidget(self._missing)
        haut = QHBoxLayout()
        haut.addWidget(self._image)
        haut.addWidget(self._cards, 1)
        droite.addLayout(haut, 1)

        self._open = QPushButton()
        self._open.clicked.connect(self._open_current)
        self._export = QPushButton()
        self._export.clicked.connect(self._export_current)
        self._import = QPushButton()
        self._import.clicked.connect(self._import_file)
        self._rename = QPushButton()
        self._rename.clicked.connect(self._rename_current)
        self._delete = QPushButton()
        self._delete.clicked.connect(self._delete_current)
        self._close = QPushButton()
        self._close.clicked.connect(self.accept)

        boutons = QHBoxLayout()
        for bouton in (self._open, self._export, self._import, self._rename,
                       self._delete):
            boutons.addWidget(bouton)
        boutons.addStretch(1)
        boutons.addWidget(self._close)

        panneau = QWidget()
        panneau.setLayout(droite)
        milieu = QHBoxLayout()
        milieu.addWidget(self._list)
        milieu.addWidget(panneau, 1)

        pile = QVBoxLayout(self)
        pile.addLayout(milieu, 1)
        pile.addLayout(boutons)
        self.resize(DIALOG_SIZE)
        self.retranslate_ui()

    def retranslate_ui(self) -> None:
        self.setWindowTitle(self.tr("Agencements enregistrés"))
        self._open.setText(self.tr("Mettre dans une case"))
        self._export.setText(self.tr("Exporter en JSON…"))
        self._import.setText(self.tr("Importer un JSON…"))
        self._rename.setText(self.tr("Renommer…"))
        self._delete.setText(self.tr("Supprimer…"))
        self._close.setText(self.tr("Fermer"))
        self._show_current()

    # --- La liste ---------------------------------------------------------

    def reload(self, select: str | None = None) -> None:
        """Relit la bibliothèque et garde l'agencement demandé sélectionné."""
        self._arrangements = list_arrangements(self._directory)
        self._list.clear()
        for arrangement in self._arrangements:
            manquantes = len(self._session.missing_cards(arrangement))
            texte = arrangement.name
            if manquantes:
                texte += "\n" + self.tr("%n carte(s) manquante(s)", "", manquantes)
            self._list.addItem(QListWidgetItem(texte))
        if self._arrangements:
            rangs = [rang for rang, un in enumerate(self._arrangements)
                     if un.name == select]
            self._list.setCurrentRow(rangs[0] if rangs else 0)
        self._show_current()

    def current(self) -> Arrangement | None:
        rang = self._list.currentRow()
        if 0 <= rang < len(self._arrangements):
            return self._arrangements[rang]
        return None

    def _show_current(self) -> None:
        arrangement = self.current()
        for bouton in (self._export, self._rename, self._delete):
            bouton.setEnabled(arrangement is not None)
        if arrangement is None:
            self._title.setText(self.tr("Aucun agencement enregistré."))
            self._missing.setText("")
            self._image.setPixmap(QPixmap())
            self._cards.clear()
            self._open.setEnabled(False)
            return

        manquantes = self._session.missing_cards(arrangement)
        colonnes, lignes = arrangement.shape
        self._title.setText(
            self.tr("%1 : %2 × %3 cartes, score %4")
            .replace("%1", arrangement.name)
            .replace("%2", str(colonnes)).replace("%3", str(lignes))
            .replace("%4", f"{arrangement.score:.1f}")
        )
        # ⚠️ **Amputé, ce n'est plus l'agencement qu'on a partagé.** On le
        # montre, on dit ce qui manque, et on ne le laisse pas passer.
        self._open.setEnabled(not manquantes)
        self._missing.setText(
            "" if not manquantes else
            self.tr("%n carte(s) de cet agencement manquent au catalogue : "
                    "il ne peut pas être ouvert.", "", len(manquantes))
        )
        image = arrangement_image(arrangement, self._session,
                                  self._session.empty_colour)
        self._image.setPixmap(QPixmap() if image is None else QPixmap.fromImage(
            image.scaled(PREVIEW, Qt.KeepAspectRatio, Qt.SmoothTransformation)))

        self._cards.clear()
        absentes = set(manquantes)
        for chemin in sorted(arrangement.cards, key=lambda c: (c not in absentes, c)):
            item = QListWidgetItem(
                ("✕ " if chemin in absentes else "") + chemin)
            if chemin in absentes:
                item.setForeground(QColor(theme.colours(self.palette())["error"]))
            self._cards.addItem(item)

    # --- Les gestes -------------------------------------------------------

    def _open_current(self) -> None:
        """Range l'agencement choisi dans une case, prêt pour l'export."""
        arrangement = self.current()
        if arrangement is None:
            return
        try:
            garde = self._session.saved_from_arrangement(arrangement)
        except ValueError as erreur:
            QMessageBox.warning(self, self.tr("Agencement incomplet"),
                                str(erreur))
            return
        rang = self._session.save_grid(garde.grid, garde.cards,
                                       garde.iteration, garde.score)
        if rang is None:
            QMessageBox.information(
                self, self.tr("Aucune case libre"),
                self.tr("Les %n case(s) sont prises : videz-en une pour "
                        "ouvrir celui-ci.", "", MAX_SAVED))
            return
        self.accept()

    def _export_current(self) -> None:
        arrangement = self.current()
        if arrangement is None:
            return
        chemin, _ = QFileDialog.getSaveFileName(
            self, self.tr("Exporter l'agencement"),
            os.path.join(os.path.expanduser("~"), f"{arrangement.name}.json"),
            self.tr("Agencement (*.json)"))
        if not chemin:
            return
        try:
            write_arrangement(chemin, arrangement)
        except OSError as erreur:
            QMessageBox.warning(self, self.tr("Écriture impossible"), str(erreur))

    def _import_file(self) -> None:
        """Lit un JSON venu d'ailleurs et le range dans la bibliothèque.

        Le nom est rendu unique : deux personnes nomment volontiers leur essai
        de la même façon, et l'import écraserait le sien sans le dire.
        """
        chemin, _ = QFileDialog.getOpenFileName(
            self, self.tr("Importer un agencement"),
            os.path.expanduser("~"), self.tr("Agencement (*.json)"))
        if not chemin:
            return
        try:
            arrangement = read_arrangement(chemin)
        except (OSError, ValueError) as erreur:
            QMessageBox.warning(self, self.tr("Fichier illisible"), str(erreur))
            return
        nom = unique_name(self._directory, arrangement.name or os.path.basename(chemin))
        save_arrangement(self._directory, Arrangement(
            name=nom, cards=arrangement.cards, grid=arrangement.grid,
            presentation=arrangement.presentation, score=arrangement.score,
            saved_at=arrangement.saved_at))
        self.reload(select=nom)

    def _rename_current(self) -> None:
        arrangement = self.current()
        if arrangement is None:
            return
        nom, valide = QInputDialog.getText(
            self, self.tr("Renommer l'agencement"), self.tr("Nom"),
            text=arrangement.name)
        if not valide or not nom.strip() or nom == arrangement.name:
            return
        rename_arrangement(self._directory, arrangement.name,
                           unique_name(self._directory, nom.strip()))
        self.reload(select=nom.strip())

    def _delete_current(self) -> None:
        arrangement = self.current()
        if arrangement is None:
            return
        reponse = QMessageBox.question(
            self, self.tr("Supprimer cet agencement ?"),
            self.tr("« %1 » sera effacé de la bibliothèque. Le calcul ne "
                    "redonne pas deux fois le même.")
            .replace("%1", arrangement.name),
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reponse == QMessageBox.Yes:
            delete_arrangement(self._directory, arrangement.name)
            self.reload()
