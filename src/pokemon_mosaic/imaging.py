"""Utilitaires d'inspection et de réduction des mosaïques générées."""

import os

from PIL import Image

# Les mosaïques dépassent largement la limite anti-décompression-bomb de Pillow.
Image.MAX_IMAGE_PIXELS = None


def print_image_properties(image_path: str) -> bool:
    """Affiche format, dimensions et mode d'une image.

    Renvoie False en cas d'échec : l'appelant doit pouvoir en tenir compte plutôt
    que de poursuivre comme si le fichier existait.
    """
    try:
        with Image.open(image_path) as img:
            print(f"--- Propriétés de : {os.path.basename(image_path)} ---")
            print(f"Format : {img.format}")
            print(f"Taille : {img.size} (largeur {img.width}, hauteur {img.height})")
            print(f"Mode   : {img.mode}")
            print("-" * 30)
        return True
    except FileNotFoundError:
        print(f"Erreur : fichier introuvable, {image_path}")
    except OSError as e:
        print(f"Erreur de lecture de l'image : {e}")
    return False


def resize_and_save(
    input_path: str,
    output_path: str,
    new_width: int = 800,
    new_height: int = 600,
    percent: int = 100,
) -> bool:
    """Réduit une image et l'enregistre.

    Si `percent` est différent de 100, il prime sur `new_width`/`new_height`.
    Renvoie False si l'écriture a échoué, un disque plein ne doit pas passer
    pour un succès auprès d'un script qui enchaîne.
    """
    try:
        with Image.open(input_path) as img:
            if percent != 100:
                new_width = int(img.width * percent / 100)
                new_height = int(img.height * percent / 100)

            parent = os.path.dirname(output_path)
            if parent:
                os.makedirs(parent, exist_ok=True)

            resized = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            resized.save(output_path)
            print(f"Enregistré : {output_path}, nouvelle taille {resized.size}")
        return True
    except FileNotFoundError:
        print(f"Erreur : fichier d'entrée introuvable, {input_path}")
    except OSError as e:
        print(f"Erreur de redimensionnement : {e}")
    return False
