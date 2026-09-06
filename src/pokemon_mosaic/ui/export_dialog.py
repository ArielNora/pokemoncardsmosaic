"""Choix du format et de la destination avant d'écrire le poster.

Le format d'impression, l'orientation et le nombre de panneaux viennent de
l'étape 2 : ils sont rappelés ici sans être modifiables, pour qu'on sache ce
qu'on exporte sans avoir à revenir en arrière. Ne restent réglables que les
décisions propres à l'écriture du fichier.

⚠️ **La finesse en fait partie.** Elle était demandée à l'étape 2, avant que la
mosaïque n'existe : elle n'y changeait rien de visible, tout s'y mesure en
millimètres, et il fallait deviner le poids d'un fichier qu'on n'avait pas
encore décrit. Elle se choisit ici, à côté du nombre de mégapixels qu'elle
donne. Le choix est écrit dans la session : les aperçus arrondissent leurs
pixels comme l'export, et un préréglage le retrouve.
"""

import os

from PySide6.QtCore import QStandardPaths
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from ..export import PosterSettings, panel_paths, plan_poster
from . import theme
from .session import Session

# Extension par format, dans l'ordre d'affichage.
FORMATS = (("PNG", ".png"), ("JPEG", ".jpg"), ("PDF", ".pdf"))


# Le nom de base des fichiers, quand l'utilisateur n'en donne pas.
DEFAULT_BASENAME = "poster"


def _default_folder() -> str:
    return QStandardPaths.writableLocation(
        QStandardPaths.PicturesLocation) or os.getcwd()


class ExportDialog(QDialog):
    """Recueille tout ce qu'il faut pour écrire le poster."""

    def __init__(self, session: Session, grid, cards, parent=None):
        super().__init__(parent)
        self._session = session
        self._grid = grid
        self._cards = cards
        # None tant que les réglages décrivent un poster impossible : c'est ce
        # qui interdit de valider un export dont l'échec est déjà connu.
        self._plan = None
        self._build()

    def _build(self) -> None:
        self._format = QComboBox()
        for name, extension in FORMATS:
            self._format.addItem(name, extension)
        self._format.currentIndexChanged.connect(self._on_format_changed)

        self._quality = QSpinBox()
        self._quality.setRange(1, 100)
        self._quality.setValue(95)

        # ⚠️ **Le dossier et le nom, séparés.** Un seul champ de chemin
        # mélangeait les deux, et l'extension y menait sa propre vie : on
        # pouvait laisser « .png » en ayant choisi JPEG. Le nom est celui de
        # base, les feuilles y ajoutant « page1 », « page2 ».
        self._folder = QLineEdit(_default_folder())
        self._folder.textChanged.connect(self._update_plan)
        self._browse = QPushButton()
        self._browse.clicked.connect(self._pick_folder)
        folder_row = QHBoxLayout()
        folder_row.addWidget(self._folder, 1)
        folder_row.addWidget(self._browse)

        self._basename = QLineEdit(DEFAULT_BASENAME)
        self._basename.textChanged.connect(self._update_plan)

        self._layout_recap = QLabel()
        self._plan_label = QLabel()
        self._plan_label.setWordWrap(True)
        self._warnings = QLabel()
        self._warnings.setWordWrap(True)
        theme.mark(self._warnings, "warning")
        self._files = QLabel()
        self._files.setWordWrap(True)

        self._form = QFormLayout()
        self._layout_row = QLabel()
        self._form.addRow(self._layout_row, self._layout_recap)
        self._format_row = QLabel()
        self._form.addRow(self._format_row, self._format)
        self._quality_row = QLabel()
        self._form.addRow(self._quality_row, self._quality)
        self._folder_row = QLabel()
        self._form.addRow(self._folder_row, folder_row)
        self._name_row = QLabel()
        self._form.addRow(self._name_row, self._basename)

        self._buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        self._buttons.accepted.connect(self._try_accept)
        self._buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(self._form)
        layout.addWidget(self._plan_label)
        layout.addWidget(self._files)
        layout.addWidget(self._warnings)
        layout.addWidget(self._buttons)
        self.resize(560, 360)
        self.retranslate_ui()
        self._on_format_changed()

    def retranslate_ui(self) -> None:
        self.setWindowTitle(self.tr("Exporter le poster"))
        self._layout_row.setText(self.tr("Mise en page"))
        self._format_row.setText(self.tr("Format"))
        self._quality_row.setText(self.tr("Qualité JPEG"))
        self._folder_row.setText(self.tr("Dossier"))
        self._name_row.setText(self.tr("Nom des fichiers"))
        self._basename.setToolTip(
            self.tr("Le nom de base. Une feuille seule le porte tel quel ; "
                    "plusieurs y ajoutent « page1 », « page2 »."))
        self._browse.setText(self.tr("Parcourir…"))
        self._update_plan()

    # --- Réglages ---------------------------------------------------------

    def _extension(self) -> str:
        return self._format.currentData()

    def _on_format_changed(self) -> None:
        extension = self._extension()
        is_jpeg = extension in (".jpg", ".jpeg")
        self._quality.setVisible(is_jpeg)
        self._quality_row.setVisible(is_jpeg)
        self._update_plan()

    def _pick_folder(self) -> None:
        chosen = QFileDialog.getExistingDirectory(
            self, self.tr("Où écrire le poster"), self._folder.text())
        if chosen:
            self._folder.setText(chosen)

    def settings(self) -> PosterSettings:
        session = self._session
        return PosterSettings(
            paper=session.paper,
            # ⚠️ **Les dimensions aussi.** Une feuille hors catalogue n'a pas de
            # nom : le seul `paper` aurait fait échouer la traduction, ou pire,
            # imprimé un A2 à la place de ce que l'écran montrait.
            paper_size_mm=session.paper_size_mm,
            landscape=session.landscape,
            dpi=session.dpi,
            panels=session.panels,
            panel_rows=session.panel_rows,
            # ⚠️ Les déplacements aussi : sans eux, le fichier écrit remettrait
            # chaque bout de grille à sa place par défaut, et n'aurait plus rien
            # à voir avec ce que l'écran montrait.
            panel_offsets=dict(session.panel_offsets),
            # ⚠️ **La taille de carte et l'écart aussi.** Oubliés ici, l'export
            # repassait en taille automatique et sans écart : le fichier écrit
            # n'avait rien à voir avec l'aperçu que l'utilisateur venait de
            # régler.
            card_width_mm=session.card_width_mm,
            card_gap_mm=session.card_gap_mm,
            # ⚠️ Le chevauchement et les repères viennent de la session : ils
            # se règlent à l'onglet « Coupe », et non plus ici.
            overlap_mm=session.overlap_mm,
            crop_marks=session.crop_marks,
            # ⚠️ **Les trois couleurs, et pas la seule des cases vides.** Le
            # fond et l'écart entre les cartes se règlent à l'étape d'export :
            # oubliés ici, le fichier serait blanc là où l'écran montrait une
            # couleur.
            background=session.background_colour,
            gap_colour=session.gap_colour,
            empty_colour=session.empty_colour,
            # Le mode caméléon aussi : oublié, le fichier écrit reprenait des
            # aplats là où l'écran montrait des dégradés.
            chameleon_gaps=session.chameleon_gaps,
            chameleon_border=session.chameleon_border,
            jpeg_quality=self._quality.value(),
        )

    def path(self) -> str:
        """Le chemin du premier fichier : dossier, nom de base, extension."""
        nom = self._basename.text().strip() or DEFAULT_BASENAME
        return os.path.join(self._folder.text().strip(),
                            nom + self._extension())

    def full_resolution(self) -> bool:
        return self._session.full_resolution

    # --- Aperçu chiffré ---------------------------------------------------

    def _update_plan(self, *_) -> None:
        session = self._session
        orientation = (self.tr("paysage") if session.landscape
                       else self.tr("portrait"))
        panels = self.tr("%n panneau(x)", "", session.panel_count())
        largeur, hauteur = session.paper_mm()
        feuille = session.paper or f"{largeur / 10:.1f} × {hauteur / 10:.1f} cm"
        self._layout_recap.setText(f"{feuille} {orientation} : {panels}")

        try:
            plan = self._plan = plan_poster(self._grid, self._cards, self.settings())
        except ValueError as error:
            self._plan = None
            self._plan_label.setText(str(error))
            self._files.setText("")
            self._warnings.setText("")
            self._buttons.button(QDialogButtonBox.Ok).setEnabled(False)
            return
        self._buttons.button(QDialogButtonBox.Ok).setEnabled(True)

        panel_w, panel_h = plan.settings.paper_px
        megapixels = panel_w * panel_h * plan.settings.panel_count / 1e6
        source = (self.tr("images d'origine") if self.full_resolution()
                  else self.tr("vignettes, rendu rapide et flou à l'impression"))
        self._plan_label.setText(
            self.tr("%1 × %2 cartes de %3 × %4 px : %5 × %6 px par panneau, "
                    "%7 Mpx au total (%8)")
            .replace("%1", str(plan.cols)).replace("%2", str(plan.rows))
            .replace("%3", str(plan.card_px[0])).replace("%4", str(plan.card_px[1]))
            .replace("%5", str(panel_w)).replace("%6", str(panel_h))
            .replace("%7", f"{megapixels:.0f}")
            .replace("%8", source)
        )
        self._warnings.setText("\n".join(plan.warnings))
        self._show_targets()

    def _show_targets(self) -> None:
        """Nomme les fichiers qui seront écrits, et signale ceux qui existent.

        Avec plusieurs feuilles, le nom « poster » écrit en réalité
        « poster_page1sur2.png » et « poster_page2sur2.png » : rien d'autre ne
        prévient de leur écrasement.
        """
        try:
            targets = panel_paths(self.path(), self._session.panels,
                                  self._session.panel_rows)
        except ValueError:
            self._files.setText("")
            return
        existing = [t for t in targets if os.path.exists(t)]
        names = ", ".join(os.path.basename(t) for t in targets)
        text = self.tr("Fichier(s) : %1").replace("%1", names)
        if existing:
            text += ", " + self.tr("%n fichier(s) seront écrasés", "",
                                      len(existing))
        self._files.setText(text)

    # --- Validation -------------------------------------------------------

    def _try_accept(self) -> None:
        if not self._folder.text().strip():
            self._warnings.setText(self.tr("Choisissez un dossier de destination."))
            return
        path = self.path()
        if self._plan is None:
            # Le plan est déjà affiché en clair : accepter lancerait un fil de
            # fond pour qu'il échoue aussitôt sur la même erreur.
            return
        try:
            panel_paths(path, self._session.panels, self._session.panel_rows)
        except ValueError as error:
            self._warnings.setText(str(error))
            return
        self.accept()
