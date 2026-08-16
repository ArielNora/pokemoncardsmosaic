"""Construction et optimisation de la grille.

Trois contraintes cohabitent :

- les **liens** maintiennent des cartes côte à côte, en bloc indivisible ;
- un lien **sans ordre imposé** peut être retourné par l'optimiseur ;
- les **cases vides** sont figées : jamais déplacées, jamais recouvertes.
"""

import random
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from .cards import CardSet
from .grid import calculate_grid_dims
from .links import Link, LinkLibrary
from .scoring import EMPTY, EdgeDistances, grid_score, local_score

Cell = Tuple[int, int]

# Probabilité de tenter un retournement sur place plutôt qu'un déplacement, quand la
# carte tirée appartient à un lien sans ordre imposé.
FLIP_PROBABILITY = 0.25


@dataclass
class OptimizationResult:
    """Ce que rapporte une passe d'optimisation."""

    accepted: int
    attempted: int

    @property
    def acceptance_rate(self) -> float:
        return self.accepted / self.attempted if self.attempted else 0.0


def _locate_block(
    grid: np.ndarray, row: int, col: int, card: int, link: Link
) -> Optional[Tuple[int, Tuple[int, ...]]]:
    """Retrouve la position et l'orientation courante d'un bloc dans la grille.

    Un lien sans ordre imposé peut avoir été retourné : on essaie les deux
    orientations et on renvoie celle qui correspond réellement à la grille.
    """
    cols = grid.shape[1]
    orientations = [link.cards]
    if not link.ordered:
        orientations.append(link.reversed_cards())

    for sequence in orientations:
        head = col - sequence.index(card)
        if head < 0 or head + len(sequence) > cols:
            continue
        if all(grid[row, head + k] == value for k, value in enumerate(sequence)):
            return head, sequence
    return None


def _validate_links(grid: np.ndarray, links: Dict[int, Link]) -> None:
    """Vérifie que chaque lien est déjà intact dans la grille de départ.

    L'optimiseur ne sait que **préserver** un bloc, pas le reconstituer : une carte
    liée dont le bloc est rompu ne serait jamais rapprochée de ses voisines, et la
    contrainte serait violée en silence jusqu'à l'image finale. Mieux vaut refuser
    tout de suite.
    """
    for link in {id(l): l for l in links.values()}.values():
        found = np.argwhere(np.isin(grid, link.cards))
        if len(found) != len(link.cards):
            raise ValueError(
                f"Lien {link.cards} : {len(found)} carte(s) trouvée(s) dans la grille "
                f"sur {len(link.cards)} attendues."
            )
        row, col = found[0]
        if _locate_block(grid, int(row), int(col), int(grid[row, col]), link) is None:
            raise ValueError(
                f"Lien {link.cards} : les cartes ne sont pas contiguës dans la grille "
                f"de départ. Utilisez build_initial_grid pour la construire."
            )


def _try_flip_in_place(
    grid: np.ndarray, cells: List[Cell], sequence: Tuple[int, ...],
    distances: EdgeDistances,
) -> bool:
    """Retourne un bloc sur place et ne garde le retournement que s'il améliore."""
    before = local_score(cells, grid, distances)
    flipped = tuple(reversed(sequence))

    for k, (r, c) in enumerate(cells):
        grid[r, c] = flipped[k]

    if local_score(cells, grid, distances) < before:
        return True

    for k, (r, c) in enumerate(cells):
        grid[r, c] = sequence[k]
    return False


def optimize_grid(
    grid: np.ndarray,
    distances: EdgeDistances,
    links: Optional[Dict[int, Link]] = None,
    iterations: int = 50000,
    rng: Optional[random.Random] = None,
) -> OptimizationResult:
    """Descente par échanges aléatoires (hill climbing strict).

    À chaque tour : on tire une case au hasard, on identifie l'objet qui s'y trouve
    (une carte seule, ou le bloc entier auquel elle appartient), on tente de le
    déplacer vers une zone tirée au hasard, et on annule si le score local ne
    s'améliore pas. Aucun coup perdant n'est jamais accepté.

    `grid` est modifiée sur place. Le **nombre d'échanges retenus** rapporté est ce
    qui cadence les snapshots de la timeline — pas le nombre de tentatives, dont le
    taux de réussite s'effondre de 19 % à 0,3 % au fil du calcul (SPEC.md §5).
    """
    links = links or {}
    rng = rng or random
    rows, cols = grid.shape
    accepted = 0

    if links:
        _validate_links(grid, links)

    for _ in range(iterations):
        # 1. Objet source : une carte seule, ou le bloc auquel elle appartient.
        r1, c1 = rng.randrange(rows), rng.randrange(cols)
        card = int(grid[r1, c1])
        if card == EMPTY:
            continue

        link = links.get(card)
        if link is not None:
            located = _locate_block(grid, r1, c1, card, link)
            if located is None:
                continue
            head, sequence = located
            source = [(r1, head + k) for k in range(len(sequence))]

            # Un bloc libre de son sens peut simplement se retourner sur place.
            if not link.ordered and rng.random() < FLIP_PROBABILITY:
                if _try_flip_in_place(grid, source, sequence, distances):
                    accepted += 1
                continue
        else:
            sequence = (card,)
            source = [(r1, c1)]

        width = len(sequence)

        # 2. Zone cible, de même largeur, sans chevauchement avec la source.
        r2, c2 = rng.randrange(rows), rng.randrange(cols)
        if c2 + width > cols:
            continue
        target = [(r2, c2 + k) for k in range(width)]
        if any(cell in source for cell in target):
            continue

        # La cible ne doit contenir que des cartes libres : on ne casse pas un autre
        # bloc, et on ne recouvre jamais une case vide figée.
        occupants: List[int] = []
        for r, c in target:
            value = int(grid[r, c])
            if value == EMPTY or value in links:
                break
            occupants.append(value)
        else:
            if _try_move(grid, source, target, sequence, occupants, link, distances):
                accepted += 1

    return OptimizationResult(accepted=accepted, attempted=iterations)


def _try_move(
    grid: np.ndarray,
    source: List[Cell],
    target: List[Cell],
    sequence: Tuple[int, ...],
    occupants: List[int],
    link: Optional[Link],
    distances: EdgeDistances,
) -> bool:
    """Tente de déplacer un objet vers la zone cible, en testant les orientations.

    Un lien sans ordre imposé est essayé dans les deux sens, et le meilleur est
    retenu — c'est ce qui double le nombre de placements possibles.
    """
    # Les deux zones sont évaluées en un seul appel : la couture qui les sépare,
    # lorsqu'elles sont adjacentes, n'est ainsi comptée qu'une fois.
    cells = source + target
    before = local_score(cells, grid, distances)

    candidates = [sequence]
    if link is not None and not link.ordered:
        candidates.append(tuple(reversed(sequence)))

    def place(order: Tuple[int, ...]) -> None:
        for k, (r, c) in enumerate(target):
            grid[r, c] = order[k]
        for k, (r, c) in enumerate(source):
            grid[r, c] = occupants[k]

    def restore() -> None:
        for k, (r, c) in enumerate(source):
            grid[r, c] = sequence[k]
        for k, (r, c) in enumerate(target):
            grid[r, c] = occupants[k]

    best_score, best_order = before, None
    for order in candidates:
        place(order)
        score = local_score(cells, grid, distances)
        if score < best_score:
            best_score, best_order = score, order
        restore()

    if best_order is None:
        return False
    place(best_order)
    return True


def build_initial_grid(
    cards: CardSet,
    shape: Optional[Tuple[int, int]] = None,
    links: Optional[LinkLibrary] = None,
    empty_cells: Sequence[Cell] = (),
    rng: Optional[random.Random] = None,
) -> np.ndarray:
    """Pose les cases vides, puis les blocs imposés, puis les cartes libres.

    `shape` est (colonnes, lignes). Sans `shape`, la grille est déduite de la
    factorisation du nombre de cartes — comportement de la ligne de commande.
    """
    rng = rng or random
    cols, rows = shape or calculate_grid_dims(len(cards))
    grid = np.full((rows, cols), EMPTY, dtype=int)

    # 1. Cases vides : elles sont figées, donc réservées avant tout le reste.
    reserved = set()
    for r, c in empty_cells:
        if not (0 <= r < rows and 0 <= c < cols):
            raise ValueError(f"Case vide hors grille : ({r}, {c})")
        reserved.add((r, c))

    groups = links.to_groups() if links else []
    capacity = rows * cols - len(reserved)
    if len(cards) > capacity:
        raise ValueError(
            f"{len(cards)} cartes pour seulement {capacity} cases disponibles "
            f"({rows}×{cols} moins {len(reserved)} vides)."
        )

    # 2. Blocs imposés, posés à la suite en sautant les cases réservées.
    used = set()
    r = c = 0
    for group in groups:
        placed = False
        while r < rows and not placed:
            if c + len(group) > cols:
                r, c = r + 1, 0
                continue
            span = [(r, c + k) for k in range(len(group))]
            if any(cell in reserved for cell in span):
                c += 1
                continue
            for k, idx in enumerate(group):
                grid[r, c + k] = idx
                used.add(idx)
            c += len(group)
            placed = True

    # 3. Cartes libres dans les cases restantes, en ordre aléatoire.
    available = [card.index for card in cards if card.index not in used]
    rng.shuffle(available)
    for r in range(rows):
        for c in range(cols):
            if (r, c) in reserved:
                continue
            if grid[r, c] == EMPTY and available:
                grid[r, c] = available.pop()

    return grid


def generate_grid(
    cards: CardSet,
    links: Optional[LinkLibrary] = None,
    iterations: int = 500000,
    shape: Optional[Tuple[int, int]] = None,
    empty_cells: Sequence[Cell] = (),
    rng: Optional[random.Random] = None,
) -> np.ndarray:
    """Construit la grille, l'optimise, et rend compte de la progression."""
    if not len(cards):
        return np.array([])

    distances = EdgeDistances(cards.cards)
    print(f"Matrices de distances : {distances.nbytes / 1024 / 1024:.1f} Mo")

    grid = build_initial_grid(cards, shape, links, empty_cells, rng)
    print(f"--- Grille : {grid.shape[1]}x{grid.shape[0]} ---")
    if empty_cells:
        print(f"Cases vides figées : {len(empty_cells)}")
    print(f"Score initial : {grid_score(grid, distances):.2f}")

    link_map = links.group_map() if links else {}
    result = optimize_grid(grid, distances, link_map, iterations, rng)

    print(f"Échanges retenus : {result.accepted} "
          f"({result.acceptance_rate * 100:.2f} % des tentatives)")
    print(f"Score final   : {grid_score(grid, distances):.2f}")
    return grid
