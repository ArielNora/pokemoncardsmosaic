"""Liens entre cartes : des blocs qui doivent rester côte à côte.

Un lien regroupe deux cartes ou plus, maintenues adjacentes horizontalement. Son
**ordre est optionnel** : imposé, la séquence saisie est respectée à la lettre (utile
quand le sens a une signification, comme Solgaleo puis Lunala) ; libre, l'optimiseur
peut retourner le bloc et dispose donc de deux fois plus de placements possibles.

Les liens vivent dans une bibliothèque indépendante des préréglages : un lien est un
travail durable, un préréglage est un essai de mise en page. Voir SPEC.md §3.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

# Liens fournis d'office : ces cartes vont par paires dans un sens qui a un sens.
# Décrits par fragments de chemin, parce que les indices dépendent du dossier chargé.
DEFAULT_PAIRS = (
    ("serie_A/6_gardiens_astraux/solgaleo.png",
     "serie_A/6_gardiens_astraux/lunala.png"),
    ("serie_A/10_source_secrete/entei.png",
     "serie_A/10_source_secrete/raikou.png"),
)


@dataclass(frozen=True)
class Link:
    """Un groupe de cartes à garder côte à côte.

    `cards` contient des indices de cartes, dans l'ordre souhaité.
    `ordered` : si faux, l'optimiseur peut inverser le bloc.
    `enabled` : un lien désactivé est ignoré sans être supprimé.
    """

    cards: tuple[int, ...]
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

    def reversed_cards(self) -> tuple[int, ...]:
        return tuple(reversed(self.cards))


@dataclass
class LinkLibrary:
    """La collection de liens, indépendante de toute mise en page."""

    links: list[Link] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.links)

    def __iter__(self):
        return iter(self.links)

    @property
    def active(self) -> list[Link]:
        return [link for link in self.links if link.enabled]

    def add(self, link: Link) -> None:
        """Ajoute un lien, en refusant qu'une carte appartienne à deux liens actifs."""
        self.check_free(link)
        self.links.append(link)

    def remove(self, link: Link) -> None:
        del self.links[self.position_of(link)]

    def replace(self, old: Link, new: Link) -> None:
        """Remplace un lien par une version modifiée, à la même place dans la liste.

        Le lien remplacé est retiré **avant** la validation : sinon il se
        déclarerait en conflit avec lui-même dès qu'on ne change que son nom ou
        son ordre, et aucune modification ne serait possible.
        """
        position = self.position_of(old)
        del self.links[position]
        try:
            self.check_free(new)
        except ValueError:
            self.links.insert(position, old)
            raise
        self.links.insert(position, new)

    def position_of(self, link: Link) -> int:
        """Position de **cet objet-là**, pas d'un lien qui lui ressemble.

        `list.index` et `list.remove` comparent par égalité, et `Link` est un
        dataclass gelé : deux liens désactivés portant les mêmes cartes sont
        indiscernables. Modifier ou supprimer le second agirait sur le premier,
        et l'interface montrerait une ligne cochée pendant qu'une autre change.
        """
        for position, existing in enumerate(self.links):
            if existing is link:
                return position
        raise ValueError(f"Lien absent de la bibliothèque : {link.cards}")

    def check_free(self, link: Link) -> None:
        """Vérifie qu'aucune carte du lien n'est déjà prise par un lien actif."""
        if not link.enabled:
            # Un lien désactivé ne réserve rien : deux liens contradictoires
            # peuvent coexister tant qu'un seul est actif.
            return
        overlap = self.claimed_cards().intersection(link.cards)
        if overlap:
            raise ValueError(
                f"Ces cartes appartiennent déjà à un lien actif : {sorted(overlap)}"
            )

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

    def remapped(self, mapping: dict) -> "LinkLibrary":
        """Traduit les indices des liens selon `mapping` (ancien -> nouveau).

        Indispensable en même temps que `CardSet.subset()`, qui renumérote les
        cartes de 0 à n-1 : sans cette traduction, un lien continue de désigner
        d'anciens indices qui pointent désormais sur d'autres cartes. La grille
        collerait alors deux cartes que l'utilisateur n'a jamais liées, sans qu'aucune
        erreur ne le signale.

        Les liens dont une carte a disparu du mapping sont écartés : ils ne sont
        plus applicables.
        """
        translated = []
        for link in self.links:
            if not all(index in mapping for index in link.cards):
                continue
            translated.append(
                Link(cards=tuple(mapping[index] for index in link.cards),
                     ordered=link.ordered, enabled=link.enabled, name=link.name)
            )
        return LinkLibrary(translated)

    def to_groups(self) -> list[tuple[int, ...]]:
        """Les blocs actifs, sous la forme attendue par l'optimiseur."""
        return [link.cards for link in self.active]

    def group_map(self) -> dict[int, Link]:
        """Table carte -> lien, pour retrouver le bloc d'une carte en O(1)."""
        return {idx: link for link in self.active for idx in link.cards}


def resolve_links(
    library: LinkLibrary,
    finder,
    pairs: Sequence[Sequence[str]],
    ordered: bool = True,
) -> list[str]:
    """Ajoute des liens décrits par fragments de chemin, en signalant les manquants.

    `finder` prend un fragment et renvoie un indice de carte ou None.
    Renvoie la liste des fragments introuvables, pour information.
    """
    missing: list[str] = []
    for pair in pairs:
        indices = [finder(fragment) for fragment in pair]
        if all(idx is not None for idx in indices):
            library.add(Link(cards=tuple(indices), ordered=ordered))
        else:
            missing.extend(f for f, idx in zip(pair, indices, strict=True) if idx is None)
    return missing
