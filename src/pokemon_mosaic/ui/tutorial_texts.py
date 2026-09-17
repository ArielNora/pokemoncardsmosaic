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
        return self.tr("Vous pouvez filtrer, inclure ou exclure par extension.")

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

    # --- Étape 2 : la colonne des parties ----------------------------------

    def layout_parts(self) -> str:
        return self.tr("Réglez les parties dans l'ordre, puis validez chacune "
                       "avec « Suivant ».")

    # --- Étape 2 : Pages ---------------------------------------------------

    def paper_format(self) -> str:
        return self.tr("Choisissez le format de la feuille, ou tapez ses "
                       "dimensions.")

    def paper_landscape(self) -> str:
        return self.tr("Cochez pour mettre la feuille en paysage.")

    def paper_preview(self) -> str:
        return self.tr("Vous pouvez ajouter ou enlever des feuilles avec les "
                       "boutons ＋ et −.")

    def paper_summary(self) -> str:
        return self.tr("La surface totale de vos feuilles.")

    def paper_warnings(self) -> str:
        return self.tr("Les liens qui ne tiennent pas dans la grille.")

    # --- Étape 2 : Taille et cases vides -----------------------------------

    def grid_cols(self) -> str:
        return self.tr("Le nombre de colonnes de la grille.")

    def grid_rows(self) -> str:
        return self.tr("Le nombre de lignes de la grille.")

    def grid_suggestions(self) -> str:
        return self.tr("Double-cliquez une grille recommandée pour "
                       "l'appliquer.")

    def grid_preview(self) -> str:
        return self.tr("Cliquez ou glissez dans la grille pour poser les cases "
                       "vides.")

    def grid_auto_place(self) -> str:
        return self.tr("Placez automatiquement les cases vides qui manquent.")

    def grid_clear(self) -> str:
        return self.tr("Retirez toutes les cases vides.")

    def grid_status(self) -> str:
        return self.tr("Ce qui reste à régler sur la grille.")

    # --- Étape 2 : Taille des cartes et écarts -----------------------------

    def card_width(self) -> str:
        return self.tr("Réglez la largeur des cartes, ou laissez-la en "
                       "automatique.")

    def card_real(self) -> str:
        return self.tr("Vous pouvez donner aux cartes la taille d'une vraie "
                       "carte.")

    def card_gap(self) -> str:
        return self.tr("Réglez l'écart entre les cartes.")

    def card_shapes(self) -> str:
        return self.tr("Affichez les grilles qui tiendraient à cette taille.")

    def card_preview(self) -> str:
        return self.tr("L'aperçu des cartes sur les feuilles.")

    def card_status(self) -> str:
        return self.tr("Vous pouvez continuer quand la grille tient sur les "
                       "feuilles.")

    # --- Étape 2 : Emplacement de la grille --------------------------------

    def placement_preview(self) -> str:
        return self.tr("Cliquez et tirez dans la mosaïque pour la déplacer sur "
                       "sa feuille.")

    def placement_center(self) -> str:
        return self.tr("Centrez chaque morceau sur sa feuille.")

    def placement_reset(self) -> str:
        return self.tr("Remettez les morceaux à leur place par défaut.")

    def placement_status(self) -> str:
        return self.tr("Combien de feuilles ont été déplacées.")

    # --- Étape 2 : Paramètres avancés --------------------------------------

    def advanced_notice(self) -> str:
        return self.tr("Vous pouvez garder les valeurs par défaut et passer à "
                       "la suite.")

    def advanced_metric(self) -> str:
        return self.tr("Réglez l'épaisseur des bandes comparées entre deux "
                       "cartes voisines.")

    def advanced_saving(self) -> str:
        return self.tr("Choisissez tous les combien d'échanges un agencement "
                       "est enregistré.")

    def advanced_settings(self) -> str:
        return self.tr("Choisissez l'algorithme et quand il s'arrête.")

    def advanced_projection(self) -> str:
        return self.tr("La durée estimée du calcul et le gain attendu.")

    # --- Étape 3 : Lancement ----------------------------------------------

    def run_tabs(self) -> str:
        return self.tr("Lancez un calcul ici, ou plusieurs d'un coup dans "
                       "Multi-lancement.")

    def run_welcome(self) -> str:
        return self.tr("Lancez le calcul pour voir la mosaïque se construire.")

    def run_image(self) -> str:
        return self.tr("La mosaïque du cliché affiché.")

    def run_slider(self) -> str:
        return self.tr("Parcourez les clichés avec le curseur ou les flèches "
                       "du clavier.")

    def run_zoom(self) -> str:
        return self.tr("Zoomez avec + et −, ou revenez à l'image entière.")

    def run_start(self) -> str:
        return self.tr("Lancez un nouveau calcul.")

    def run_pause(self) -> str:
        return self.tr("Mettez le calcul en pause, puis reprenez-le.")

    def run_stop(self) -> str:
        return self.tr("Arrêtez le calcul.")

    def run_extend(self) -> str:
        return self.tr("Poursuivez le calcul depuis le dernier cliché.")

    def run_resume(self) -> str:
        return self.tr("Reprenez du cliché affiché (attention, supprime les "
                       "clichés d'après).")

    def run_keep(self) -> str:
        return self.tr("Enregistrez le cliché affiché dans une case, pour "
                       "l'export.")

    def run_saved(self) -> str:
        return self.tr("Les agencements gardés pour l'export. Cliquez pour "
                       "revoir.")

    # --- Étape 3 : Multi-lancement -----------------------------------------

    def multi_count(self) -> str:
        return self.tr("Choisissez combien de lancements enchaîner, vingt au "
                       "plus.")

    def multi_estimate(self) -> str:
        return self.tr("La durée estimée de tous les lancements.")

    def multi_start(self) -> str:
        return self.tr("Lancez les calculs, l'un après l'autre.")

    def multi_pause(self) -> str:
        return self.tr("Mettez les lancements en pause, puis reprenez-les.")

    def multi_stop(self) -> str:
        return self.tr("Arrêtez les lancements : ce qui est calculé est gardé.")

    def multi_progress(self) -> str:
        return self.tr("Où en sont les lancements.")

    def multi_view(self) -> str:
        return self.tr("La mosaïque en cours de calcul, puis le cliché choisi.")

    def multi_groups(self) -> str:
        return self.tr("Les derniers clichés de chaque lancement. Cliquez-en un, "
                       "ou utilisez les flèches.")

    def multi_choice(self) -> str:
        return self.tr("Le cliché choisi et son score : plus il est bas, mieux "
                       "c'est.")

    def multi_keep(self) -> str:
        return self.tr("Gardez le cliché choisi dans une case, pour l'export.")

    def multi_save(self) -> str:
        return self.tr("Enregistrez-le aussi dans la bibliothèque, sans prendre "
                       "de case.")

    # --- Étape 4 : Export -------------------------------------------------

    def export_preview(self) -> str:
        return self.tr("L'aperçu du poster tel qu'il sera imprimé.")

    def export_loupe(self) -> str:
        return self.tr("Zoomez, ou cliquez « Ajuster » pour déplacer la mosaïque "
                       "sur sa feuille.")

    def export_presentation(self) -> str:
        return self.tr("Retouchez la taille des cartes et l'écart, ou centrez "
                       "la mosaïque.")

    def export_colours(self) -> str:
        return self.tr("Choisissez les couleurs des vides, ou activez le "
                       "caméléon.")

    def export_cut(self) -> str:
        return self.tr("Réglez le chevauchement et les repères pour assembler "
                       "les feuilles.")

    def export_resolution(self) -> str:
        return self.tr("Réglez la finesse d'impression du fichier.")

    def export_saved(self) -> str:
        return self.tr("Choisissez l'agencement à exporter.")

    def export_warning(self) -> str:
        return self.tr("Des cartes sortent des pages : corrigez avant "
                       "d'exporter.")

    def export_summary(self) -> str:
        return self.tr("L'agencement affiché et son score.")

    def export_button(self) -> str:
        return self.tr("Exportez l'agencement affiché en fichiers à imprimer.")

    # --- Fenêtre : bibliothèque des agencements ----------------------------

    def library_list(self) -> str:
        return self.tr("Les agencements enregistrés. Cliquez-en un pour le "
                       "voir.")

    def library_image(self) -> str:
        return self.tr("L'aperçu de l'agencement choisi.")

    def library_cards(self) -> str:
        return self.tr("Ses cartes : celles qui manquent sont en rouge.")

    def library_start(self) -> str:
        return self.tr("Repartez de cet agencement : cartes, grille et "
                       "habillage.")

    def library_slot(self) -> str:
        return self.tr("Mettez cet agencement dans une case, pour l'export.")

    def library_export(self) -> str:
        return self.tr("Exportez-le en JSON pour le partager.")

    def library_import(self) -> str:
        return self.tr("Importez un agencement reçu en JSON.")

    def library_rename(self) -> str:
        return self.tr("Renommez l'agencement choisi.")

    def library_delete(self) -> str:
        return self.tr("Supprimez l'agencement choisi de la bibliothèque.")

    # --- Fenêtre : éditeur de liens ----------------------------------------

    def link_grid(self) -> str:
        return self.tr("Glissez des cartes ici. Agrandissez le rectangle avec "
                       "les boutons +.")

    def link_palette(self) -> str:
        return self.tr("Les cartes disponibles, à glisser dans le lien.")

    def link_search(self) -> str:
        return self.tr("Filtrez les cartes par nom.")

    def link_folder(self) -> str:
        return self.tr("Filtrez les cartes par extension.")

    def link_ordered(self) -> str:
        return self.tr("Cochez pour interdire de pivoter le lien d'un "
                       "demi-tour.")

    def link_name(self) -> str:
        return self.tr("Vous pouvez donner un nom au lien.")

    def link_buttons(self) -> str:
        return self.tr("Validez quand le rectangle est complet.")

    # --- Fenêtre : export du poster ----------------------------------------

    def export_dialog_layout(self) -> str:
        return self.tr("Le rappel de la mise en page.")

    def export_dialog_format(self) -> str:
        return self.tr("Choisissez le format des fichiers.")

    def export_dialog_quality(self) -> str:
        return self.tr("Réglez la qualité, pour le JPEG seulement.")

    def export_dialog_folder(self) -> str:
        return self.tr("Choisissez où écrire les fichiers.")

    def export_dialog_name(self) -> str:
        return self.tr("Le nom des fichiers : plusieurs feuilles ajoutent "
                       "« page1 », « page2 ».")

    def export_dialog_plan(self) -> str:
        return self.tr("La taille des fichiers en pixels.")

    def export_dialog_files(self) -> str:
        return self.tr("Les fichiers qui seront écrits.")

    def export_dialog_buttons(self) -> str:
        return self.tr("Lancez l'export.")

    # --- Fenêtre : agencement gardé ----------------------------------------

    def saved_notice(self) -> str:
        return self.tr("Cet agencement gardé n'est plus dans la timeline du "
                       "calcul.")

    def saved_view(self) -> str:
        return self.tr("L'agencement tel qu'il a été gardé.")

    def saved_zoom(self) -> str:
        return self.tr("Zoomez avec + et −.")

    # --- La fenêtre, présentée avec la première étape ----------------------

    def window_presets(self) -> str:
        return self.tr("Enregistrez vos réglages sous un nom, ou repartez d'un "
                       "agencement enregistré.")

    def window_next(self) -> str:
        return self.tr("Vous pouvez passer à l'étape suivante quand l'aura "
                       "est verte.")

    def window_help(self) -> str:
        return self.tr("Cliquez pour afficher l'aide de la page. Clic droit "
                       "pour revoir les visites guidées.")
