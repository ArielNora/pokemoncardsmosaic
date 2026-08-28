"""Création et modification d'un lien entre cartes.

Le lien se compose en deux temps : on choisit les cartes à gauche, on ordonne la
séquence à droite. Deux listes plutôt qu'une seule à cocher, parce que l'ordre
compte : une case cochée n'a pas de rang, une ligne dans une liste en a un.

Un lien étant un **rectangle plein** d'au plus trois cases de côté, le nombre de
cartes ne suffit plus à le décrire : deux cartes font un 2×1 ou un 1×2, six font
un 3×2 ou un 2×3. D'où le choix de forme, limité aux seules formes que le nombre
de cartes retenues peut remplir.
"""

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..links import Link, shapes_for
from .gallery import numpy_to_pixmap
from .session import Session

# Assez grand pour reconnaître une carte, assez petit pour en voir une vingtaine.
ICON_WIDTH = 32


class LinkDialog(QDialog):
    """Compose un `Link`. `link` non nul ouvre le dialogue en modification."""

    def __init__(self, session: Session, link: Link | None = None, parent=None):
        super().__init__(parent)
        self._session = session
        self._editing = link
        self._icons: dict[int, QListWidgetItem] = {}
        self._build()
        if link is not None:
            self._name.setText(link.name)
            self._ordered.setChecked(link.ordered)
            for index in link.cards:
                self._append_to_sequence(index)
            # Après le remplissage, sinon la liste de formes est encore vide.
            self._refresh_shapes(len(link.cards))
            self.select_shape(link.shape)
        self._fill_candidates()
        self._update_buttons()

    # --- Construction -----------------------------------------------------

    def _build(self) -> None:
        self._search = QLineEdit()
        self._search.textChanged.connect(self._fill_candidates)
        self._candidates = QListWidget()
        self._candidates.setIconSize(QSize(ICON_WIDTH, int(ICON_WIDTH * 984 / 713)))
        self._candidates.setSelectionMode(QListWidget.ExtendedSelection)
        # Les noms longs sont abrégés plutôt que poussés derrière une barre de
        # défilement horizontale, qui obligerait à faire glisser pour lire.
        self._candidates.setTextElideMode(Qt.ElideMiddle)
        self._candidates.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._candidates.itemDoubleClicked.connect(self._add_selected)

        self._sequence = QListWidget()
        self._sequence.setIconSize(QSize(ICON_WIDTH, int(ICON_WIDTH * 984 / 713)))
        self._sequence.setTextElideMode(Qt.ElideMiddle)
        self._sequence.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._sequence.currentRowChanged.connect(self._update_buttons)

        self._add = QPushButton()
        self._remove = QPushButton()
        self._up = QPushButton()
        self._down = QPushButton()
        self._add.clicked.connect(lambda: self._add_selected())
        self._remove.clicked.connect(self._remove_current)
        self._up.clicked.connect(lambda: self._move(-1))
        self._down.clicked.connect(lambda: self._move(1))

        self._candidates_label = QLabel()
        self._sequence_label = QLabel()
        self._name_label = QLabel()
        self._name = QLineEdit()
        self._shape_label = QLabel()
        self._shape = QComboBox()
        self._ordered = QCheckBox()
        self._ordered.setChecked(True)
        self._error = QLabel()
        self._error.setWordWrap(True)
        self._error.setStyleSheet("color: #b00;")

        left = QVBoxLayout()
        left.addWidget(self._candidates_label)
        left.addWidget(self._search)
        left.addWidget(self._candidates, 1)
        left_panel = QWidget()
        left_panel.setLayout(left)

        middle = QVBoxLayout()
        middle.addStretch(1)
        middle.addWidget(self._add)
        middle.addWidget(self._remove)
        middle.addStretch(1)

        right = QVBoxLayout()
        right.addWidget(self._sequence_label)
        right.addWidget(self._sequence, 1)
        order_buttons = QHBoxLayout()
        order_buttons.addWidget(self._up)
        order_buttons.addWidget(self._down)
        right.addLayout(order_buttons)
        shape_row = QHBoxLayout()
        shape_row.addWidget(self._shape_label)
        shape_row.addWidget(self._shape, 1)
        right.addLayout(shape_row)
        right_panel = QWidget()
        right_panel.setLayout(right)

        columns = QHBoxLayout()
        columns.addWidget(left_panel, 3)
        columns.addLayout(middle)
        columns.addWidget(right_panel, 2)

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
        self.resize(760, 480)
        self.retranslate_ui()

    def retranslate_ui(self) -> None:
        self.setWindowTitle(self.tr("Modifier le lien") if self._editing
                            else self.tr("Nouveau lien"))
        self._candidates_label.setText(self.tr("Cartes disponibles"))
        self._sequence_label.setText(self.tr("Cartes du lien, en ordre de lecture"))
        self._shape_label.setText(self.tr("Forme"))
        self._shape.setToolTip(
            self.tr("Colonnes × lignes. Les cartes remplissent le rectangle de "
                    "gauche à droite, puis rangée suivante."))
        self._search.setPlaceholderText(self.tr("Filtrer par nom ou dossier…"))
        self._add.setText(self.tr("Ajouter →"))
        self._remove.setText(self.tr("← Retirer"))
        self._up.setText(self.tr("Monter"))
        self._down.setText(self.tr("Descendre"))
        self._name_label.setText(self.tr("Nom (facultatif)"))
        self._ordered.setText(
            self.tr("Ordre imposé (sinon l'optimiseur peut retourner le bloc)")
        )

    # --- Cartes disponibles ----------------------------------------------

    def _icon(self, index: int):
        card = self._session.card_set[index]
        return numpy_to_pixmap(card.thumbnail).scaledToWidth(
            ICON_WIDTH, Qt.SmoothTransformation
        )

    def _label_for(self, index: int, with_folder: bool = True) -> str:
        card = self._session.card_set[index]
        # Le dossier lève l'ambiguïté entre deux cartes homonymes de séries
        # différentes ; dans la séquence, où les cartes sont déjà choisies, il ne
        # ferait que tronquer les noms.
        text = f"{card.name}  —  {self._session.folder_of(index)}" if with_folder \
            else card.name
        if self._session.is_excluded(index):
            # Un lien portant sur une carte retirée ne s'appliquera jamais : mieux
            # vaut le voir au moment de le composer qu'après une exécution entière.
            text += "  " + self.tr("(carte exclue)")
        return text

    def _chosen(self) -> list[int]:
        return [self._sequence.item(row).data(Qt.UserRole)
                for row in range(self._sequence.count())]

    def _fill_candidates(self) -> None:
        """Toutes les cartes non déjà retenues, filtrées par la recherche."""
        self._candidates.clear()
        if not self._session.card_set:
            return
        needle = self._search.text().strip().lower()
        chosen = set(self._chosen())
        for card in self._session.card_set:
            if card.index in chosen:
                continue
            label = self._label_for(card.index)
            if needle and needle not in label.lower():
                continue
            item = QListWidgetItem(self._icon(card.index), label)
            item.setData(Qt.UserRole, card.index)
            self._candidates.addItem(item)

    # --- Séquence ---------------------------------------------------------

    def _append_to_sequence(self, index: int) -> None:
        item = QListWidgetItem(self._icon(index),
                               self._label_for(index, with_folder=False))
        item.setData(Qt.UserRole, index)
        self._sequence.addItem(item)

    def _add_selected(self, *_) -> None:
        added = False
        for item in self._candidates.selectedItems():
            self._append_to_sequence(item.data(Qt.UserRole))
            added = True
        if added:
            # La dernière carte ajoutée devient la ligne courante : sans cela les
            # boutons d'ordre restent gris jusqu'à ce qu'on pense à cliquer une
            # ligne, et l'utilisateur croit ne pas pouvoir réordonner.
            self._sequence.setCurrentRow(self._sequence.count() - 1)
        self._fill_candidates()
        self._update_buttons()

    def _remove_current(self) -> None:
        row = self._sequence.currentRow()
        if row >= 0:
            self._sequence.takeItem(row)
            self._fill_candidates()
            self._update_buttons()

    def _move(self, delta: int) -> None:
        row = self._sequence.currentRow()
        target = row + delta
        if row < 0 or not 0 <= target < self._sequence.count():
            return
        item = self._sequence.takeItem(row)
        self._sequence.insertItem(target, item)
        self._sequence.setCurrentRow(target)

    def _update_buttons(self, *_) -> None:
        row = self._sequence.currentRow()
        count = self._sequence.count()
        self._remove.setEnabled(row >= 0)
        self._up.setEnabled(row > 0)
        self._down.setEnabled(0 <= row < count - 1)
        self._refresh_shapes(count)
        self._buttons.button(QDialogButtonBox.Ok).setEnabled(
            count >= 2 and self._shape.count() > 0)

    def _refresh_shapes(self, count: int) -> None:
        """N'offre que les formes que ce nombre de cartes remplit exactement.

        Cinq, sept et huit cartes n'en remplissent aucune : la liste est alors
        vide et le dialogue le dit, plutôt que de laisser valider un lien que
        `Link` refuserait par une exception.
        """
        possibles = shapes_for(count)
        offertes = tuple(tuple(self._shape.itemData(i))
                         for i in range(self._shape.count()))
        # La liste n'est reconstruite que si elle change : la vider ferait
        # perdre le choix de l'utilisateur à chaque frappe dans le nom.
        # ⚠️ Le message, lui, est posé dans tous les cas — le sauter avec la
        # reconstruction laissait « 5 cartes » sans explication, la liste étant
        # déjà vide au départ.
        if offertes != possibles:
            courante = self._shape.currentData()
            courante = tuple(courante) if courante else None
            self._shape.clear()
            for cols, rows in possibles:
                self._shape.addItem(f"{cols} × {rows}", (cols, rows))
            if courante in possibles:
                self._shape.setCurrentIndex(possibles.index(courante))
            elif possibles:
                self._shape.setCurrentIndex(0)
        self._shape.setEnabled(bool(possibles))
        if count >= 2 and not possibles:
            self._error.setText(
                self.tr("%n carte(s) ne remplissent aucun rectangle d'au plus "
                        "3 cases de côté. Les tailles possibles sont 2, 3, 4, 6 "
                        "et 9.", "", count))
        elif self._error.text():
            self._error.clear()

    def select_shape(self, shape: tuple[int, int]) -> bool:
        """Choisit cette forme si elle est offerte. Rend vrai si c'est fait.

        ⚠️ Pas `QComboBox.findData` : il compare des `QVariant` et ne retrouve
        pas un tuple Python, si bien qu'un lien vertical rouvert repartait en
        ligne — sans erreur, la forme changeant en silence.
        """
        for position in range(self._shape.count()):
            if tuple(self._shape.itemData(position)) == tuple(shape):
                self._shape.setCurrentIndex(position)
                return True
        return False

    # --- Validation -------------------------------------------------------

    def link(self) -> Link:
        return Link(cards=tuple(self._chosen()),
                    shape=self._shape.currentData() or (),
                    ordered=self._ordered.isChecked(),
                    enabled=self._editing.enabled if self._editing else True,
                    name=self._name.text().strip())

    def _try_accept(self) -> None:
        """N'accepte que si la bibliothèque veut bien du lien.

        Le conflit est affiché dans le dialogue plutôt que remonté en exception :
        l'utilisateur peut corriger sa séquence sans avoir tout à ressaisir.
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
