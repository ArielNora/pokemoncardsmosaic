"""Timeline : les états successifs de la grille, pour naviguer pendant le calcul.

Un snapshot n'est **pas une image** mais la grille d'indices qui la décrit : ~600
octets au lieu de plusieurs mégaoctets. On peut donc en garder des milliers sans
purge, et reconstruire l'image à la demande — 5 ms depuis les vignettes, largement
sous le budget de 16 ms d'une image à 60 par seconde.

La cadence se compte en **échanges retenus**, pas en tentatives : le taux
d'acceptation s'effondre de 19 % à 0,3 % au fil du calcul, donc un intervalle
d'itérations régulier écraserait toute la partie intéressante dans le premier cliché.
Voir SPEC.md §5 et §6.
"""

from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np


@dataclass(frozen=True)
class Snapshot:
    """Un état de la grille, avec de quoi le situer dans le calcul."""

    grid: np.ndarray
    iteration: int
    accepted: int
    score: float
    elapsed: float

    @property
    def nbytes(self) -> int:
        return self.grid.nbytes


@dataclass
class Timeline:
    """Les snapshots d'une exécution, cadencés par échanges retenus.

    `every` est le nombre d'échanges retenus entre deux clichés — mais il **s'adapte
    tout seul**, car on ne sait pas à l'avance combien d'échanges seront retenus : une
    descente stricte en accepte ~800 sur un million de tentatives, un recuit simulé
    ~73 000. À cadence fixe, le second produirait 7 348 clichés indiscernables deux à
    deux, pour une timeline inutilisable.

    Dès que `max_snapshots` est dépassé, un cliché sur deux est jeté et l'intervalle
    double. La timeline reste donc bornée **et** régulièrement répartie sur toute la
    durée du calcul, quel que soit l'algorithme.
    """

    every: int = 10
    max_snapshots: Optional[int] = 70
    snapshots: List[Snapshot] = field(default_factory=list)
    _next_at: int = 0

    def __len__(self) -> int:
        return len(self.snapshots)

    def __iter__(self):
        return iter(self.snapshots)

    def __getitem__(self, index: int) -> Snapshot:
        return self.snapshots[index]

    @property
    def nbytes(self) -> int:
        return sum(s.nbytes for s in self.snapshots)

    def record(
        self, grid: np.ndarray, iteration: int, accepted: int,
        score: float, elapsed: float,
    ) -> Snapshot:
        """Enregistre un cliché, en copiant la grille.

        La copie est indispensable : la grille d'origine continue d'être modifiée
        sur place par l'optimisation.
        """
        snapshot = Snapshot(
            grid=grid.astype(np.int16, copy=True),
            iteration=iteration,
            accepted=accepted,
            score=score,
            elapsed=elapsed,
        )
        self.snapshots.append(snapshot)
        self._next_at = accepted + self.every
        if self.max_snapshots is not None and len(self.snapshots) > self.max_snapshots:
            self._thin_out()
        return snapshot

    def _thin_out(self) -> None:
        """Divise la timeline par deux en gardant un cliché sur deux.

        Le premier et le dernier sont toujours conservés : le point de départ et
        l'état courant doivent rester atteignables.
        """
        latest = self.snapshots[-1]
        kept = self.snapshots[::2]
        if kept[-1] is not latest:
            kept.append(latest)
        self.snapshots = kept
        self.every *= 2
        self._next_at = latest.accepted + self.every

    def maybe_record(
        self, grid: np.ndarray, iteration: int, accepted: int,
        score: float, elapsed: float,
    ) -> Optional[Snapshot]:
        """Enregistre si assez d'échanges ont été retenus depuis le dernier cliché."""
        if accepted < self._next_at:
            return None
        return self.record(grid, iteration, accepted, score, elapsed)

    def best(self) -> Optional[Snapshot]:
        """Le cliché au meilleur score — pas forcément le dernier avec un recuit."""
        return min(self.snapshots, key=lambda s: s.score, default=None)

    def summary(self) -> str:
        if not self.snapshots:
            return "Aucun snapshot."
        first, last = self.snapshots[0], self.snapshots[-1]
        return (
            f"{len(self.snapshots)} snapshots, {self.nbytes / 1024:.1f} Ko au total — "
            f"score {first.score:.0f} -> {last.score:.0f} "
            f"sur {last.iteration:,} itérations"
        )
