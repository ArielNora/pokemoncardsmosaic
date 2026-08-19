"""Projections chiffrées affichées à côté des réglages sans aperçu visuel.

Certains réglages n'ont rien à montrer — on ne dessine pas un nombre d'itérations.
On peut en revanche annoncer leur conséquence, ce qui reste plus utile qu'un champ
nu. Voir SPEC.md §5.

Les repères viennent de mesures sur le jeu de référence (280 cartes, grille 20×14) :
ce sont des ordres de grandeur, pas des garanties.
"""

from bisect import bisect_left

# Débits mesurés, en tentatives par seconde. Le recuit est un peu plus lent : il
# accepte bien plus d'échanges, et chaque acceptation coûte une écriture.
RATE_STRICT = 127_000
RATE_ANNEALING = 120_000

# Part du score initial effacée, mesurée aux itérations indiquées (SPEC.md §5).
GAIN_STRICT = [(50_000, 0.563), (200_000, 0.595), (1_000_000, 0.610)]
GAIN_ANNEALING = [(50_000, 0.594), (200_000, 0.648), (1_000_000, 0.675)]

# Bornes du taux d'acceptation observées. Une valeur unique serait trompeuse : le
# taux s'effondre en cours de calcul (19 % au départ, 0,3 % à la fin) et dépend du
# jeu de cartes. Mesuré entre 0,00065 (60 cartes, 200 k, descente stricte) et
# 0,0027 (280 cartes, 300 k) ; le recuit est bien plus stable.
ACCEPTANCE_STRICT = (0.0005, 0.003)
ACCEPTANCE_ANNEALING = (0.07, 0.10)


def estimated_seconds(iterations: int, annealing: bool) -> float:
    rate = RATE_ANNEALING if annealing else RATE_STRICT
    return max(0.0, iterations / rate)


def estimated_gain(iterations: int, annealing: bool) -> float:
    """Part du score initial qu'on peut espérer effacer, entre 0 et 1.

    Interpolation linéaire entre les points mesurés, prolongée à plat au-delà :
    la courbe est un plateau, promettre mieux serait trompeur.
    """
    table = GAIN_ANNEALING if annealing else GAIN_STRICT
    if iterations <= table[0][0]:
        # En deçà du premier point mesuré, on garde la proportionnalité au gain
        # très rapide du début : 30 % du total tombe dans les 1000 premières.
        return table[0][1] * min(1.0, iterations / table[0][0]) ** 0.25
    if iterations >= table[-1][0]:
        return table[-1][1]

    position = bisect_left([point[0] for point in table], iterations)
    (x0, y0), (x1, y1) = table[position - 1], table[position]
    return y0 + (y1 - y0) * (iterations - x0) / (x1 - x0)


def estimated_snapshots(iterations: int, every: int, annealing: bool,
                        maximum: int | None = 70) -> tuple[int, int]:
    """Fourchette du nombre de clichés attendus dans la timeline.

    Une valeur unique ne peut pas être honnête ici : le nombre de clichés dépend du
    nombre d'échanges *retenus*, dont le taux varie d'un facteur cinq selon le jeu
    de cartes et l'avancement du calcul. Une projection fausse informerait moins
    bien qu'une fourchette large.

    L'élagage est pris en compte : au-delà de `maximum`, la timeline jette un
    cliché sur deux, donc le compte final se situe entre la moitié et le plafond.
    """
    if every <= 0:
        return (0, 0)

    low_rate, high_rate = ACCEPTANCE_ANNEALING if annealing else ACCEPTANCE_STRICT
    low = int(iterations * low_rate / every) + 1
    high = int(iterations * high_rate / every) + 1

    if maximum is None:
        return (low, high)

    # Si même la borne basse dépasse le plafond, l'élagage est certain : le compte
    # tombe entre la moitié du plafond et le plafond.
    if low > maximum:
        return (maximum // 2 + 1, maximum)
    return (low, min(high, maximum))


def format_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.0f} s"
    minutes, rest = divmod(int(seconds), 60)
    return f"{minutes} min {rest:02d} s"
