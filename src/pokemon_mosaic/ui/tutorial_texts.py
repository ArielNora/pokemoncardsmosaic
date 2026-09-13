"""Tous les textes des tutoriels, réunis pour être relus d'un seul tenant.

Décidé le 2026-09-13 avec l'utilisateur, voir `SPEC.md` §10 : les explications
ne se dispersent pas dans chaque écran, où personne ne les relirait ensemble.
Une méthode par zone.

⚠️ **Des textes directs** : une phrase courte, qui dit quoi faire. Demandé par
l'utilisateur à la relecture de l'étape 1, les premières versions expliquaient
trop et se lisaient mal dans une bulle.

⚠️ **Des chaînes littérales dans `self.tr`**, jamais une variable : `lupdate`
n'extrait que les littéraux, et un texte non extrait resterait en français dans
l'interface anglaise sans que rien ne le signale.
"""

from PySide6.QtCore import QObject


class TutorialTexts(QObject):
    """Les explications des zones, dans la langue affichée au moment de les lire."""

    # --- Étape 1, sans carte chargée ---------------------------------------

    def cards_welcome(self) -> str:
        return self.tr("Pokémon Mosaic assemble vos cartes en un poster à "
                       "imprimer. Commencez par récupérer les illustrations.")

    def cards_download(self) -> str:
        return self.tr("Téléchargez les illustrations dans le dossier de votre "
                       "choix.")

    def cards_locate(self) -> str:
        return self.tr("Vous avez déjà les illustrations ? Choisissez leur "
                       "dossier.")

    # --- Étape 1, la galerie -----------------------------------------------

    def cards_gallery(self) -> str:
        return self.tr("Cliquez une carte pour l'inclure ou l'exclure du "
                       "poster.")

    def cards_folders(self) -> str:
        return self.tr("Sélectionnez les extensions pour filtrer les cartes, "
                       "utilisez les boutons pour les inclure ou les exclure.")

    def cards_search(self) -> str:
        return self.tr("Tapez un nom pour filtrer les cartes.")

    def cards_bulk(self) -> str:
        return self.tr("Incluez, excluez ou inversez d'un coup les cartes "
                       "affichées.")

    def cards_links(self) -> str:
        return self.tr("Créez des liens pour garder des cartes côte à côte "
                       "dans le poster.")

    def cards_count(self) -> str:
        return self.tr("Le nombre de cartes retenues pour le poster.")

    def cards_update(self) -> str:
        return self.tr("Récupérez les nouvelles cartes publiées.")

    def cards_warnings(self) -> str:
        return self.tr("Les cartes à vérifier : format inattendu ou fichier "
                       "illisible.")

    # --- La fenêtre, présentée avec la première étape ----------------------

    def window_presets(self) -> str:
        return self.tr("Enregistrez vos réglages sous un nom, ou repartez d'un "
                       "agencement enregistré.")

    def window_next(self) -> str:
        return self.tr("Passez à l'étape suivante quand l'aura est verte.")

    def window_help(self) -> str:
        return self.tr("Cliquez pour afficher l'aide de la page. Clic droit "
                       "pour revoir les visites guidées.")
