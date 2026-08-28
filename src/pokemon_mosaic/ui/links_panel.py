"""Bibliothèque de liens : la liste, et de quoi la modifier.

Un lien garde des cartes côte à côte horizontalement. La case à cocher l'active
ou le désactive sans le supprimer — un lien est un travail durable, on ne le perd
pas parce qu'on essaie une mise en page sans lui. Voir SPEC.md §3.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..links import Link
from .link_dialog import LinkDialog
from .session import Session


class LinksPanel(QWidget):
    """Liste des liens, avec création, modification et activation."""

    def __init__(self, session: Session, parent=None):
        super().__init__(parent)
        self._session = session
        # Vrai pendant qu'on remplit la liste : les `setCheckState` du remplissage
        # émettent `itemChanged` comme les clics de l'utilisateur, et rappelleraient
        # la session en boucle.
        self._filling = False
        self._build()
        session.links_changed.connect(self.refresh)
        session.selection_changed.connect(self.refresh)
        session.loading_started.connect(self.refresh)
        self.refresh()

    # --- Construction -----------------------------------------------------

    def _build(self) -> None:
        self._title = QLabel()
        self._list = QListWidget()
        self._list.itemChanged.connect(self._on_item_changed)
        self._list.itemDoubleClicked.connect(lambda _: self._edit())
        self._list.currentRowChanged.connect(self._update_buttons)

        self._new = QPushButton()
        self._edit_button = QPushButton()
        self._delete = QPushButton()
        self._new.clicked.connect(lambda: self._create())
        self._edit_button.clicked.connect(lambda: self._edit())
        self._delete.clicked.connect(lambda: self._remove())

        self._warning = QLabel()
        self._warning.setWordWrap(True)
        self._warning.setStyleSheet("color: #a60;")
        self._warning.hide()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._title)
        layout.addWidget(self._list, 1)
        layout.addWidget(self._warning)
        buttons = QHBoxLayout()
        buttons.addWidget(self._new)
        buttons.addWidget(self._edit_button)
        buttons.addWidget(self._delete)
        layout.addLayout(buttons)
        self.retranslate_ui()

    def retranslate_ui(self) -> None:
        self._title.setText(self.tr("Liens"))
        self._new.setText(self.tr("Nouveau…"))
        self._edit_button.setText(self.tr("Modifier…"))
        self._delete.setText(self.tr("Supprimer"))
        # Les libellés des liens contiennent des mots traduits (« exclue »…) :
        # ils doivent être recomposés au changement de langue.
        self.refresh()

    # --- Affichage --------------------------------------------------------

    def _label_for(self, link: Link) -> str:
        card_set = self._session.card_set
        names = []
        for index in link.cards:
            names.append(card_set[index].name if card_set else str(index))
        # La flèche dit le sens : imposé à sens unique, libre à double sens.
        # ⚠️ Elle ne convient qu'à une **barre**. Sur un 2×2, « A → B → C → D »
        # décrirait une chaîne là où les cartes forment un carré : au-delà d'une
        # rangée ou d'une colonne, seul le point sépare, et c'est la forme
        # annoncée qui dit la disposition.
        barre = link.cols == 1 or link.rows == 1
        separateur = (" → " if link.ordered else " ↔ ") if barre else " · "
        text = f"{link.cols} × {link.rows}  " + separateur.join(names)
        if link.name:
            text = f"{link.name} : {text}"
        return text

    def refresh(self) -> None:
        current = self._list.currentRow()
        self._filling = True
        self._list.clear()
        unusable = set(self._session.unusable_links())
        for link in self._session.links:
            item = QListWidgetItem(self._label_for(link))
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if link.enabled else Qt.Unchecked)
            if link in unusable:
                item.setToolTip(
                    self.tr("Une carte de ce lien est exclue : il ne s'appliquera pas.")
                )
            self._list.addItem(item)
        self._filling = False

        if 0 <= current < self._list.count():
            self._list.setCurrentRow(current)
        self._show_warning(len(unusable))
        self._update_buttons()

    def _show_warning(self, count: int) -> None:
        if count:
            self._warning.setText(
                self.tr("%n lien(s) actif(s) sur une carte exclue : "
                        "ignoré(s) au calcul.", "", count)
            )
            self._warning.show()
        else:
            self._warning.hide()

    def _update_buttons(self, *_) -> None:
        has_selection = self._list.currentRow() >= 0
        self._edit_button.setEnabled(has_selection)
        self._delete.setEnabled(has_selection)
        self._new.setEnabled(self._session.total_cards >= 2)

    # --- Actions ----------------------------------------------------------

    def _link_at(self, row: int) -> Link | None:
        links = self._session.links.links
        return links[row] if 0 <= row < len(links) else None

    def _current_link(self) -> Link | None:
        return self._link_at(self._list.currentRow())

    def _on_item_changed(self, item: QListWidgetItem) -> None:
        if self._filling:
            return
        link = self._link_at(self._list.row(item))
        if link is None:
            return
        enabled = item.checkState() == Qt.Checked
        try:
            self._session.set_link_enabled(link, enabled)
        except ValueError:
            # Réactiver un lien dont les cartes ont été reprises par un autre est
            # refusé par la bibliothèque : on remet la case comme elle était.
            self.refresh()

    def _open(self, link: Link | None) -> Link | None:
        """Ouvre le dialogue et renvoie le lien composé, ou None si annulé.

        Le dialogue est détruit explicitement : parenté au panneau, Qt le garde
        sinon en vie après sa fermeture, avec une vignette par carte à bord —
        environ 1,6 Mo par ouverture sur un jeu de 280 cartes.
        """
        dialog = LinkDialog(self._session, link=link, parent=self)
        try:
            return dialog.link() if dialog.exec() else None
        finally:
            dialog.deleteLater()

    def _create(self) -> None:
        composed = self._open(None)
        if composed is not None:
            self._session.add_link(composed)

    def _edit(self) -> None:
        link = self._current_link()
        if link is None:
            return
        composed = self._open(link)
        if composed is not None:
            self._session.replace_link(link, composed)

    def _remove(self) -> None:
        link = self._current_link()
        if link is not None:
            self._session.remove_link(link)
