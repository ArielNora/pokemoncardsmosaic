"""Les onglets de l'algorithme, dans l'étape des paramètres.

L'algorithme avait son écran à lui, entre la mise en page et l'exécution. Il
n'avait pourtant rien de plus à décider : ce sont des **paramètres**, comme le
papier et la grille, et les séparer obligeait à traverser une étape entière pour
revenir changer une durée.

Deux onglets, et une division claire : ce qu'on **voit** d'un côté — l'épaisseur
des bandes de bord se montre —, ce qu'on ne peut qu'**expliquer** de l'autre.
Aucun de ces réglages ne bloque quoi que ce soit : ils ont tous une valeur qui
marche, et l'utilisateur n'a pas à y toucher pour lancer un calcul.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .big_spin import BigFloatSpin
from .estimates import (
    estimated_gain,
    estimated_seconds,
    estimated_snapshots,
    format_duration,
)
from .layout_tabs import STATUS_BOOST, LayoutTab
from .session import Session
from .strip_preview import StripPreview

# En deçà, la timeline offrira trop peu d'états pour être navigable.
USEFUL_SNAPSHOTS = 10
# Ce qu'un intitulé de réglage gagne sur la police de l'interface, et le retrait
# de son explication. Le paragraphe se lit sous son titre, pas à côté.
ENTRY_BOOST = 1
ENTRY_INDENT = 14
# Hauteur maximale de l'aperçu des bandes.
PREVIEW_HEIGHT = 300


class SearchTab(LayoutTab):
    """L'épaisseur des bandes de bord, et ce qu'elle change.

    Seule de tous les réglages de l'algorithme à se **voir** : la bande mesurée
    se dessine sur une carte, et une petite grille d'essai montre ce que
    l'appariement donne à cette épaisseur. Les autres n'ont rien à montrer —
    on ne dessine pas un nombre d'itérations.
    """

    def __init__(self, session: Session, parent=None):
        super().__init__(parent)
        self._session = session
        self._updating = False
        self._build()
        session.algorithm_changed.connect(self.refresh)
        session.cards_loaded.connect(self.refresh)

    def title(self) -> str:
        return self.tr("Recherche")

    def _build(self) -> None:
        self._strip = BigFloatSpin(0.01, 0.50, step=0.05, decimals=2)
        self._strip.setFixedWidth(150)
        self._strip.value_changed.connect(self._on_form_changed)

        self._hint = QLabel()
        self._hint.setWordWrap(True)
        self._hint.setAlignment(Qt.AlignTop)

        haut = QHBoxLayout()
        haut.setSpacing(24)
        haut.addWidget(self._strip)
        haut.addWidget(self._hint, 1)
        bandeau = QWidget()
        bandeau.setLayout(haut)

        self._preview = StripPreview(self._session)
        # ⚠️ **Bornée en hauteur.** Laissée libre, une carte d'essai occupait
        # tout le panneau : on ne juge pas une bande de bord à sa taille, et la
        # phrase qui l'explique se retrouvait rejetée en bas de l'écran.
        self._preview.setMaximumHeight(PREVIEW_HEIGHT)

        self._status = QLabel()
        self._status.setWordWrap(True)
        etat = self._status.font()
        etat.setPointSize(etat.pointSize() + STATUS_BOOST)
        self._status.setFont(etat)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.addWidget(bandeau)
        layout.addWidget(self._preview)
        layout.addWidget(self._status)
        layout.addStretch(1)
        self.retranslate_ui()

    def retranslate_ui(self) -> None:
        self._strip.setTitle(self.tr("Épaisseur"))
        self._hint.setText(
            self.tr("C'est la part de chaque carte que l'assemblage regarde : "
                    "une bande le long de ses quatre bords, dont il compare la "
                    "couleur moyenne à celle de sa voisine. Fine, elle ne voit "
                    "que l'extrême bord et laisse les motifs se contredire juste "
                    "derrière ; large, elle mélange le bord au centre de "
                    "l'illustration et les raccords se relâchent.")
        )
        self._status.setText(
            self.tr("À gauche, la zone mesurée sur une carte. À droite, une "
                    "petite grille d'essai réoptimisée à cette épaisseur.")
        )
        self.refresh()

    def _on_form_changed(self, *_) -> None:
        if not self._updating:
            self._session.set_algorithm(strip_size=self._strip.value())

    def refresh(self) -> None:
        self._updating = True
        self._strip.setValue(self._session.strip_size)
        self._updating = False
        # ⚠️ Le champ a pu écrêter une valeur venue d'un préréglage écrit à la
        # main : on renvoie à la session ce qu'il a réellement accepté.
        if self._strip.value() != self._session.strip_size:
            self._session.set_algorithm(strip_size=self._strip.value())
        self.state_changed.emit()


class AdvancedTab(LayoutTab):
    """Les réglages qu'on ne peut pas montrer, chacun sous son explication.

    ⚠️ **Le texte fait partie du réglage.** « Tolérance d'acceptation : 0,30 »
    ne dit rien à personne — pas même à qui a écrit le programme, six mois
    après. Chaque champ est donc précédé de ce qu'il est, de ce à quoi il sert
    et de ce qu'il change, chiffres mesurés à l'appui.
    """

    def __init__(self, session: Session, parent=None):
        super().__init__(parent)
        self._session = session
        self._updating = False
        self._labels: dict[str, QLabel] = {}
        self._notes: dict[str, QLabel] = {}
        self._build()
        session.algorithm_changed.connect(self.refresh)
        session.cards_loaded.connect(self.refresh)

    def title(self) -> str:
        return self.tr("Paramètres avancés")

    # --- Construction -----------------------------------------------------

    def _build(self) -> None:
        self._iterations = QSpinBox()
        self._iterations.setRange(1000, 50_000_000)
        self._iterations.setSingleStep(50_000)
        self._iterations.setGroupSeparatorShown(True)
        self._snapshot_every = QSpinBox()
        self._snapshot_every.setRange(1, 1000)
        self._algorithm = QComboBox()
        self._algorithm.addItem("", True)      # recuit
        self._algorithm.addItem("", False)     # descente stricte
        self._acceptance = QDoubleSpinBox()
        self._acceptance.setRange(0.01, 0.99)
        self._acceptance.setSingleStep(0.05)
        self._stop_on_stagnation = QCheckBox()
        self._stagnation = QSpinBox()
        self._stagnation.setRange(1000, 10_000_000)
        self._stagnation.setSingleStep(10_000)
        self._stagnation.setGroupSeparatorShown(True)
        self._stop_on_time = QCheckBox()
        self._time_budget = QDoubleSpinBox()
        self._time_budget.setRange(1.0, 3600.0)
        self._time_budget.setSuffix(" s")
        self._stop_on_score = QCheckBox()
        self._target_score = QDoubleSpinBox()
        self._target_score.setRange(0.0, 10_000_000.0)
        self._target_score.setDecimals(0)
        for champ in (self._iterations, self._snapshot_every, self._stagnation,
                      self._time_budget, self._acceptance, self._target_score):
            champ.setMinimumWidth(210)

        contenu = QWidget()
        colonne = QVBoxLayout(contenu)
        colonne.setContentsMargins(4, 4, 12, 4)
        colonne.setSpacing(4)
        self._add_entry(colonne, "iterations", self._iterations)
        self._add_entry(colonne, "algorithm", self._algorithm)
        self._add_entry(colonne, "acceptance", self._acceptance)
        self._add_entry(colonne, "stagnation", self._stagnation,
                        self._stop_on_stagnation)
        self._add_entry(colonne, "time", self._time_budget, self._stop_on_time)
        self._add_entry(colonne, "score", self._target_score,
                        self._stop_on_score)
        self._add_entry(colonne, "snapshot_every", self._snapshot_every)
        colonne.addStretch(1)

        # ⚠️ **Défilante.** Sept réglages et leurs paragraphes ne tiennent sur
        # aucun écran : sans cela, les derniers seraient hors du cadre, et rien
        # ne dirait qu'ils existent.
        self._scroll = QScrollArea()
        self._scroll.setWidget(contenu)
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QScrollArea.NoFrame)

        self._projection = QLabel()
        self._projection.setWordWrap(True)
        etat = self._projection.font()
        etat.setPointSize(etat.pointSize() + STATUS_BOOST)
        self._projection.setFont(etat)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.addWidget(self._scroll, 1)
        layout.addWidget(self._projection)
        self._connect_all()
        self.retranslate_ui()

    def _add_entry(self, colonne: QVBoxLayout, key: str, champ: QWidget,
                   bascule: QCheckBox | None = None) -> None:
        """Un réglage : son intitulé, son explication, puis le champ.

        L'explication vient **avant** le champ. Après, elle se lit comme une
        note de bas de page qu'on saute ; avant, elle est la question à laquelle
        le champ répond.
        """
        titre = QLabel()
        police = titre.font()
        police.setBold(True)
        police.setPointSize(police.pointSize() + ENTRY_BOOST)
        titre.setFont(police)
        self._labels[key] = titre

        note = QLabel()
        note.setWordWrap(True)
        note.setContentsMargins(ENTRY_INDENT, 0, 0, 0)
        # ⚠️ Le texte enrichi n'est pas une coquetterie : sans lui, les balises
        # de mise en gras s'afficheraient telles quelles au milieu des phrases.
        note.setTextFormat(Qt.RichText)
        self._notes[key] = note

        # ⚠️ **Un champ ne s'étire pas.** Laissé seul dans sa ligne, il prenait
        # toute la largeur du panneau : un compteur de mille pixels de large ne
        # se lit pas mieux, et il éloigne ses flèches de son nombre.
        ligne = QHBoxLayout()
        ligne.setContentsMargins(ENTRY_INDENT, 2, 0, 10)
        if bascule is not None:
            ligne.addWidget(bascule)
        ligne.addWidget(champ)
        ligne.addStretch(1)

        colonne.addWidget(titre)
        colonne.addWidget(note)
        colonne.addLayout(ligne)

    def _connect_all(self) -> None:
        for widget in (self._iterations, self._snapshot_every, self._stagnation,
                       self._time_budget, self._acceptance, self._target_score):
            widget.valueChanged.connect(self._on_form_changed)
        for widget in (self._stop_on_stagnation, self._stop_on_time,
                       self._stop_on_score):
            widget.toggled.connect(self._on_form_changed)
        self._algorithm.currentIndexChanged.connect(self._on_form_changed)

    # --- Ce que chaque réglage est, et ce qu'il change --------------------

    def retranslate_ui(self) -> None:
        self._algorithm.setItemText(0, self.tr("Recuit simulé"))
        self._algorithm.setItemText(1, self.tr("Descente stricte"))
        self._stop_on_stagnation.setText(self.tr("Activer"))
        self._stop_on_time.setText(self.tr("Activer"))
        self._stop_on_score.setText(self.tr("Activer"))
        self._stagnation.setSuffix(self.tr(" itérations sans gain"))
        self._target_score.setPrefix(self.tr("score "))

        self._labels["iterations"].setText(self.tr("Durée du calcul"))
        self._notes["iterations"].setText(self.tr(
            "Le nombre d'échanges de cartes que l'assemblage tentera. Il en "
            "essaie environ 127 000 par seconde en descente stricte, 120 000 au "
            "recuit. ⚠️ Le gain ne suit pas : les mille premières itérations "
            "effacent déjà près d'un tiers de ce qu'on peut gagner, et la courbe "
            "s'aplatit ensuite — 56 % du score de départ effacés à 50 000 "
            "itérations, 61 % à un million. Multiplier la durée par vingt ne "
            "rapporte donc que quelques points."))

        self._labels["algorithm"].setText(self.tr("Manière de chercher"))
        self._notes["algorithm"].setText(self.tr(
            "La <b>descente stricte</b> ne retient un échange que s'il améliore "
            "le score. Elle est simple et rapide, mais reste prisonnière du "
            "premier arrangement correct qu'elle trouve. Le <b>recuit "
            "simulé</b> accepte au "
            "début des échanges qui dégradent le score, pour sortir de ces "
            "impasses, puis devient de plus en plus exigeant. Mesuré : 67,5 % du "
            "score effacé au recuit contre 61,0 % en descente stricte, à un "
            "million d'itérations."))

        self._labels["acceptance"].setText(self.tr("Tolérance d'acceptation"))
        self._notes["acceptance"].setText(self.tr(
            "Au recuit seulement : la proportion d'échanges dégradants acceptés "
            "au démarrage. Elle tombe d'elle-même au fil du calcul — mesuré, "
            "19 % au départ et 0,3 % à la fin. Trop basse, le recuit se comporte "
            "comme une descente stricte ; trop haute, il brasse longtemps sans "
            "converger. En descente stricte, le champ n'a aucun effet et reste "
            "éteint."))

        self._labels["stagnation"].setText(self.tr("Arrêter sur stagnation"))
        self._notes["stagnation"].setText(self.tr(
            "Arrête le calcul quand aucun échange n'a été retenu depuis ce "
            "nombre d'itérations. C'est le seul arrêt qui s'adapte au jeu de "
            "cartes : il coupe quand il n'y a plus rien à gagner, au lieu "
            "d'attendre une durée décidée d'avance."))

        self._labels["time"].setText(self.tr("Arrêter sur le temps"))
        self._notes["time"].setText(self.tr(
            "Un budget en secondes, quoi qu'il arrive. Utile pour essayer une "
            "mise en page sans y passer l'après-midi ; le résultat est alors "
            "celui qu'on a au moment où le chronomètre tombe, pas un résultat "
            "abouti."))

        self._labels["score"].setText(self.tr("Arrêter sur score atteint"))
        self._notes["score"].setText(self.tr(
            "Arrête dès que le score descend sous cette valeur. ⚠️ Le score n'a "
            "pas d'échelle absolue : il dépend du nombre de cartes <b>et</b> de "
            "l'épaisseur des bandes — la même grille vaut 621,7 avec une bande "
            "de 0,10 et 552,0 avec 0,30. Une valeur relevée sur un calcul "
            "précédent ne vaut donc que pour les mêmes réglages."))

        self._labels["snapshot_every"].setText(self.tr("Clichés de la timeline"))
        self._notes["snapshot_every"].setText(self.tr(
            "Un cliché est gardé tous les N échanges <b>retenus</b>, pour "
            "pouvoir "
            "revenir en arrière dans le calcul et choisir un état plutôt qu'un "
            "autre. Resserrer la cadence donne une timeline plus fine et occupe "
            "plus de mémoire ; l'élargir peut ne laisser que deux ou trois états "
            "à comparer."))
        self.refresh()

    # --- Réactions --------------------------------------------------------

    def _on_form_changed(self, *_) -> None:
        if self._updating:
            return
        self._session.set_algorithm(
            iterations=self._iterations.value(),
            snapshot_every=self._snapshot_every.value(),
            stop_on_stagnation=self._stop_on_stagnation.isChecked(),
            stagnation_iterations=self._stagnation.value(),
            stop_on_time=self._stop_on_time.isChecked(),
            time_budget=self._time_budget.value(),
            use_annealing=self._algorithm.currentData(),
            acceptance=self._acceptance.value(),
            stop_on_score=self._stop_on_score.isChecked(),
            target_score=self._target_score.value(),
        )

    def refresh(self) -> None:
        self._sync_form()
        self._update_enabled()
        self._update_projections()
        self.state_changed.emit()

    def _sync_form(self) -> None:
        """Recopie la session dans les champs, sans réémettre."""
        self._updating = True
        session = self._session
        self._iterations.setValue(session.iterations)
        self._snapshot_every.setValue(session.snapshot_every)
        self._stop_on_stagnation.setChecked(session.stop_on_stagnation)
        self._stagnation.setValue(session.stagnation_iterations)
        self._stop_on_time.setChecked(session.stop_on_time)
        self._time_budget.setValue(session.time_budget)
        self._algorithm.setCurrentIndex(0 if session.use_annealing else 1)
        self._acceptance.setValue(session.acceptance)
        self._stop_on_score.setChecked(session.stop_on_score)
        self._target_score.setValue(session.target_score)
        self._updating = False
        self._push_back_clamped()

    def _push_back_clamped(self) -> None:
        """Renvoie à la session ce que les champs ont réellement accepté.

        Un préréglage écrit à la main peut porter une valeur hors bornes — le
        format est du JSON, et la spec assume qu'on le retouche. Le champ
        l'écrête pour l'afficher ; sans ce retour, la session garderait la
        valeur d'origine et le formulaire annoncerait un calcul différent de
        celui qui aura lieu.
        """
        session = self._session
        accepted = {
            "iterations": self._iterations.value(),
            "snapshot_every": self._snapshot_every.value(),
            "stagnation_iterations": self._stagnation.value(),
            "time_budget": self._time_budget.value(),
            "acceptance": self._acceptance.value(),
            "target_score": self._target_score.value(),
        }
        drifted = {name: value for name, value in accepted.items()
                   if getattr(session, name) != value}
        if drifted:
            session.set_algorithm(**drifted)

    def _update_enabled(self) -> None:
        """Un champ dont le seuil est décoché reste visible mais inactif."""
        self._stagnation.setEnabled(self._session.stop_on_stagnation)
        self._time_budget.setEnabled(self._session.stop_on_time)
        self._target_score.setEnabled(self._session.stop_on_score)
        # La tolérance ne veut rien dire en descente stricte : elle n'accepte
        # jamais un coup dégradant.
        self._acceptance.setEnabled(self._session.use_annealing)

    def _update_projections(self) -> None:
        """Ce que ces réglages impliquent, en une ligne sous les champs."""
        session = self._session
        annealing = session.use_annealing
        seconds = estimated_seconds(session.iterations, annealing)
        gain = estimated_gain(session.iterations, annealing)
        low, high = estimated_snapshots(session.iterations,
                                        session.snapshot_every, annealing)
        texte = (self.tr("Durée estimée : %1  —  gain attendu : environ %2 %  —  "
                         "timeline : entre %3 et %4 clichés")
                 .replace("%1", format_duration(seconds))
                 .replace("%2", f"{gain * 100:.0f}")
                 .replace("%3", str(low)).replace("%4", str(high)))
        if high < USEFUL_SNAPSHOTS:
            texte += "  —  " + self.tr("trop peu pour naviguer, resserrez la "
                                       "cadence")
        self._projection.setText(texte)
