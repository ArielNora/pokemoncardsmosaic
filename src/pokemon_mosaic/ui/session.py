"""État partagé entre les étapes de l'assistant.

Une seule source de vérité : les écrans lisent et modifient cet objet, et se
préviennent par signaux. Rien n'est recalculé en double d'un écran à l'autre.
"""

import os
from typing import Dict, List, Optional, Set

from PySide6.QtCore import QObject, Signal

from ..cards import CardSet
from ..links import Link, LinkLibrary


class Session(QObject):
    """Ce que l'utilisateur a choisi jusqu'ici."""

    loading_started = Signal()
    cards_added = Signal(list)      # indices des cartes qui viennent d'arriver
    cards_loaded = Signal()         # chargement terminé
    selection_changed = Signal()
    links_changed = Signal()

    def __init__(self):
        super().__init__()
        self.card_set: Optional[CardSet] = None
        self.data_dir: Optional[str] = None
        self._excluded: Set[int] = set()
        self._folder_of: Dict[int, str] = {}
        self.links = LinkLibrary()

    # --- Cartes -----------------------------------------------------------

    def start_loading(self, data_dir: str) -> None:
        """Vide la session et prépare l'arrivée des cartes, dossier par dossier."""
        self.data_dir = data_dir
        self.card_set = CardSet(cards=[], full_size=(0, 0), thumb_size=(0, 0))
        self._excluded.clear()
        self._folder_of.clear()
        self.loading_started.emit()
        self.selection_changed.emit()

    def append_cards(self, cards) -> None:
        """Ajoute un lot de cartes déjà chargées, en conservant leurs indices."""
        if not cards:
            return
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
        """Fixe les dimensions définitives une fois tout chargé."""
        self.card_set.full_size = card_set.full_size
        self.card_set.thumb_size = card_set.thumb_size
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

    def toggle(self, index: int) -> None:
        self.set_excluded([index], index not in self._excluded)

    def selected_indices(self) -> List[int]:
        if not self.card_set:
            return []
        return [c.index for c in self.card_set if c.index not in self._excluded]

    # --- Dossiers ---------------------------------------------------------

    def folders(self) -> List[str]:
        """Dossiers rencontrés, en chemin relatif à la racine, triés."""
        return sorted(set(self._folder_of.values()))

    def indices_in_folder(self, folder: str) -> List[int]:
        return [i for i, f in self._folder_of.items() if f == folder]

    def folder_of(self, index: int) -> str:
        return self._folder_of.get(index, "")

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
