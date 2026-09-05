"""Barre des préréglages : enregistrer, recharger, supprimer une configuration.

Elle vit dans la fenêtre et non dans une étape : un préréglage couvre la
sélection, les liens actifs, la grille et les réglages, soit les trois premières
étapes à la fois. Voir SPEC.md §3.
"""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QWidget,
)

from ..presets import delete_preset, list_presets, load_preset, save_preset
from .session import Session


class PresetsBar(QWidget):
    """Liste des préréglages enregistrés, et les trois gestes qui vont avec."""

    status_message = Signal(str)

    def __init__(self, session: Session, directory: str, parent=None):
        super().__init__(parent)
        self._session = session
        self._directory = directory
        self._build()
        # ⚠️ Sans cela « Enregistrer… » reste grisé après le chargement : il ne
        # se réévaluait qu'au changement de préréglage dans la liste, geste
        # impossible tant qu'on n'en a aucun : le tout premier préréglage était
        # donc définitivement impossible à créer. Même défaut que « Suivant »,
        # corrigé au même endroit dans `main_window`.
        session.cards_loaded.connect(self._update_buttons)
        session.cards_added.connect(self._update_buttons)
        self.refresh()

    def _build(self) -> None:
        self._label = QLabel()
        self._names = QComboBox()
        self._names.setMinimumWidth(200)
        self._load = QPushButton()
        self._save = QPushButton()
        self._delete = QPushButton()
        self._load.clicked.connect(lambda: self.load_selected())
        self._save.clicked.connect(lambda: self.save_current())
        self._delete.clicked.connect(lambda: self.delete_selected())
        self._names.currentIndexChanged.connect(self._update_buttons)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._label)
        layout.addWidget(self._names)
        layout.addWidget(self._load)
        layout.addWidget(self._delete)
        layout.addStretch(1)
        layout.addWidget(self._save)
        self.retranslate_ui()

    def retranslate_ui(self) -> None:
        self._label.setText(self.tr("Préréglage"))
        self._load.setText(self.tr("Charger"))
        self._save.setText(self.tr("Enregistrer…"))
        self._delete.setText(self.tr("Supprimer"))
        self._save.setToolTip(
            self.tr("Enregistre la sélection, les liens actifs, la grille "
                    "et les réglages sous un nom.")
        )
        self._update_buttons()

    # --- Liste ------------------------------------------------------------

    def refresh(self, keep: str | None = None) -> None:
        current = keep if keep is not None else self._names.currentText()
        self._names.blockSignals(True)
        self._names.clear()
        self._names.addItems(list_presets(self._directory))
        position = self._names.findText(current)
        if position >= 0:
            self._names.setCurrentIndex(position)
        self._names.blockSignals(False)
        self._update_buttons()

    def _update_buttons(self, *_) -> None:
        has_selection = self._names.currentIndex() >= 0
        self._load.setEnabled(has_selection)
        self._delete.setEnabled(has_selection)
        self._save.setEnabled(self._session.card_set is not None)

    # --- Actions ----------------------------------------------------------

    def save_current(self, name: str | None = None) -> None:
        """Enregistre la configuration courante. `name` non nul court-circuite
        la saisie, ce qui rend l'action testable sans dialogue modal."""
        if name is None:
            name, accepted = QInputDialog.getText(
                self, self.tr("Enregistrer le préréglage"), self.tr("Nom"),
                text=self._names.currentText()
            )
            if not accepted:
                return
        name = name.strip()
        if not name:
            return
        if name in list_presets(self._directory) and not self._confirm_overwrite(name):
            return

        try:
            save_preset(self._directory, self._session.to_preset(name))
        except (OSError, ValueError) as error:
            self.status_message.emit(
                self.tr("Échec de l'enregistrement : %1").replace("%1", str(error))
            )
            return
        self.refresh(keep=name)
        self.status_message.emit(
            self.tr("Préréglage « %1 » enregistré.").replace("%1", name)
        )

    def _confirm_overwrite(self, name: str) -> bool:
        answer = QMessageBox.question(
            self, self.tr("Remplacer le préréglage"),
            self.tr("« %1 » existe déjà. Le remplacer ?").replace("%1", name),
        )
        return answer == QMessageBox.Yes

    def load_selected(self) -> None:
        name = self._names.currentText()
        if not name:
            return
        try:
            preset = load_preset(self._directory, name)
        except (OSError, ValueError) as error:
            self.status_message.emit(
                self.tr("Préréglage illisible : %1").replace("%1", str(error))
            )
            return

        missing = self._session.apply_preset(preset)
        if missing:
            # On applique quand même : un préréglage doit survivre à la
            # disparition d'une carte, et le dire vaut mieux que le taire.
            self.status_message.emit(
                self.tr("Préréglage « %1 » chargé : %n carte(s) introuvable(s).",
                        "", len(missing)).replace("%1", name)
            )
        else:
            self.status_message.emit(
                self.tr("Préréglage « %1 » chargé.").replace("%1", name)
            )

    def delete_selected(self) -> None:
        name = self._names.currentText()
        if not name:
            return
        answer = QMessageBox.question(
            self, self.tr("Supprimer le préréglage"),
            self.tr("Supprimer « %1 » ? La bibliothèque de liens n'est pas "
                    "touchée.").replace("%1", name),
        )
        if answer != QMessageBox.Yes:
            return
        try:
            delete_preset(self._directory, name)
        except OSError as error:
            self.status_message.emit(
                self.tr("Échec de la suppression : %1").replace("%1", str(error))
            )
            return
        self.refresh(keep="")
        self.status_message.emit(
            self.tr("Préréglage « %1 » supprimé.").replace("%1", name)
        )
