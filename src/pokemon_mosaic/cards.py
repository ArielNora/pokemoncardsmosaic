"""Chargement des cartes et calcul de leurs signatures de bord."""

import os
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

import cv2
import numpy as np

VALID_EXTENSIONS = (".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff")


@dataclass
class ImagePart:
    """Une carte redimensionnée, avec la couleur moyenne de ses quatre bords.

    `top`/`bottom`/`left`/`right` sont des vecteurs BGR (3 valeurs) : la moyenne
    d'une bande occupant `strip_size` de la hauteur (ou largeur) de la carte.
    C'est toute la signature utilisée pour juger si deux cartes se raccordent.
    """

    full_image: np.ndarray
    original_index: int
    path: str = ""

    top: np.ndarray = None
    bottom: np.ndarray = None
    left: np.ndarray = None
    right: np.ndarray = None

    def calculate_features(self, strip_size: float = 0.2) -> None:
        h, w, _ = self.full_image.shape
        strip_h = max(1, int(h * strip_size))
        strip_w = max(1, int(w * strip_size))

        self.top = np.mean(self.full_image[0:strip_h, :], axis=(0, 1))
        self.bottom = np.mean(self.full_image[h - strip_h : h, :], axis=(0, 1))
        self.left = np.mean(self.full_image[:, 0:strip_w], axis=(0, 1))
        self.right = np.mean(self.full_image[:, w - strip_w : w], axis=(0, 1))


def load_and_process_images(
    root_dir: str,
    remove_list: Sequence[str] = (),
    strip_size: float = 0.1,
) -> Tuple[List[ImagePart], Optional[Tuple[int, int]]]:
    """Charge récursivement les cartes et les ramène toutes à une taille commune.

    Toutes les cartes sont redimensionnées aux dimensions de la *plus petite*
    trouvée, pour que les tuiles de la mosaïque soient uniformes.

    `remove_list` contient des fragments de chemin : toute carte dont le chemin
    contient l'un d'eux est ignorée. Sert notamment à ajuster le nombre total de
    cartes (voir la note sur la factorisation dans `grid.calculate_grid_dims`).

    Note : `cv2.imread` lit en BGR 3 canaux et écarte le canal alpha. Une partie
    des cartes sont en RGBA avec de la vraie transparence ; leurs couleurs de
    bord sont donc calculées sur les pixels sous-jacents. Connu, non corrigé.
    """
    images_data: List[Tuple[np.ndarray, str]] = []
    min_h, min_w = float("inf"), float("inf")

    print(f"Chargement des images depuis : {root_dir}")
    for dirpath, _, filenames in os.walk(root_dir):
        for filename in filenames:
            full_path = os.path.join(dirpath, filename)
            if any(rem in full_path for rem in remove_list):
                print(f"  Exclue : {full_path}")
                continue
            if os.path.splitext(filename)[1].lower() not in VALID_EXTENSIONS:
                continue
            try:
                img = cv2.imread(full_path)
            except Exception as e:
                print(f"  Illisible, ignorée : {full_path} ({e})")
                continue
            if img is None:
                print(f"  Illisible, ignorée : {full_path}")
                continue
            images_data.append((img, full_path))
            h, w = img.shape[:2]
            min_h, min_w = min(min_h, h), min(min_w, w)

    print(f"Total d'images trouvées : {len(images_data)}")
    if not images_data:
        return [], None

    smallest = (int(min_w), int(min_h))
    parts: List[ImagePart] = []
    for i, (img, path) in enumerate(images_data):
        try:
            resized = cv2.resize(img, smallest, interpolation=cv2.INTER_AREA)
        except Exception as e:
            # Attention : `original_index` suit l'indice d'entrée, pas la position
            # dans `parts`. Si une carte est écartée ici, les deux divergent alors
            # que le reste du code indexe par `original_index`. Connu, non corrigé.
            print(f"  Erreur de redimensionnement sur {path} : {e}")
            continue
        part = ImagePart(full_image=resized, original_index=i, path=path)
        part.calculate_features(strip_size=strip_size)
        parts.append(part)

    return parts, smallest


def find_index(parts: Sequence[ImagePart], path_fragment: str) -> Optional[int]:
    """Retrouve l'indice d'une carte à partir d'un fragment de son chemin."""
    return next((p.original_index for p in parts if path_fragment in p.path), None)
