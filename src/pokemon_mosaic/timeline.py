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

from collections.abc import Callable
from dataclasses import dataclass, field

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
    max_snapshots: int | None = 70
    snapshots: list[Snapshot] = field(default_factory=list)
    # Dégradation moyenne mesurée sur la grille **de départ**, à la première
    # passe. Une prolongation la réutilise au lieu de remesurer : mesurer sur une
    # grille déjà optimisée donne une valeur bien plus haute — température ×3,6 —,
    # parce qu'un échange au hasard y dégrade davantage le score. Remettre ainsi
    # le recuit à chaud défait une partie du travail acquis.
    #
    # C'est la **dégradation** qui est gardée, et non la température qu'on en
    # tire : la température encode aussi le taux d'acceptation, et la mémoriser
    # ferait ignorer un taux modifié entre deux passes.
    mean_penalty: float | None = None
    # Appelé à chaque cliché enregistré. Un simple rappel, pas un signal Qt : le
    # cœur doit rester utilisable sans interface. C'est à l'appelant de faire le
    # pont s'il vit dans un autre fil.
    on_record: Callable[[Snapshot], None] | None = None
    _next_at: int = 0
    # Cadence demandée à la construction. `every` grossit à chaque élagage ;
    # celle-ci ne bouge pas, et sert à repartir d'un cliché sans hériter d'une
    # cadence calculée pour une timeline bien plus longue.
    _every_0: int = field(init=False, repr=False, default=0)

    def __post_init__(self):
        self._every_0 = self.every

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
        if self.on_record is not None:
            self.on_record(snapshot)
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
    ) -> Snapshot | None:
        """Enregistre si assez d'échanges ont été retenus depuis le dernier cliché."""
        if accepted < self._next_at:
            return None
        return self.record(grid, iteration, accepted, score, elapsed)

    def truncate_after(self, index: int) -> None:
        """Jette les clichés postérieurs à `index`, pour repartir de celui-là.

        L'avenir abandonné n'a plus de sens une fois qu'on relance le calcul
        depuis un état antérieur : le garder ferait une timeline dont la seconde
        moitié ne descend pas de la première.
        """
        if not 0 <= index < len(self.snapshots):
            raise IndexError(f"Cliché {index} hors de la timeline "
                             f"({len(self.snapshots)} clichés).")
        self.snapshots = self.snapshots[: index + 1]
        # La cadence redescend à la valeur demandée : la branche repartant d'ici
        # est neuve et courte, et garder l'intervalle grossi par les élagages
        # d'une timeline dix fois plus longue n'y laisserait presque aucun cliché.
        self.every = self._every_0
        self._next_at = self.snapshots[-1].accepted + self.every

    def best(self) -> Snapshot | None:
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
