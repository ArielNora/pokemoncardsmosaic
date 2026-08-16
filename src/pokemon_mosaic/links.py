"""Liens entre cartes : des blocs qui doivent rester côte à côte.

Un lien regroupe deux cartes ou plus, maintenues adjacentes horizontalement. Son
**ordre est optionnel** : imposé, la séquence saisie est respectée à la lettre (utile
quand le sens a une signification, comme Solgaleo puis Lunala) ; libre, l'optimiseur
peut retourner le bloc et dispose donc de deux fois plus de placements possibles.

Les liens vivent dans une bibliothèque indépendante des préréglages : un lien est un
travail durable, un préréglage est un essai de mise en page. Voir SPEC.md §3.
"""

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


@dataclass(frozen=True)
class Link:
    """Un groupe de cartes à garder côte à côte.

    `cards` contient des indices de cartes, dans l'ordre souhaité.
    `ordered` : si faux, l'optimiseur peut inverser le bloc.
    `enabled` : un lien désactivé est ignoré sans être supprimé.
    """

    cards: Tuple[int, ...]
    ordered: bool = True
    enabled: bool = True
    name: str = ""

    def __post_init__(self):
        if len(self.cards) < 2:
            raise ValueError("Un lien doit regrouper au moins deux cartes.")
        if len(set(self.cards)) != len(self.cards):
            raise ValueError(f"Une carte est répétée dans le lien : {self.cards}")

    def __len__(self) -> int:
        return len(self.cards)

    def reversed_cards(self) -> Tuple[int, ...]:
        return tuple(reversed(self.cards))


@dataclass
class LinkLibrary:
    """La collection de liens, indépendante de toute mise en page."""

    links: List[Link] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.links)

    def __iter__(self):
        return iter(self.links)

    @property
    def active(self) -> List[Link]:
        return [link for link in self.links if link.enabled]

    def add(self, link: Link) -> None:
        """Ajoute un lien, en refusant qu'une carte appartienne à deux liens actifs."""
        if link.enabled:
            claimed = self.claimed_cards()
            overlap = claimed.intersection(link.cards)
            if overlap:
                raise ValueError(
                    f"Ces cartes appartiennent déjà à un lien actif : {sorted(overlap)}"
                )
        self.links.append(link)

    def remove(self, link: Link) -> None:
        self.links.remove(link)

    def claimed_cards(self) -> set:
        """Toutes les cartes engagées dans un lien actif."""
        return {idx for link in self.active for idx in link.cards}

    def for_cards(self, available: Iterable[int]) -> "LinkLibrary":
        """Ne garde que les liens dont **toutes** les cartes sont encore présentes.

        Un lien dont une carte a été retirée de la sélection est inapplicable : il est
        écarté silencieusement plutôt que de faire échouer la génération.
        """
        available = set(available)
        return LinkLibrary(
            [link for link in self.links if available.issuperset(link.cards)]
        )

    def to_groups(self) -> List[Tuple[int, ...]]:
        """Les blocs actifs, sous la forme attendue par l'optimiseur."""
        return [link.cards for link in self.active]

    def group_map(self) -> Dict[int, Link]:
        """Table carte -> lien, pour retrouver le bloc d'une carte en O(1)."""
        return {idx: link for link in self.active for idx in link.cards}


def resolve_links(
    library: LinkLibrary,
    finder,
    pairs: Sequence[Sequence[str]],
    ordered: bool = True,
) -> List[str]:
    """Ajoute des liens décrits par fragments de chemin, en signalant les manquants.

    `finder` prend un fragment et renvoie un indice de carte ou None.
    Renvoie la liste des fragments introuvables, pour information.
    """
    missing: List[str] = []
    for pair in pairs:
        indices = [finder(fragment) for fragment in pair]
        if all(idx is not None for idx in indices):
            library.add(Link(cards=tuple(indices), ordered=ordered))
        else:
            missing.extend(f for f, idx in zip(pair, indices) if idx is None)
    return missing
