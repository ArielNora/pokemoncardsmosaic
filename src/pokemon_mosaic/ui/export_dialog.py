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
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
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

        self._full_resolution = QCheckBox()
        self._full_resolution.setChecked(True)
        self._full_resolution.stateChanged.connect(self._update_plan)

        # Écrite dans la session sur-le-champ : les aperçus de l'étape 2
        # calculent leur géométrie à cette résolution, et se tromperaient d'un
        # arrondi si le fichier partait à une autre.
        self._dpi = QSpinBox()
        self._dpi.setRange(50, 1200)
        self._dpi.setSingleStep(50)
        self._dpi.setValue(self._session.dpi)
        # Un préréglage écrit à la main peut porter une finesse hors bornes : le
        # champ l'a écrêtée, et la session doit apprendre ce qu'il a accepté.
        if self._dpi.value() != self._session.dpi:
            self._session.set_layout(dpi=self._dpi.value())
        self._dpi.valueChanged.connect(self._on_dpi_changed)

        self._quality = QSpinBox()
        self._quality.setRange(1, 100)
        self._quality.setValue(95)

        self._overlap = QDoubleSpinBox()
        self._overlap.setRange(0.0, 50.0)
        self._overlap.setDecimals(1)
        self._overlap.setSingleStep(1.0)
        self._overlap.setSuffix(" mm")
        self._overlap.valueChanged.connect(self._update_plan)

        self._crop_marks = QCheckBox()

        self._path = QLineEdit(self._default_path())
        self._path.textChanged.connect(self._update_plan)
        self._browse = QPushButton()
        self._browse.clicked.connect(lambda: self._pick_file())
        path_row = QHBoxLayout()
        path_row.addWidget(self._path, 1)
        path_row.addWidget(self._browse)

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
        self._dpi_row = QLabel()
        self._form.addRow(self._dpi_row, self._dpi)
        self._resolution_row = QLabel()
        self._form.addRow(self._resolution_row, self._full_resolution)
        self._quality_row = QLabel()
        self._form.addRow(self._quality_row, self._quality)
        self._overlap_row = QLabel()
        self._form.addRow(self._overlap_row, self._overlap)
        self._marks_row = QLabel()
        self._form.addRow(self._marks_row, self._crop_marks)
        self._file_row = QLabel()
        self._form.addRow(self._file_row, path_row)

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
        self._dpi_row.setText(self.tr("Finesse (DPI)"))
        self._dpi.setToolTip(
            self.tr("Combien de points par pouce l'imprimante recevra. Elle ne "
                    "change rien aux dimensions du poster, seulement au poids du "
                    "fichier et à la netteté.")
        )
        self._resolution_row.setText(self.tr("Résolution"))
        self._quality_row.setText(self.tr("Qualité JPEG"))
        self._overlap_row.setText(self.tr("Chevauchement"))
        self._marks_row.setText(self.tr("Repères de coupe"))
        self._file_row.setText(self.tr("Fichier"))
        self._browse.setText(self.tr("Parcourir…"))
        self._full_resolution.setText(
            self.tr("Pleine résolution (relit les images d'origine)")
        )
        self._crop_marks.setText(self.tr("Tracer les repères aux angles"))
        self._update_plan()

    # --- Réglages ---------------------------------------------------------

    def _default_path(self) -> str:
        folder = QStandardPaths.writableLocation(QStandardPaths.PicturesLocation)
        return os.path.join(folder or os.getcwd(), "poster.png")

    def _extension(self) -> str:
        return self._format.currentData()

    def _on_format_changed(self) -> None:
        extension = self._extension()
        is_jpeg = extension in (".jpg", ".jpeg")
        self._quality.setVisible(is_jpeg)
        self._quality_row.setVisible(is_jpeg)
        # L'extension suit le format choisi : laisser « poster.png » alors que
        # JPEG est sélectionné écrirait un PNG sans le dire.
        base = os.path.splitext(self._path.text())[0]
        if base:
            self._path.setText(base + extension)
        self._update_plan()

    def _on_dpi_changed(self, dpi: int) -> None:
        self._session.set_layout(dpi=dpi)
        self._update_plan()

    def _pick_file(self) -> None:
        name = self._format.currentText()
        extension = self._extension()
        chosen, _ = QFileDialog.getSaveFileName(
            self, self.tr("Enregistrer le poster"), self._path.text(),
            f"{name} (*{extension})"
        )
        if chosen:
            base = os.path.splitext(chosen)[0]
            self._path.setText(base + extension)

    def settings(self) -> PosterSettings:
        session = self._session
        return PosterSettings(
            paper=session.paper,
            # ⚠️ **Les dimensions aussi.** Une feuille hors catalogue n'a pas de
            # nom : le seul `paper` aurait fait échouer la traduction, ou pire,
            # imprimé un A2 à la place de ce que l'écran montrait.
            paper_size_mm=session.paper_size_mm,
            landscape=session.landscape,
            dpi=self._dpi.value(),
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
            overlap_mm=self._overlap.value(),
            crop_marks=self._crop_marks.isChecked(),
            # ⚠️ **Les trois couleurs, et pas la seule des cases vides.** Le
            # fond et l'écart entre les cartes se règlent à l'étape d'export :
            # oubliés ici, le fichier serait blanc là où l'écran montrait une
            # couleur.
            background=session.background_colour,
            gap_colour=session.gap_colour,
            empty_colour=session.empty_colour,
            jpeg_quality=self._quality.value(),
        )

    def path(self) -> str:
        return self._path.text().strip()

    def full_resolution(self) -> bool:
        return self._full_resolution.isChecked()

    # --- Aperçu chiffré ---------------------------------------------------

    def _update_plan(self, *_) -> None:
        session = self._session
        orientation = (self.tr("paysage") if session.landscape
                       else self.tr("portrait"))
        panels = self.tr("%n panneau(x)", "", session.panel_count())
        largeur, hauteur = session.paper_mm()
        feuille = session.paper or f"{largeur / 10:.1f} × {hauteur / 10:.1f} cm"
        self._layout_recap.setText(f"{feuille} {orientation} : {panels}")
        self._overlap.setEnabled(session.panel_count() > 1)

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

        Avec plusieurs panneaux, choisir « poster.png » écrit en réalité
        « poster_1of2.png » et « poster_2of2.png » : aucun sélecteur de fichier
        ne prévient de leur écrasement.
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
        path = self.path()
        if not path:
            self._warnings.setText(self.tr("Choisissez un fichier de destination."))
            return
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
