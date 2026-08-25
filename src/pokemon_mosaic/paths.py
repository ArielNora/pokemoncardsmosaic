"""Où trouver les ressources et les données — en source comme une fois empaqueté.

Trois chemins étaient déduits de `__file__` par remontée de dossiers parents.
La déduction est juste tant que le code vit dans l'arborescence du dépôt, et
**fausse dès qu'il est empaqueté** : PyInstaller déplie les ressources dans un
dossier temporaire, et l'exécutable se trouve dans `Contents/MacOS` d'un paquet
`.app`, où il n'y a ni `translations/` ni `data/`.
"""

import sys
from pathlib import Path

APP_NAME = "Pokémon Mosaic"


def frozen() -> bool:
    """L'application tourne-t-elle depuis un paquet plutôt que depuis le dépôt ?"""
    return getattr(sys, "frozen", False)


def resource_dir() -> Path:
    """Racine des ressources en lecture seule — traductions, et rien d'autre.

    ⚠️ `sys._MEIPASS` et non `Path(sys.executable).parent` : le second pointe sur
    `Contents/MacOS`, où PyInstaller ne déplie rien.
    """
    if frozen():
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parents[2]


def user_data_dir() -> Path:
    """Où l'application range ce qui appartient à l'utilisateur.

    Depuis le dépôt, c'est `data/` — le dossier de travail habituel. Une fois
    installée, écrire à côté de l'exécutable est impossible : un `.app` vit dans
    `/Applications`, en lecture seule pour l'utilisateur courant.
    """
    if not frozen():
        return resource_dir() / "data"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME
    if sys.platform == "win32":
        base = Path.home() / "AppData" / "Roaming"
        return base / APP_NAME
    return Path.home() / ".local" / "share" / APP_NAME


def output_dir() -> Path:
    """Où la **ligne de commande** dépose les mosaïques produites.

    L'interface graphique ne passe pas par ici : son dialogue d'export propose
    `QStandardPaths.PicturesLocation`, que le système sait localiser dans la
    langue et l'arborescence de l'utilisateur.
    """
    if not frozen():
        return resource_dir() / "output"
    return Path.home() / "Pictures" / APP_NAME
