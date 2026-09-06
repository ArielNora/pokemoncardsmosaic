"""Le mode caméléon : les vides prennent la couleur de ce qui les borde.

Un écart entre deux cartes n'est plus un aplat mais un **dégradé**, tiré d'un
bord à l'autre. ⚠️ **Pixel par pixel**, et non d'une moyenne à l'autre : le
raccord suit alors les motifs, un ciel reste bleu en face du ciel et l'herbe
verte en face de l'herbe, ce qu'une couleur unique par carte ne saurait faire.

Trois cas, et ce sont tous les cas :

- un écart **vertical**, entre deux cartes côte à côte : chaque rangée de pixels
  relie le pixel du bord droit de la gauche à celui du bord gauche de la droite ;
- un écart **horizontal**, même chose d'une carte à celle du dessous ;
- une **croisée**, le carré où deux écarts se rencontrent : quatre cartes le
  bordent, et ses quatre coins se mélangent en bilinéaire. C'est le seul endroit
  où l'on ne peut pas s'en tirer avec un dégradé à une dimension.

La **bordure** de la grille suit la même idée : une bande large comme l'écart,
qui va du bord de la carte à la couleur du fond.

Les fonctions d'ici ne connaissent que des tableaux de pixels : elles servent
telles quelles à l'aperçu, sur les vignettes, et à l'export, en pleine
résolution.
"""

import numpy as np


def _weights(count: int) -> np.ndarray:
    """Les poids d'un dégradé de `count` pas, du premier bord vers le second.

    Ni 0 ni 1 aux extrémités : le premier pixel de l'écart n'est pas le bord de
    la carte, il vient juste après. Les prendre ferait deux pixels identiques
    côte à côte, et le dégradé paraîtrait décalé d'un cran.
    """
    if count <= 0:
        return np.zeros(0, dtype=np.float32)
    return (np.arange(count, dtype=np.float32) + 1.0) / (count + 1.0)


def gradient_between(start: np.ndarray, end: np.ndarray,
                     count: int, horizontal: bool) -> np.ndarray:
    """Le dégradé qui relie deux lignes de pixels, une par bord.

    `start` et `end` sont des lignes de `(n, 3)` : le bord de la carte d'avant
    et celui de la carte d'après. Rend un tableau `(n, count, 3)` pour un écart
    vertical, `(count, n, 3)` pour un horizontal.
    """
    poids = _weights(count)
    if not len(poids):
        return np.zeros((0, 0, 3), np.uint8)
    depart = start.astype(np.float32)
    arrivee = end.astype(np.float32)
    melange = (depart[:, None, :] * (1.0 - poids)[None, :, None]
               + arrivee[:, None, :] * poids[None, :, None])
    bande = np.clip(melange, 0, 255).astype(np.uint8)
    return bande if horizontal else np.transpose(bande, (1, 0, 2))


def crossing(top_left, top_right, bottom_left, bottom_right,
             width: int, height: int) -> np.ndarray:
    """Le carré d'une croisée, mélangé de ses quatre coins.

    ⚠️ **Quatre cartes s'y touchent.** Un dégradé à une dimension y ferait
    apparaître une couture avec l'écart voisin, qui, lui, tient compte des deux
    autres cartes.
    """
    if width <= 0 or height <= 0:
        return np.zeros((0, 0, 3), np.uint8)
    u = _weights(width)[None, :, None]
    v = _weights(height)[:, None, None]
    coins = [np.asarray(coin, dtype=np.float32).reshape(1, 1, 3)
             for coin in (top_left, top_right, bottom_left, bottom_right)]
    haut = coins[0] * (1 - u) + coins[1] * u
    bas = coins[2] * (1 - u) + coins[3] * u
    return np.clip(haut * (1 - v) + bas * v, 0, 255).astype(np.uint8)


def border_band(edge: np.ndarray, colour, count: int,
                horizontal: bool, outwards: bool) -> np.ndarray:
    """La bande qui va du bord d'une carte à la couleur du fond.

    `outwards` dit le sens : vrai quand la bande s'éloigne de la mosaïque vers
    la droite ou vers le bas, faux quand elle va vers la gauche ou vers le haut.
    Le bord de la carte reste du côté de la mosaïque dans les deux cas.
    """
    fond = np.tile(np.asarray(colour, dtype=np.float32), (len(edge), 1))
    if outwards:
        return gradient_between(edge, fond, count, horizontal)
    return gradient_between(fond, edge, count, horizontal)
