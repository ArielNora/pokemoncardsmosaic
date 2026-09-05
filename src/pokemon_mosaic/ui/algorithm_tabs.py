"""L'onglet de l'algorithme, dans l'étape des paramètres.

L'algorithme avait son écran à lui, entre la mise en page et l'exécution. Il
n'avait pourtant rien de plus à décider : ce sont des **paramètres**, comme le
papier et la grille, et les séparer obligeait à traverser une étape entière pour
revenir changer une durée.

Un seul onglet, lu de haut en bas : ce que l'assemblage **mesure**, l'épaisseur
des bandes de bord et son aperçu, puis ce qu'il **fait** de cette mesure, une
phrase par réglage. L'épaisseur avait un onglet à elle ; elle y était seule, et
séparer la métrique des réglages qui s'en servent obligeait à faire l'aller-retour
pour comprendre l'un par l'autre.

Aucun de ces réglages ne bloque quoi que ce soit : ils ont tous une valeur qui
marche, et l'utilisateur n'a pas à y toucher pour lancer un calcul.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from . import theme
from .big_spin import BigFloatSpin
from .estimates import (
    estimated_gain,
    estimated_seconds,
    estimated_snapshots,
    format_duration,
)
from .layout_tabs import STATUS_BOOST, LayoutTab
from .runner import MAX_SEED
from .session import Session
from .strip_preview import StripPreview

# En deçà, la timeline offrira trop peu d'états pour être navigable.
USEFUL_SNAPSHOTS = 10
# Les champs posés dans une phrase : assez larges pour leur nombre, jamais plus.
# Un compteur qui s'étire casse la ligne de texte qui le porte.
FIELD_WIDTH = 150
SMALL_FIELD_WIDTH = 110
# Le retrait des lignes qui dépendent de celle du dessus.
SENTENCE_INDENT = 26
# Hauteur maximale de l'aperçu des bandes.
PREVIEW_HEIGHT = 300
# La place laissée autour d'une ligne pour que son aura ne soit pas rognée.
GLOW_ROOM = theme.GLOW_ROOM
# L'air entre le cadre d'une partie et ce qu'elle contient.
SECTION_PADDING = 10


class AdvancedTab(LayoutTab):
    """Les réglages de l'algorithme, posés **dans** les phrases qui les disent.

    ⚠️ **Le texte fait partie du réglage.** « Tolérance d'acceptation : 0,30 »
    ne dit rien à personne, pas même à qui a écrit le programme six mois après.
    Chaque champ vit donc au milieu de la phrase qu'il complète, « l'algorithme
    s'arrête lorsqu'il a fait N itérations », et les mots en gras du paragraphe
    d'ouverture, itération, échange, métrique, agencement, sont ceux que ces
    phrases réemploient : le vocabulaire s'apprend une fois.
    """

    def __init__(self, session: Session, parent=None):
        super().__init__(parent)
        self._session = session
        self._updating = False
        # Chaque phrase est coupée en deux autour de son champ : ce qui le
        # précède, ce qui le suit.
        self._sentences: dict[str, tuple[QLabel, QLabel]] = {}
        # L'aura de chaque ligne à cocher, reposée à chaque changement d'état
        # ou de mode.
        self._glows: dict[str, QGraphicsDropShadowEffect] = {}
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
        # ⚠️ **Zéro veut dire « au hasard ».** Une graine se recopie et se
        # partage : fixée, elle rejoue exactement le même calcul, clichés
        # compris. Un champ vide aurait demandé un second réglage pour dire
        # « pas de graine » ; le zéro le dit, et aucune graine tirée ne le vaut.
        self._seed = QSpinBox()
        self._seed.setRange(0, MAX_SEED - 1)
        self._seed.setSpecialValueText(" ")
        self._seed.setGroupSeparatorShown(True)
        self._algorithm = QComboBox()
        self._algorithm.addItem("", True)      # recuit
        self._algorithm.addItem("", False)     # descente stricte
        self._acceptance = QDoubleSpinBox()
        self._acceptance.setRange(0.01, 0.99)
        self._acceptance.setSingleStep(0.05)
        # ⚠️ **Toujours cochée, et non débrayable.** Un calcul sans borne
        # d'itérations n'existe pas : les autres arrêts ne font que le couper
        # plus tôt. La case le dit au lieu de laisser croire qu'on peut la
        # retirer, et un champ désactivé se lit mieux qu'un clic sans effet.
        self._always_iterations = QCheckBox()
        self._always_iterations.setChecked(True)
        self._always_iterations.setEnabled(False)
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
        for champ in (self._iterations, self._stagnation, self._seed):
            champ.setFixedWidth(FIELD_WIDTH)
        for champ in (self._time_budget, self._acceptance, self._target_score,
                      self._snapshot_every):
            champ.setFixedWidth(SMALL_FIELD_WIDTH)

        # ⚠️ **L'avertissement vient en premier.** Sans lui, sept réglages en
        # tête d'écran se lisent comme sept décisions à prendre avant de
        # pouvoir lancer quoi que ce soit.
        self._notice = QLabel()
        self._notice.setWordWrap(True)
        theme.mark(self._notice, "warning")
        gras = self._notice.font()
        gras.setBold(True)
        self._notice.setFont(gras)

        self._intro = QLabel()
        self._intro.setWordWrap(True)
        self._intro.setTextFormat(Qt.RichText)

        # --- La métrique : l'épaisseur mesurée, et ce qu'elle donne --------
        self._metric_title = QLabel()
        self._metric_title.setTextFormat(Qt.RichText)
        self._settings_title = QLabel()
        self._settings_title.setTextFormat(Qt.RichText)
        self._saving_title = QLabel()
        self._saving_title.setTextFormat(Qt.RichText)

        self._metric_note = QLabel()
        self._metric_note.setWordWrap(True)

        self._strip = BigFloatSpin(0.01, 0.50, step=0.05, decimals=2)
        self._strip.setFixedWidth(150)
        self._strip.value_changed.connect(self._on_form_changed)
        self._preview = StripPreview(self._session)
        self._preview.setMaximumHeight(PREVIEW_HEIGHT)

        # Le réglage à gauche, ce qu'il donne à droite : on lit la cause puis
        # l'effet, sur la même ligne.
        mesure = QHBoxLayout()
        mesure.setSpacing(24)
        mesure.addWidget(self._strip, 0, Qt.AlignTop)
        mesure.addWidget(self._preview, 1)
        self._metric_box = QWidget()
        self._metric_box.setLayout(mesure)

        self._metric_status = QLabel()
        self._metric_status.setWordWrap(True)
        # Même corps que la projection du bas : ce sont deux commentaires de
        # l'écran sur ce qu'il montre, pas des réglages.
        legende = self._metric_status.font()
        legende.setPointSize(legende.pointSize() + STATUS_BOOST)
        self._metric_status.setFont(legende)

        self._stop_title = QLabel()
        self._stop_title.setTextFormat(Qt.RichText)

        contenu = QWidget()
        colonne = QVBoxLayout(contenu)
        colonne.setContentsMargins(4, 4, 12, 4)
        colonne.setSpacing(8)
        colonne.addWidget(self._notice)
        colonne.addWidget(self._section(
            self._metric_title, self._metric_note, self._metric_box,
            self._metric_status))
        colonne.addWidget(self._section(
            self._saving_title,
            self._sentence("snapshot_every", self._snapshot_every)))
        colonne.addWidget(self._section(
            self._settings_title, self._intro,
            self._sentence("algorithm", self._algorithm),
            self._sentence("acceptance", self._acceptance,
                           retrait=SENTENCE_INDENT),
            self._sentence("seed", self._seed),
            self._stop_title,
            self._sentence("iterations", self._iterations,
                           self._always_iterations, retrait=SENTENCE_INDENT),
            self._sentence("stagnation", self._stagnation,
                           self._stop_on_stagnation, retrait=SENTENCE_INDENT),
            self._sentence("time", self._time_budget,
                           self._stop_on_time, retrait=SENTENCE_INDENT),
            self._sentence("score", self._target_score,
                           self._stop_on_score, retrait=SENTENCE_INDENT)))
        colonne.addStretch(1)

        # ⚠️ **Défilante.** Le texte et ses réglages ne tiennent pas sur toutes
        # les fenêtres : sans cela, les dernières lignes seraient hors du cadre,
        # et rien ne dirait qu'elles existent.
        self._scroll = QScrollArea()
        self._scroll.setWidget(contenu)
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QScrollArea.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

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

    def _section(self, *contenus: QWidget) -> QFrame:
        """Une partie des réglages, dans son cadre.

        Trois blocs de texte à la suite se lisaient comme un seul : rien ne
        disait où la métrique s'arrêtait et où l'algorithme commençait.
        """
        cadre = QFrame()
        theme.mark(cadre, "section")
        pile = QVBoxLayout(cadre)
        pile.setContentsMargins(SECTION_PADDING, SECTION_PADDING,
                                SECTION_PADDING, SECTION_PADDING)
        pile.setSpacing(6)
        for contenu in contenus:
            pile.addWidget(contenu)
        return cadre

    def _sentence(self, key: str, champ: QWidget,
                  bascule: QCheckBox | None = None,
                  retrait: int = 0) -> QWidget:
        """Une phrase dont le réglage est un mot comme les autres.

        Le texte se coupe autour de `%1` : ce qui précède le champ, ce qui le
        suit. Une seule chaîne à traduire, et le champ reste à sa place dans la
        phrase quelle que soit la langue.

        ⚠️ **Quand la ligne se coche, ses mots appartiennent à la case.** Une
        case nue à côté d'un libellé n'offre que douze pixels à viser, et
        cliquer la phrase ne ferait rien. Le texte est donc porté par la
        `QCheckBox` elle-même. L'exception est la case **désactivée** des
        itérations : elle griserait la phrase qui décrit le réglage par défaut,
        celui-là même qui est actif.
        """
        porte_le_texte = bascule is not None and bascule.isEnabled()
        avant = bascule if porte_le_texte else QLabel()
        apres = QLabel()
        for morceau in (avant, apres):
            if isinstance(morceau, QLabel):
                morceau.setTextFormat(Qt.RichText)
        # ⚠️ **La fin de phrase se replie, le début non.** Sans cela, une
        # phrase un peu longue élargissait le panneau jusqu'à faire apparaître
        # une barre de défilement horizontale, et le texte sortait du cadre.
        # Le début, lui, doit rester collé à son champ.
        apres.setWordWrap(True)
        self._sentences[key] = (avant, apres)

        ligne = QHBoxLayout()
        ligne.setSpacing(6)
        if bascule is not None:
            ligne.addWidget(bascule)
        if avant is not bascule:
            ligne.addWidget(avant)
        ligne.addWidget(champ)
        ligne.addWidget(apres, 1)

        cadre = QFrame()
        cadre.setLayout(ligne)
        if bascule is None:
            ligne.setContentsMargins(retrait, 0, 0, 0)
            return cadre
        # ⚠️ **Une ligne à cocher porte l'aura de son état**, comme « Suivant » :
        # verte quand elle compte, rouge, plus discrète, quand elle est éteinte.
        # Il lui faut donc un cadre opaque à border, et de la place autour pour
        # que le halo ne soit pas rogné par ses voisines.
        theme.mark(cadre, "stop-line")
        ligne.setContentsMargins(GLOW_ROOM, 4, GLOW_ROOM, 4)
        halo = QGraphicsDropShadowEffect(cadre)
        halo.setOffset(0, 0)
        cadre.setGraphicsEffect(halo)
        self._glows[key] = halo

        entoure = QHBoxLayout()
        entoure.setContentsMargins(retrait, GLOW_ROOM // 2, GLOW_ROOM,
                                   GLOW_ROOM // 2)
        entoure.addWidget(cadre)
        porteur = QWidget()
        porteur.setLayout(entoure)
        return porteur

    def _say(self, key: str, texte: str) -> None:
        """Pose une phrase autour de son champ, en coupant sur `%1`."""
        avant, apres = self._sentences[key]
        morceaux = texte.split("%1")
        avant.setText(morceaux[0].strip())
        apres.setText(morceaux[1].strip() if len(morceaux) > 1 else "")

    def _connect_all(self) -> None:
        for widget in (self._iterations, self._snapshot_every, self._stagnation,
                       self._time_budget, self._acceptance, self._target_score,
                       self._seed):
            widget.valueChanged.connect(self._on_form_changed)
        for widget in (self._stop_on_stagnation, self._stop_on_time,
                       self._stop_on_score):
            widget.toggled.connect(self._on_form_changed)
        self._algorithm.currentIndexChanged.connect(self._on_form_changed)

    # --- Ce que l'algorithme fait, et ce que chaque réglage y change ------

    def retranslate_ui(self) -> None:
        self._algorithm.setItemText(0, self.tr("le recuit simulé"))
        self._algorithm.setItemText(1, self.tr("la descente stricte"))

        self._strip.setTitle(self.tr("Épaisseur des bandes"))
        self._metric_title.setText(self.tr("<b>La métrique :</b>"))
        self._metric_note.setText(self.tr(
            "La partie la plus importante de l'algorithme. Elle prend les "
            "bandes voisines de deux cartes et en tire un score, qui dit à quel "
            "point ces bandes se ressemblent. Tout le travail de l'algorithme "
            "est ensuite de déplacer les cartes pour obtenir le meilleur score "
            "d'ensemble."))
        self._metric_status.setText(self.tr(
            "À gauche, deux cartes voisines : la flèche relie les deux bandes "
            "que le score compare. À droite, une petite grille d'essai "
            "réoptimisée à cette épaisseur."))
        self._saving_title.setText(self.tr("<b>Fréquence de sauvegarde :</b>"))
        self._settings_title.setText(self.tr("<b>Paramètres de l'algorithme :</b>"))

        self._notice.setText(self.tr(
            "Les valeurs par défaut donnent presque toujours un bon résultat. "
            "Vous pouvez les changer, ou passer directement à la suite."))

        # Les mots en gras sont ceux que les phrases plus bas réemploient.
        self._intro.setText(self.tr(
            "À chaque <b>itération</b>, l'algorithme tente un <b>échange</b> : "
            "il permute deux cartes de la grille et regarde ce que devient la "
            "<b>métrique</b>, l'écart de couleur entre les bords qui se "
            "touchent. L'échange est <b>retenu</b> s'il rapproche "
            "l'<b>agencement</b> du but, une mosaïque dont les bords voisins se "
            "ressemblent, et le calcul continue jusqu'à ce qu'un <b>arrêt</b> "
            "tombe."))

        self._say("algorithm", self.tr("L'algorithme utilisé est %1"))
        self._say("seed", self.tr(
            "Le hasard part de la graine %1 (vide : une neuve à chaque calcul). "
            "La même graine rejoue exactement le même calcul, clichés compris, "
            "sur les mêmes cartes et les mêmes réglages."))
        self._say("acceptance", self.tr(
            "Le recuit accepte au départ %1 d'échanges qui dégradent la "
            "métrique, puis devient de plus en plus exigeant."))

        self._stop_title.setText(self.tr("<b>L'algorithme s'arrête</b> lorsque :"))
        self._say("iterations", self.tr("il a fait %1 itérations (toujours actif)"))
        self._say("stagnation", self.tr(
            "la métrique ne s'améliore plus depuis %1 itérations"))
        self._say("time", self.tr("il a calculé pendant %1"))
        self._say("score", self.tr("la métrique descend sous %1"))

        self._say("snapshot_every", self.tr(
            "Un agencement sera enregistré tous les %1 échanges retenus."))

        self.refresh()

    # --- Réactions --------------------------------------------------------

    def _on_form_changed(self, *_) -> None:
        if self._updating:
            return
        self._session.set_algorithm(
            # Zéro n'est pas une graine : c'est l'absence de graine.
            seed=self._seed.value() or None,
            strip_size=self._strip.value(),
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
        self._seed.setValue(session.seed or 0)
        self._strip.setValue(session.strip_size)
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

        Un préréglage écrit à la main peut porter une valeur hors bornes, le
        format est du JSON, et la spec assume qu'on le retouche. Le champ
        l'écrête pour l'afficher ; sans ce retour, la session garderait la
        valeur d'origine et le formulaire annoncerait un calcul différent de
        celui qui aura lieu.
        """
        session = self._session
        accepted = {
            "strip_size": self._strip.value(),
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
        # jamais un coup dégradant. La phrase se grise avec son champ, sinon
        # elle promettrait un comportement que le calcul n'aura pas.
        self._acceptance.setEnabled(self._session.use_annealing)
        for morceau in self._sentences["acceptance"]:
            morceau.setEnabled(self._session.use_annealing)
        self._update_glows()

    def _update_glows(self) -> None:
        """Verte sur une ligne d'arrêt qui compte, rouge sur une ligne éteinte."""
        actifs = {
            "iterations": True,      # jamais débrayable
            "stagnation": self._session.stop_on_stagnation,
            "time": self._session.stop_on_time,
            "score": self._session.stop_on_score,
        }
        for cle, halo in self._glows.items():
            theme.set_glow(halo, self.palette(), actifs[cle])

    def _update_projections(self) -> None:
        """Ce que ces réglages impliquent, en une ligne sous les champs."""
        session = self._session
        annealing = session.use_annealing
        seconds = estimated_seconds(session.iterations, annealing)
        gain = estimated_gain(session.iterations, annealing)
        low, high = estimated_snapshots(session.iterations,
                                        session.snapshot_every, annealing)
        texte = (self.tr("Durée estimée : %1, gain attendu : environ %2 %, "
                         "timeline : entre %3 et %4 clichés")
                 .replace("%1", format_duration(seconds))
                 .replace("%2", f"{gain * 100:.0f}")
                 .replace("%3", str(low)).replace("%4", str(high)))
        if high < USEFUL_SNAPSHOTS:
            texte += ", " + self.tr("trop peu pour naviguer, resserrez la "
                                       "cadence")
        self._projection.setText(texte)
