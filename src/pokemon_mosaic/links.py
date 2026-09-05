"""Liens entre cartes : des blocs qui doivent rester groupés.

Un lien est un **rectangle plein**, de trois cases de côté au maximum. Une ligne
de trois cartes est un 3×1, une colonne un 1×3, un carré un 2×2 : un seul concept
remplace « horizontal », « vertical » et « groupe ». Voir SPEC.md §10, 2026-08-27.

Son **ordre est optionnel** : imposé, la disposition saisie est respectée à la
lettre (utile quand le sens a une signification, comme Solgaleo puis Lunala) ;
libre, l'optimiseur peut retourner le bloc et dispose donc de deux fois plus de
placements possibles.

Les liens vivent dans une bibliothèque indépendante des préréglages : un lien est un
travail durable, un préréglage est un essai de mise en page. Voir SPEC.md §3.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

# Côté maximal d'un lien. Au-delà, le bloc devient trop gros devant la grille :
# mesuré sur 21×21, un 3×3 garde 361 ancrages possibles contre 399 pour une barre
# de trois : l'optimiseur ne voit pas la différence, là où un 9×9 tombe à 169
# pour 18 % du poster figé d'un coup.
MAX_SIDE = 3

# Les huit formes possibles, en **(colonnes, lignes)**, la convention de
# `build_initial_grid`, pour qu'il n'y en ait qu'une dans tout le code. Le 1×1 est
# exclu : un lien qui ne regroupe qu'une carte ne contraint rien.
SHAPES = tuple(
    (cols, rows)
    for rows in range(1, MAX_SIDE + 1)
    for cols in range(1, MAX_SIDE + 1)
    if cols * rows >= 2
)


def shapes_for(count: int) -> tuple[tuple[int, int], ...]:
    """Formes accueillant exactement `count` cartes, en (colonnes, lignes).

    ⚠️ **Vide pour 5, 7 et 8.** Ces nombres ne se factorisent pas en un rectangle
    d'au plus 3 de côté : 5 et 7 sont premiers et dépassent 3, 8 demanderait un
    côté de 4. L'interface doit le dire au moment de la sélection, plutôt que de
    proposer une liste de formes vide.
    """
    return tuple(shape for shape in SHAPES if shape[0] * shape[1] == count)

@dataclass(frozen=True)
class DefaultLink:
    """Un lien fourni d'office, décrit par **fragments de chemin**.

    Par chemin et non par indice : celui-ci dépend du dossier chargé et du tri,
    et changerait à la première extension ajoutée.
    """

    cards: tuple[str, ...]
    shape: tuple[int, int]


# Ces cartes vont ensemble dans un sens qui a un sens. Les fragments sont donnés
# en **ordre de lecture** du rectangle : de gauche à droite, puis rangée
# suivante, donc de haut en bas pour une colonne.
DEFAULT_LINKS = (
    DefaultLink(("a3-gardiens-celestes/a3-207-solgaleo-ex.webp",
                 "a3-gardiens-celestes/a3-204-lunala-ex.webp"), (2, 1)),
    DefaultLink(("a4a-source-secrete/a4a-087-entei-ex.webp",
                 "a4a-source-secrete/a4a-088-raikou-ex.webp"), (2, 1)),
    # La lignée d'Arcko, dressée : la plus évoluée en haut, comme sur un arbre
    # généalogique. C'est le premier cas d'usage vertical demandé, et ce qui a
    # motivé le passage des liens en rectangles.
    # Gromago-ex au-dessus de Mordudor : la forme évoluée domine, comme la
    # lignée d'Arcko plus bas.
    DefaultLink(("b2a-merveilles-de-paldea/b2a-114-gromago-ex.webp",
                 "b2a-merveilles-de-paldea/b2a-096-mordudor.webp"), (1, 2)),
    DefaultLink(("b3-aura-palpitante/b3-194-mega-jungko-ex.webp",
                 "b3-aura-palpitante/b3-157-massko.webp",
                 "b3-aura-palpitante/b3-156-arcko.webp"), (1, 3)),
)


@dataclass(frozen=True)
class Link:
    """Un rectangle plein de cartes à garder groupées.

    `cards` contient des indices de cartes **dans l'ordre de lecture** du
    rectangle : de gauche à droite, puis rangée suivante.
    `shape` est (colonnes, lignes). Omise, elle vaut une seule rangée.
    `ordered` : si faux, l'optimiseur peut retourner le bloc.
    `enabled` : un lien désactivé est ignoré sans être supprimé.
    """

    cards: tuple[int, ...]
    shape: tuple[int, int] = ()
    ordered: bool = True
    enabled: bool = True
    name: str = ""

    def __post_init__(self):
        if len(self.cards) < 2:
            raise ValueError("Un lien doit regrouper au moins deux cartes.")
        if len(set(self.cards)) != len(self.cards):
            raise ValueError(f"Une carte est répétée dans le lien : {self.cards}")
        if not self.shape:
            # Une seule rangée : c'est ce qu'était tout lien avant les
            # rectangles, donc ce que valent les liens déjà enregistrés.
            object.__setattr__(self, "shape", (len(self.cards), 1))
        cols, rows = self.shape
        if not (1 <= cols <= MAX_SIDE and 1 <= rows <= MAX_SIDE):
            raise ValueError(
                f"Forme {cols}×{rows} : un lien fait au plus {MAX_SIDE} cases "
                f"de côté."
            )
        if cols * rows != len(self.cards):
            raise ValueError(
                f"Forme {cols}×{rows} = {cols * rows} cases pour "
                f"{len(self.cards)} carte(s) : un lien est un rectangle "
                f"**plein**, jamais entamé."
            )

    def __len__(self) -> int:
        return len(self.cards)

    @property
    def cols(self) -> int:
        return self.shape[0]

    @property
    def rows(self) -> int:
        return self.shape[1]

    def offsets(self) -> tuple[tuple[int, int], ...]:
        """Décalages (ligne, colonne) de chaque carte, dans l'ordre de `cards`."""
        cols = self.shape[0]
        return tuple((k // cols, k % cols) for k in range(len(self.cards)))

    def cells_at(self, top: int, left: int) -> list[tuple[int, int]]:
        """Cases occupées si le coin haut-gauche du bloc est en (top, left)."""
        return [(top + dr, left + dc) for dr, dc in self.offsets()]

    def reversed_cards(self) -> tuple[int, ...]:
        """Le bloc tourné d'un demi-tour.

        Inverser la liste **est** la rotation à 180° d'un rectangle lu en ordre
        de lecture : la dernière carte passe en haut à gauche et la première en
        bas à droite. Rien de particulier à écrire pour la 2D, et la forme est
        préservée : un 3×2 retourné reste un 3×2.
        """
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
                     shape=link.shape, ordered=link.ordered,
                     enabled=link.enabled, name=link.name)
            )
        return LinkLibrary(translated)

    def group_map(self) -> dict[int, Link]:
        """Table carte -> lien, pour retrouver le bloc d'une carte en O(1)."""
        return {idx: link for link in self.active for idx in link.cards}


def resolve_links(
    library: LinkLibrary,
    finder,
    defaults: Sequence[DefaultLink],
    ordered: bool = True,
) -> list[str]:
    """Ajoute des liens décrits par fragments de chemin, en signalant les manquants.

    `finder` prend un fragment et renvoie un indice de carte ou None.
    Renvoie la liste des fragments introuvables, pour information.

    Un lien dont **une seule** carte manque est écarté en entier : la forme est
    un rectangle plein, et il n'y a pas de version amputée qui ait un sens.
    """
    missing: list[str] = []
    for default in defaults:
        indices = [finder(fragment) for fragment in default.cards]
        if all(idx is not None for idx in indices):
            library.add(Link(cards=tuple(indices), shape=default.shape,
                             ordered=ordered))
        else:
            missing.extend(f for f, idx in zip(default.cards, indices, strict=True)
                           if idx is None)
    return missing
