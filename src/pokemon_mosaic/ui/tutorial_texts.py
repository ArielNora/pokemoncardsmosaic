"""Tous les textes des tutoriels, réunis pour être relus d'un seul tenant.

Décidé le 2026-09-13 avec l'utilisateur, voir `SPEC.md` §10 : les explications
ne se dispersent pas dans chaque écran, où personne ne les relirait ensemble.
Une méthode par zone, une à trois phrases.

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
                       "imprimer. Tout commence par les illustrations des "
                       "cartes, qui ne sont pas fournies avec l'application.")

    def cards_download(self) -> str:
        return self.tr("Récupère les illustrations dans le dossier de votre "
                       "choix. Interrompu, le téléchargement se complète en le "
                       "relançant.")

    def cards_locate(self) -> str:
        return self.tr("Vous avez déjà un dossier d'illustrations : désignez-le "
                       "ici. L'application le rouvrira au prochain lancement.")

    # --- Étape 1, la galerie -----------------------------------------------

    def cards_gallery(self) -> str:
        return self.tr("Toutes les cartes chargées. Un clic sur une carte "
                       "l'inclut dans le poster ou l'en exclut ; une carte "
                       "exclue apparaît effacée.")

    def cards_folders(self) -> str:
        return self.tr("Les extensions, rangées par série. Sélectionnez-en une "
                       "pour n'afficher que ses cartes, puis incluez-la ou "
                       "excluez-la d'un coup avec les boutons dessous.")

    def cards_search(self) -> str:
        return self.tr("Filtre la galerie par nom de carte, en plus des "
                       "extensions sélectionnées.")

    def cards_bulk(self) -> str:
        return self.tr("Ces boutons agissent sur les cartes affichées : toutes "
                       "sans filtre, seulement celles qui restent visibles "
                       "sinon.")

    def cards_links(self) -> str:
        return self.tr("Les liens gardent des cartes ensemble dans le poster, "
                       "par exemple une lignée d'évolution. La case à cocher "
                       "suspend un lien sans le supprimer.")

    def cards_count(self) -> str:
        return self.tr("Combien de cartes iront dans le poster, sur toutes "
                       "celles chargées.")

    def cards_update(self) -> str:
        return self.tr("Récupère les cartes publiées depuis votre dernier "
                       "téléchargement, sans perdre vos exclusions ni vos "
                       "liens.")

    def cards_warnings(self) -> str:
        return self.tr("Ce que le chargement a trouvé d'anormal : des cartes "
                       "d'un format inattendu, ou des fichiers illisibles.")

    # --- La fenêtre, présentée avec la première étape ----------------------

    def window_presets(self) -> str:
        return self.tr("Les préréglages enregistrent sous un nom la sélection, "
                       "les liens, la grille et les réglages. « Tous les "
                       "agencements… » repart d'un poster déjà enregistré.")

    def window_next(self) -> str:
        return self.tr("Passe à l'étape suivante. Son aura est verte quand vous "
                       "pouvez avancer, rouge tant qu'il reste quelque chose à "
                       "faire.")

    def window_help(self) -> str:
        return self.tr("Ce bouton rallume l'aide quand vous voulez : chaque zone "
                       "s'entoure, et son explication apparaît au survol. Un "
                       "clic droit fait revoir les visites guidées.")
