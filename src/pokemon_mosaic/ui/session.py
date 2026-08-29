"""État partagé entre les étapes de l'assistant.

Une seule source de vérité : les écrans lisent et modifient cet objet, et se
préviennent par signaux. Rien n'est recalculé en double d'un écran à l'autre.
"""

import os
from dataclasses import replace as dataclass_replace

from PySide6.QtCore import QObject, Signal

from ..annealing import Annealing
from ..cards import DEFAULT_STRIP_SIZE, CardSet
from ..layout import DEFAULT_DPI, GridFit, distribute_empty_cells
from ..links import DEFAULT_LINKS, Link, LinkLibrary, resolve_links
from ..optimize import StopConditions
from ..presets import LinkRef, Preset


class Session(QObject):
    """Ce que l'utilisateur a choisi jusqu'ici."""

    # Liste explicite des réglages d'algorithme. Valider par `hasattr` accepterait
    # tout attribut de QObject ou de mise en page : `set_algorithm(dpi=600)`
    # passerait et émettrait `algorithm_changed`, alors que l'aperçu fil de fer
    # n'écoute que `layout_changed` — il n'aurait jamais connaissance du changement.
    ALGORITHM_SETTINGS = frozenset({
        "iterations", "snapshot_every", "empty_colour",
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

    def __init__(self):
        super().__init__()
        self.card_set: CardSet | None = None
        self.data_dir: str | None = None
        self._excluded: set[int] = set()
        self._folder_of: dict[int, str] = {}
        self.links = LinkLibrary()

        # Mise en page (étape 2). Le format d'impression commande : la taille des
        # cartes en pixels s'en déduit, jamais l'inverse.
        self.paper = "A2"
        self.landscape = False
        self.dpi = DEFAULT_DPI
        self.panels = 1
        self.cols = 17
        self.rows = 17
        # Liste ordonnée, pas un ensemble : le rang sert à savoir quel trou céder
        # sa place quand l'utilisateur en pose un nouveau alors que le quota est
        # atteint. Le plus ancien s'efface, façon file d'attente.
        self._empty_cells: list[tuple[int, int]] = []
        self._empty_pinned = False

        # Réglages d'algorithme (étape 3), séparés en « de base » et « avancés ».
        # De base : ce qui se décide par intention.
        self.iterations = 1_000_000
        self.snapshot_every = 10
        self.empty_colour = (255, 255, 255)
        self.stop_on_stagnation = False
        self.stagnation_iterations = 50_000
        self.stop_on_time = False
        self.time_budget = 60.0
        # Avancés : ce qui exige de comprendre le fonctionnement interne.
        self.use_annealing = True
        self.acceptance = 0.5
        self.strip_size = DEFAULT_STRIP_SIZE
        self.stop_on_score = False
        self.target_score = 0.0

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
        """Chargement en un bloc, sans progression — utile aux tests."""
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
        peut le laisser identique — dix cartes dedans, dix dehors. L'écran ne se
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

    def indices_in_folder(self, folder: str) -> list[int]:
        return [i for i, f in self._folder_of.items() if f == folder]

    def folder_of(self, index: int) -> str:
        return self._folder_of.get(index, "")

    # --- Mise en page -----------------------------------------------------

    def set_layout(self, **changes) -> None:
        """Modifie un ou plusieurs réglages de grille et prévient une seule fois."""
        # On compare les valeurs avant de les appliquer : le formulaire renvoie
        # toujours les six réglages d'un bloc, donc tester la seule présence de
        # « cols » effacerait le placement manuel à chaque changement de DPI,
        # de format ou d'orientation.
        grid_changed = (changes.get("cols", self.cols) != self.cols
                        or changes.get("rows", self.rows) != self.rows)

        touched = False
        for name, value in changes.items():
            if getattr(self, name) != value:
                setattr(self, name, value)
                touched = True
        if not touched:
            return

        if grid_changed:
            # Les positions choisies à la main n'ont plus de sens sur une autre
            # grille : on repart d'une répartition automatique.
            self._empty_pinned = False
            self._empty_cells = []
        self.layout_changed.emit()

    def grid_fit(self) -> GridFit:
        return GridFit(cols=self.cols, rows=self.rows,
                       card_count=self.selected_count)

    def empty_cells(self) -> list[tuple[int, int]]:
        """Cases vides à figer : celles posées à la main, sinon la répartition
        automatique. Le nombre suit toujours la grille et la sélection."""
        needed = self.grid_fit().empty_cells
        if not self._empty_pinned:
            return distribute_empty_cells((self.rows, self.cols), needed)

        # On garde les plus récents : ce sont les choix explicites de l'utilisateur.
        pinned = list(self._empty_cells[-needed:]) if needed else []
        if len(pinned) < needed:
            # La sélection a changé et il faut plus de trous : on complète avec la
            # répartition automatique, sans défaire ce qui a été posé à la main.
            for cell in distribute_empty_cells((self.rows, self.cols), needed):
                if len(pinned) >= needed:
                    break
                if cell not in pinned:
                    pinned.append(cell)
        return sorted(pinned)

    def toggle_empty_cell(self, row: int, col: int) -> None:
        """Pose ou retire une case vide à cet emplacement."""
        if not (0 <= row < self.rows and 0 <= col < self.cols):
            return
        if not self._empty_pinned:
            # Premier clic : on fige la répartition automatique avant de la modifier.
            self._empty_cells = list(self.empty_cells())
            self._empty_pinned = True

        cell = (row, col)
        if cell in self._empty_cells:
            self._empty_cells.remove(cell)
        else:
            self._empty_cells.append(cell)
            # Quota atteint : le trou posé il y a le plus longtemps cède sa place,
            # sinon le clic n'aurait aucun effet visible.
            excess = len(self._empty_cells) - self.grid_fit().empty_cells
            if excess > 0:
                del self._empty_cells[:excess]
        self.layout_changed.emit()

    def reset_empty_cells(self) -> None:
        self._empty_pinned = False
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
                "paper": self.paper, "landscape": self.landscape,
                "dpi": self.dpi, "panels": self.panels,
                "cols": self.cols, "rows": self.rows,
                # Seules les cases posées à la main sont mémorisées : la
                # répartition automatique se recalcule, et la figer empêcherait
                # de suivre un changement de grille ou de sélection.
                "empty_cells": ([list(cell) for cell in self._empty_cells]
                                if self._empty_pinned else None),
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
        if "empty_colour" in known:
            known["empty_colour"] = tuple(known["empty_colour"])
        if known:
            self.set_algorithm(**known)

    def _apply_layout(self, layout: dict) -> None:
        cells = layout.get("empty_cells")
        known = {name: value for name, value in layout.items()
                 if name != "empty_cells"}
        if known:
            self.set_layout(**known)
        # Après `set_layout` : changer la grille efface les cases posées à la
        # main, ce qui annulerait celles du préréglage si on les posait avant.
        if cells is None:
            self.reset_empty_cells()
        else:
            self._empty_cells = [tuple(cell) for cell in cells]
            self._empty_pinned = True
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
