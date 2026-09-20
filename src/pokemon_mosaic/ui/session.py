"""État partagé entre les étapes de l'assistant.

Une seule source de vérité : les écrans lisent et modifient cet objet, et se
préviennent par signaux. Rien n'est recalculé en double d'un écran à l'autre.
"""

import math
import os
import re
from dataclasses import dataclass
from dataclasses import replace as dataclass_replace
from datetime import datetime

import numpy as np
from PySide6.QtCore import QObject, Signal

from ..annealing import Annealing
from ..arrangements import Arrangement
from ..cards import DEFAULT_STRIP_SIZE, EDGE_PARTS, CardSet
from ..layout import (
    DEFAULT_DPI,
    MM_PER_INCH,
    PAPER_FORMATS_MM,
    GridFit,
    card_useful_dpi,
    cards_on_panel,
    clamp_offset_mm,
    distribute_empty_cells,
    format_name,
    grid_geometry,
)
from ..links import DEFAULT_LINKS, Link, LinkLibrary, resolve_links
from ..optimize import StopConditions, link_is_intact, select_cards
from ..presets import LinkRef, Preset
from ..scoring import EMPTY

# ⚠️ **La série se lit dans le nom du dossier.** Le miroir les nomme
# « a1-puissance-genetique », « a3b-la-clairiere-d-evoli », « promo-a-promo-a » :
# la lettre de tête est la série, et les promos d'une série portent la même. Rien
# d'autre ne la donne : le catalogue ne connaît que des extensions.
_SERIE = re.compile(r"^(?:promo-)?([a-z])(?=\d|-|$)", re.IGNORECASE)


# Le nombre d'agencements que l'utilisateur peut mettre de côté. Quatre : de quoi
# comparer des essais sans transformer l'export en bibliothèque, et quatre cases
# se lisent d'un coup d'œil en colonne sans la faire défiler.
MAX_SAVED = 4

# La finesse à laquelle se mesure la carte pour calculer sa finesse utile.
# ⚠️ **Fixe, et non celle de la session.** La largeur de carte en pixels dépend
# de la finesse par ses arrondis : mesurée à la finesse courante, la finesse
# utile bougerait avec celle qu'elle sert à régler, et l'onglet « Résolution »,
# qui s'y cale, pourrait osciller entre deux valeurs. À 1200, l'arrondi pèse
# moins d'un centième de millimètre.
USEFUL_DPI_REFERENCE = 1200

# Les bornes d'un habillage relu, celles des champs qui le règlent : côtés de la
# feuille de 1 à 200 cm, carte de 1 à 2000 mm et écart de 0 à 100 mm (étape 2),
# chevauchement de 0 à 50 mm et finesse de 50 à 1200 DPI (export), feuilles
# jusqu'à 5 de front et 3 lignes (aperçu). Les écrans importent la session, qui
# ne peut donc pas lire leurs constantes : un test les compare.
PRESENTATION_BOUNDS = {
    "paper_side_mm": (10.0, 2000.0),
    "card_width_mm": (1.0, 2000.0),
    "card_gap_mm": (0.0, 100.0),
    "overlap_mm": (0.0, 50.0),
    "dpi": (50, 1200),
    "panels": (1, 5),
    "panel_rows": (1, 3),
}


def _nombre(valeur, bas: float, haut: float) -> float | None:
    """Un nombre fini dans ses bornes, ou None. Un booléen n'en est pas un."""
    if isinstance(valeur, bool) or not isinstance(valeur, (int, float)):
        return None
    if not math.isfinite(valeur) or not bas <= valeur <= haut:
        return None
    return float(valeur)


def _entier(valeur, bas: int, haut: int) -> int | None:
    """Un entier dans ses bornes, ou None. `150.0`, écrit par un autre outil,
    reste lisible."""
    if isinstance(valeur, float) and math.isfinite(valeur) and valeur.is_integer():
        valeur = int(valeur)
    if isinstance(valeur, bool) or not isinstance(valeur, int):
        return None
    return valeur if bas <= valeur <= haut else None


def _couleur(valeur) -> tuple[int, int, int] | None:
    """Trois composantes entières de 0 à 255, ou None."""
    if not isinstance(valeur, (list, tuple)) or len(valeur) != 3:
        return None
    if any(_entier(composante, 0, 255) is None for composante in valeur):
        return None
    return tuple(int(composante) for composante in valeur)


def _drapeau(valeur) -> bool | None:
    """Un booléen, ou 0 et 1 qui en tiennent lieu ; None sinon."""
    if isinstance(valeur, bool):
        return valeur
    if isinstance(valeur, int) and valeur in (0, 1):
        return bool(valeur)
    return None


class NoFreeSlot(ValueError):
    """Les quatre cases sont prises : rien n'a été touché."""


@dataclass
class ArrangementStart:
    """Ce que reprendre un agencement a fait, pour le dire à l'utilisateur."""

    slot: int
    ignored: list          # champs de l'habillage écartés, par leur nom
    disabled_links: list   # liens désactivés, faute de tenir dans la grille


@dataclass
class SavedGrid:
    """Un agencement mis de côté, avec de quoi le montrer et l'exporter.

    ⚠️ **Le jeu de cartes fait partie de l'agencement.** La grille indexe le
    **sous-ensemble retenu** au moment du calcul, pas le catalogue : sans lui,
    les mêmes nombres désigneraient d'autres cartes dès que l'utilisateur change
    sa sélection. C'est une simple référence, l'objet est partagé avec la
    timeline et ne coûte rien de plus.
    """

    grid: object                    # np.ndarray, non importé ici
    cards: CardSet
    iteration: int
    score: float
    # ⚠️ **Le dossier d'où viennent ses cartes**, lu au lancement du calcul.
    # Un calcul et ses clichés survivent au chargement d'un autre dossier : lus
    # par rapport au dossier chargé ensuite, les chemins écrits dans la
    # bibliothèque devenaient « ../A/… », et l'agencement ne retrouvait plus
    # ses cartes. `None` : le dossier chargé.
    data_dir: str | None = None


def series_of(folder: str) -> str:
    """La série d'un dossier d'extension, ou `""` s'il n'en annonce aucune.

    Un dossier choisi à la main ne suit aucune convention : il ne rejoint alors
    aucun groupe, et se lit tel quel dans la liste.
    """
    trouve = _SERIE.match(os.path.basename(folder))
    return trouve.group(1).upper() if trouve else ""


class Session(QObject):
    """Ce que l'utilisateur a choisi jusqu'ici."""

    # Liste explicite des réglages d'algorithme. Valider par `hasattr` accepterait
    # tout attribut de QObject ou de mise en page : `set_algorithm(dpi=600)`
    # passerait et émettrait `algorithm_changed`, alors que l'aperçu fil de fer
    # n'écoute que `layout_changed` : il n'aurait jamais connaissance du changement.
    # ⚠️ **Les trois couleurs voyagent avec ce groupe**, alors qu'elles ne
    # changent rien au calcul : elles y étaient déjà pour `empty_colour`, elles
    # se relisent ainsi dans les préréglages écrits avant elles, et un second
    # groupe pour trois valeurs ferait deux signaux à écouter au lieu d'un.
    ALGORITHM_SETTINGS = frozenset({
        "iterations", "snapshot_every",
        "empty_colour", "gap_colour", "background_colour",
        "chameleon_gaps", "chameleon_border",
        "overlap_mm", "crop_marks", "full_resolution", "beyond_useful_dpi",
        "stop_on_stagnation", "stagnation_iterations",
        "stop_on_time", "time_budget",
        "use_annealing", "acceptance", "strip_size", "fine_metric",
        "stop_on_score", "target_score",
    })

    loading_started = Signal()
    layout_changed = Signal()
    cards_added = Signal(list)      # indices des cartes qui viennent d'arriver
    cards_loaded = Signal()         # chargement terminé
    selection_changed = Signal()
    links_changed = Signal()
    algorithm_changed = Signal()
    saved_changed = Signal()        # un agencement mis de côté, ou retiré
    # Un agencement enregistré vient de régler cartes, grille et habillage :
    # l'étape 2 valide alors ses parties d'office.
    arrangement_applied = Signal()

    def __init__(self):
        super().__init__()
        self.card_set: CardSet | None = None
        # Vrai du premier lot de cartes à la fin du chargement : le jeu est
        # alors partiel, et d'autres cartes arrivent encore, retenues.
        self.loading = False
        # L'agencement dont on est parti, voir `apply_arrangement` : l'exécution
        # le montre comme son premier cliché. Sa grille numérote les cartes
        # retenues comme le fait un calcul.
        self.started_from: SavedGrid | None = None
        # Le rang de chaque carte par son chemin relatif, refait quand le jeu
        # change : voir `index_of_path`.
        self._path_table: dict[str, int] | None = None
        self.data_dir: str | None = None
        self._excluded: set[int] = set()
        self._folder_of: dict[int, str] = {}
        self.links = LinkLibrary()

        # Mise en page (étape 2). Le format d'impression commande : la taille des
        # cartes en pixels s'en déduit, jamais l'inverse.
        # ⚠️ **Les dimensions sont la vérité, le nom en découle.** La feuille se
        # saisit aussi au centimètre près : un format hors catalogue n'a pas de
        # nom, et `paper` vaut alors la chaîne vide. Les deux ne peuvent pas
        # diverger : `set_layout` recalcule toujours l'un depuis l'autre.
        # Toujours en portrait : c'est `landscape` qui décide de l'orientation,
        # et stocker la feuille déjà tournée ferait deux façons de dire pareil.
        self.paper_size_mm: tuple[float, float] = PAPER_FORMATS_MM["A2"]
        self.paper = "A2"
        self.landscape = False
        self.dpi = DEFAULT_DPI
        # ⚠️ **Tant que personne n'a choisi**, la finesse suit le maximum utile,
        # que l'étape d'export repose à chaque passage. `DEFAULT_DPI` n'est
        # qu'un point de départ pour le temps où il n'y a pas encore de cartes :
        # le maximum se calcule sur elles.
        self.dpi_chosen = False
        # Feuilles côte à côte, et lignes de feuilles superposées : le poster
        # est leur somme. Une coupe ne tombe jamais sur une carte, dans un sens
        # comme dans l'autre.
        self.panels = 1
        self.panel_rows = 1
        # Où l'utilisateur a posé le bout de grille de chaque feuille, en
        # millimètres depuis le coin haut-gauche de **sa** feuille. Vide tant
        # qu'il n'a rien déplacé, et vidé dès que la mise en page change.
        self.panel_offsets: dict[int, tuple[float, float]] = {}
        self.cols = 17
        self.rows = 17
        # Largeur d'une carte sur le papier. `None` = automatique : la plus
        # grande qui fasse tenir la grille, recalculée à chaque changement.
        # Une valeur la fige, et c'est alors à la grille de s'y adapter.
        self.card_width_mm: float | None = None
        # Écart entre deux cartes, en millimètres, la même unité que la carte
        # et la feuille, seule mesurable sur le poster imprimé.
        self.card_gap_mm: float = 0.0
        # Liste ordonnée, pas un ensemble : le rang sert à savoir quel trou céder
        # sa place quand l'utilisateur en pose un nouveau alors que le quota est
        # atteint. Le plus ancien s'efface, façon file d'attente.
        self._empty_cells: list[tuple[int, int]] = []

        # Réglages d'algorithme (étape 3), séparés en « de base » et « avancés ».
        # De base, ce qui se décide par intention.
        self.iterations = 1_000_000
        self.snapshot_every = 10
        # Les couleurs de ce qui n'est pas une carte. Neutres au départ : le
        # blanc du papier ne prétend rien, et c'est à l'export qu'on essaie
        # autre chose. La couleur d'une case vide n'entre pas dans le score,
        # `grid_score` écarte toute paire qui en contient une.
        self.empty_colour = (255, 255, 255)
        self.gap_colour = (255, 255, 255)
        self.background_colour = (255, 255, 255)
        # Le mode caméléon : les écarts, et le pourtour de la grille, prennent
        # la couleur de ce qui les borde au lieu d'un aplat. Voir
        # `chameleon.py` : c'est un habillage, le calcul n'en sait rien.
        self.chameleon_gaps = False
        self.chameleon_border = False
        # Ce que l'écriture du fichier demande, et qui se règle désormais dans
        # les onglets plutôt que dans le dialogue : celui-ci ne garde que le
        # format, le dossier et le nom.
        self.overlap_mm = 0.0
        self.crop_marks = False
        # Relire les images d'origine, ou se contenter des vignettes. Change la
        # finesse utile d'un facteur quatre : les vignettes font le quart.
        self.full_resolution = True
        # ⚠️ Passer outre le maximum utile : au-delà, l'impression agrandit sans
        # ajouter un pixel de détail. Le champ s'y arrête, cette case le libère.
        self.beyond_useful_dpi = False
        self.stop_on_stagnation = False
        self.stagnation_iterations = 50_000
        self.stop_on_time = False
        self.time_budget = 60.0
        # Avancés, ce qui exige de comprendre le fonctionnement interne.
        self.use_annealing = True
        self.acceptance = 0.5
        self.strip_size = DEFAULT_STRIP_SIZE
        # ⚠️ **Décochée par défaut.** La métrique en dix parties est plus
        # exigeante : elle ne rend pas les mêmes scores, et les agencements
        # déjà gardés ont été jugés avec l'autre. C'est un choix, pas un
        # progrès qu'on impose.
        self.fine_metric = False
        self.stop_on_score = False
        self.target_score = 0.0

        # Les agencements mis de côté à l'exécution, quatre cases numérotées. Une
        # liste à trous plutôt qu'une liste courte : la case 3 reste la case 3
        # quand on vide la 2, et la colonne ne se réordonne pas sous la souris.
        self.saved: list[SavedGrid | None] = [None] * MAX_SAVED

    # --- Agencements mis de côté ------------------------------------------

    def save_grid(self, grid, cards: CardSet, iteration: int,
                  score: float, data_dir: str | None = None) -> int | None:
        """Range un agencement dans la première case libre, et rend son rang.

        Rend `None` quand les quatre cases sont prises : rien n'est écrasé sans
        que l'utilisateur l'ait demandé, il retire lui-même celle dont il ne
        veut plus. `data_dir` est le dossier de ses cartes, le chargé à défaut.
        """
        for rang, place in enumerate(self.saved):
            if place is None:
                # La grille est copiée : celle de la timeline continue de vivre,
                # et une reprise de calcul la réécrirait sous nos yeux.
                self.saved[rang] = SavedGrid(grid.copy(), cards, iteration, score,
                                             data_dir or self.data_dir)
                self.saved_changed.emit()
                return rang
        return None

    def remove_saved(self, slot: int) -> None:
        if 0 <= slot < MAX_SAVED and self.saved[slot] is not None:
            self.saved[slot] = None
            self.saved_changed.emit()

    def saved_count(self) -> int:
        return sum(1 for place in self.saved if place is not None)

    def first_saved(self) -> int | None:
        """Le rang de la première case occupée, celle que l'export ouvre."""
        for rang, place in enumerate(self.saved):
            if place is not None:
                return rang
        return None

    # --- Agencements enregistrés ------------------------------------------

    def arrangement_of(self, saved: SavedGrid, name: str) -> Arrangement:
        """Décrit un agencement gardé par les **chemins** de ses cartes.

        ⚠️ La grille d'un calcul indexe le sous-ensemble retenu, renuméroté de 0
        à n-1 : ces nombres ne veulent rien dire ailleurs. Le fichier liste donc
        les cartes une fois, par chemin, et la grille désigne des rangs de cette
        liste.
        """
        racine = saved.data_dir or self.data_dir
        chemins = [os.path.relpath(card.path, racine)
                   for card in saved.cards.cards]
        grille = tuple(tuple(int(case) for case in ligne)
                       for ligne in saved.grid)
        return Arrangement(
            name=name, cards=tuple(chemins), grid=grille,
            presentation=self.presentation(), score=saved.score,
            saved_at=datetime.now().astimezone().isoformat(timespec="seconds"),
        )

    def missing_cards(self, arrangement: Arrangement) -> list[str]:
        """Les cartes de l'agencement que le catalogue chargé n'a pas."""
        if self.card_set is None:
            return list(arrangement.cards)
        return [chemin for chemin in arrangement.cards
                if self.index_of_path(chemin) is None]

    def saved_from_arrangement(self, arrangement: Arrangement) -> SavedGrid:
        """Retraduit un agencement en grille sur les cartes chargées.

        ⚠️ **`subset` trie les indices**, il ne garde pas l'ordre qu'on lui
        donne : la case qui disait « la troisième carte du fichier » doit donc
        être retraduite, sans quoi la mosaïque montrerait les bonnes cartes aux
        mauvaises places.

        Lève `ValueError` si une carte manque : `missing_cards` le dit avant, et
        un agencement amputé n'est plus celui qu'on a partagé.
        """
        manquantes = self.missing_cards(arrangement)
        if manquantes:
            raise ValueError(f"{len(manquantes)} carte(s) absente(s) du "
                             f"catalogue.")
        indices = [self.index_of_path(chemin) for chemin in arrangement.cards]
        subset, _ = select_cards(self.card_set, indices)
        rang = subset.index_mapping()
        grille = np.array(
            [[EMPTY if case == EMPTY else rang[indices[case]] for case in ligne]
             for ligne in arrangement.grid], dtype=int)
        return SavedGrid(grille, subset, iteration=0, score=arrangement.score)

    def apply_arrangement(self, arrangement: Arrangement) -> "ArrangementStart":
        """Part d'un agencement enregistré : cartes, grille, habillage, case.

        Décidé par l'utilisateur le 2026-09-13. Seules ses cartes restent
        retenues ; la forme de la grille et ses cases vides sont reprises,
        l'habillage aussi, et l'agencement est rangé dans une case. Les réglages
        de l'algorithme ne bougent pas : le fichier ne les enregistre pas.

        ⚠️ **Tout est vérifié avant de toucher à quoi que ce soit.** Une carte
        absente lève `ValueError`, aucune case libre `NoFreeSlot` : un refus ne
        doit pas laisser une sélection à moitié remplacée.

        ⚠️ **Les liens qui ne tiennent pas dans la grille sont désactivés**,
        sans être supprimés, et rendus pour être nommés : un calcul qui part
        d'une grille exige que chaque lien actif y soit déjà intact, et
        « Lancer » échouerait sinon.
        """
        # ⚠️ **Pas pendant un chargement.** Les lots suivants arriveraient
        # retenus, la sélection ne serait plus celle de l'agencement, et la fin
        # du chargement réarmerait la grille proposée d'office, qui écraserait
        # la forme reprise au premier passage à l'étape 2.
        if self.loading:
            raise ValueError("Chargement des cartes en cours.")
        manquantes = self.missing_cards(arrangement)
        if manquantes:
            raise ValueError(f"{len(manquantes)} carte(s) absente(s) du "
                             f"catalogue.")
        if self.saved_count() >= MAX_SAVED:
            raise NoFreeSlot("Aucune case libre.")
        garde = self.saved_from_arrangement(arrangement)

        voulues = {self.index_of_path(chemin) for chemin in arrangement.cards}
        self.set_excluded(set(range(self.total_cards)) - voulues, True)
        self.set_excluded(voulues, False)

        colonnes, lignes = arrangement.shape
        self.set_layout(cols=colonnes, rows=lignes)
        # Après `set_layout` : changer la grille efface les cases posées.
        self._empty_cells = [(int(ligne), int(colonne)) for ligne, colonne
                             in np.argwhere(garde.grid == EMPTY)]
        # ⚠️ **Toujours prévenir**, comme un préréglage : c'est ce signal qui
        # dit à l'étape 2 que la grille est choisie, et qu'elle n'a plus à la
        # proposer. Sans lui, la grille reprise était écrasée au premier passage.
        self.layout_changed.emit()

        ignores = self.apply_presentation(arrangement.presentation)
        desactives = self._disable_links_broken_in(garde.grid)
        rang = self.save_grid(garde.grid, garde.cards, garde.iteration,
                              garde.score)
        self.started_from = self.saved[rang]
        self.arrangement_applied.emit()
        return ArrangementStart(slot=rang, ignored=ignores,
                                disabled_links=desactives)

    def _disable_links_broken_in(self, grid) -> list[Link]:
        """Désactive les liens actifs qui ne forment pas leur bloc dans `grid`.

        `grid` numérote les cartes retenues de 0 à n-1, dans l'ordre du
        catalogue : c'est la numérotation d'un calcul, et celle dans laquelle
        chaque lien se traduit pour être vérifié.
        """
        rang = {index: position
                for position, index in enumerate(self.selected_indices())}
        desactives = []
        for link in list(self.usable_links().active):
            traduit = dataclass_replace(
                link, cards=tuple(rang[index] for index in link.cards))
            if not link_is_intact(grid, traduit):
                self.links.replace(link, dataclass_replace(link, enabled=False))
                desactives.append(link)
        if desactives:
            self.links_changed.emit()
        return desactives

    def choose_dpi(self, value: int) -> None:
        """La finesse posée par l'utilisateur : elle cesse de suivre le maximum.

        Sans ce partage, un changement de format ou de source ramènerait au
        maximum une valeur qu'on venait de baisser exprès.
        """
        self.dpi_chosen = True
        self.set_layout(dpi=value)

    def useful_dpi(self, shape: tuple[int, int] | None = None) -> float:
        """La finesse au-delà de laquelle on agrandit sans gagner de détail.

        Elle dépend de la **source** : les vignettes font le quart des images
        d'origine, donc le quart de la finesse utile. `shape`, lignes puis
        colonnes, est celle de l'agencement exporté, voir `_shape`.
        """
        rows, cols = self._shape(shape)
        cartes = self.card_set
        if cartes is None or not len(cartes):
            return float("inf")
        source = (cartes.full_size[0] if self.full_resolution
                  else cartes.thumb_size[0])
        # ⚠️ **La carte réelle, écart et largeur imposée compris**, et non la
        # feuille divisée par les colonnes : avec un écart, la carte est plus
        # étroite, et son plafond plus haut. La finesse proposée d'office était
        # donc trop basse dès qu'on écartait les cartes.
        geometrie = grid_geometry(
            self.paper_mm(), self.panels, max(1, cols), max(1, rows),
            self._card_aspect(), USEFUL_DPI_REFERENCE, self.card_width_mm,
            self.card_gap_mm, self.panel_rows)
        return card_useful_dpi(geometrie.card_w, USEFUL_DPI_REFERENCE, source)

    def presentation(self) -> dict:
        """L'habillage du poster : tout ce que l'étape d'export laisse régler.

        Ni la forme de la grille ni les cases vides : elles sont dans
        l'agencement lui-même, qui les porte case par case.
        """
        return {
            "paper": self.paper,
            "paper_size_mm": list(self.paper_size_mm),
            "landscape": self.landscape,
            "dpi": self.dpi,
            "panels": self.panels,
            "panel_rows": self.panel_rows,
            "panel_offsets": [[index, *offset] for index, offset
                              in sorted(self.panel_offsets.items())] or None,
            "card_width_mm": self.card_width_mm,
            "card_gap_mm": self.card_gap_mm,
            "empty_colour": list(self.empty_colour),
            "gap_colour": list(self.gap_colour),
            "background_colour": list(self.background_colour),
            "chameleon_gaps": self.chameleon_gaps,
            "chameleon_border": self.chameleon_border,
            "overlap_mm": self.overlap_mm,
            "crop_marks": self.crop_marks,
            "full_resolution": self.full_resolution,
            "beyond_useful_dpi": self.beyond_useful_dpi,
        }

    def apply_presentation(self, presentation: dict) -> list[str]:
        """Repose l'habillage venu d'un agencement. Rend les champs écartés.

        ⚠️ **L'habillage d'un fichier n'est pas digne de foi.** Un agencement se
        partage et se modifie à la main, et `Arrangement.from_json` ne vérifie
        que sa grille. Reproduit : une couleur entière ou un chevauchement en
        texte levaient une exception une fois la case remplie ; une finesse
        « haute » ou -2 feuilles s'installaient dans la session, et faisaient
        tomber le calcul suivant loin de leur cause. Chaque champ est donc
        vérifié (type, bornes des champs qui le règlent, valeur finie) : ce qui
        passe est repris, le reste est écarté et nommé.

        Les couleurs passent par `set_algorithm`, qui est le groupe où elles
        voyagent ; le reste par `set_layout`. ⚠️ Les déplacements de feuilles
        **après** : tout autre réglage de mise en page les défait.
        """
        bornes = PRESENTATION_BOUNDS
        ecartes: list[str] = []

        def retenir(nom, valeur, cible):
            if valeur is None:
                ecartes.append(nom)
            else:
                cible[nom] = valeur

        reglages: dict = {}
        for nom in ("empty_colour", "gap_colour", "background_colour"):
            if presentation.get(nom) is not None:
                retenir(nom, _couleur(presentation[nom]), reglages)
        for nom in ("chameleon_gaps", "chameleon_border", "crop_marks",
                    "full_resolution", "beyond_useful_dpi"):
            if nom in presentation:
                retenir(nom, _drapeau(presentation[nom]), reglages)
        if "overlap_mm" in presentation:
            retenir("overlap_mm",
                    _nombre(presentation["overlap_mm"], *bornes["overlap_mm"]),
                    reglages)

        mise_en_page: dict = {}
        if "paper" in presentation:
            papier = presentation["paper"]
            retenir("paper", papier if isinstance(papier, str) else None,
                    mise_en_page)
        if "landscape" in presentation:
            retenir("landscape", _drapeau(presentation["landscape"]), mise_en_page)
        if "dpi" in presentation:
            retenir("dpi", _entier(presentation["dpi"], *bornes["dpi"]),
                    mise_en_page)
        for nom in ("panels", "panel_rows"):
            if nom in presentation:
                retenir(nom, _entier(presentation[nom], *bornes[nom]), mise_en_page)
        if "card_width_mm" in presentation:
            # `None` a un sens : la largeur automatique.
            largeur = presentation["card_width_mm"]
            if largeur is None:
                mise_en_page["card_width_mm"] = None
            else:
                retenir("card_width_mm",
                        _nombre(largeur, *bornes["card_width_mm"]), mise_en_page)
        if "card_gap_mm" in presentation:
            retenir("card_gap_mm",
                    _nombre(presentation["card_gap_mm"], *bornes["card_gap_mm"]),
                    mise_en_page)
        if presentation.get("paper_size_mm"):
            cotes = presentation["paper_size_mm"]
            lus = ([_nombre(cote, *bornes["paper_side_mm"]) for cote in cotes]
                   if isinstance(cotes, (list, tuple)) and len(cotes) == 2 else [None])
            retenir("paper_size_mm",
                    None if None in lus else tuple(lus), mise_en_page)

        deplacements = []
        brut = presentation.get("panel_offsets") or ()
        lisibles = isinstance(brut, (list, tuple))
        for entree in brut if lisibles else ():
            if (isinstance(entree, (list, tuple)) and len(entree) == 3
                    and _entier(entree[0], 0, bornes["panels"][1]
                                * bornes["panel_rows"][1]) is not None
                    and None not in [_nombre(v, 0.0, bornes["paper_side_mm"][1])
                                     for v in entree[1:]]):
                deplacements.append((int(entree[0]), float(entree[1]),
                                     float(entree[2])))
            else:
                lisibles = False
        if not lisibles:
            # Tout ou rien : reprendre les entrées lues avant l'abîmée aurait
            # déplacé des feuilles que l'avertissement dit non reprises.
            ecartes.append("panel_offsets")
            deplacements = []

        if mise_en_page:
            # ⚠️ **Le drapeau se lève avant.** La finesse d'un agencement gardé
            # est un choix, pas un défaut ; et `set_layout` prévient l'écran,
            # qui reposerait le maximum avant que le drapeau soit levé.
            self.dpi_chosen = self.dpi_chosen or "dpi" in mise_en_page
            self.set_layout(**mise_en_page)
        if reglages:
            self.set_algorithm(**reglages)
        for index, x, y in deplacements:
            if index < self.panel_count():
                self.move_panel(index, x, y)
        return ecartes

    # --- Cartes -----------------------------------------------------------

    def start_loading(self, data_dir: str) -> None:
        """Vide la session et prépare l'arrivée des cartes, dossier par dossier."""
        self.data_dir = data_dir
        self.loading = True
        # Un autre jeu de cartes : les indices de l'agencement repris ne
        # désigneraient plus les mêmes cartes.
        self.started_from = None
        self.card_set = CardSet(cards=[], full_size=(0, 0), thumb_size=(0, 0))
        self._path_table = None
        self._excluded.clear()
        self._folder_of.clear()
        # Les liens désignent des indices de cartes : conservés d'un dossier à
        # l'autre, ils pointeraient sur d'autres cartes sans que rien ne le
        # signale, puisque ces indices existent toujours.
        self.links = LinkLibrary()
        self.loading_started.emit()
        self.links_changed.emit()
        self.selection_changed.emit()

    def append_cards(self, cards) -> None:
        """Ajoute un lot de cartes déjà chargées, en conservant leurs indices."""
        if not cards:
            return
        # Les cartes arrivent d'un fil de fond qui a figé l'épaisseur de bande au
        # démarrage. Si l'utilisateur l'a changée entre-temps, les dossiers déjà
        # arrivés ont été recalculés et pas ceux-ci : le même jeu porterait des
        # signatures calculées sur deux épaisseurs, et les distances entre les deux
        # groupes n'auraient plus aucun sens. On réaligne systématiquement.
        # ⚠️ Le découpage des bords aussi : le fil de fond mesure toujours
        # d'un bloc, et la métrique améliorée se coche dans la même session.
        for card in cards:
            card.calculate_features(self.strip_size, self.edge_parts())

        self.card_set.cards.extend(cards)
        self._path_table = None
        for card in cards:
            # Le nom de dossier seul ne suffit pas : deux séries peuvent avoir un
            # « 0_promo ». On garde le chemin relatif à la racine.
            self._folder_of[card.index] = os.path.relpath(
                os.path.dirname(card.path), self.data_dir
            )
        self.cards_added.emit([card.index for card in cards])
        self.selection_changed.emit()

    def finish_loading(self, card_set: CardSet) -> None:
        """Fixe les dimensions définitives une fois tout chargé.

        Les avertissements suivent aussi : la session tient un `CardSet` **à
        elle**, rempli lot par lot, et non celui que le chargeur a produit. Les
        laisser derrière donnerait un `session.card_set.has_warnings` toujours
        faux, alors que le chargement en a relevé.
        """
        self.card_set.full_size = card_set.full_size
        self.card_set.thumb_size = card_set.thumb_size
        self.card_set.odd_sizes = list(card_set.odd_sizes)
        self.card_set.unreadable = list(card_set.unreadable)
        self.loading = False
        self.cards_loaded.emit()

    def abandon_loading(self) -> None:
        """Un chargement a échoué après ses premiers lots : il n'arrivera plus
        rien. Sans cela, ce qui attend la fin d'un chargement attendrait pour
        toujours."""
        self.loading = False

    def set_cards(self, card_set: CardSet, data_dir: str) -> None:
        """Chargement en un bloc, sans progression, utile aux tests."""
        self.start_loading(data_dir)
        self.append_cards(list(card_set))
        self.finish_loading(card_set)

    @property
    def total_cards(self) -> int:
        return len(self.card_set) if self.card_set else 0

    @property
    def selected_count(self) -> int:
        return self.total_cards - len(self._excluded)

    def is_excluded(self, index: int) -> bool:
        return index in self._excluded

    def set_excluded(self, indices, excluded: bool) -> None:
        """Inclut ou exclut un lot de cartes, en un seul signal."""
        before = len(self._excluded)
        for index in indices:
            if excluded:
                self._excluded.add(index)
            else:
                self._excluded.discard(index)
        if len(self._excluded) != before:
            self.selection_changed.emit()

    def invert_excluded(self, indices) -> None:
        """Bascule chaque carte : les incluses sortent, les exclues rentrent.

        ⚠️ Deux appels à `set_excluded`, un par sens, ne conviendraient pas : il
        ne prévient que si le **nombre** d'exclues a changé, et une inversion
        peut le laisser identique : dix cartes dedans, dix dehors. L'écran ne se
        repeindrait pas alors que tout a changé de camp.
        """
        avant = set(self._excluded)
        for index in indices:
            if index in self._excluded:
                self._excluded.discard(index)
            else:
                self._excluded.add(index)
        if self._excluded != avant:
            self.selection_changed.emit()

    def toggle(self, index: int) -> None:
        self.set_excluded([index], index not in self._excluded)

    def selected_indices(self) -> list[int]:
        if not self.card_set:
            return []
        return [c.index for c in self.card_set if c.index not in self._excluded]

    def relative_path(self, index: int) -> str:
        """Chemin de la carte, relatif au dossier chargé.

        C'est l'identité stable d'une carte : son indice, lui, dépend du contenu
        du dossier et se décale à l'arrivée d'une extension.
        """
        return os.path.relpath(self.card_set[index].path, self.data_dir)

    def index_of_path(self, relative: str) -> int | None:
        """Le rang d'une carte désignée par son chemin relatif au dossier.

        ⚠️ **Une table, et non un parcours.** Chercher carte par carte refaisait
        un `relpath` sur tout le catalogue à chaque appel : le menu des
        agencements, qui compte les cartes absentes de chacun, mettait 34 s à
        s'ouvrir sur dix agencements de 441 cartes. La table se refait quand le
        jeu change, remplacé par un autre dossier ou grossi d'un lot.
        """
        if not self.card_set:
            return None
        if self._path_table is None:
            self._path_table = {}
            for card in self.card_set:
                self._path_table.setdefault(
                    os.path.relpath(card.path, self.data_dir), card.index)
        return self._path_table.get(relative)

    # --- Dossiers ---------------------------------------------------------

    def folders(self) -> list[str]:
        """Dossiers rencontrés, en chemin relatif à la racine, triés."""
        return sorted(set(self._folder_of.values()))

    def folders_by_series(self) -> list[tuple[str, list[str]]]:
        """Les dossiers groupés par série, dans l'ordre d'affichage.

        Les dossiers sans série viennent en dernier, sous une clé vide : ils
        n'ont pas de groupe et se posent tels quels.
        """
        groupes: dict[str, list[str]] = {}
        for folder in self.folders():
            groupes.setdefault(series_of(folder), []).append(folder)
        nommees = sorted((nom, dossiers) for nom, dossiers in groupes.items()
                         if nom)
        return nommees + ([("", groupes[""])] if "" in groupes else [])

    def indices_in_folder(self, folder: str) -> list[int]:
        return [i for i, f in self._folder_of.items() if f == folder]

    def folder_of(self, index: int) -> str:
        return self._folder_of.get(index, "")

    # --- Mise en page -----------------------------------------------------

    def paper_mm(self) -> tuple[float, float]:
        """La feuille telle qu'elle sortira, orientation comprise."""
        width, height = self.paper_size_mm
        return (height, width) if self.landscape else (width, height)

    def panel_count(self) -> int:
        """Le nombre de feuilles à imprimer, toutes lignes confondues."""
        return self.panels * self.panel_rows

    def _shape(self, shape: tuple[int, int] | None) -> tuple[int, int]:
        """Lignes et colonnes de la mosaïque mise en page.

        ⚠️ **À l'export, la forme est celle de l'agencement affiché**, et non
        celle de l'étape 2 : un agencement gardé ou ouvert depuis la
        bibliothèque peut en avoir une autre, et le fichier écrit suit
        l'agencement. L'aperçu et ses réglages lisaient la session : un 3×3
        gardé puis une grille passée en 2×2 se dessinait en quatre cases.
        `None` garde la forme de la session, celle de l'étape 2.
        """
        return (self.rows, self.cols) if shape is None else tuple(shape)

    def move_panel(self, index: int, x_mm: float, y_mm: float,
                   shape: tuple[int, int] | None = None) -> None:
        """Pose le bout de grille d'une feuille à cet endroit **de sa feuille**.

        Les coordonnées partent de son coin haut-gauche, et sont bornées à ce
        qui reste de libre : un bout de grille ne déborde jamais sur la feuille
        voisine, faute de quoi la coupe tomberait en pleine carte.
        """
        libre = self.panel_free_mm(index, shape)
        borne = clamp_offset_mm((x_mm, y_mm), libre)
        if self.panel_offsets.get(index) == borne:
            return
        self.set_layout(panel_offsets={**self.panel_offsets, index: borne})

    def center_panels(self, shape: tuple[int, int] | None = None) -> None:
        """Pose chaque morceau au milieu de sa feuille.

        ⚠️ **Les feuilles vides sont laissées de côté.** Une feuille qui ne
        porte aucune carte : la dernière, quand la grille s'arrête avant, n'a
        rien à centrer, et lui inventer une position la ferait compter parmi
        les feuilles déplacées.

        ⚠️ Jamais branchée telle quelle sur `clicked` : Qt y passerait son
        booléen en guise de forme.
        """
        places = {}
        for index in range(self.panel_count()):
            if not self.panel_carries_cards(index, shape):
                continue
            libre = self.panel_free_mm(index, shape)
            places[index] = (libre[0] / 2, libre[1] / 2)
        if places != self.panel_offsets:
            self.set_layout(panel_offsets=places)

    def panels_are_centred(self, shape: tuple[int, int] | None = None) -> bool:
        """Vrai si chaque morceau est déjà au milieu de sa feuille."""
        for index in range(self.panel_count()):
            if not self.panel_carries_cards(index, shape):
                continue
            libre = self.panel_free_mm(index, shape)
            pose = self.panel_position_mm(index, shape)
            if (abs(pose[0] - libre[0] / 2) > 0.05
                    or abs(pose[1] - libre[1] / 2) > 0.05):
                return False
        return True

    def panel_carries_cards(self, index: int,
                            shape: tuple[int, int] | None = None) -> bool:
        """Cette feuille porte-t-elle au moins une carte ?"""
        rows, cols = self._shape(shape)
        geometrie = self.panel_geometry(shape)
        ligne, colonne = divmod(index, max(1, self.panels))
        return bool(cards_on_panel(cols, geometrie.per_panel, colonne)
                    and cards_on_panel(rows, geometrie.rows_per_panel, ligne))

    def _card_aspect(self) -> float:
        """Largeur sur hauteur d'une carte : celle du jeu chargé, sinon l'usuelle."""
        if self.card_set and self.card_set.full_size[1]:
            return self.card_set.full_size[0] / self.card_set.full_size[1]
        return 713 / 984

    def panel_geometry(self, shape: tuple[int, int] | None = None):
        """La géométrie des cartes pour la mise en page courante."""
        rows, cols = self._shape(shape)
        return grid_geometry(
            self.paper_mm(), self.panels, max(1, cols), max(1, rows),
            self._card_aspect(), self.dpi, self.card_width_mm, self.card_gap_mm,
            self.panel_rows)

    def panel_of(self, row: int, col: int, shape: tuple[int, int] | None = None,
                 geometry=None) -> int:
        """La feuille qui porte cette case, lue de gauche à droite.

        ⚠️ **Un seul endroit le calcule côté écran.** Le dessin, la saisie à la
        souris et la place libre s'accordaient chacun de leur côté sur la même
        division : trois occasions de diverger pour une formule de deux lignes.

        `geometry`, déjà calculée pour `shape`, évite de la refaire à chaque
        case quand l'aperçu en interroge des milliers.
        """
        geometrie = geometry or self.panel_geometry(shape)
        return ((row // max(1, geometrie.rows_per_panel)) * self.panels
                + col // max(1, geometrie.per_panel))

    def panel_free_mm(self, index: int,
                      shape: tuple[int, int] | None = None) -> tuple[float, float]:
        """Place libre autour du bout de grille d'une feuille, en millimètres."""
        rows, cols = self._shape(shape)
        geometrie = self.panel_geometry(shape)
        ligne, colonne = divmod(index, max(1, self.panels))
        paper_w, paper_h = self.paper_mm()
        en_mm = MM_PER_INCH / self.dpi

        def libre(total, par_feuille, rang, taille, papier):
            combien = cards_on_panel(total, par_feuille, rang)
            occupe = (combien * taille
                      + max(0, combien - 1) * geometrie.gap) * en_mm
            return max(0.0, papier - occupe)

        return (libre(cols, geometrie.per_panel, colonne,
                      geometrie.card_w, paper_w),
                libre(rows, geometrie.rows_per_panel, ligne,
                      geometrie.card_h, paper_h))

    def panel_default_mm(self, index: int,
                         shape: tuple[int, int] | None = None) -> tuple[float, float]:
        """Où se pose ce bout de grille quand on n'y a pas touché.

        Calé à gauche, et centré en hauteur tant qu'il n'y a qu'une ligne de
        feuilles : la même règle qu'à l'export, d'où la lecture de la place
        libre plutôt qu'un calcul refait à côté.
        """
        if self.panel_rows > 1:
            return (0.0, 0.0)
        return (0.0, self.panel_free_mm(index, shape)[1] / 2)

    def panel_position_mm(self, index: int,
                          shape: tuple[int, int] | None = None) -> tuple[float, float]:
        """Où ce bout de grille se trouve : déplacé s'il l'a été, défaut sinon.

        ⚠️ **Le déplacement est borné à la forme demandée.** Les déplacements
        valent pour la forme où ils ont été faits ; exporter un agencement
        d'une autre forme les rejoue sur des feuilles plus ou moins chargées,
        donc sur une autre place libre. L'aperçu montrait alors un bout de
        grille poussé à 340 mm que l'export, qui borne en écrivant, ramenait à
        180 (mesuré le 2026-09-20). Un aperçu qui ne calcule pas comme l'export
        ment, et c'est lui qu'on regarde avant d'imprimer.
        """
        if index in self.panel_offsets:
            return clamp_offset_mm(self.panel_offsets[index],
                                   self.panel_free_mm(index, shape))
        return self.panel_default_mm(index, shape)

    def sheet_mm(self) -> tuple[float, float]:
        """La surface entière, toutes feuilles mises bout à bout."""
        width, height = self.paper_mm()
        return width * self.panels, height * self.panel_rows

    def set_layout(self, **changes) -> None:
        """Modifie un ou plusieurs réglages de grille et prévient une seule fois."""
        changes = self._settle_paper(changes)
        # On compare les valeurs avant de les appliquer : le formulaire renvoie
        # toujours les six réglages d'un bloc, donc tester la seule présence de
        # « cols » effacerait le placement manuel à chaque changement de DPI,
        # de format ou d'orientation.
        grid_changed = (changes.get("cols", self.cols) != self.cols
                        or changes.get("rows", self.rows) != self.rows)
        # ⚠️ **Tout le reste défait les déplacements.** Une carte plus large,
        # une feuille de plus, un autre format : le bout de grille de chaque
        # feuille n'a plus la même taille, et la place qu'on lui avait choisie
        # ne veut plus rien dire. On revient aux emplacements par défaut plutôt
        # que de garder des positions calculées pour une autre mise en page.
        moved = "panel_offsets" in changes

        touched = set()
        for name, value in changes.items():
            if getattr(self, name) != value:
                setattr(self, name, value)
                touched.add(name)
        if not touched:
            return

        if grid_changed:
            # Les positions choisies à la main n'ont plus de sens sur une autre
            # grille : elles tomberaient à des endroits qui ne veulent plus rien
            # dire, quand elles ne sortiraient pas carrément du cadre.
            self._empty_cells = []
        # ⚠️ **Sauf la finesse seule.** Les déplacements sont en millimètres, et
        # la finesse ne change la place libre que par arrondi, quelques
        # centièmes de millimètre. Trouvé par l'audit du 2026-09-18 : taper une
        # finesse, ou basculer « Images d'origine », remettait sans un mot
        # chaque feuille placée à la main à sa place par défaut. L'export borne
        # de toute façon chaque déplacement à sa feuille en écrivant.
        if not moved and self.panel_offsets and touched != {"dpi"}:
            self.panel_offsets = {}
        self.layout_changed.emit()

    def _settle_paper(self, changes: dict) -> dict:
        """Accorde le nom du format et les dimensions, quel que soit le donné.

        ⚠️ Un nom **inconnu**, un préréglage écrit à la main, ne laisse ni le
        nom ni des dimensions fausses : on garde la feuille en place et le nom
        qui lui revient. Sans cela, la session portait un format que l'export
        refusait de traduire, et l'erreur ne sortait qu'à l'écriture du fichier.

        Donnés tous les deux et en désaccord, ce sont les **dimensions** qui
        l'emportent : elles décrivent la feuille, le nom ne fait que la nommer.
        """
        if not changes.keys() & {"paper", "paper_size_mm"}:
            return changes
        changes = dict(changes)
        nom = changes.get("paper")
        if nom and nom.upper() in PAPER_FORMATS_MM:
            changes.setdefault("paper_size_mm", PAPER_FORMATS_MM[nom.upper()])
            changes["paper"] = nom.upper()
        taille = tuple(round(float(côté), 1)
                       for côté in changes.get("paper_size_mm",
                                               self.paper_size_mm))
        changes["paper_size_mm"] = taille
        changes["paper"] = format_name(taille)
        return changes

    def grid_fit(self) -> GridFit:
        return GridFit(cols=self.cols, rows=self.rows,
                       card_count=self.selected_count)

    def empty_cells(self) -> list[tuple[int, int]]:
        """Les cases vides posées, et rien de plus.

        ⚠️ **Aucune répartition automatique.** L'application en plaçait une
        d'office, quitte à la remplacer ensuite : la grille s'ouvrait donc déjà
        trouée, à des endroits que personne n'avait choisis, et rien ne disait
        qu'on pouvait les déplacer. C'est désormais un geste de l'utilisateur,
        que l'étape 2 compte et réclame avant de laisser passer, la répartition
        régulière reste offerte, mais sur un bouton.

        Le résultat est écrêté au quota courant : la sélection a pu changer
        depuis, et on garde les plus récemment posées.
        """
        return sorted(self._placed())

    def _placed(self) -> list[tuple[int, int]]:
        """Les cases en vigueur, **dans l'ordre où elles ont été posées**.

        ⚠️ C'est la seule liste qui compte, et tout doit passer par elle. Écrêter
        au seul affichage laissait des cases hors quota stockées mais jamais
        dessinées : cliquer l'une d'elles la retirait d'une liste invisible au
        lieu de poser un trou, et le clic était avalé sans le moindre retour.
        Mesuré : cinq trous posés puis quatre cartes réintégrées, un seul trou
        affiché, et un clic sur une case apparemment pleine sans aucun effet.

        L'ordre est conservé : c'est lui qui désigne le trou qui cède sa place
        quand on en pose un de plus alors que le quota est atteint.
        """
        needed = self.grid_fit().empty_cells
        inside = [cell for cell in self._empty_cells
                  if 0 <= cell[0] < self.rows and 0 <= cell[1] < self.cols]
        # On garde les plus récentes : ce sont les choix explicites de l'utilisateur.
        return inside[-needed:] if needed else []

    def missing_empty_cells(self) -> int:
        """Combien de cases vides restent à poser pour que la grille soit prête."""
        return max(0, self.grid_fit().empty_cells - len(self.empty_cells()))

    def auto_place_empty_cells(self) -> None:
        """Complète les cases vides manquantes par la répartition régulière.

        Ce qui a déjà été posé à la main n'est pas défait : le bouton achève un
        placement commencé aussi bien qu'il en fait un de bout en bout.
        """
        needed = self.grid_fit().empty_cells
        placed = self._placed()
        if len(placed) >= needed:
            return
        for cell in distribute_empty_cells((self.rows, self.cols), needed):
            if len(placed) >= needed:
                break
            if cell not in placed:
                placed.append(cell)
        self._empty_cells = placed
        self.layout_changed.emit()

    def toggle_empty_cell(self, row: int, col: int) -> None:
        """Pose ou retire une case vide à cet emplacement."""
        if not (0 <= row < self.rows and 0 <= col < self.cols):
            return
        cell = (row, col)
        # On repart de ce qui est **réellement en vigueur**, et non de la liste
        # brute : elle peut porter des cases hors quota, invisibles, dont le
        # retrait passerait pour un clic sans effet.
        placed = self._placed()
        if cell in placed:
            placed.remove(cell)
        else:
            placed.append(cell)
            # Quota atteint : le trou posé il y a le plus longtemps cède sa place,
            # sinon le clic n'aurait aucun effet visible.
            excess = len(placed) - self.grid_fit().empty_cells
            if excess > 0:
                del placed[:excess]
        self._empty_cells = placed
        self.layout_changed.emit()

    def paint_empty_cells(self, cells, empty: bool) -> None:
        """Applique un geste de glissement : pose ou retire ce lot de cases.

        Reçoit **tout le trajet** parcouru depuis le début du geste, et non la
        seule case qui vient d'être atteinte : la pose est alors idempotente, et
        la vue n'a rien à mémoriser de l'état d'avant.

        ⚠️ **Le quota borne la pose, il ne chasse rien.** Poser au-delà en
        évinçant les plus anciennes ferait courir les trous derrière le curseur
        au lieu d'en poser : on ignore la suite du trajet. Un clic isolé, lui,
        passe toujours par `toggle_empty_cell` et garde son éviction, c'est
        ainsi qu'on déplace un trou quand la grille est déjà complète.
        """
        placed = self._placed()
        avant = list(placed)
        if empty:
            libre = self.grid_fit().empty_cells - len(placed)
            for row, col in cells:
                if libre <= 0:
                    break
                cell = (row, col)
                if cell in placed or not (0 <= row < self.rows
                                          and 0 <= col < self.cols):
                    continue
                placed.append(cell)
                libre -= 1
        else:
            efface = {(row, col) for row, col in cells}
            placed = [cell for cell in placed if cell not in efface]
        if placed == avant:
            return
        self._empty_cells = placed
        self.layout_changed.emit()

    def reset_empty_cells(self) -> None:
        """Retire toutes les cases vides posées. Il n'en reste aucune."""
        if not self._empty_cells:
            return
        self._empty_cells = []
        self.layout_changed.emit()

    # --- Réglages d'algorithme --------------------------------------------

    def set_algorithm(self, **changes) -> None:
        """Modifie un ou plusieurs réglages et ne prévient qu'une fois."""
        unknown = set(changes) - self.ALGORITHM_SETTINGS
        if unknown:
            raise AttributeError(
                f"Réglage inconnu : {', '.join(sorted(unknown))}. "
                f"Les réglages de mise en page passent par set_layout()."
            )

        # On compare les valeurs avant de les appliquer : l'écran de réglages
        # renvoie tous les champs d'un bloc, donc tester la présence de la clé
        # « strip_size » recalculerait les 280 signatures (~47 ms) à chaque cran
        # de molette sur un réglage sans rapport.
        strip_changed = changes.get("strip_size", self.strip_size) != self.strip_size
        # Le découpage des bords change les signatures tout autant que
        # l'épaisseur : cocher la case sans recalculer laisserait le score sur
        # des mesures qui ne sont plus celles qu'on annonce.
        metric_changed = (changes.get("fine_metric", self.fine_metric)
                          != self.fine_metric)

        touched = False
        for name, value in changes.items():
            if getattr(self, name) != value:
                setattr(self, name, value)
                touched = True
        if not touched:
            return

        # L'épaisseur des bandes change les signatures : sans recalcul, le score
        # reposerait sur des mesures périmées. Le découpage des bords de même.
        if (strip_changed or metric_changed) and self.card_set:
            self.card_set.recalculate_features(self.strip_size,
                                               self.edge_parts())
        self.algorithm_changed.emit()

    def edge_parts(self) -> int:
        """En combien de parties chaque bord se mesure : une, ou dix.

        Un seul endroit traduit la case en nombre de parties : le calcul des
        signatures, l'aperçu qui les montre et le chargement doivent découper
        pareil, sans quoi l'écran désignerait des parties que le score ne
        mesure pas.
        """
        return EDGE_PARTS if self.fine_metric else 1

    def annealing(self) -> Annealing | None:
        """Le recuit configuré, ou None pour une descente stricte."""
        if not self.use_annealing:
            return None
        return Annealing(initial_acceptance=self.acceptance)

    def stop_conditions(self) -> StopConditions:
        """Traduit les cases cochées en conditions d'arrêt.

        Un seuil décoché vaut None : le champ garde sa valeur pour que la
        décocher puis la recocher n'oblige pas à la ressaisir.
        """
        return StopConditions(
            max_iterations=self.iterations,
            target_score=self.target_score if self.stop_on_score else None,
            stagnation_iterations=(self.stagnation_iterations
                                   if self.stop_on_stagnation else None),
            time_budget=self.time_budget if self.stop_on_time else None,
        )

    # --- Liens ------------------------------------------------------------

    def usable_links(self) -> LinkLibrary:
        """Liens dont toutes les cartes sont encore sélectionnées.

        Un lien dont une carte a été retirée devient inapplicable : il est écarté
        du calcul sans être supprimé de la bibliothèque.
        """
        return self.links.for_cards(self.selected_indices())

    def add_link(self, link: Link) -> None:
        self.links.add(link)
        self.links_changed.emit()

    def remove_link(self, link: Link) -> None:
        self.links.remove(link)
        self.links_changed.emit()

    def replace_link(self, old: Link, new: Link) -> Link:
        """Remplace un lien par une version modifiée, à sa place dans la liste."""
        self.links.replace(old, new)
        self.links_changed.emit()
        return new

    def set_link_enabled(self, link: Link, enabled: bool) -> Link:
        """Active ou désactive un lien sans le supprimer de la bibliothèque.

        `Link` est immuable : on remplace l'objet plutôt que de le modifier, ce
        qui garantit qu'aucune copie détenue ailleurs ne change dans le dos de
        son propriétaire.
        """
        if link.enabled == enabled:
            return link
        return self.replace_link(link, dataclass_replace(link, enabled=enabled))

    def apply_default_links(self) -> list[str]:
        """Ajoute les liens fournis d'office, une fois les cartes chargées.

        Renvoie les fragments de chemin introuvables : le dossier chargé n'est pas
        forcément celui d'origine, et un lien par défaut n'a alors pas de sens.
        Les cartes déjà engagées dans un lien sont laissées tranquilles.
        """
        if not self.card_set:
            return []

        def find(fragment: str) -> int | None:
            index = self.card_set.find(fragment)
            if index is None or index in self.links.claimed_cards():
                return None
            return index

        missing = resolve_links(self.links, find, DEFAULT_LINKS)
        self.links_changed.emit()
        return missing

    def selection_by_path(self) -> tuple[tuple[str, ...],
                                         tuple[tuple[LinkRef, bool], ...]]:
        """Les exclusions et **tous** les liens, désignés par chemin.

        Ce qui doit survivre au rechargement du même dossier, où les indices se
        décalent dès qu'une carte arrive. ⚠️ Un préréglage ne garde que les liens
        actifs : un lien composé puis désactivé s'y serait perdu.
        """
        exclues = tuple(sorted(self.relative_path(index) for index in self._excluded))
        liens = tuple(
            (LinkRef(cards=tuple(self.relative_path(index) for index in link.cards),
                     shape=link.shape, ordered=link.ordered, name=link.name),
             link.enabled)
            for link in self.links.links)
        return exclues, liens

    def restore_selection(self, excluded, links) -> list[str]:
        """Repose exclusions et liens après le rechargement du même dossier.

        Les cartes arrivées depuis sont retenues, comme toute carte nouvelle. Un
        chemin disparu est rendu, et le lien qui le portait est écarté.
        """
        manquants: list[str] = []
        voulues = set()
        for chemin in excluded:
            index = self.index_of_path(chemin)
            if index is None:
                manquants.append(chemin)
            else:
                voulues.add(index)
        self.set_excluded(voulues, True)
        self.set_excluded(set(range(self.total_cards)) - voulues, False)

        # ⚠️ **Un lien fourni d'office dont les cartes viennent d'arriver reste
        # actif**, comme au premier chargement. Il n'existait pas avant, donc ne
        # figure pas dans ce qu'on repose : le reprendre tel quel l'aurait
        # désactivé, alors qu'un chargement neuf l'aurait laissé en place.
        connus = {ref.cards for ref, _ in links}
        arrives = []
        for link in self.links.active:
            chemins = tuple(self.relative_path(index) for index in link.cards)
            if chemins not in connus:
                arrives.append(LinkRef(cards=chemins, shape=link.shape,
                                       ordered=link.ordered, name=link.name))
        manquants.extend(self._apply_links(
            [ref for ref, actif in links if actif] + arrives))
        presents = {link.cards for link in self.links.links}
        for ref, actif in links:
            if actif:
                continue
            indices = [self.index_of_path(chemin) for chemin in ref.cards]
            if None in indices:
                manquants.extend(chemin for chemin, index
                                 in zip(ref.cards, indices, strict=True)
                                 if index is None)
                continue
            if tuple(indices) in presents:
                continue
            try:
                self.links.add(Link(cards=tuple(indices), shape=ref.shape,
                                    ordered=ref.ordered, enabled=False,
                                    name=ref.name))
            except ValueError:
                # Un lien désactivé ne devrait gêner personne ; si la
                # bibliothèque le refuse quand même, on le dit plutôt que de
                # faire échouer la reprise du reste.
                manquants.extend(ref.cards)
        self.links_changed.emit()
        return manquants

    # --- Préréglages ------------------------------------------------------

    def to_preset(self, name: str) -> Preset:
        """Fige la configuration courante sous ce nom."""
        return Preset(
            name=name,
            excluded=tuple(sorted(self.relative_path(index)
                                  for index in self._excluded)),
            active_links=tuple(
                LinkRef(cards=tuple(self.relative_path(index)
                                    for index in link.cards),
                        shape=link.shape, ordered=link.ordered, name=link.name)
                for link in self.links.active
            ),
            layout={
                # Les dimensions **et** le nom : le nom se relit d'un coup
                # d'œil dans le fichier, les dimensions survivent à un format
                # hors catalogue.
                "paper": self.paper,
                "paper_size_mm": list(self.paper_size_mm),
                "landscape": self.landscape,
                "dpi": self.dpi, "panels": self.panels,
                "panel_rows": self.panel_rows,
                # Une liste, JSON ne sachant pas nommer une clé entière. Vide
                # quand rien n'a été déplacé, ce qui est le cas le plus courant.
                "panel_offsets": [[index, *offset] for index, offset
                                  in sorted(self.panel_offsets.items())] or None,
                "cols": self.cols, "rows": self.rows,
                "card_width_mm": self.card_width_mm,
                "card_gap_mm": self.card_gap_mm,
                # Toutes les cases vides sont posées à la main désormais : il
                # n'y a plus de répartition d'office à distinguer d'un choix.
                # `None` reste écrit quand il n'y en a aucune, pour qu'un
                # préréglage ancien se relise sans traitement de faveur.
                "empty_cells": ([list(cell) for cell in self._placed()]
                                or None),
            },
            algorithm={name: getattr(self, name)
                       for name in sorted(self.ALGORITHM_SETTINGS)},
        )

    def apply_preset(self, preset: Preset) -> list[str]:
        """Rejoue un préréglage. Renvoie les chemins introuvables, pour information.

        Une carte absente est signalée sans faire échouer le reste : un préréglage
        doit survivre à la disparition d'une carte comme à l'arrivée d'une
        extension, sans quoi il ne servirait qu'au dossier qui l'a vu naître.
        """
        missing: list[str] = []
        self._apply_algorithm(preset.algorithm)
        self._apply_layout(preset.layout)

        if self.card_set:
            wanted = set()
            for relative in preset.excluded:
                index = self.index_of_path(relative)
                if index is None:
                    missing.append(relative)
                else:
                    wanted.add(index)
            # Un seul passage : les cartes hors du préréglage redeviennent
            # retenues, y compris celles d'une extension arrivée depuis.
            self.set_excluded(wanted, True)
            self.set_excluded(set(range(self.total_cards)) - wanted, False)
            missing.extend(self._apply_links(preset.active_links))
        return missing

    def _apply_algorithm(self, algorithm: dict) -> None:
        known = {name: value for name, value in algorithm.items()
                 if name in self.ALGORITHM_SETTINGS}
        # JSON ne connaît pas les tuples : sans cette conversion, la couleur
        # relue serait une liste, éternellement différente de la valeur courante,
        # et chaque rechargement rejouerait un changement pour rien.
        for couleur in ("empty_colour", "gap_colour", "background_colour"):
            if couleur in known:
                known[couleur] = tuple(known[couleur])
        if known:
            self.set_algorithm(**known)

    def _apply_layout(self, layout: dict) -> None:
        cells = layout.get("empty_cells")
        # ⚠️ Posés **après** `set_layout`, comme les cases vides : tout autre
        # réglage défait les déplacements, et les poser avant les effacerait.
        deplacements = {int(index): (float(x), float(y))
                        for index, x, y in (layout.get("panel_offsets") or ())}
        known = {name: value for name, value in layout.items()
                 if name not in ("empty_cells", "panel_offsets")}
        # JSON ne connaît pas les tuples, et une liste ne serait jamais égale à
        # la taille en place : chaque rechargement rejouerait un changement.
        if known.get("paper_size_mm"):
            known["paper_size_mm"] = tuple(known["paper_size_mm"])
        if known:
            self.set_layout(**known)
        # Après `set_layout` : changer la grille efface les cases posées à la
        # main, ce qui annulerait celles du préréglage si on les posait avant.
        self._empty_cells = [tuple(cell) for cell in (cells or ())]
        # ⚠️ **Bornés en entrant.** Un préréglage écrit à la main pousserait
        # sinon un morceau hors de sa feuille : l'export le ramènerait, l'écran
        # non, et les deux ne montreraient plus le même poster.
        self.panel_offsets = {
            index: clamp_offset_mm(offset, self.panel_free_mm(index))
            for index, offset in deplacements.items()
            if 0 <= index < self.panel_count()
        }
        # ⚠️ **On prévient toujours**, même quand rien n'a bougé. Un préréglage
        # est une mise en page affirmée : c'est ce signal qui dit à l'étape 2 que
        # la grille a été choisie, et qu'elle n'a donc plus à la proposer. Un
        # préréglage décrivant la grille déjà en place se taisait, et l'écran
        # l'écrasait au premier passage.
        self.layout_changed.emit()

    def _apply_links(self, active_links) -> list[str]:
        """Active les liens du préréglage, désactive les autres.

        Un lien du préréglage absent de la bibliothèque y est ajouté : sans cela,
        recharger une configuration sur une bibliothèque vidée perdrait en silence
        les paires qu'elle décrit.
        """
        missing: list[str] = []
        wanted: list[tuple[tuple[int, ...], LinkRef]] = []
        for reference in active_links:
            indices = [self.index_of_path(path) for path in reference.cards]
            if any(index is None for index in indices):
                missing.extend(path for path, index
                               in zip(reference.cards, indices, strict=True)
                               if index is None)
                continue
            wanted.append((tuple(indices), reference))

        # Tout désactiver d'abord : la bibliothèque refuse qu'une carte
        # appartienne à deux liens actifs, et l'ancien état bloquerait le nouveau.
        for link in list(self.links.active):
            self.links.replace(link, dataclass_replace(link, enabled=False))

        existing = {link.cards: link for link in self.links.links}
        for cards, reference in wanted:
            link = existing.get(cards)
            if link is None:
                # Recréé à l'identique : hériter des valeurs par défaut ferait
                # revenir un lien à ordre libre en lien imposé, changeant la
                # contrainte donnée à l'optimiseur sans que rien ne le dise.
                self.links.add(Link(cards=cards, shape=reference.shape,
                                    ordered=reference.ordered,
                                    name=reference.name))
            else:
                # La **forme** du préréglage l'emporte : les mêmes cartes en
                # colonne ou en ligne ne sont pas la même contrainte, et garder
                # celle de la bibliothèque rechargerait autre chose que ce qui a
                # été enregistré, sans rien dire.
                # `or link.shape` : un préréglage d'avant les rectangles n'en
                # porte aucune, et la laisser vide aplatirait le lien en une
                # rangée à la première relecture.
                self.links.replace(link, dataclass_replace(
                    link, enabled=True, shape=reference.shape or link.shape))
        self.links_changed.emit()
        return missing

    def unusable_links(self) -> list[Link]:
        """Liens actifs dont une carte a été retirée de la sélection.

        Ils sont ignorés au calcul sans être supprimés : l'interface doit pouvoir
        le dire, sinon un lien resterait coché sans jamais s'appliquer.
        """
        selected = set(self.selected_indices())
        return [link for link in self.links.active
                if not selected.issuperset(link.cards)]
