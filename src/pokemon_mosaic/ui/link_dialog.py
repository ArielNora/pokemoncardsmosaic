"""Création et modification d'un lien entre cartes.

Deux panneaux : à gauche le **rectangle** en cours de composition, à droite les
cartes disponibles. On remplit les cases en y faisant glisser une illustration.

Composer un rectangle en posant les cartes plutôt qu'en ordonnant une liste :
sur un 3×3, « la septième » ne dit rien, alors que la case le dit tout de suite.
Le rectangle grandit par ses bords, et ne peut être validé que **plein** — un
lien est un rectangle sans trou, et une case vide n'a pas de sens à donner à
l'optimiseur.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..links import MAX_SIDE, Link
from . import theme
from .gallery import numpy_to_pixmap
from .link_grid import CELL_WIDTH, CardPalette, GridPanel
from .session import Session

# Toutes les extensions, dans le filtre. Une chaîne vide comme donnée, pour la
# distinguer d'un dossier réellement nommé.
ALL_FOLDERS = ""


class LinkDialog(QDialog):
    """Compose un `Link`. `link` non nul ouvre le dialogue en modification."""

    def __init__(self, session: Session, link: Link | None = None, parent=None):
        super().__init__(parent)
        self._session = session
        self._editing = link
        self._build()
        self._grid.set_thumbnails(
            {card.index: card.thumbnail for card in session.card_set}
            if session.card_set else {}
        )
        if link is not None:
            self._name.setText(link.name)
            self._ordered.setChecked(link.ordered)
            self._grid.load(link.cards, link.shape)
        self._fill_folders()
        self._fill_palette()
        self._update_buttons()

    # --- Construction -----------------------------------------------------

    def _build(self) -> None:
        self._panel = GridPanel()
        self._grid = self._panel.grid
        self._grid.changed.connect(self._on_grid_changed)

        self._search = QLineEdit()
        self._search.textChanged.connect(self._fill_palette)
        self._folder = QComboBox()
        self._folder.currentIndexChanged.connect(self._fill_palette)
        self._palette = CardPalette()
        self._palette_label = QLabel()

        right = QVBoxLayout()
        right.addWidget(self._palette_label)
        filters = QHBoxLayout()
        filters.addWidget(self._search, 2)
        filters.addWidget(self._folder, 1)
        right.addLayout(filters)
        right.addWidget(self._palette, 1)
        right_panel = QWidget()
        right_panel.setLayout(right)

        columns = QHBoxLayout()
        columns.addWidget(self._panel, 2)
        columns.addWidget(right_panel, 3)

        self._name_label = QLabel()
        self._name = QLineEdit()
        self._ordered = QCheckBox()
        self._ordered.setChecked(True)
        self._error = QLabel()
        self._error.setWordWrap(True)
        theme.mark(self._error, "error")

        name_row = QHBoxLayout()
        name_row.addWidget(self._name_label)
        name_row.addWidget(self._name, 1)

        self._buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        self._buttons.accepted.connect(self._try_accept)
        self._buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(columns, 1)
        layout.addWidget(self._ordered)
        layout.addLayout(name_row)
        layout.addWidget(self._error)
        layout.addWidget(self._buttons)
        self.resize(820, 520)
        self.retranslate_ui()

    def retranslate_ui(self) -> None:
        self.setWindowTitle(self.tr("Modifier le lien") if self._editing
                            else self.tr("Nouveau lien"))
        self._panel.title.setText(self.tr("Le lien"))
        self._palette_label.setText(self.tr("Cartes disponibles"))
        self._search.setPlaceholderText(self.tr("Filtrer par nom…"))
        self._name_label.setText(self.tr("Nom (facultatif)"))
        self._ordered.setText(
            self.tr("Ordre imposé (sinon l'optimiseur peut retourner le bloc)")
        )
        self._fill_folders()
        self._update_buttons()

    # --- Cartes disponibles ----------------------------------------------

    def _icon(self, index: int):
        card = self._session.card_set[index]
        return numpy_to_pixmap(card.thumbnail).scaledToWidth(
            CELL_WIDTH, Qt.SmoothTransformation
        )

    def _label_for(self, index: int) -> str:
        card = self._session.card_set[index]
        # Le dossier lève l'ambiguïté entre deux cartes homonymes de séries
        # différentes.
        text = f"{card.name}  —  {self._session.folder_of(index)}"
        if self._session.is_excluded(index):
            # Un lien portant sur une carte retirée ne s'appliquera jamais : mieux
            # vaut le voir au moment de le composer qu'après une exécution entière.
            text += "  " + self.tr("(carte exclue)")
        return text

    def _fill_folders(self) -> None:
        """Le filtre par extension. Reconstruit sans perdre le choix courant."""
        courant = self._folder.currentData()
        self._folder.blockSignals(True)
        self._folder.clear()
        self._folder.addItem(self.tr("Toutes les extensions"), ALL_FOLDERS)
        for folder in self._session.folders():
            self._folder.addItem(folder, folder)
        if courant:
            position = self._folder.findData(courant)
            if position >= 0:
                self._folder.setCurrentIndex(position)
        self._folder.blockSignals(False)

    def _fill_palette(self) -> None:
        """Les cartes non encore posées, filtrées par nom et par extension."""
        self._palette.clear()
        if not self._session.card_set:
            return
        needle = self._search.text().strip().lower()
        folder = self._folder.currentData() or ALL_FOLDERS
        posees = self._grid.placed_cards()
        for card in self._session.card_set:
            if card.index in posees:
                continue
            if folder and self._session.folder_of(card.index) != folder:
                continue
            label = self._label_for(card.index)
            if needle and needle not in label.lower():
                continue
            item = QListWidgetItem(self._icon(card.index), label)
            item.setData(Qt.UserRole, card.index)
            self._palette.addItem(item)

    # --- État -------------------------------------------------------------

    def _on_grid_changed(self) -> None:
        self._fill_palette()
        self._update_buttons()

    def _update_buttons(self) -> None:
        cols, rows = self._grid.shape
        self._panel.hint.setText(self._hint_text())
        self._buttons.button(QDialogButtonBox.Ok).setEnabled(
            self._grid.complete and cols * rows >= 2)

    def _hint_text(self) -> str:
        """Dit ce qui manque pour pouvoir valider, et rien d'autre."""
        vides = self._grid.empty_count()
        cols, rows = self._grid.shape
        if vides:
            return self.tr(
                "Toutes les cases doivent être remplies : il en reste %n vide(s). "
                "Faites glisser une carte depuis la droite.", "", vides)
        if cols * rows < 2:
            return self.tr(
                "Un lien groupe au moins deux cartes : ajoutez une ligne ou une "
                "colonne.")
        return self.tr("Rectangle %1 × %2, complet.").replace(
            "%1", str(cols)).replace("%2", str(rows))

    # --- Validation -------------------------------------------------------

    def link(self) -> Link:
        return Link(cards=tuple(self._grid.cards()),
                    shape=self._grid.shape,
                    ordered=self._ordered.isChecked(),
                    enabled=self._editing.enabled if self._editing else True,
                    name=self._name.text().strip())

    def _try_accept(self) -> None:
        """N'accepte que si la bibliothèque veut bien du lien.

        Le conflit est affiché dans le dialogue plutôt que remonté en exception :
        l'utilisateur peut corriger son rectangle sans avoir tout à ressaisir.
        """
        library = self._session.links
        candidate = self.link()
        try:
            if self._editing is not None:
                # Simulation du remplacement : le lien modifié ne doit pas être
                # jugé en conflit avec la version qu'il remplace.
                without = [link for link in library.links if link is not self._editing]
                type(library)(without).check_free(candidate)
            else:
                library.check_free(candidate)
        except ValueError as error:
            self._error.setText(str(error))
            return
        self.accept()


__all__ = ["MAX_SIDE", "LinkDialog"]
