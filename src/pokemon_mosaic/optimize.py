"""Construction et optimisation de la grille.

Trois contraintes cohabitent :

- les **liens** maintiennent des cartes côte à côte, en bloc indivisible ;
- un lien **sans ordre imposé** peut être retourné par l'optimiseur ;
- les **cases vides** sont figées : jamais déplacées, jamais recouvertes.
"""

import random
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from .annealing import Annealing
from .cards import CardSet
from .grid import calculate_grid_dims
from .links import Link, LinkLibrary
from .scoring import EMPTY, EdgeDistances, grid_score, local_score
from .timeline import Timeline

Cell = Tuple[int, int]

# Probabilité de tenter un retournement sur place plutôt qu'un déplacement, quand la
# carte tirée appartient à un lien sans ordre imposé.
FLIP_PROBABILITY = 0.25

# Les seuils d'arrêt ne sont vérifiés que tous les N tours : appeler l'horloge à
# 127 000 itérations par seconde coûterait plus cher que l'optimisation elle-même.
CHECK_INTERVAL = 1000


@dataclass
class StopConditions:
    """Les quatre seuils d'arrêt de l'étape 3.

    Tous optionnels : le premier atteint met fin au calcul. `max_iterations` reste la
    borne dure.
    """

    max_iterations: int = 1_000_000
    target_score: Optional[float] = None
    stagnation_iterations: Optional[int] = None
    time_budget: Optional[float] = None

    def check(self, score: float, since_improvement: int, elapsed: float) -> Optional[str]:
        """Renvoie la raison d'arrêter, ou None pour continuer."""
        if self.target_score is not None and score <= self.target_score:
            return "score atteint"
        if self.stagnation_iterations is not None and since_improvement >= self.stagnation_iterations:
            return "stagnation"
        if self.time_budget is not None and elapsed >= self.time_budget:
            return "budget de temps"
        return None


@dataclass
class OptimizationResult:
    """Ce que rapporte une passe d'optimisation."""

    accepted: int
    attempted: int
    initial_score: float
    final_score: float
    stopped_by: str
    elapsed: float

    @property
    def acceptance_rate(self) -> float:
        return self.accepted / self.attempted if self.attempted else 0.0

    @property
    def gain(self) -> float:
        """Part du score initial effacée, entre 0 et 1."""
        if self.initial_score <= 0:
            return 0.0
        return (self.initial_score - self.final_score) / self.initial_score


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
    distances: EdgeDistances, accept,
) -> Optional[float]:
    """Retourne un bloc sur place. Renvoie le delta de score si retenu, sinon None."""
    before = local_score(cells, grid, distances)
    flipped = tuple(reversed(sequence))

    for k, (r, c) in enumerate(cells):
        grid[r, c] = flipped[k]

    delta = local_score(cells, grid, distances) - before
    if accept(delta):
        return delta

    for k, (r, c) in enumerate(cells):
        grid[r, c] = sequence[k]
    return None


def optimize_grid(
    grid: np.ndarray,
    distances: EdgeDistances,
    links: Optional[Dict[int, Link]] = None,
    iterations: int = 50000,
    rng: Optional[random.Random] = None,
    annealing: Optional[Annealing] = None,
    stop: Optional[StopConditions] = None,
    timeline: Optional[Timeline] = None,
) -> OptimizationResult:
    """Optimise la grille par échanges aléatoires.

    À chaque tour : on tire une case au hasard, on identifie l'objet qui s'y trouve
    (une carte seule, ou le bloc entier auquel elle appartient), et on tente de le
    déplacer vers une zone tirée au hasard.

    Sans `annealing`, c'est une **descente stricte** : aucun coup dégradant n'est
    jamais accepté, ce qui fait plafonner le résultat dans un minimum local. Avec
    `annealing`, un coup dégradant passe parfois, avec une probabilité qui décroît au
    fil du calcul — et la **meilleure grille rencontrée** est restituée à la fin,
    puisque l'état courant peut être moins bon qu'un état traversé plus tôt.

    `grid` est modifiée sur place.
    """
    links = links or {}
    rng = rng or random
    stop = stop or StopConditions(max_iterations=iterations)
    rows, cols = grid.shape

    if links:
        _validate_links(grid, links)

    score = grid_score(grid, distances)
    initial_score = score
    best_score, best_grid = score, grid.copy()
    accepted = 0
    last_improvement = 0
    iteration = -1  # défini même si `iterations` vaut 0
    started = time.monotonic()
    stopped_by = "itérations épuisées"

    if annealing is not None:
        temperature_0 = annealing.initial_temperature or annealing.calibrate(
            grid, distances, rng
        )

    def accept(delta: float) -> bool:
        if annealing is None:
            return delta < 0
        temperature = annealing.temperature_at(iteration / iterations, temperature_0)
        return annealing.accepts(delta, temperature, rng)

    if timeline is not None:
        timeline.record(grid, 0, 0, score, 0.0)

    for iteration in range(iterations):
        if iteration % CHECK_INTERVAL == 0:
            reason = stop.check(
                best_score, iteration - last_improvement, time.monotonic() - started
            )
            if reason:
                stopped_by = reason
                break

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
                delta = _try_flip_in_place(grid, source, sequence, distances, accept)
                if delta is not None:
                    accepted += 1
                    score += delta
                    if score < best_score:
                        best_score, last_improvement = score, iteration
                        best_grid = grid.copy()
                    if timeline is not None:
                        timeline.maybe_record(
                            grid, iteration, accepted, score,
                            time.monotonic() - started,
                        )
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
            delta = _try_move(
                grid, source, target, sequence, occupants, link, distances, accept
            )
            if delta is not None:
                accepted += 1
                score += delta
                if score < best_score:
                    best_score, last_improvement = score, iteration
                    best_grid = grid.copy()
                if timeline is not None:
                    timeline.maybe_record(
                        grid, iteration, accepted, score, time.monotonic() - started
                    )

    # Avec un recuit, l'état final peut être moins bon qu'un état traversé : on
    # restitue la meilleure grille rencontrée.
    if best_score < score:
        grid[:] = best_grid

    # Cliché final imposé. Sans lui, la timeline s'arrêterait avant la fin : le recuit
    # accepte beaucoup à chaud et presque plus à froid, donc les derniers échanges
    # n'atteignent jamais le seuil de cadence. L'état finalement retenu — celui que
    # l'utilisateur voudra exporter — serait absent de la timeline.
    if timeline is not None:
        timeline.record(
            grid, iteration + 1, accepted, best_score, time.monotonic() - started
        )

    return OptimizationResult(
        accepted=accepted,
        attempted=iteration + 1,
        initial_score=initial_score,
        final_score=best_score,
        stopped_by=stopped_by,
        elapsed=time.monotonic() - started,
    )


def _try_move(
    grid: np.ndarray,
    source: List[Cell],
    target: List[Cell],
    sequence: Tuple[int, ...],
    occupants: List[int],
    link: Optional[Link],
    distances: EdgeDistances,
    accept,
) -> Optional[float]:
    """Tente de déplacer un objet vers la zone cible, en testant les orientations.

    Un lien sans ordre imposé est essayé dans les deux sens, et le meilleur est
    retenu — c'est ce qui double le nombre de placements possibles.

    Renvoie le delta de score si le déplacement est retenu, sinon None.
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

    # On retient la meilleure orientation disponible, puis on décide séparément si
    # elle est acceptée : avec un recuit, même la meilleure peut être dégradante.
    best_score, best_order = None, None
    for order in candidates:
        place(order)
        score = local_score(cells, grid, distances)
        if best_score is None or score < best_score:
            best_score, best_order = score, order
        restore()

    delta = best_score - before
    if not accept(delta):
        return None
    place(best_order)
    return delta


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
    annealing: Optional[Annealing] = None,
    stop: Optional[StopConditions] = None,
    timeline: Optional[Timeline] = None,
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

    link_map = links.group_map() if links else {}
    result = optimize_grid(
        grid, distances, link_map, iterations, rng, annealing, stop, timeline
    )

    print(f"Score {result.initial_score:.0f} -> {result.final_score:.0f} "
          f"({result.gain * 100:.1f} % de gain)")
    print(f"{result.accepted} échanges retenus sur {result.attempted:,} tentatives "
          f"({result.acceptance_rate * 100:.2f} %) en {result.elapsed:.1f} s")
    print(f"Arrêt : {result.stopped_by}")
    if timeline is not None:
        print(timeline.summary())
    return grid
