"""État partagé entre les étapes de l'assistant.

Une seule source de vérité : les écrans lisent et modifient cet objet, et se
préviennent par signaux. Rien n'est recalculé en double d'un écran à l'autre.
"""

import os
import re
from dataclasses import dataclass
from dataclasses import replace as dataclass_replace
from datetime import datetime

import numpy as np
from PySide6.QtCore import QObject, Signal

from ..annealing import Annealing
from ..arrangements import Arrangement
from ..cards import DEFAULT_STRIP_SIZE, CardSet
from ..layout import (
    DEFAULT_DPI,
    MM_PER_INCH,
    PAPER_FORMATS_MM,
    GridFit,
    cards_on_panel,
    clamp_offset_mm,
    distribute_empty_cells,
    format_name,
    grid_geometry,
    max_useful_dpi,
)
from ..links import DEFAULT_LINKS, Link, LinkLibrary, resolve_links
from ..optimize import StopConditions, select_cards
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
        "use_annealing", "acceptance", "strip_size",
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

    def __init__(self):
        super().__init__()
        self.card_set: CardSet | None = None
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
        self.stop_on_score = False
        self.target_score = 0.0

        # Les agencements mis de côté à l'exécution, quatre cases numérotées. Une
        # liste à trous plutôt qu'une liste courte : la case 3 reste la case 3
        # quand on vide la 2, et la colonne ne se réordonne pas sous la souris.
        self.saved: list[SavedGrid | None] = [None] * MAX_SAVED

    # --- Agencements mis de côté ------------------------------------------

    def save_grid(self, grid, cards: CardSet, iteration: int,
                  score: float) -> int | None:
        """Range un agencement dans la première case libre, et rend son rang.

        Rend `None` quand les quatre cases sont prises : rien n'est écrasé sans
        que l'utilisateur l'ait demandé, il retire lui-même celle dont il ne
        veut plus.
        """
        for rang, place in enumerate(self.saved):
            if place is None:
                # La grille est copiée : celle de la timeline continue de vivre,
                # et une reprise de calcul la réécrirait sous nos yeux.
                self.saved[rang] = SavedGrid(grid.copy(), cards, iteration, score)
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
        chemins = [os.path.relpath(card.path, self.data_dir)
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

    def useful_dpi(self) -> float:
        """La finesse au-delà de laquelle on agrandit sans gagner de détail.

        Elle dépend de la **source** : les vignettes font le quart des images
        d'origine, donc le quart de la finesse utile.
        """
        cartes = self.card_set
        if cartes is None or not len(cartes):
            return float("inf")
        source = (cartes.full_size[0] if self.full_resolution
                  else cartes.thumb_size[0])
        return max_useful_dpi(self.paper_mm(), max(1, self.cols), source)

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

    def apply_presentation(self, presentation: dict) -> None:
        """Repose l'habillage venu d'un agencement.

        Les couleurs passent par `set_algorithm`, qui est le groupe où elles
        voyagent ; le reste par `set_layout`. ⚠️ Les déplacements de feuilles
        **après** : tout autre réglage de mise en page les défait.
        """
        couleurs = {nom: tuple(presentation[nom]) for nom in
                    ("empty_colour", "gap_colour", "background_colour")
                    if presentation.get(nom) is not None}
        couleurs.update({nom: bool(presentation[nom]) for nom in
                         ("chameleon_gaps", "chameleon_border", "crop_marks",
                          "full_resolution", "beyond_useful_dpi")
                         if nom in presentation})
        if "overlap_mm" in presentation:
            couleurs["overlap_mm"] = float(presentation["overlap_mm"])
        mise_en_page = {nom: presentation[nom] for nom in
                        ("paper", "landscape", "dpi", "panels", "panel_rows",
                         "card_width_mm", "card_gap_mm")
                        if nom in presentation}
        if presentation.get("paper_size_mm"):
            mise_en_page["paper_size_mm"] = tuple(presentation["paper_size_mm"])
        if mise_en_page:
            self.set_layout(**mise_en_page)
        if couleurs:
            self.set_algorithm(**couleurs)
        for index, x, y in (presentation.get("panel_offsets") or ()):
            self.move_panel(int(index), float(x), float(y))

    # --- Cartes -----------------------------------------------------------

    def start_loading(self, data_dir: str) -> None:
        """Vide la session et prépare l'arrivée des cartes, dossier par dossier."""
        self.data_dir = data_dir
        self.card_set = CardSet(cards=[], full_size=(0, 0), thumb_size=(0, 0))
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
        for card in cards:
            card.calculate_features(self.strip_size)

        self.card_set.cards.extend(cards)
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
        self.cards_loaded.emit()

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
        if not self.card_set:
            return None
        return next(
            (card.index for card in self.card_set
             if os.path.relpath(card.path, self.data_dir) == relative),
            None,
        )

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

    def move_panel(self, index: int, x_mm: float, y_mm: float) -> None:
        """Pose le bout de grille d'une feuille à cet endroit **de sa feuille**.

        Les coordonnées partent de son coin haut-gauche, et sont bornées à ce
        qui reste de libre : un bout de grille ne déborde jamais sur la feuille
        voisine, faute de quoi la coupe tomberait en pleine carte.
        """
        libre = self.panel_free_mm(index)
        borne = clamp_offset_mm((x_mm, y_mm), libre)
        if self.panel_offsets.get(index) == borne:
            return
        self.set_layout(panel_offsets={**self.panel_offsets, index: borne})

    def center_panels(self) -> None:
        """Pose chaque morceau au milieu de sa feuille.

        ⚠️ **Les feuilles vides sont laissées de côté.** Une feuille qui ne
        porte aucune carte : la dernière, quand la grille s'arrête avant, n'a
        rien à centrer, et lui inventer une position la ferait compter parmi
        les feuilles déplacées.
        """
        places = {}
        for index in range(self.panel_count()):
            if not self.panel_carries_cards(index):
                continue
            libre = self.panel_free_mm(index)
            places[index] = (libre[0] / 2, libre[1] / 2)
        if places != self.panel_offsets:
            self.set_layout(panel_offsets=places)

    def panels_are_centred(self) -> bool:
        """Vrai si chaque morceau est déjà au milieu de sa feuille."""
        for index in range(self.panel_count()):
            if not self.panel_carries_cards(index):
                continue
            libre = self.panel_free_mm(index)
            pose = self.panel_position_mm(index)
            if (abs(pose[0] - libre[0] / 2) > 0.05
                    or abs(pose[1] - libre[1] / 2) > 0.05):
                return False
        return True

    def panel_carries_cards(self, index: int) -> bool:
        """Cette feuille porte-t-elle au moins une carte ?"""
        geometrie = self.panel_geometry()
        ligne, colonne = divmod(index, max(1, self.panels))
        return bool(cards_on_panel(self.cols, geometrie.per_panel, colonne)
                    and cards_on_panel(self.rows, geometrie.rows_per_panel,
                                       ligne))

    def panel_geometry(self):
        """La géométrie des cartes pour la mise en page courante."""
        aspect = 713 / 984
        if self.card_set and self.card_set.full_size[1]:
            aspect = self.card_set.full_size[0] / self.card_set.full_size[1]
        return grid_geometry(
            self.paper_mm(), self.panels, max(1, self.cols), max(1, self.rows),
            aspect, self.dpi, self.card_width_mm, self.card_gap_mm,
            self.panel_rows)

    def panel_of(self, row: int, col: int) -> int:
        """La feuille qui porte cette case, lue de gauche à droite.

        ⚠️ **Un seul endroit le calcule côté écran.** Le dessin, la saisie à la
        souris et la place libre s'accordaient chacun de leur côté sur la même
        division : trois occasions de diverger pour une formule de deux lignes.
        """
        geometrie = self.panel_geometry()
        return ((row // max(1, geometrie.rows_per_panel)) * self.panels
                + col // max(1, geometrie.per_panel))

    def panel_free_mm(self, index: int) -> tuple[float, float]:
        """Place libre autour du bout de grille d'une feuille, en millimètres."""
        geometrie = self.panel_geometry()
        ligne, colonne = divmod(index, max(1, self.panels))
        paper_w, paper_h = self.paper_mm()
        en_mm = MM_PER_INCH / self.dpi

        def libre(total, par_feuille, rang, taille, papier):
            combien = cards_on_panel(total, par_feuille, rang)
            occupe = (combien * taille
                      + max(0, combien - 1) * geometrie.gap) * en_mm
            return max(0.0, papier - occupe)

        return (libre(self.cols, geometrie.per_panel, colonne,
                      geometrie.card_w, paper_w),
                libre(self.rows, geometrie.rows_per_panel, ligne,
                      geometrie.card_h, paper_h))

    def panel_default_mm(self, index: int) -> tuple[float, float]:
        """Où se pose ce bout de grille quand on n'y a pas touché.

        Calé à gauche, et centré en hauteur tant qu'il n'y a qu'une ligne de
        feuilles : la même règle qu'à l'export, d'où la lecture de la place
        libre plutôt qu'un calcul refait à côté.
        """
        if self.panel_rows > 1:
            return (0.0, 0.0)
        return (0.0, self.panel_free_mm(index)[1] / 2)

    def panel_position_mm(self, index: int) -> tuple[float, float]:
        """Où ce bout de grille se trouve : déplacé s'il l'a été, défaut sinon."""
        return self.panel_offsets.get(index, self.panel_default_mm(index))

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

        touched = False
        for name, value in changes.items():
            if getattr(self, name) != value:
                setattr(self, name, value)
                touched = True
        if not touched:
            return

        if grid_changed:
            # Les positions choisies à la main n'ont plus de sens sur une autre
            # grille : elles tomberaient à des endroits qui ne veulent plus rien
            # dire, quand elles ne sortiraient pas carrément du cadre.
            self._empty_cells = []
        if not moved and self.panel_offsets:
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

        touched = False
        for name, value in changes.items():
            if getattr(self, name) != value:
                setattr(self, name, value)
                touched = True
        if not touched:
            return

        # L'épaisseur des bandes change les signatures : sans recalcul, le score
        # reposerait sur des mesures périmées.
        if strip_changed and self.card_set:
            self.card_set.recalculate_features(self.strip_size)
        self.algorithm_changed.emit()

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
