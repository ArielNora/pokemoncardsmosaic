"""Écrire un agencement dans la bibliothèque, depuis l'un ou l'autre onglet.

Le lancement simple et le multi-lancement enregistrent de la même façon : un
nom posé sans rien demander, rendu unique, et le fichier écrit. Deux copies de
ces lignes auraient fini par nommer différemment ce qui vient de l'un et de
l'autre.
"""

from ..arrangements import default_name, save_arrangement, unique_name


def store_in_library(session, directory: str, saved) -> str:
    """Écrit l'agencement et rend le nom retenu, vide sans bibliothèque.

    ⚠️ Lève `OSError` quand l'écriture échoue, disque plein ou dossier devenu
    non inscriptible : à l'appelant de le dire, lui seul sait ce qui a déjà été
    fait (une case remplie, ou rien).
    """
    if not directory or saved is None:
        return ""
    colonnes, lignes = saved.grid.shape[1], saved.grid.shape[0]
    nom = unique_name(directory, default_name((colonnes, lignes), saved.score))
    save_arrangement(directory, session.arrangement_of(saved, nom))
    return nom
