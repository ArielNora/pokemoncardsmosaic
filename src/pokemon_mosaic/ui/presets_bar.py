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

from ..presets import (
    delete_preset,
    existing_name,
    list_presets,
    load_preset,
    replace_preset,
    save_preset,
)
from .session import Session


class PresetsBar(QWidget):
    """Liste des préréglages enregistrés, et les trois gestes qui vont avec.

    Elle porte aussi l'accès à la bibliothèque des agencements : comme un
    préréglage, un agencement se choisit dès le début du parcours.
    """

    status_message = Signal(str)
    # La fenêtre ouvre la bibliothèque : c'est elle qui sait où elle est rangée.
    arrangements_requested = Signal()

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
        self._arrangements = QPushButton()
        self._arrangements.clicked.connect(self.arrangements_requested.emit)
        # Vrai aux deux premières étapes seulement, voir `set_arrangements_enabled`.
        self._arrangements_allowed = True

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._label)
        layout.addWidget(self._names)
        layout.addWidget(self._load)
        layout.addWidget(self._delete)
        layout.addStretch(1)
        layout.addWidget(self._arrangements)
        layout.addWidget(self._save)
        self.retranslate_ui()

    def set_arrangements_enabled(self, allowed: bool) -> None:
        """Autorise la bibliothèque aux deux premières étapes, pas au-delà.

        ⚠️ **Grisé, et non masqué.** Aux étapes 3 et 4, choisir un agencement ne
        doit rien remplacer : l'infobulle renvoie au bouton sous les cases, qui
        ajoute seulement un agencement aux cases. Masqué, le bouton aurait
        disparu sans dire où le retrouver.
        """
        self._arrangements_allowed = bool(allowed)
        self._update_arrangements_button()

    def retranslate_ui(self) -> None:
        self._label.setText(self.tr("Préréglage"))
        self._load.setText(self.tr("Charger"))
        self._save.setText(self.tr("Enregistrer…"))
        self._delete.setText(self.tr("Supprimer"))
        self._save.setToolTip(
            self.tr("Enregistre la sélection, les liens actifs, la grille "
                    "et les réglages sous un nom.")
        )
        self._arrangements.setText(self.tr("Tous les agencements…"))
        self._update_buttons()
        self._update_arrangements_button()

    def _update_arrangements_button(self) -> None:
        self._arrangements.setEnabled(self._arrangements_allowed)
        self._arrangements.setToolTip(
            self.tr("Parcourir les agencements enregistrés.")
            if self._arrangements_allowed else
            self.tr("À cette étape, ajoutez un agencement aux cases avec le "
                    "bouton « Tous les agencements… » placé sous les cases."))

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
        # ⚠️ **L'homonyme se cherche casse et accents confondus** : « essai »
        # écrasait « Essai » sans rien demander, le disque les confondant.
        existant = existing_name(self._directory, name)
        if existant is not None and not self._confirm_overwrite(existant):
            return

        try:
            preset = self._session.to_preset(name)
            if existant is None:
                save_preset(self._directory, preset)
            else:
                replace_preset(self._directory, preset, existant)
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
