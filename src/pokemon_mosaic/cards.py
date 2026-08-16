"""Chargement des cartes et calcul de leurs signatures de bord.

Architecture : tout le travail se fait sur des **vignettes réduites**. Les images
pleine résolution ne sont relues du disque qu'au moment de l'export. Voir SPEC.md §8.
"""

import os
from dataclasses import dataclass, field
from typing import Iterator, List, Optional, Sequence, Tuple

import numpy as np
from PIL import Image

VALID_EXTENSIONS = (".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff")

# Les mosaïques dépassent la limite anti-décompression-bomb de Pillow.
Image.MAX_IMAGE_PIXELS = None

DEFAULT_SCALE = 0.25
DEFAULT_STRIP_SIZE = 0.1


@dataclass
class Card:
    """Une carte, représentée par sa vignette et les couleurs de ses quatre bords.

    `top`/`bottom`/`left`/`right` sont des vecteurs RGB : la moyenne d'une bande
    occupant `strip_size` de la hauteur (ou largeur) de la vignette. C'est toute la
    signature utilisée pour juger si deux cartes se raccordent.

    `path` permet de relire l'original en pleine résolution à l'export.
    """

    path: str
    index: int
    thumbnail: np.ndarray

    top: np.ndarray = field(default=None, repr=False)
    bottom: np.ndarray = field(default=None, repr=False)
    left: np.ndarray = field(default=None, repr=False)
    right: np.ndarray = field(default=None, repr=False)

    @property
    def name(self) -> str:
        """Nom lisible de la carte, sans dossier ni extension."""
        return os.path.splitext(os.path.basename(self.path))[0]

    @property
    def folder(self) -> str:
        """Dossier contenant la carte, utile pour les sélections par groupe."""
        return os.path.basename(os.path.dirname(self.path))

    def calculate_features(self, strip_size: float = DEFAULT_STRIP_SIZE) -> None:
        h, w = self.thumbnail.shape[:2]
        strip_h = max(1, int(h * strip_size))
        strip_w = max(1, int(w * strip_size))

        self.top = self.thumbnail[:strip_h, :].mean(axis=(0, 1))
        self.bottom = self.thumbnail[h - strip_h :, :].mean(axis=(0, 1))
        self.left = self.thumbnail[:, :strip_w].mean(axis=(0, 1))
        self.right = self.thumbnail[:, w - strip_w :].mean(axis=(0, 1))


@dataclass
class CardSet:
    """L'ensemble des cartes chargées, plus les dimensions nécessaires à l'export."""

    cards: List[Card]
    full_size: Tuple[int, int]
    thumb_size: Tuple[int, int]

    def __len__(self) -> int:
        return len(self.cards)

    def __iter__(self) -> Iterator[Card]:
        return iter(self.cards)

    def __getitem__(self, i: int) -> Card:
        return self.cards[i]

    def recalculate_features(self, strip_size: float) -> None:
        """Recalcule toutes les signatures — utilisé par l'aperçu temps réel.

        Mesuré à ~46 ms pour 280 cartes sur vignettes à 25 %, contre 713 ms en
        pleine résolution. C'est ce qui rend le réglage interactif.
        """
        for card in self.cards:
            card.calculate_features(strip_size)

    def find(self, path_fragment: str) -> Optional[int]:
        """Retrouve l'indice d'une carte à partir d'un fragment de son chemin."""
        return next((c.index for c in self.cards if path_fragment in c.path), None)


def iter_image_paths(root_dir: str, exclude: Sequence[str] = ()) -> Iterator[str]:
    """Parcourt récursivement les fichiers image, en ordre stable.

    L'ordre est trié pour que deux chargements successifs donnent les mêmes indices —
    condition nécessaire pour que les préréglages restent valides d'une session à
    l'autre.
    """
    for dirpath, dirnames, filenames in os.walk(root_dir):
        dirnames.sort()
        for filename in sorted(filenames):
            if os.path.splitext(filename)[1].lower() not in VALID_EXTENSIONS:
                continue
            path = os.path.join(dirpath, filename)
            if any(fragment in path for fragment in exclude):
                continue
            yield path


def load_cards(
    root_dir: str,
    exclude: Sequence[str] = (),
    scale: float = DEFAULT_SCALE,
    strip_size: float = DEFAULT_STRIP_SIZE,
) -> CardSet:
    """Charge les cartes sous forme de vignettes et calcule leurs signatures.

    Deux passes : la première ne lit que les en-têtes pour trouver la plus petite
    taille commune (Pillow donne `.size` sans décoder les pixels) ; la seconde décode
    et réduit directement à la taille de vignette. Les images pleine résolution ne
    sont donc jamais toutes en mémoire — 35 Mo au lieu de 562 Mo.

    Note : les cartes en RGBA voient leur canal alpha écarté, sans composition sur un
    fond. Comportement identique à l'ancien chargement OpenCV. Voir TODO.md.
    """
    paths = list(iter_image_paths(root_dir, exclude))
    if not paths:
        return CardSet(cards=[], full_size=(0, 0), thumb_size=(0, 0))

    # Passe 1 — en-têtes seulement, pour la plus petite taille commune.
    min_w, min_h = None, None
    readable: List[str] = []
    for path in paths:
        try:
            with Image.open(path) as img:
                w, h = img.size
        except Exception as e:
            print(f"  Illisible, ignorée : {path} ({e})")
            continue
        readable.append(path)
        min_w = w if min_w is None else min(min_w, w)
        min_h = h if min_h is None else min(min_h, h)

    if not readable:
        return CardSet(cards=[], full_size=(0, 0), thumb_size=(0, 0))

    full_size = (min_w, min_h)
    thumb_size = (max(1, round(min_w * scale)), max(1, round(min_h * scale)))

    # Passe 2 — décodage et réduction directe à la taille de vignette.
    # BOX est une moyenne de blocs : c'est exactement l'opération qui justifie de
    # calculer les signatures sur les vignettes plutôt qu'en pleine résolution.
    cards: List[Card] = []
    for path in readable:
        try:
            with Image.open(path) as img:
                thumb = np.asarray(
                    img.convert("RGB").resize(thumb_size, Image.Resampling.BOX)
                )
        except Exception as e:
            print(f"  Erreur de traitement, ignorée : {path} ({e})")
            continue
        card = Card(path=path, index=len(cards), thumbnail=thumb)
        card.calculate_features(strip_size)
        cards.append(card)

    return CardSet(cards=cards, full_size=full_size, thumb_size=thumb_size)


def load_full_image(card: Card, size: Tuple[int, int]) -> np.ndarray:
    """Relit une carte en pleine résolution, pour l'export uniquement."""
    with Image.open(card.path) as img:
        return np.asarray(img.convert("RGB").resize(size, Image.Resampling.LANCZOS))
