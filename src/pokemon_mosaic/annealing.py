"""Recuit simulé : accepter parfois un coup moins bon pour sortir des minima locaux.

La descente stricte n'accepte jamais un échange qui dégrade le score. Mesurée sur les
280 cartes, elle plafonne à ~63 % de gain avec un taux d'acceptation tombé à 0,3 % :
elle est bloquée dans un minimum local. Le recuit accepte un coup dégradant avec la
probabilité `exp(-Δ / T)`, où la température `T` décroît au fil du calcul.

La difficulté pratique est que `T` s'exprime dans l'unité du score, qui n'a aucun sens
pour l'utilisateur. D'où la **calibration automatique** : on échantillonne des échanges
au hasard pour mesurer l'ordre de grandeur des dégradations, et on en déduit une
température de départ. L'utilisateur ne règle qu'une chose lisible — la proportion de
coups dégradants acceptés au début.
"""

import math
import random
from dataclasses import dataclass
from typing import Optional

import numpy as np

from .scoring import EMPTY, EdgeDistances, local_score


@dataclass
class Annealing:
    """Programme de refroidissement.

    `initial_acceptance` : proportion de coups dégradants acceptés au démarrage.
    0,5 signifie « au début, un échange qui dégrade a une chance sur deux de passer ».
    C'est le seul réglage vraiment lisible ; la température en est déduite.

    `final_ratio` : la température finale vaut `final_ratio` fois l'initiale. Plus il
    est petit, plus la fin du calcul ressemble à une descente stricte.
    """

    initial_acceptance: float = 0.5
    final_ratio: float = 0.001
    initial_temperature: Optional[float] = None

    def __post_init__(self):
        if not 0.0 < self.initial_acceptance < 1.0:
            raise ValueError("initial_acceptance doit être strictement entre 0 et 1.")
        if not 0.0 < self.final_ratio < 1.0:
            raise ValueError("final_ratio doit être strictement entre 0 et 1.")

    def calibrate(
        self,
        grid: np.ndarray,
        distances: EdgeDistances,
        rng: random.Random,
        samples: int = 400,
    ) -> float:
        """Déduit la température de départ de l'ampleur typique d'une dégradation.

        On tire des échanges au hasard et on retient la dégradation moyenne. La
        température qui accepte une telle dégradation avec la probabilité `p` vaut
        `Δ / ln(1/p)`.
        """
        rows, cols = grid.shape
        penalties = []

        for _ in range(samples):
            r1, c1 = rng.randrange(rows), rng.randrange(cols)
            r2, c2 = rng.randrange(rows), rng.randrange(cols)
            if (r1, c1) == (r2, c2) or grid[r1, c1] == EMPTY or grid[r2, c2] == EMPTY:
                continue
            cells = [(r1, c1), (r2, c2)]
            before = local_score(cells, grid, distances)
            grid[r1, c1], grid[r2, c2] = grid[r2, c2], grid[r1, c1]
            delta = local_score(cells, grid, distances) - before
            grid[r1, c1], grid[r2, c2] = grid[r2, c2], grid[r1, c1]
            if delta > 0:
                penalties.append(delta)

        if not penalties:
            return 1.0
        mean_penalty = sum(penalties) / len(penalties)
        return mean_penalty / math.log(1.0 / self.initial_acceptance)

    def temperature_at(self, progress: float, initial: float) -> float:
        """Température à l'avancement `progress` (0 au début, 1 à la fin).

        Décroissance géométrique : la température est divisée par le même facteur à
        chaque pas, ce qui laisse beaucoup de temps aux basses températures.
        """
        progress = min(max(progress, 0.0), 1.0)
        return initial * (self.final_ratio ** progress)

    def accepts(self, delta: float, temperature: float, rng: random.Random) -> bool:
        """Un échange dégradant de `delta` passe-t-il à cette température ?"""
        if delta <= 0:
            return True
        if temperature <= 0:
            return False
        # Au-delà de ~700, exp(-x) sous-dépasse : autant répondre non directement.
        exponent = delta / temperature
        if exponent > 700:
            return False
        return rng.random() < math.exp(-exponent)
