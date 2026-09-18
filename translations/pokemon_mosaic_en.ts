<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE TS>
<TS version="2.1" language="en_US">
<context>
    <name>AdvancedTab</name>
    <message>
        <location filename="../src/pokemon_mosaic/ui/algorithm_tabs.py" line="90"/>
        <source>Paramètres avancés</source>
        <translation>Advanced settings</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/algorithm_tabs.py" line="343"/>
        <source>le recuit simulé</source>
        <translation>simulated annealing</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/algorithm_tabs.py" line="344"/>
        <source>la descente stricte</source>
        <translation>strict descent</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/algorithm_tabs.py" line="347"/>
        <source>&lt;b&gt;La métrique :&lt;/b&gt;</source>
        <translation>&lt;b&gt;The metric:&lt;/b&gt;</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/algorithm_tabs.py" line="346"/>
        <source>Épaisseur des bandes</source>
        <translation>Strip thickness</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/algorithm_tabs.py" line="349"/>
        <source>La partie la plus importante de l&apos;algorithme. Elle prend les bandes voisines de deux cartes et en tire un score, qui dit à quel point ces bandes se ressemblent. Tout le travail de l&apos;algorithme est ensuite de déplacer les cartes pour obtenir le meilleur score d&apos;ensemble.</source>
        <translation>The most important part of the algorithm. It takes the neighbouring strips of two cards and draws a score from them, saying how alike those strips are. All the algorithm then does is move the cards around to reach the best overall score.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/algorithm_tabs.py" line="355"/>
        <source>À gauche, deux cartes voisines : la flèche relie les deux bandes que le score compare. À droite, une petite grille d&apos;essai réoptimisée à cette épaisseur.</source>
        <translation>On the left, two neighbouring cards: the arrow joins the two strips the score compares. On the right, a small test grid re-optimised at that thickness.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/algorithm_tabs.py" line="358"/>
        <source>&lt;b&gt;Fréquence de sauvegarde :&lt;/b&gt;</source>
        <translation>&lt;b&gt;Saving frequency:&lt;/b&gt;</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/algorithm_tabs.py" line="359"/>
        <source>&lt;b&gt;Paramètres de l&apos;algorithme :&lt;/b&gt;</source>
        <translation>&lt;b&gt;Algorithm settings:&lt;/b&gt;</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/algorithm_tabs.py" line="362"/>
        <source>Les valeurs par défaut donnent presque toujours un bon résultat. Vous pouvez les changer, ou passer directement à la suite.</source>
        <translation>The default values almost always give a good result. You may change them, or move straight on.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/algorithm_tabs.py" line="367"/>
        <source>À chaque &lt;b&gt;itération&lt;/b&gt;, l&apos;algorithme tente un &lt;b&gt;échange&lt;/b&gt; : il permute deux cartes de la grille et regarde ce que devient la &lt;b&gt;métrique&lt;/b&gt;, l&apos;écart de couleur entre les bords qui se touchent. L&apos;échange est &lt;b&gt;retenu&lt;/b&gt; s&apos;il rapproche l&apos;&lt;b&gt;agencement&lt;/b&gt; du but, une mosaïque dont les bords voisins se ressemblent, et le calcul continue jusqu&apos;à ce qu&apos;un &lt;b&gt;arrêt&lt;/b&gt; tombe.</source>
        <translation>At every &lt;b&gt;iteration&lt;/b&gt; the algorithm tries a &lt;b&gt;swap&lt;/b&gt;: it exchanges two cards of the grid and looks at what becomes of the &lt;b&gt;metric&lt;/b&gt;, the colour gap between the edges that touch. The swap is &lt;b&gt;kept&lt;/b&gt; if it brings the &lt;b&gt;arrangement&lt;/b&gt; closer to the goal, a mosaic whose neighbouring edges match, and the run carries on until a &lt;b&gt;stop&lt;/b&gt; falls.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/algorithm_tabs.py" line="375"/>
        <source>L&apos;algorithme utilisé est %1</source>
        <translation>The algorithm used is %1</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/algorithm_tabs.py" line="377"/>
        <source>Le recuit accepte au départ %1 d&apos;échanges qui dégradent la métrique, puis devient de plus en plus exigeant.</source>
        <translation>Annealing accepts %1 of swaps that worsen the metric to begin with, then grows steadily more demanding.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/algorithm_tabs.py" line="380"/>
        <source>&lt;b&gt;L&apos;algorithme s&apos;arrête&lt;/b&gt; lorsque :</source>
        <translation>&lt;b&gt;The algorithm stops&lt;/b&gt; when:</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/algorithm_tabs.py" line="381"/>
        <source>il a fait %1 itérations (toujours actif)</source>
        <translation>it has run %1 iterations (always on)</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/algorithm_tabs.py" line="383"/>
        <source>la métrique ne s&apos;améliore plus depuis %1 itérations</source>
        <translation>the metric has not improved for %1 iterations</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/algorithm_tabs.py" line="384"/>
        <source>il a calculé pendant %1</source>
        <translation>it has run for %1</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/algorithm_tabs.py" line="385"/>
        <source>la métrique descend sous %1</source>
        <translation>the metric falls below %1</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/algorithm_tabs.py" line="388"/>
        <source>Un agencement sera enregistré tous les %1 échanges retenus.</source>
        <translation>An arrangement is saved every %1 kept swaps.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/algorithm_tabs.py" line="490"/>
        <source>Durée estimée : %1, gain attendu : environ %2 %, timeline : entre %3 et %4 clichés</source>
        <translation>Estimated duration: %1, expected gain: about %2%, timeline: between %3 and %4 snapshots</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/algorithm_tabs.py" line="496"/>
        <source>trop peu pour naviguer, resserrez la cadence</source>
        <translation>too few to navigate, tighten the cadence</translation>
    </message>
</context>
<context>
    <name>ArrangementsDialog</name>
    <message>
        <location filename="../src/pokemon_mosaic/ui/arrangements_dialog.py" line="260"/>
        <source>Agencements enregistrés</source>
        <translation>Kept arrangements</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/arrangements_dialog.py" line="261"/>
        <source>Partir de cet agencement</source>
        <translation>Start from this arrangement</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/arrangements_dialog.py" line="262"/>
        <source>Mettre dans une case</source>
        <translation>Put in a slot</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/arrangements_dialog.py" line="263"/>
        <source>Exporter en JSON…</source>
        <translation>Export as JSON…</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/arrangements_dialog.py" line="264"/>
        <source>Importer un JSON…</source>
        <translation>Import a JSON…</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/arrangements_dialog.py" line="265"/>
        <source>Renommer…</source>
        <translation>Rename…</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/arrangements_dialog.py" line="266"/>
        <source>Supprimer…</source>
        <translation>Delete…</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/arrangements_dialog.py" line="267"/>
        <source>Fermer</source>
        <translation>Close</translation>
    </message>
    <message numerus="yes">
        <location filename="../src/pokemon_mosaic/ui/arrangements_dialog.py" line="305"/>
        <source>%n carte(s) manquante(s)</source>
        <translation>
            <numerusform>%n missing card</numerusform>
            <numerusform>%n missing cards</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/arrangements_dialog.py" line="347"/>
        <source>Aucun agencement enregistré.</source>
        <translation>No arrangement kept yet.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/arrangements_dialog.py" line="357"/>
        <source>%1 : %2 × %3 cartes, score %4</source>
        <translation>%1: %2 × %3 cards, score %4</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/arrangements_dialog.py" line="371"/>
        <source>Chargez d&apos;abord les cartes : un agencement ne s&apos;ouvre qu&apos;avec elles.</source>
        <translation>Load the cards first: an arrangement only opens with them.</translation>
    </message>
    <message numerus="yes">
        <location filename="../src/pokemon_mosaic/ui/arrangements_dialog.py" line="376"/>
        <source>%n carte(s) de cet agencement manquent au catalogue : il ne peut pas être ouvert.</source>
        <translation>
            <numerusform>%n card of this arrangement is missing from the catalogue: it cannot be opened.</numerusform>
            <numerusform>%n cards of this arrangement are missing from the catalogue: it cannot be opened.</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/arrangements_dialog.py" line="465"/>
        <location filename="../src/pokemon_mosaic/ui/arrangements_dialog.py" line="507"/>
        <source>Agencement incomplet</source>
        <translation>Incomplete arrangement</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/arrangements_dialog.py" line="472"/>
        <location filename="../src/pokemon_mosaic/ui/arrangements_dialog.py" line="502"/>
        <source>Aucune case libre</source>
        <translation>No free slot</translation>
    </message>
    <message numerus="yes">
        <location filename="../src/pokemon_mosaic/ui/arrangements_dialog.py" line="473"/>
        <source>Les %n case(s) sont prises : videz-en une pour ouvrir celui-ci.</source>
        <translation>
            <numerusform>The %n slot is taken: empty one to open this arrangement.</numerusform>
            <numerusform>All %n slots are taken: empty one to open this arrangement.</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/arrangements_dialog.py" line="485"/>
        <source>Habillage incomplet</source>
        <translation>Presentation partly restored</translation>
    </message>
    <message numerus="yes">
        <location filename="../src/pokemon_mosaic/ui/arrangements_dialog.py" line="486"/>
        <location filename="../src/pokemon_mosaic/ui/arrangements_dialog.py" line="519"/>
        <source>%n réglage(s) de l&apos;habillage étaient illisibles et n&apos;ont pas été repris : %1.</source>
        <translation>
            <numerusform>%n presentation setting was unreadable and was not restored: %1.</numerusform>
            <numerusform>%n presentation settings were unreadable and were not restored: %1.</numerusform>
        </translation>
    </message>
    <message numerus="yes">
        <location filename="../src/pokemon_mosaic/ui/arrangements_dialog.py" line="503"/>
        <source>Les %n case(s) sont prises : videz-en une pour partir de celui-ci.</source>
        <translation>
            <numerusform>The %n slot is taken: empty it to start from this one.</numerusform>
            <numerusform>All %n slots are taken: empty one to start from this one.</numerusform>
        </translation>
    </message>
    <message numerus="yes">
        <location filename="../src/pokemon_mosaic/ui/arrangements_dialog.py" line="514"/>
        <source>%n lien(s) ne tenaient pas dans cet agencement et ont été désactivés.</source>
        <translation>
            <numerusform>%n link did not fit in this arrangement and was disabled.</numerusform>
            <numerusform>%n links did not fit in this arrangement and were disabled.</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/arrangements_dialog.py" line="523"/>
        <source>Agencement repris</source>
        <translation>Arrangement taken up</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/arrangements_dialog.py" line="533"/>
        <source>Exporter l&apos;agencement</source>
        <translation>Export the arrangement</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/arrangements_dialog.py" line="535"/>
        <location filename="../src/pokemon_mosaic/ui/arrangements_dialog.py" line="551"/>
        <source>Agencement (*.json)</source>
        <translation>Arrangement (*.json)</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/arrangements_dialog.py" line="541"/>
        <location filename="../src/pokemon_mosaic/ui/arrangements_dialog.py" line="566"/>
        <source>Écriture impossible</source>
        <translation>Cannot write</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/arrangements_dialog.py" line="550"/>
        <source>Importer un agencement</source>
        <translation>Import an arrangement</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/arrangements_dialog.py" line="557"/>
        <source>Fichier illisible</source>
        <translation>Unreadable file</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/arrangements_dialog.py" line="575"/>
        <source>Renommer l&apos;agencement</source>
        <translation>Rename the arrangement</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/arrangements_dialog.py" line="575"/>
        <source>Nom</source>
        <translation>Name</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/arrangements_dialog.py" line="587"/>
        <source>Renommage impossible</source>
        <translation>Cannot rename</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/arrangements_dialog.py" line="596"/>
        <source>Supprimer cet agencement ?</source>
        <translation>Delete this arrangement?</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/arrangements_dialog.py" line="597"/>
        <source>« %1 » sera effacé de la bibliothèque. Le calcul ne redonne pas deux fois le même.</source>
        <translation>“%1” will be erased from the library. No run gives the same one twice.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/arrangements_dialog.py" line="605"/>
        <source>Suppression impossible</source>
        <translation>Cannot delete</translation>
    </message>
</context>
<context>
    <name>CardCell</name>
    <message>
        <location filename="../src/pokemon_mosaic/ui/link_grid.py" line="139"/>
        <source>carte</source>
        <translation>card</translation>
    </message>
</context>
<context>
    <name>CardGalleryModel</name>
    <message>
        <location filename="../src/pokemon_mosaic/ui/gallery.py" line="138"/>
        <source>exclue</source>
        <translation>excluded</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/gallery.py" line="139"/>
        <source>incluse</source>
        <translation>included</translation>
    </message>
</context>
<context>
    <name>CardSizeTab</name>
    <message>
        <location filename="../src/pokemon_mosaic/ui/layout_tabs.py" line="639"/>
        <source>Taille des cartes et écarts</source>
        <translation>Card size and gaps</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/layout_tabs.py" line="764"/>
        <source>automatique</source>
        <translation>automatic</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/layout_tabs.py" line="766"/>
        <source>La plus grande taille qui fasse tenir la grille, recalculée à chaque changement.</source>
        <translation>The largest size that lets the grid fit, recomputed on every change.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/layout_tabs.py" line="769"/>
        <source>Taille d&apos;une vraie carte</source>
        <translation>Real card size</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/layout_tabs.py" line="771"/>
        <source>Fixe la largeur à %1 mm, celle d&apos;une carte qu&apos;on tient en main. Ne touche à rien d&apos;autre.</source>
        <translation>Sets the width to %1 mm, that of a card you hold in your hand. Touches nothing else.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/layout_tabs.py" line="775"/>
        <source>Grilles qui tiendraient</source>
        <translation>Grids that would fit</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/layout_tabs.py" line="762"/>
        <source>Largeur d&apos;une carte (mm)</source>
        <translation>Card width (mm)</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/layout_tabs.py" line="763"/>
        <source>Écart entre cartes (mm)</source>
        <translation>Gap between cards (mm)</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/layout_tabs.py" line="776"/>
        <location filename="../src/pokemon_mosaic/ui/layout_tabs.py" line="859"/>
        <source>Double-cliquez pour appliquer</source>
        <translation>Double-click to apply</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/layout_tabs.py" line="778"/>
        <source>Ajoutez des feuilles pour qu&apos;aucune carte ne reste en trop.</source>
        <translation>Add sheets so that no card is left out.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/layout_tabs.py" line="830"/>
        <source>pile poil</source>
        <translation>exact fit</translation>
    </message>
    <message numerus="yes">
        <location filename="../src/pokemon_mosaic/ui/layout_tabs.py" line="832"/>
        <source>%n case(s) vide(s)</source>
        <translation>
            <numerusform>%n blank cell</numerusform>
            <numerusform>%n blank cells</numerusform>
        </translation>
    </message>
    <message numerus="yes">
        <location filename="../src/pokemon_mosaic/ui/layout_tabs.py" line="834"/>
        <source>%n carte(s) en trop</source>
        <translation>
            <numerusform>%n card too many</numerusform>
            <numerusform>%n cards too many</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/layout_tabs.py" line="860"/>
        <source>Aucune grille ne tiendrait à cette taille de carte.</source>
        <translation>No grid would fit at this card size.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/layout_tabs.py" line="892"/>
        <source>Cartes de &lt;b&gt;%1 × %2 mm&lt;/b&gt;, %3 par feuille. La grille tient.</source>
        <translation>Cards of &lt;b&gt;%1 × %2 mm&lt;/b&gt;, %3 per sheet. The grid fits.</translation>
    </message>
    <message numerus="yes">
        <location filename="../src/pokemon_mosaic/ui/layout_tabs.py" line="899"/>
        <source>À &lt;b&gt;%1 mm&lt;/b&gt;, la grille %2 × %3 ne tient pas sur %n feuille(s) : elle en logerait &lt;b&gt;%4 × %5&lt;/b&gt;.</source>
        <translation>
            <numerusform>At &lt;b&gt;%1 mm&lt;/b&gt;, the %2 × %3 grid does not fit on %n sheet: it would hold &lt;b&gt;%4 × %5&lt;/b&gt;.</numerusform>
            <numerusform>At &lt;b&gt;%1 mm&lt;/b&gt;, the %2 × %3 grid does not fit on %n sheets: it would hold &lt;b&gt;%4 × %5&lt;/b&gt;.</numerusform>
        </translation>
    </message>
</context>
<context>
    <name>CardsStep</name>
    <message>
        <location filename="../src/pokemon_mosaic/ui/cards_step.py" line="290"/>
        <source>Dossiers</source>
        <translation>Folders</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/cards_step.py" line="856"/>
        <source>Tout inclure</source>
        <translation>Include all</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/cards_step.py" line="857"/>
        <source>Tout exclure</source>
        <translation>Exclude all</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/cards_step.py" line="294"/>
        <source>Choisir le dossier de cartes…</source>
        <translation>Choose card folder…</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/cards_step.py" line="293"/>
        <source>Afficher tous les dossiers</source>
        <translation>Show all folders</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/cards_step.py" line="295"/>
        <source>Mettre à jour le catalogue</source>
        <translation>Update the card list</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/cards_step.py" line="297"/>
        <source>Relit la liste des cartes publiée et récupère celles qui manquent au dossier.</source>
        <translation>Re-reads the published card list and fetches whatever the folder is missing.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/cards_step.py" line="299"/>
        <source>Annuler</source>
        <translation>Cancel</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/cards_step.py" line="302"/>
        <source>Les illustrations ne sont pas fournies avec l&apos;application. Téléchargez-les, ou désignez un dossier qui les contient déjà.</source>
        <translation>The artwork does not ship with the application. Download it, or point to a folder that already holds it.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/cards_step.py" line="305"/>
        <source>Télécharger les cartes…</source>
        <translation>Download the cards…</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/cards_step.py" line="306"/>
        <source>J&apos;ai déjà les cartes : choisir le dossier…</source>
        <translation>I already have the cards: choose the folder…</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/cards_step.py" line="309"/>
        <source>Cliquez une carte pour l&apos;inclure ou l&apos;exclure. Sélectionnez un dossier pour n&apos;afficher que ses cartes.</source>
        <translation>Click a card to include or exclude it. Select a folder to show only its cards.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/cards_step.py" line="312"/>
        <source>Rechercher une carte par nom…</source>
        <translation>Search a card by name…</translation>
    </message>
    <message numerus="yes">
        <location filename="../src/pokemon_mosaic/ui/cards_step.py" line="426"/>
        <source>, et %n autre(s) format(s)</source>
        <translation>
            <numerusform>, and %n other size</numerusform>
            <numerusform>, and %n other sizes</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/cards_step.py" line="429"/>
        <source>%1 carte(s) ne sont pas au format %2 : %3. Elles seront étirées à ce format, ce qui déforme l&apos;illustration et fausse les couleurs de bord dont l&apos;assemblage se sert.</source>
        <translation>%1 card(s) are not %2: %3. They will be stretched to that size, which distorts the artwork and skews the edge colours the assembly relies on.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/cards_step.py" line="436"/>
        <source>%1 fichier(s) illisibles, ignorés : %2</source>
        <translation>%1 unreadable file(s), skipped: %2</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/cards_step.py" line="446"/>
        <source>Dossier contenant les cartes</source>
        <translation>Folder containing the cards</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/cards_step.py" line="487"/>
        <source>Chargement des cartes…</source>
        <translation>Loading cards…</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/cards_step.py" line="523"/>
        <source>Où déposer les cartes</source>
        <translation>Where to put the cards</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/cards_step.py" line="545"/>
        <source>Lecture du catalogue…</source>
        <translation>Reading the card list…</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/cards_step.py" line="560"/>
        <source>Arrêt demandé…</source>
        <translation>Stopping…</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/cards_step.py" line="564"/>
        <source>Le dossier est déjà complet.</source>
        <translation>The folder is already complete.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/cards_step.py" line="569"/>
        <source>%1 carte(s) à récupérer, %2 Mo…</source>
        <translation>%1 card(s) to fetch, %2 MB…</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/cards_step.py" line="577"/>
        <source>Téléchargement : %1</source>
        <translation>Downloading: %1</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/cards_step.py" line="597"/>
        <source>%1 échec(s), dont %2 : %3</source>
        <translation>%1 failure(s), including %2: %3</translation>
    </message>
    <message numerus="yes">
        <location filename="../src/pokemon_mosaic/ui/cards_step.py" line="602"/>
        <source>%n carte(s) récupérée(s).</source>
        <translation>
            <numerusform>%n card fetched.</numerusform>
            <numerusform>%n cards fetched.</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/cards_step.py" line="640"/>
        <source>Téléchargement impossible : %1</source>
        <translation>Download failed: %1</translation>
    </message>
    <message numerus="yes">
        <location filename="../src/pokemon_mosaic/ui/cards_step.py" line="673"/>
        <source>%n carte(s) chargée(s).</source>
        <translation>
            <numerusform>%n card loaded.</numerusform>
            <numerusform>%n cards loaded.</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/cards_step.py" line="694"/>
        <source>Échec du chargement : %1</source>
        <translation>Loading failed: %1</translation>
    </message>
    <message numerus="yes">
        <location filename="../src/pokemon_mosaic/ui/cards_step.py" line="705"/>
        <source>%n carte(s) exclue(s) ou liée(s) ont disparu du dossier : leur réglage n&apos;a pas été repris.</source>
        <translation>
            <numerusform>%n excluded or linked card has disappeared from the folder: its setting was not restored.</numerusform>
            <numerusform>%n excluded or linked cards have disappeared from the folder: their settings were not restored.</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/cards_step.py" line="734"/>
        <source>Arrêt en cours : le chargement ne répond pas encore.</source>
        <translation>Stopping: the loading is not responding yet.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/cards_step.py" line="764"/>
        <source>Série %1  (%2)</source>
        <translation>Series %1  (%2)</translation>
    </message>
    <message numerus="yes">
        <location filename="../src/pokemon_mosaic/ui/cards_step.py" line="852"/>
        <source>Inclure les %n affichée(s)</source>
        <translation>
            <numerusform>Include the %n shown</numerusform>
            <numerusform>Include the %n shown</numerusform>
        </translation>
    </message>
    <message numerus="yes">
        <location filename="../src/pokemon_mosaic/ui/cards_step.py" line="854"/>
        <source>Exclure les %n affichée(s)</source>
        <translation>
            <numerusform>Exclude the %n shown</numerusform>
            <numerusform>Exclude the %n shown</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/cards_step.py" line="861"/>
        <source>Inverser</source>
        <translation>Invert</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/cards_step.py" line="863"/>
        <source>Les cartes affichées changent de camp : les incluses sortent, les exclues rentrent.</source>
        <translation>The shown cards swap sides: the included ones drop out, the excluded ones come back.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/cards_step.py" line="866"/>
        <source>Toutes les cartes changent de camp : les incluses sortent, les exclues rentrent.</source>
        <translation>Every card swaps sides: the included ones drop out, the excluded ones come back.</translation>
    </message>
    <message numerus="yes">
        <location filename="../src/pokemon_mosaic/ui/cards_step.py" line="904"/>
        <source>%n carte(s) trouvée(s)</source>
        <translation>
            <numerusform>%n card found</numerusform>
            <numerusform>%n cards found</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/cards_step.py" line="300"/>
        <location filename="../src/pokemon_mosaic/ui/cards_step.py" line="890"/>
        <source>Aucune carte chargée</source>
        <translation>No cards loaded</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/cards_step.py" line="291"/>
        <source>Inclure l&apos;extension</source>
        <translation>Include the set</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/cards_step.py" line="292"/>
        <source>Exclure l&apos;extension</source>
        <translation>Exclude the set</translation>
    </message>
    <message numerus="yes">
        <location filename="../src/pokemon_mosaic/ui/cards_step.py" line="610"/>
        <source>Téléchargement interrompu : %n carte(s) récupérée(s).</source>
        <translation>
            <numerusform>Download interrupted: %n card retrieved.</numerusform>
            <numerusform>Download interrupted: %n cards retrieved.</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/cards_step.py" line="892"/>
        <source>%1 cartes retenues sur %2</source>
        <translation>%1 of %2 cards kept</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/cards_step.py" line="898"/>
        <source>filtré sur %1</source>
        <translation>filtered on %1</translation>
    </message>
    <message numerus="yes">
        <location filename="../src/pokemon_mosaic/ui/cards_step.py" line="900"/>
        <source>filtré sur %n dossiers</source>
        <translation>
            <numerusform>filtered on %n folder</numerusform>
            <numerusform>filtered on %n folders</numerusform>
        </translation>
    </message>
</context>
<context>
    <name>ColoursTab</name>
    <message>
        <location filename="../src/pokemon_mosaic/ui/export_step.py" line="295"/>
        <source>Couleurs des vides</source>
        <translation>Colours of the voids</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/export_step.py" line="298"/>
        <source>Autour de la grille</source>
        <translation>Around the grid</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/export_step.py" line="299"/>
        <source>Entre les cartes</source>
        <translation>Between the cards</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/export_step.py" line="300"/>
        <source>Cases vides</source>
        <translation>Empty cells</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/export_step.py" line="303"/>
        <source>Prélever une couleur dans l&apos;image</source>
        <translation>Pick a colour from the image</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/export_step.py" line="304"/>
        <source>Caméléon</source>
        <translation>Chameleon</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/export_step.py" line="305"/>
        <source>Écarts entre les cartes</source>
        <translation>Gaps between the cards</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/export_step.py" line="306"/>
        <source>Pourtour de la grille</source>
        <translation>Around the grid</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/export_step.py" line="308"/>
        <source>Chaque écart passe d&apos;un bord de carte à l&apos;autre en dégradé, au lieu d&apos;un aplat.</source>
        <translation>Each gap fades from one card edge to the other, instead of a flat colour.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/export_step.py" line="311"/>
        <source>Une bande large comme l&apos;écart cerne la mosaïque, du bord des cartes vers la couleur du fond.</source>
        <translation>A band as wide as the gap surrounds the mosaic, from the card edges towards the background colour.</translation>
    </message>
</context>
<context>
    <name>CutTab</name>
    <message>
        <location filename="../src/pokemon_mosaic/ui/export_step.py" line="382"/>
        <source>Coupe</source>
        <translation>Cutting</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/export_step.py" line="385"/>
        <source>Chevauchement (mm)</source>
        <translation>Overlap (mm)</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/export_step.py" line="386"/>
        <source>Repères de coupe</source>
        <translation>Crop marks</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/export_step.py" line="402"/>
        <source>Une bande commune à deux feuilles voisines, pour les rabouter sans laisser de blanc, et de discrets repères aux angles pour rogner droit.</source>
        <translation>A strip shared by two neighbouring sheets, to join them without a white line, and discreet marks at the corners to trim straight.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/export_step.py" line="405"/>
        <source>Une seule feuille : rien à rabouter.</source>
        <translation>A single sheet: nothing to join.</translation>
    </message>
</context>
<context>
    <name>ExportDialog</name>
    <message>
        <location filename="../src/pokemon_mosaic/ui/export_dialog.py" line="133"/>
        <source>Exporter le poster</source>
        <translation>Export the poster</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/export_dialog.py" line="134"/>
        <source>Mise en page</source>
        <translation>Layout</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/export_dialog.py" line="135"/>
        <source>Format</source>
        <translation>Format</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/export_dialog.py" line="136"/>
        <source>Qualité JPEG</source>
        <translation>JPEG quality</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/export_dialog.py" line="142"/>
        <source>Parcourir…</source>
        <translation>Browse…</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/export_dialog.py" line="137"/>
        <source>Dossier</source>
        <translation>Folder</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/export_dialog.py" line="138"/>
        <source>Nom des fichiers</source>
        <translation>File name</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/export_dialog.py" line="140"/>
        <source>Le nom de base. Une feuille seule le porte tel quel ; plusieurs y ajoutent « page1 », « page2 ».</source>
        <translation>The base name. A single sheet carries it as is; several add “page1”, “page2”.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/export_dialog.py" line="179"/>
        <source>Où écrire le poster</source>
        <translation>Where to write the poster</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/export_dialog.py" line="236"/>
        <source>paysage</source>
        <translation>landscape</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/export_dialog.py" line="237"/>
        <source>portrait</source>
        <translation>portrait</translation>
    </message>
    <message numerus="yes">
        <location filename="../src/pokemon_mosaic/ui/export_dialog.py" line="238"/>
        <source>%n panneau(x)</source>
        <translation>
            <numerusform>%n panel</numerusform>
            <numerusform>%n panels</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/export_dialog.py" line="256"/>
        <source>images d&apos;origine</source>
        <translation>original images</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/export_dialog.py" line="257"/>
        <source>vignettes, rendu rapide et flou à l&apos;impression</source>
        <translation>thumbnails, fast to render and blurry in print</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/export_dialog.py" line="259"/>
        <source>%1 × %2 cartes de %3 × %4 px : %5 × %6 px par panneau, %7 Mpx au total (%8)</source>
        <translation>%1 × %2 cards of %3 × %4 px, %5 × %6 px per panel, %7 Mpx in total (%8)</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/export_dialog.py" line="285"/>
        <source>Fichier(s) : %1</source>
        <translation>File(s): %1</translation>
    </message>
    <message numerus="yes">
        <location filename="../src/pokemon_mosaic/ui/export_dialog.py" line="287"/>
        <source>%n fichier(s) seront écrasés</source>
        <translation>
            <numerusform>%n file will be overwritten</numerusform>
            <numerusform>%n files will be overwritten</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/export_dialog.py" line="295"/>
        <source>Choisissez un dossier de destination.</source>
        <translation>Choose a destination folder.</translation>
    </message>
</context>
<context>
    <name>ExportStep</name>
    <message>
        <location filename="../src/pokemon_mosaic/ui/export_step.py" line="895"/>
        <source>Cliquez dans l&apos;image pour prélever une couleur.</source>
        <translation>Click in the image to pick a colour.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/export_step.py" line="982"/>
        <source>Tirez la mosaïque pour la placer sur sa feuille.</source>
        <translation>Drag the mosaic to place it on its sheet.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/export_step.py" line="1019"/>
        <source>Derniers ajustements avant l&apos;export</source>
        <translation>Final touches before exporting</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/export_step.py" line="1023"/>
        <source>Ajuster</source>
        <translation>Fit</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/export_step.py" line="1025"/>
        <source>Déplacer la mosaïque dans sa feuille, à la souris.</source>
        <translation>Move the mosaic within its sheet, with the mouse.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/export_step.py" line="1027"/>
        <source>Molette ou pincement pour zoomer, glissement pour se déplacer.</source>
        <translation>Wheel or pinch to zoom, drag to move around.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/export_step.py" line="1030"/>
        <source>Exporter cet agencement…</source>
        <translation>Export this arrangement…</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/export_step.py" line="1031"/>
        <source>Annuler l&apos;export</source>
        <translation>Cancel the export</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/export_step.py" line="1105"/>
        <source>Des cartes sortent des pages : ajoutez une feuille, réduisez la taille des cartes ou l&apos;écart.</source>
        <translation>Some cards fall outside the pages: add a sheet, or reduce the card size or the gap.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/export_step.py" line="1108"/>
        <source>Aucun agencement gardé.</source>
        <translation>No arrangement kept.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/export_step.py" line="1120"/>
        <source>Agencement %1 sur %2, score %3</source>
        <translation>Arrangement %1 of %2, score %3</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/export_step.py" line="1176"/>
        <source>Export en cours…</source>
        <translation>Exporting…</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/export_step.py" line="1194"/>
        <source>Panneau %1 / %2 : %3</source>
        <translation>Panel %1 / %2: %3</translation>
    </message>
    <message numerus="yes">
        <location filename="../src/pokemon_mosaic/ui/export_step.py" line="1209"/>
        <source>%n fichier(s) écrit(s) : %1</source>
        <translation>
            <numerusform>%n file written: %1</numerusform>
            <numerusform>%n files written: %1</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/export_step.py" line="1216"/>
        <source>Export annulé ; les fichiers partiels ont été effacés.</source>
        <translation>Export cancelled; the partial files were removed.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/export_step.py" line="1222"/>
        <source>Échec de l&apos;export : %1</source>
        <translation>Export failed: %1</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/export_step.py" line="1241"/>
        <source>Arrêt en cours : l&apos;export ne répond pas encore.</source>
        <translation>Stopping: the export is not answering yet.</translation>
    </message>
</context>
<context>
    <name>GridSizeTab</name>
    <message>
        <location filename="../src/pokemon_mosaic/ui/layout_tabs.py" line="134"/>
        <source>Taille et cases vides</source>
        <translation>Size and blank cells</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/layout_tabs.py" line="300"/>
        <source>Colonnes</source>
        <translation>Columns</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/layout_tabs.py" line="301"/>
        <source>Lignes</source>
        <translation>Rows</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/layout_tabs.py" line="302"/>
        <source>Recommandations de grilles</source>
        <translation>Grid recommendations</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/layout_tabs.py" line="303"/>
        <source>Double-cliquez pour appliquer</source>
        <translation>Double-click to apply</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/layout_tabs.py" line="304"/>
        <source>Placer les vides automatiquement</source>
        <translation>Place the blanks automatically</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/layout_tabs.py" line="306"/>
        <source>Répartit régulièrement les cases vides qui manquent, sans défaire celles que vous avez posées.</source>
        <translation>Spreads the missing blank cells evenly, without undoing the ones you placed.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/layout_tabs.py" line="309"/>
        <source>Tout retirer</source>
        <translation>Remove them all</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/layout_tabs.py" line="347"/>
        <source>pile poil</source>
        <translation>exact fit</translation>
    </message>
    <message numerus="yes">
        <location filename="../src/pokemon_mosaic/ui/layout_tabs.py" line="349"/>
        <source>%n case(s) vide(s)</source>
        <translation>
            <numerusform>%n blank cell</numerusform>
            <numerusform>%n blank cells</numerusform>
        </translation>
    </message>
    <message numerus="yes">
        <location filename="../src/pokemon_mosaic/ui/layout_tabs.py" line="351"/>
        <source>%n carte(s) en trop</source>
        <translation>
            <numerusform>%n card too many</numerusform>
            <numerusform>%n cards too many</numerusform>
        </translation>
    </message>
    <message numerus="yes">
        <location filename="../src/pokemon_mosaic/ui/layout_tabs.py" line="389"/>
        <source>&lt;b&gt;%n&lt;/b&gt; carte(s) ne tiennent pas dans la grille : agrandissez-la, ou retirez-les à l&apos;étape précédente.</source>
        <translation>
            <numerusform>&lt;b&gt;%n&lt;/b&gt; card does not fit in the grid: enlarge it, or drop it at the previous step.</numerusform>
            <numerusform>&lt;b&gt;%n&lt;/b&gt; cards do not fit in the grid: enlarge it, or drop them at the previous step.</numerusform>
        </translation>
    </message>
    <message numerus="yes">
        <location filename="../src/pokemon_mosaic/ui/layout_tabs.py" line="393"/>
        <source>Il reste &lt;b&gt;%n&lt;/b&gt; case(s) vide(s) à placer : cliquez dans la grille pour choisir où.</source>
        <translation>
            <numerusform>&lt;b&gt;%n&lt;/b&gt; blank cell left to place: click in the grid to choose where.</numerusform>
            <numerusform>&lt;b&gt;%n&lt;/b&gt; blank cells left to place: click in the grid to choose where.</numerusform>
        </translation>
    </message>
    <message numerus="yes">
        <location filename="../src/pokemon_mosaic/ui/layout_tabs.py" line="397"/>
        <source>Les &lt;b&gt;%n&lt;/b&gt; case(s) vide(s) sont placées.</source>
        <translation>
            <numerusform>The &lt;b&gt;%n&lt;/b&gt; blank cell is placed.</numerusform>
            <numerusform>The &lt;b&gt;%n&lt;/b&gt; blank cells are placed.</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/layout_tabs.py" line="400"/>
        <source>La grille a exactement autant de cases que de cartes retenues.</source>
        <translation>The grid has exactly as many cells as selected cards.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/layout_tabs.py" line="404"/>
        <source>Des cartes sortent des pages : réduisez la grille, ajoutez une feuille, ou diminuez la taille des cartes à l&apos;onglet suivant.</source>
        <translation>Some cards fall outside the pages: shrink the grid, add a sheet, or reduce the card size in the next tab.</translation>
    </message>
</context>
<context>
    <name>HelpButton</name>
    <message>
        <location filename="../src/pokemon_mosaic/ui/tutorial.py" line="550"/>
        <source>Afficher ou masquer l&apos;aide de cette page. Clic droit : revoir les visites guidées.</source>
        <translation>Show or hide this page’s help. Right-click: replay the guided tours.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/tutorial.py" line="552"/>
        <source>Revoir les visites guidées</source>
        <translation>Replay the guided tours</translation>
    </message>
</context>
<context>
    <name>LayoutStep</name>
    <message>
        <location filename="../src/pokemon_mosaic/ui/layout_step.py" line="413"/>
        <source>Grille</source>
        <translation>Grid</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/layout_step.py" line="454"/>
        <source>Cliquez « Suivant » sur les parties précédentes pour ouvrir celle-ci.</source>
        <translation>Click “Next” on the earlier parts to open this one.</translation>
    </message>
</context>
<context>
    <name>LinkDialog</name>
    <message>
        <location filename="../src/pokemon_mosaic/ui/link_dialog.py" line="141"/>
        <source>Modifier le lien</source>
        <translation>Edit link</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/link_dialog.py" line="142"/>
        <source>Nouveau lien</source>
        <translation>New link</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/link_dialog.py" line="143"/>
        <source>Le lien</source>
        <translation>The link</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/link_dialog.py" line="144"/>
        <source>Cartes disponibles</source>
        <translation>Available cards</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/link_dialog.py" line="145"/>
        <source>Filtrer par nom…</source>
        <translation>Filter by name…</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/link_dialog.py" line="148"/>
        <source>Ordre imposé (sinon l&apos;optimiseur peut le pivoter d&apos;un demi-tour)</source>
        <translation>Fixed order (otherwise the optimiser may turn it half way round)</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/link_dialog.py" line="151"/>
        <source>Montrer ce qu&apos;est ce demi-tour</source>
        <translation>Show what that half turn does</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/link_dialog.py" line="198"/>
        <source>Toutes les extensions</source>
        <translation>All sets</translation>
    </message>
    <message numerus="yes">
        <location filename="../src/pokemon_mosaic/ui/link_dialog.py" line="249"/>
        <source>Toutes les cases doivent être remplies : il en reste %n vide(s). Faites glisser une carte depuis la droite.</source>
        <translation>
            <numerusform>Every cell must be filled: %n is still empty. Drag a card in from the right.</numerusform>
            <numerusform>Every cell must be filled: %n are still empty. Drag a card in from the right.</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/link_dialog.py" line="253"/>
        <source>Un lien groupe au moins deux cartes : ajoutez une ligne ou une colonne.</source>
        <translation>A link groups at least two cards: add a row or a column.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/link_dialog.py" line="255"/>
        <source>Rectangle %1 × %2, complet.</source>
        <translation>Rectangle %1 × %2, complete.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/link_dialog.py" line="146"/>
        <source>Nom (facultatif)</source>
        <translation>Name (optional)</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/link_dialog.py" line="190"/>
        <source>(carte exclue)</source>
        <translation>(card excluded)</translation>
    </message>
</context>
<context>
    <name>LinkGrid</name>
    <message>
        <location filename="../src/pokemon_mosaic/ui/link_grid.py" line="351"/>
        <source>Ajouter une ligne</source>
        <translation>Add a row</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/link_grid.py" line="361"/>
        <source>Supprimer cette ligne</source>
        <translation>Remove this row</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/link_grid.py" line="376"/>
        <source>Ajouter une colonne</source>
        <translation>Add a column</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/link_grid.py" line="386"/>
        <source>Supprimer cette colonne</source>
        <translation>Remove this column</translation>
    </message>
</context>
<context>
    <name>LinksPanel</name>
    <message>
        <location filename="../src/pokemon_mosaic/ui/links_panel.py" line="75"/>
        <source>Liens</source>
        <translation>Links</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/links_panel.py" line="76"/>
        <source>Nouveau…</source>
        <translation>New…</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/links_panel.py" line="77"/>
        <source>Modifier…</source>
        <translation>Edit…</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/links_panel.py" line="78"/>
        <source>Supprimer</source>
        <translation>Delete</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/links_panel.py" line="113"/>
        <source>Une carte de ce lien est exclue : il ne s&apos;appliquera pas.</source>
        <translation>One card of this link is excluded: it will not apply.</translation>
    </message>
    <message numerus="yes">
        <location filename="../src/pokemon_mosaic/ui/links_panel.py" line="126"/>
        <source>%n lien(s) actif(s) sur une carte exclue : ignoré(s) au calcul.</source>
        <translation>
            <numerusform>%n active link on an excluded card: ignored.</numerusform>
            <numerusform>%n active links on excluded cards: ignored.</numerusform>
        </translation>
    </message>
</context>
<context>
    <name>MainWindow</name>
    <message>
        <location filename="../src/pokemon_mosaic/ui/main_window.py" line="109"/>
        <source>Cartes</source>
        <translation>Cards</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/main_window.py" line="110"/>
        <source>Paramètres</source>
        <translation>Parameters</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/main_window.py" line="111"/>
        <source>Exécution</source>
        <translation>Run</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/main_window.py" line="112"/>
        <source>Export</source>
        <translation>Export</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/main_window.py" line="336"/>
        <source>Les visites guidées reviendront à la prochaine ouverture de chaque page.</source>
        <translation>The guided tours will come back the next time each page opens.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/main_window.py" line="371"/>
        <source>Agencement « %1 » repris : cartes, grille et habillage.</source>
        <translation>Arrangement “%1” taken up: cards, grid and presentation.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/main_window.py" line="490"/>
        <source>Fermeture forcée : un traitement de fond n&apos;a pas répondu.</source>
        <translation>Closing anyway: a background task did not respond.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/main_window.py" line="497"/>
        <source>Pokémon Mosaic</source>
        <translation>Pokémon Mosaic</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/main_window.py" line="500"/>
        <source>Précédent</source>
        <translation>Back</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/main_window.py" line="501"/>
        <source>Suivant</source>
        <translation>Next</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/main_window.py" line="502"/>
        <source>Langue</source>
        <translation>Language</translation>
    </message>
</context>
<context>
    <name>MultiRunTab</name>
    <message>
        <location filename="../src/pokemon_mosaic/ui/multi_run_tab.py" line="273"/>
        <source>Nombre de lancements</source>
        <translation>Number of runs</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/multi_run_tab.py" line="275"/>
        <source>Vingt au plus. Ils tournent l&apos;un après l&apos;autre, avec les mêmes réglages.</source>
        <translation>Twenty at most. They run one after the other, with the same settings.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/multi_run_tab.py" line="277"/>
        <source>Lancer</source>
        <translation>Start</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/multi_run_tab.py" line="278"/>
        <source>Arrêter</source>
        <translation>Stop</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/multi_run_tab.py" line="279"/>
        <source>Garder</source>
        <translation>Keep</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/multi_run_tab.py" line="281"/>
        <source>Le met dans une des quatre cases, pour l&apos;export, et dans la bibliothèque.</source>
        <translation>Puts it in one of the four slots, for export, and in the library.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/multi_run_tab.py" line="283"/>
        <source>Enregistrer dans la bibliothèque</source>
        <translation>Save to the library</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/multi_run_tab.py" line="285"/>
        <source>L&apos;écrit dans la bibliothèque des agencements, sans prendre de case.</source>
        <translation>Writes it to the arrangement library, without taking a slot.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/multi_run_tab.py" line="287"/>
        <source>Dézoomer</source>
        <translation>Zoom out</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/multi_run_tab.py" line="288"/>
        <source>Zoomer</source>
        <translation>Zoom in</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/multi_run_tab.py" line="325"/>
        <source>Calcul en cours…</source>
        <translation>Running…</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/multi_run_tab.py" line="328"/>
        <source>Multi-lancement en cours…</source>
        <translation>Multi-run in progress…</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/multi_run_tab.py" line="351"/>
        <source>Arrêt en cours : %1 ne répond pas encore.</source>
        <translation>Stopping: %1 is not responding yet.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/multi_run_tab.py" line="352"/>
        <source>le multi-lancement</source>
        <translation>the multi-run</translation>
    </message>
    <message numerus="yes">
        <location filename="../src/pokemon_mosaic/ui/multi_run_tab.py" line="382"/>
        <source>Multi-lancement terminé : %n lancement(s).</source>
        <translation>
            <numerusform>Multi-run finished: %n run.</numerusform>
            <numerusform>Multi-run finished: %n runs.</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/multi_run_tab.py" line="387"/>
        <source>Échec du multi-lancement : %1</source>
        <translation>Multi-run failed: %1</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/multi_run_tab.py" line="555"/>
        <source>Lancement %1</source>
        <translation>Run %1</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/multi_run_tab.py" line="560"/>
        <source>meilleur score %1</source>
        <translation>best score %1</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/multi_run_tab.py" line="563"/>
        <source>interrompu</source>
        <translation>interrupted</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/multi_run_tab.py" line="577"/>
        <source>Les quatre cases sont prises : retirez-en une.</source>
        <translation>All four slots are taken: remove one.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/multi_run_tab.py" line="584"/>
        <source>Agencement gardé, mais non enregistré : %1</source>
        <translation>Arrangement kept, but not written: %1</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/multi_run_tab.py" line="588"/>
        <source>Agencement gardé : %1</source>
        <translation>Arrangement kept: %1</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/multi_run_tab.py" line="589"/>
        <source>Agencement gardé.</source>
        <translation>Arrangement kept.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/multi_run_tab.py" line="604"/>
        <source>Échec de l&apos;enregistrement : %1</source>
        <translation>Saving failed: %1</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/multi_run_tab.py" line="608"/>
        <source>Agencement enregistré : %1</source>
        <translation>Arrangement saved: %1</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/multi_run_tab.py" line="621"/>
        <source>Lancement %1, cliché %2, score %3</source>
        <translation>Run %1, snapshot %2, score %3</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/multi_run_tab.py" line="692"/>
        <source>Durée estimée : %1</source>
        <translation>Estimated duration: %1</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/multi_run_tab.py" line="698"/>
        <source>Lancement %1 sur %2</source>
        <translation>Run %1 of %2</translation>
    </message>
    <message numerus="yes">
        <location filename="../src/pokemon_mosaic/ui/multi_run_tab.py" line="709"/>
        <source>%n lancement(s) terminé(s).</source>
        <translation>
            <numerusform>%n run finished.</numerusform>
            <numerusform>%n runs finished.</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/multi_run_tab.py" line="710"/>
        <source>Plus le score est bas, plus l&apos;agencement est optimisé.</source>
        <translation>The lower the score, the better optimised the arrangement.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/multi_run_tab.py" line="713"/>
        <source>Chaque lancement garde ses cinq derniers clichés.</source>
        <translation>Each run keeps its last five snapshots.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/multi_run_tab.py" line="728"/>
        <source>Reprendre</source>
        <translation>Resume</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/multi_run_tab.py" line="728"/>
        <source>Pause</source>
        <translation>Pause</translation>
    </message>
</context>
<context>
    <name>PagePreview</name>
    <message>
        <location filename="../src/pokemon_mosaic/ui/page_preview.py" line="160"/>
        <source>Ajouter une feuille à droite</source>
        <translation>Add a sheet on the right</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/page_preview.py" line="161"/>
        <source>Ajouter une ligne de feuilles</source>
        <translation>Add a row of sheets</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/page_preview.py" line="163"/>
        <location filename="../src/pokemon_mosaic/ui/page_preview.py" line="212"/>
        <source>Retirer une feuille</source>
        <translation>Remove a sheet</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/page_preview.py" line="165"/>
        <location filename="../src/pokemon_mosaic/ui/page_preview.py" line="216"/>
        <source>Retirer une ligne de feuilles</source>
        <translation>Remove a row of sheets</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/page_preview.py" line="939"/>
        <source>carte réelle
%1 × %2 cm</source>
        <translation>real card
%1 × %2 cm</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/page_preview.py" line="971"/>
        <location filename="../src/pokemon_mosaic/ui/page_preview.py" line="986"/>
        <source>%1 cm</source>
        <translation>%1 cm</translation>
    </message>
</context>
<context>
    <name>PaperTab</name>
    <message>
        <location filename="../src/pokemon_mosaic/ui/layout_tabs.py" line="532"/>
        <source>Format de la feuille</source>
        <translation>Sheet format</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/layout_tabs.py" line="533"/>
        <source>Format</source>
        <translation>Format</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/layout_tabs.py" line="534"/>
        <source>Largeur (cm)</source>
        <translation>Width (cm)</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/layout_tabs.py" line="535"/>
        <source>Hauteur (cm)</source>
        <translation>Height (cm)</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/layout_tabs.py" line="539"/>
        <source>Choisissez le format de la feuille, et appuyez sur les boutons + ou − pour ajouter ou enlever des feuilles.</source>
        <translation>Choose the sheet format, then press the + or − buttons to add or remove sheets.</translation>
    </message>
    <message numerus="yes">
        <location filename="../src/pokemon_mosaic/ui/layout_tabs.py" line="593"/>
        <source>%n feuille(s) de %1 × %2 cm : surface totale de %3 × %4 cm.</source>
        <translation>
            <numerusform>%n sheet of %1 × %2 cm, %3 × %4 cm in total.</numerusform>
            <numerusform>%n sheets of %1 × %2 cm, %3 × %4 cm in total.</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/layout_tabs.py" line="435"/>
        <source>Pages</source>
        <translation>Pages</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/layout_tabs.py" line="536"/>
        <source>Paysage</source>
        <translation>Landscape</translation>
    </message>
</context>
<context>
    <name>PlacementTab</name>
    <message>
        <location filename="../src/pokemon_mosaic/ui/layout_tabs.py" line="931"/>
        <source>Emplacement de la grille</source>
        <translation>Grid placement</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/layout_tabs.py" line="980"/>
        <source>Cliquez dans la mosaïque et tirez pour la déplacer. Chaque feuille porte son morceau et le déplace pour son compte : un morceau ne passe jamais sur la feuille voisine, sans quoi une coupe tomberait en pleine carte.</source>
        <translation>Click inside the mosaic and drag to move it. Each sheet carries its own piece and moves it independently: a piece never crosses onto the neighbouring sheet, which would put a cut through a card.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/layout_tabs.py" line="985"/>
        <source>Centrer</source>
        <translation>Centre</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/layout_tabs.py" line="987"/>
        <source>Pose chaque morceau au milieu de sa feuille, dans les deux sens. Les feuilles sans carte sont laissées de côté.</source>
        <translation>Puts every piece in the middle of its sheet, both ways. Sheets without cards are left alone.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/layout_tabs.py" line="990"/>
        <source>Remettre en place</source>
        <translation>Put back</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/layout_tabs.py" line="992"/>
        <source>Ramène tous les morceaux à leur emplacement par défaut : calés à gauche, centrés en hauteur.</source>
        <translation>Brings every piece back to its default spot: flush left, vertically centred.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/layout_tabs.py" line="1009"/>
        <source>Les morceaux sont centrés dans leur feuille.</source>
        <translation>Every piece is centred in its sheet.</translation>
    </message>
    <message numerus="yes">
        <location filename="../src/pokemon_mosaic/ui/layout_tabs.py" line="1011"/>
        <source>&lt;b&gt;%n&lt;/b&gt; feuille(s) déplacée(s).</source>
        <translation>
            <numerusform>&lt;b&gt;%n&lt;/b&gt; sheet moved.</numerusform>
            <numerusform>&lt;b&gt;%n&lt;/b&gt; sheets moved.</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/layout_tabs.py" line="1013"/>
        <source>Les morceaux sont à leur emplacement par défaut.</source>
        <translation>Every piece is at its default spot.</translation>
    </message>
</context>
<context>
    <name>PresentationTab</name>
    <message>
        <location filename="../src/pokemon_mosaic/ui/export_step.py" line="195"/>
        <source>Présentation</source>
        <translation>Presentation</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/export_step.py" line="198"/>
        <source>Largeur de la carte (mm)</source>
        <translation>Card width (mm)</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/export_step.py" line="199"/>
        <source>Écart entre les cartes (mm)</source>
        <translation>Gap between cards (mm)</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/export_step.py" line="200"/>
        <source>Taille réelle</source>
        <translation>Real size</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/export_step.py" line="202"/>
        <source>Centrer</source>
        <translation>Centre</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/export_step.py" line="204"/>
        <source>Une carte à sa taille réelle, %1 mm de large.</source>
        <translation>A card at its real size, %1 mm wide.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/export_step.py" line="201"/>
        <source>Au plus grand</source>
        <translation>As large as it fits</translation>
    </message>
</context>
<context>
    <name>PresetsBar</name>
    <message>
        <location filename="../src/pokemon_mosaic/ui/presets_bar.py" line="102"/>
        <source>Préréglage</source>
        <translation>Preset</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/presets_bar.py" line="103"/>
        <source>Charger</source>
        <translation>Load</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/presets_bar.py" line="104"/>
        <source>Enregistrer…</source>
        <translation>Save…</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/presets_bar.py" line="105"/>
        <source>Supprimer</source>
        <translation>Delete</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/presets_bar.py" line="107"/>
        <source>Enregistre la sélection, les liens actifs, la grille et les réglages sous un nom.</source>
        <translation>Saves the selection, the active links, the grid and the settings under a name.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/presets_bar.py" line="110"/>
        <source>Tous les agencements…</source>
        <translation>All arrangements…</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/presets_bar.py" line="125"/>
        <source>Parcourir les agencements enregistrés.</source>
        <translation>Browse the saved arrangements.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/presets_bar.py" line="118"/>
        <source>À cette étape, ajoutez un agencement aux cases avec le bouton « Tous les agencements… » placé sous les cases.</source>
        <translation>At this step, add an arrangement to the slots with the “All arrangements…” button below the slots.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/presets_bar.py" line="122"/>
        <source>Un calcul tourne : attendez sa fin pour partir d&apos;un agencement.</source>
        <translation>A calculation is running: wait for it to end before starting from an arrangement.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/presets_bar.py" line="154"/>
        <source>Enregistrer le préréglage</source>
        <translation>Save the preset</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/presets_bar.py" line="154"/>
        <source>Nom</source>
        <translation>Name</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/presets_bar.py" line="176"/>
        <source>Échec de l&apos;enregistrement : %1</source>
        <translation>Saving failed: %1</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/presets_bar.py" line="181"/>
        <source>Préréglage « %1 » enregistré.</source>
        <translation>Preset “%1” saved.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/presets_bar.py" line="186"/>
        <source>Remplacer le préréglage</source>
        <translation>Replace the preset</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/presets_bar.py" line="187"/>
        <source>« %1 » existe déjà. Le remplacer ?</source>
        <translation>“%1” already exists. Replace it?</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/presets_bar.py" line="199"/>
        <source>Préréglage illisible : %1</source>
        <translation>Unreadable preset: %1</translation>
    </message>
    <message numerus="yes">
        <location filename="../src/pokemon_mosaic/ui/presets_bar.py" line="208"/>
        <source>Préréglage « %1 » chargé : %n carte(s) introuvable(s).</source>
        <translation>
            <numerusform>Preset “%1” loaded: %n card not found.</numerusform>
            <numerusform>Preset “%1” loaded: %n cards not found.</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/presets_bar.py" line="213"/>
        <source>Préréglage « %1 » chargé.</source>
        <translation>Preset “%1” loaded.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/presets_bar.py" line="221"/>
        <source>Supprimer le préréglage</source>
        <translation>Delete the preset</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/presets_bar.py" line="222"/>
        <source>Supprimer « %1 » ? La bibliothèque de liens n&apos;est pas touchée.</source>
        <translation>Delete “%1”? The link library is left untouched.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/presets_bar.py" line="231"/>
        <source>Échec de la suppression : %1</source>
        <translation>Deletion failed: %1</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/presets_bar.py" line="236"/>
        <source>Préréglage « %1 » supprimé.</source>
        <translation>Preset “%1” deleted.</translation>
    </message>
</context>
<context>
    <name>ResolutionTab</name>
    <message>
        <location filename="../src/pokemon_mosaic/ui/export_step.py" line="460"/>
        <source>Résolution</source>
        <translation>Resolution</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/export_step.py" line="463"/>
        <source>Finesse (DPI)</source>
        <translation>Resolution (DPI)</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/export_step.py" line="464"/>
        <source>Images d&apos;origine</source>
        <translation>Original images</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/export_step.py" line="466"/>
        <source>Décochée, l&apos;export se contente des vignettes : rapide, mais flou à l&apos;impression.</source>
        <translation>Unchecked, the export makes do with the thumbnails: fast, but blurry in print.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/export_step.py" line="468"/>
        <source>Aller plus loin</source>
        <translation>Go further</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/export_step.py" line="470"/>
        <source>Dépasser la finesse utile. Au-delà, les cartes sont agrandies sans gagner un pixel de détail.</source>
        <translation>Go past the useful resolution. Beyond it, the cards are enlarged without gaining a single pixel of detail.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/export_step.py" line="514"/>
        <source>Finesse utile atteinte : au-delà, l&apos;impression agrandit les cartes sans ajouter de détail.</source>
        <translation>Useful resolution reached: beyond it, printing enlarges the cards without adding detail.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/export_step.py" line="504"/>
        <source>Chaque feuille fera %1 × %2 pixels.</source>
        <translation>Each sheet will be %1 × %2 pixels.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/export_step.py" line="507"/>
        <source>Finesse utile : %1 DPI.</source>
        <translation>Useful resolution: %1 DPI.</translation>
    </message>
</context>
<context>
    <name>RotationHelp</name>
    <message>
        <location filename="../src/pokemon_mosaic/ui/rotation_help.py" line="85"/>
        <source>Ordre libre : le demi-tour</source>
        <translation>Free order: the half turn</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/rotation_help.py" line="87"/>
        <source>Ordre imposé décoché, l&apos;optimiseur a le droit d&apos;essayer aussi le bloc pivoté d&apos;un demi-tour, et garde celui des deux qui s&apos;accorde le mieux avec ses voisins. Cela lui laisse deux fois plus de placements possibles.</source>
        <translation>With fixed order unchecked, the optimiser may also try the block turned half way round, and keeps whichever of the two sits better with its neighbours. That leaves it twice as many placements to choose from.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/rotation_help.py" line="91"/>
        <source>Sur une ligne, l&apos;ordre s&apos;inverse :</source>
        <translation>On a row, the order reverses:</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/rotation_help.py" line="93"/>
        <source>Sur un carré, chaque carte va dans le coin opposé, ce n&apos;est pas un effet miroir :</source>
        <translation>On a square, every card lands in the opposite corner, this is not a mirror:</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/rotation_help.py" line="96"/>
        <source>La forme ne change jamais : un 3 × 2 pivoté reste un 3 × 2. Gardez l&apos;ordre imposé quand le sens porte quelque chose, une lignée d&apos;évolution, ou une paire qui se lit dans un sens.</source>
        <translation>The shape never changes: a turned 3 × 2 is still a 3 × 2. Keep the order fixed when the direction means something, an evolution line, or a pair that reads one way.</translation>
    </message>
</context>
<context>
    <name>RunStep</name>
    <message>
        <location filename="../src/pokemon_mosaic/ui/run_step.py" line="310"/>
        <source>Lancer</source>
        <translation>Start</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/run_step.py" line="311"/>
        <source>Arrêter</source>
        <translation>Stop</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/run_step.py" line="312"/>
        <source>Dernier</source>
        <translation>Latest</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/run_step.py" line="313"/>
        <source>Prolonger</source>
        <translation>Extend</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/run_step.py" line="314"/>
        <source>Repartir de ce cliché</source>
        <translation>Restart from this snapshot</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/run_step.py" line="316"/>
        <source>Poursuit le calcul depuis le dernier cliché, en conservant toute la timeline.</source>
        <translation>Continues from the latest snapshot, keeping the whole timeline.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/run_step.py" line="320"/>
        <source>Relance le calcul depuis le cliché affiché. Les clichés suivants sont abandonnés.</source>
        <translation>Restarts from the displayed snapshot. Later snapshots are discarded.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/run_step.py" line="323"/>
        <source>Ajuster</source>
        <translation>Fit</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/run_step.py" line="324"/>
        <source>Dézoomer (touche −)</source>
        <translation>Zoom out (− key)</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/run_step.py" line="325"/>
        <source>Zoomer (touche +)</source>
        <translation>Zoom in (+ key)</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/run_step.py" line="326"/>
        <source>Revenir à l&apos;image entière</source>
        <translation>Back to the whole image</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/run_step.py" line="328"/>
        <source>Flèches gauche et droite pour parcourir les clichés.</source>
        <translation>Left and right arrows step through the snapshots.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/run_step.py" line="330"/>
        <source>Lancer le calcul</source>
        <translation>Start the run</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/run_step.py" line="331"/>
        <source>Enregistrer</source>
        <translation>Keep</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/run_step.py" line="334"/>
        <source>Tout est réglé. Lancez le calcul pour voir la mosaïque se construire, cliché après cliché.</source>
        <translation>Everything is set. Start the run to watch the mosaic take shape, snapshot after snapshot.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/run_step.py" line="413"/>
        <source>Agencement repris : « Lancer » part de lui.</source>
        <translation>Arrangement taken up: “Start” continues from it.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/run_step.py" line="457"/>
        <location filename="../src/pokemon_mosaic/ui/run_step.py" line="459"/>
        <source>Calcul en cours…</source>
        <translation>Running…</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/run_step.py" line="582"/>
        <source>Agencement gardé : %1</source>
        <translation>Arrangement kept: %1</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/run_step.py" line="583"/>
        <source>Agencement gardé.</source>
        <translation>Arrangement kept.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/run_step.py" line="594"/>
        <source>Agencement gardé, mais non enregistré : %1</source>
        <translation>Arrangement kept, but not written: %1</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/run_step.py" line="698"/>
        <source>le calcul</source>
        <translation>the run</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/run_step.py" line="697"/>
        <source>Arrêt en cours : %1 ne répond pas encore.</source>
        <translation>Stopping: %1 is not responding yet.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/run_step.py" line="307"/>
        <source>Lancement</source>
        <translation>Run</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/run_step.py" line="308"/>
        <source>Multi-lancement</source>
        <translation>Multi-run</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/run_step.py" line="571"/>
        <source>Les quatre cases sont prises : retirez-en une.</source>
        <translation>All four slots are taken: remove one.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/run_step.py" line="763"/>
        <source>itérations épuisées</source>
        <translation>iterations exhausted</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/run_step.py" line="764"/>
        <source>score atteint</source>
        <translation>target score reached</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/run_step.py" line="765"/>
        <source>stagnation</source>
        <translation>stagnation</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/run_step.py" line="766"/>
        <source>budget de temps</source>
        <translation>time budget</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/run_step.py" line="767"/>
        <source>arrêt demandé</source>
        <translation>stopped by user</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/run_step.py" line="774"/>
        <source>Score %1 → %2 (%3 % de gain), arrêt : %4</source>
        <translation>Score %1 → %2 (%3% gain), stopped: %4</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/run_step.py" line="780"/>
        <source>Calcul terminé.</source>
        <translation>Run finished.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/run_step.py" line="786"/>
        <source>Échec du calcul : %1</source>
        <translation>Run failed: %1</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/run_step.py" line="1028"/>
        <source>Reprendre</source>
        <translation>Resume</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/run_step.py" line="1028"/>
        <source>Pause</source>
        <translation>Pause</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/run_step.py" line="1034"/>
        <source>aucun cliché</source>
        <translation>no snapshot</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/run_step.py" line="1037"/>
        <source>cliché %1 / %2</source>
        <translation>snapshot %1 of %2</translation>
    </message>
</context>
<context>
    <name>SavedColumn</name>
    <message>
        <location filename="../src/pokemon_mosaic/ui/saved_column.py" line="210"/>
        <source>Agencements gardés</source>
        <translation>Kept arrangements</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/saved_column.py" line="211"/>
        <source>Tous les agencements…</source>
        <translation>All arrangements…</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/saved_column.py" line="248"/>
        <source>Retirer cet agencement ?</source>
        <translation>Remove this arrangement?</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/saved_column.py" line="249"/>
        <source>La case %1 sera vidée. L&apos;agencement reste dans la bibliothèque, « Tous les agencements… ».</source>
        <translation>Slot %1 will be emptied. The arrangement stays in the library, “All arrangements…”.</translation>
    </message>
</context>
<context>
    <name>SavedDialog</name>
    <message>
        <location filename="../src/pokemon_mosaic/ui/saved_column.py" line="323"/>
        <source>Agencement gardé</source>
        <translation>Kept arrangement</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/saved_column.py" line="324"/>
        <source>L&apos;agencement n&apos;est plus dans la timeline.</source>
        <translation>This arrangement is no longer in the timeline.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/saved_column.py" line="325"/>
        <source>Fermer</source>
        <translation>Close</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/saved_column.py" line="354"/>
        <source>Aucune image à montrer.</source>
        <translation>No image to show.</translation>
    </message>
</context>
<context>
    <name>SavedSlot</name>
    <message>
        <location filename="../src/pokemon_mosaic/ui/saved_column.py" line="118"/>
        <source>vide</source>
        <translation>empty</translation>
    </message>
</context>
<context>
    <name>StripPreview</name>
    <message>
        <location filename="../src/pokemon_mosaic/ui/strip_preview.py" line="118"/>
        <source>pas assez de cartes</source>
        <translation>not enough cards</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/strip_preview.py" line="165"/>
        <source>Aucune carte chargée</source>
        <translation>No cards loaded</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/strip_preview.py" line="171"/>
        <source>Aucune carte retenue</source>
        <translation>No cards kept</translation>
    </message>
</context>
<context>
    <name>TutorialOverlay</name>
    <message>
        <location filename="../src/pokemon_mosaic/ui/tutorial.py" line="226"/>
        <location filename="../src/pokemon_mosaic/ui/tutorial.py" line="316"/>
        <source>Passer le tutoriel</source>
        <translation>Skip the tutorial</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/tutorial.py" line="317"/>
        <source>Passer le tutoriel de cette page ?</source>
        <translation>Skip this page’s tutorial?</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/tutorial.py" line="318"/>
        <source>Passer aussi tous les tutoriels suivants</source>
        <translation>Also skip all the following tutorials</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/tutorial.py" line="408"/>
        <source>Cliquez pour continuer (%1 sur %2)</source>
        <translation>Click to continue (%1 of %2)</translation>
    </message>
</context>
<context>
    <name>TutorialTexts</name>
    <message>
        <location filename="../src/pokemon_mosaic/ui/tutorial_texts.py" line="25"/>
        <source>Pokémon Mosaic assemble vos cartes en un poster à imprimer. Commencez par récupérer les illustrations.</source>
        <translation>Pokémon Mosaic assembles your cards into a poster to print. Start by getting the illustrations.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/tutorial_texts.py" line="29"/>
        <source>Téléchargez les illustrations dans le dossier de votre choix.</source>
        <translation>Download the illustrations into the folder of your choice.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/tutorial_texts.py" line="33"/>
        <source>Vous avez déjà les illustrations ? Choisissez leur dossier.</source>
        <translation>Already have the illustrations? Choose their folder.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/tutorial_texts.py" line="39"/>
        <source>Cliquez une carte pour l&apos;inclure ou l&apos;exclure du poster.</source>
        <translation>Click a card to include it in the poster or exclude it.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/tutorial_texts.py" line="43"/>
        <source>Vous pouvez filtrer, inclure ou exclure par extension.</source>
        <translation>You can filter, include or exclude by expansion.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/tutorial_texts.py" line="46"/>
        <source>Tapez un nom pour filtrer les cartes.</source>
        <translation>Type a name to filter the cards.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/tutorial_texts.py" line="49"/>
        <source>Incluez, excluez ou inversez d&apos;un coup les cartes affichées.</source>
        <translation>Include, exclude or invert the cards shown in one go.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/tutorial_texts.py" line="53"/>
        <source>Créez des liens pour garder des cartes côte à côte dans le poster.</source>
        <translation>Create links to keep cards side by side in the poster.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/tutorial_texts.py" line="57"/>
        <source>Le nombre de cartes retenues pour le poster.</source>
        <translation>The number of cards kept for the poster.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/tutorial_texts.py" line="60"/>
        <source>Récupérez les nouvelles cartes publiées.</source>
        <translation>Get the newly published cards.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/tutorial_texts.py" line="63"/>
        <source>Les cartes à vérifier : format inattendu ou fichier illisible.</source>
        <translation>Cards to check: unexpected size or unreadable file.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/tutorial_texts.py" line="69"/>
        <source>Réglez les parties dans l&apos;ordre, puis validez chacune avec « Suivant ».</source>
        <translation>Set the parts in order, then confirm each one with “Next”.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/tutorial_texts.py" line="75"/>
        <source>Choisissez le format de la feuille, ou tapez ses dimensions.</source>
        <translation>Choose the sheet format, or type its dimensions.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/tutorial_texts.py" line="79"/>
        <source>Cochez pour mettre la feuille en paysage.</source>
        <translation>Tick to turn the sheet to landscape.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/tutorial_texts.py" line="82"/>
        <source>Vous pouvez ajouter ou enlever des feuilles avec les boutons ＋ et −.</source>
        <translation>You can add or remove sheets with the ＋ and − buttons.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/tutorial_texts.py" line="86"/>
        <source>La surface totale de vos feuilles.</source>
        <translation>The total area of your sheets.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/tutorial_texts.py" line="89"/>
        <source>Les liens qui ne tiennent pas dans la grille.</source>
        <translation>The links that do not fit in the grid.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/tutorial_texts.py" line="94"/>
        <source>Le nombre de colonnes de la grille.</source>
        <translation>The number of columns in the grid.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/tutorial_texts.py" line="97"/>
        <source>Le nombre de lignes de la grille.</source>
        <translation>The number of rows in the grid.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/tutorial_texts.py" line="100"/>
        <source>Double-cliquez une grille recommandée pour l&apos;appliquer.</source>
        <translation>Double-click a recommended grid to apply it.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/tutorial_texts.py" line="104"/>
        <source>Cliquez ou glissez dans la grille pour poser les cases vides.</source>
        <translation>Click or drag in the grid to place the empty cells.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/tutorial_texts.py" line="108"/>
        <source>Placez automatiquement les cases vides qui manquent.</source>
        <translation>Place the missing empty cells automatically.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/tutorial_texts.py" line="111"/>
        <source>Retirez toutes les cases vides.</source>
        <translation>Remove all the empty cells.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/tutorial_texts.py" line="114"/>
        <source>Ce qui reste à régler sur la grille.</source>
        <translation>What is left to set on the grid.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/tutorial_texts.py" line="119"/>
        <source>Réglez la largeur des cartes, ou laissez-la en automatique.</source>
        <translation>Set the card width, or leave it automatic.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/tutorial_texts.py" line="123"/>
        <source>Vous pouvez donner aux cartes la taille d&apos;une vraie carte.</source>
        <translation>You can give the cards the size of a real card.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/tutorial_texts.py" line="127"/>
        <source>Réglez l&apos;écart entre les cartes.</source>
        <translation>Set the gap between cards.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/tutorial_texts.py" line="130"/>
        <source>Affichez les grilles qui tiendraient à cette taille.</source>
        <translation>Show the grids that would fit at this size.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/tutorial_texts.py" line="133"/>
        <source>L&apos;aperçu des cartes sur les feuilles.</source>
        <translation>The preview of the cards on the sheets.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/tutorial_texts.py" line="136"/>
        <source>Vous pouvez continuer quand la grille tient sur les feuilles.</source>
        <translation>You can continue when the grid fits on the sheets.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/tutorial_texts.py" line="142"/>
        <source>Cliquez et tirez dans la mosaïque pour la déplacer sur sa feuille.</source>
        <translation>Click and drag in the mosaic to move it on its sheet.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/tutorial_texts.py" line="146"/>
        <source>Centrez chaque morceau sur sa feuille.</source>
        <translation>Centre each piece on its sheet.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/tutorial_texts.py" line="149"/>
        <source>Remettez les morceaux à leur place par défaut.</source>
        <translation>Put the pieces back in their default place.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/tutorial_texts.py" line="152"/>
        <source>Combien de feuilles ont été déplacées.</source>
        <translation>How many sheets have been moved.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/tutorial_texts.py" line="157"/>
        <source>Vous pouvez garder les valeurs par défaut et passer à la suite.</source>
        <translation>You can keep the default values and move on.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/tutorial_texts.py" line="161"/>
        <source>Réglez l&apos;épaisseur des bandes comparées entre deux cartes voisines.</source>
        <translation>Set the thickness of the strips compared between two neighbouring cards.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/tutorial_texts.py" line="165"/>
        <source>Choisissez tous les combien d&apos;échanges un agencement est enregistré.</source>
        <translation>Choose how many swaps pass between two saved arrangements.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/tutorial_texts.py" line="169"/>
        <source>Choisissez l&apos;algorithme et quand il s&apos;arrête.</source>
        <translation>Choose the algorithm and when it stops.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/tutorial_texts.py" line="172"/>
        <source>La durée estimée du calcul et le gain attendu.</source>
        <translation>The estimated duration of the calculation and the expected gain.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/tutorial_texts.py" line="177"/>
        <source>Lancez un calcul ici, ou plusieurs d&apos;un coup dans Multi-lancement.</source>
        <translation>Start one calculation here, or several at once in Multi-run.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/tutorial_texts.py" line="181"/>
        <source>Lancez le calcul pour voir la mosaïque se construire.</source>
        <translation>Start the calculation to watch the mosaic take shape.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/tutorial_texts.py" line="184"/>
        <source>La mosaïque du cliché affiché.</source>
        <translation>The mosaic of the snapshot shown.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/tutorial_texts.py" line="187"/>
        <source>Parcourez les clichés avec le curseur ou les flèches du clavier.</source>
        <translation>Browse the snapshots with the slider or the arrow keys.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/tutorial_texts.py" line="191"/>
        <source>Zoomez avec + et −, ou revenez à l&apos;image entière.</source>
        <translation>Zoom with + and −, or go back to the whole image.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/tutorial_texts.py" line="194"/>
        <source>Lancez un nouveau calcul.</source>
        <translation>Start a new calculation.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/tutorial_texts.py" line="197"/>
        <source>Mettez le calcul en pause, puis reprenez-le.</source>
        <translation>Pause the calculation, then resume it.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/tutorial_texts.py" line="200"/>
        <source>Arrêtez le calcul.</source>
        <translation>Stop the calculation.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/tutorial_texts.py" line="203"/>
        <source>Poursuivez le calcul depuis le dernier cliché.</source>
        <translation>Continue the calculation from the last snapshot.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/tutorial_texts.py" line="206"/>
        <source>Reprenez du cliché affiché (attention, supprime les clichés d&apos;après).</source>
        <translation>Resume from the snapshot shown (careful, deletes the later snapshots).</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/tutorial_texts.py" line="214"/>
        <source>Les agencements gardés pour l&apos;export. Cliquez pour revoir.</source>
        <translation>The arrangements kept for the export. Click to see again.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/tutorial_texts.py" line="210"/>
        <source>Enregistrez le cliché affiché dans une case, pour l&apos;export.</source>
        <translation>Save the snapshot shown in a slot, for the export.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/tutorial_texts.py" line="220"/>
        <source>Choisissez combien de lancements enchaîner, vingt au plus.</source>
        <translation>Choose how many runs to chain, twenty at most.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/tutorial_texts.py" line="224"/>
        <source>La durée estimée de tous les lancements.</source>
        <translation>The estimated duration of all the runs.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/tutorial_texts.py" line="227"/>
        <source>Lancez les calculs, l&apos;un après l&apos;autre.</source>
        <translation>Start the calculations, one after the other.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/tutorial_texts.py" line="230"/>
        <source>Mettez les lancements en pause, puis reprenez-les.</source>
        <translation>Pause the runs, then resume them.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/tutorial_texts.py" line="233"/>
        <source>Arrêtez les lancements : ce qui est calculé est gardé.</source>
        <translation>Stop the runs: what has been calculated is kept.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/tutorial_texts.py" line="236"/>
        <source>Où en sont les lancements.</source>
        <translation>How far the runs have got.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/tutorial_texts.py" line="239"/>
        <source>La mosaïque en cours de calcul, puis le cliché choisi.</source>
        <translation>The mosaic being calculated, then the chosen snapshot.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/tutorial_texts.py" line="242"/>
        <source>Les derniers clichés de chaque lancement. Cliquez-en un, ou utilisez les flèches.</source>
        <translation>The last snapshots of each run. Click one, or use the arrow keys.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/tutorial_texts.py" line="246"/>
        <source>Le cliché choisi et son score : plus il est bas, mieux c&apos;est.</source>
        <translation>The chosen snapshot and its score: the lower, the better.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/tutorial_texts.py" line="250"/>
        <source>Gardez le cliché choisi dans une case, pour l&apos;export.</source>
        <translation>Keep the chosen snapshot in a slot, for the export.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/tutorial_texts.py" line="253"/>
        <source>Enregistrez-le aussi dans la bibliothèque, sans prendre de case.</source>
        <translation>Also save it in the library, without taking a slot.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/tutorial_texts.py" line="259"/>
        <source>L&apos;aperçu du poster tel qu&apos;il sera imprimé.</source>
        <translation>The preview of the poster as it will be printed.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/tutorial_texts.py" line="262"/>
        <source>Zoomez, ou cliquez « Ajuster » pour déplacer la mosaïque sur sa feuille.</source>
        <translation>Zoom, or click “Adjust” to move the mosaic on its sheet.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/tutorial_texts.py" line="266"/>
        <source>Retouchez la taille des cartes et l&apos;écart, ou centrez la mosaïque.</source>
        <translation>Touch up the card size and the gap, or centre the mosaic.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/tutorial_texts.py" line="270"/>
        <source>Choisissez les couleurs des vides, ou activez le caméléon.</source>
        <translation>Choose the colours of the empty spaces, or turn on chameleon.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/tutorial_texts.py" line="274"/>
        <source>Réglez le chevauchement et les repères pour assembler les feuilles.</source>
        <translation>Set the overlap and the marks to assemble the sheets.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/tutorial_texts.py" line="278"/>
        <source>Réglez la finesse d&apos;impression du fichier.</source>
        <translation>Set the print resolution of the file.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/tutorial_texts.py" line="281"/>
        <source>Choisissez l&apos;agencement à exporter.</source>
        <translation>Choose the arrangement to export.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/tutorial_texts.py" line="284"/>
        <source>Des cartes sortent des pages : corrigez avant d&apos;exporter.</source>
        <translation>Cards go off the pages: fix this before exporting.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/tutorial_texts.py" line="288"/>
        <source>L&apos;agencement affiché et son score.</source>
        <translation>The arrangement shown and its score.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/tutorial_texts.py" line="291"/>
        <source>Exportez l&apos;agencement affiché en fichiers à imprimer.</source>
        <translation>Export the arrangement shown as files to print.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/tutorial_texts.py" line="296"/>
        <source>Les agencements enregistrés. Cliquez-en un pour le voir.</source>
        <translation>The saved arrangements. Click one to see it.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/tutorial_texts.py" line="300"/>
        <source>L&apos;aperçu de l&apos;agencement choisi.</source>
        <translation>The preview of the chosen arrangement.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/tutorial_texts.py" line="303"/>
        <source>Ses cartes : celles qui manquent sont en rouge.</source>
        <translation>Its cards: the missing ones are in red.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/tutorial_texts.py" line="306"/>
        <source>Repartez de cet agencement : cartes, grille et habillage.</source>
        <translation>Start again from this arrangement: cards, grid and finish.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/tutorial_texts.py" line="310"/>
        <source>Mettez cet agencement dans une case, pour l&apos;export.</source>
        <translation>Put this arrangement in a slot, for the export.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/tutorial_texts.py" line="313"/>
        <source>Exportez-le en JSON pour le partager.</source>
        <translation>Export it as JSON to share it.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/tutorial_texts.py" line="316"/>
        <source>Importez un agencement reçu en JSON.</source>
        <translation>Import an arrangement received as JSON.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/tutorial_texts.py" line="319"/>
        <source>Renommez l&apos;agencement choisi.</source>
        <translation>Rename the chosen arrangement.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/tutorial_texts.py" line="322"/>
        <source>Supprimez l&apos;agencement choisi de la bibliothèque.</source>
        <translation>Delete the chosen arrangement from the library.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/tutorial_texts.py" line="327"/>
        <source>Glissez des cartes ici. Agrandissez le rectangle avec les boutons +.</source>
        <translation>Drag cards here. Enlarge the rectangle with the + buttons.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/tutorial_texts.py" line="331"/>
        <source>Les cartes disponibles, à glisser dans le lien.</source>
        <translation>The available cards, to drag into the link.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/tutorial_texts.py" line="334"/>
        <source>Filtrez les cartes par nom.</source>
        <translation>Filter the cards by name.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/tutorial_texts.py" line="337"/>
        <source>Filtrez les cartes par extension.</source>
        <translation>Filter the cards by expansion.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/tutorial_texts.py" line="340"/>
        <source>Cochez pour interdire de pivoter le lien d&apos;un demi-tour.</source>
        <translation>Tick to forbid turning the link half a turn.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/tutorial_texts.py" line="344"/>
        <source>Vous pouvez donner un nom au lien.</source>
        <translation>You can give the link a name.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/tutorial_texts.py" line="347"/>
        <source>Validez quand le rectangle est complet.</source>
        <translation>Confirm when the rectangle is complete.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/tutorial_texts.py" line="352"/>
        <source>Le rappel de la mise en page.</source>
        <translation>A reminder of the layout.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/tutorial_texts.py" line="355"/>
        <source>Choisissez le format des fichiers.</source>
        <translation>Choose the file format.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/tutorial_texts.py" line="358"/>
        <source>Réglez la qualité, pour le JPEG seulement.</source>
        <translation>Set the quality, for JPEG only.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/tutorial_texts.py" line="361"/>
        <source>Choisissez où écrire les fichiers.</source>
        <translation>Choose where to write the files.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/tutorial_texts.py" line="364"/>
        <source>Le nom des fichiers : plusieurs feuilles ajoutent « page1 », « page2 ».</source>
        <translation>The file name: several sheets add “page1”, “page2”.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/tutorial_texts.py" line="368"/>
        <source>La taille des fichiers en pixels.</source>
        <translation>The size of the files in pixels.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/tutorial_texts.py" line="371"/>
        <source>Les fichiers qui seront écrits.</source>
        <translation>The files that will be written.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/tutorial_texts.py" line="374"/>
        <source>Lancez l&apos;export.</source>
        <translation>Start the export.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/tutorial_texts.py" line="379"/>
        <source>Cet agencement gardé n&apos;est plus dans la timeline du calcul.</source>
        <translation>This kept arrangement is no longer in the calculation timeline.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/tutorial_texts.py" line="385"/>
        <source>Enregistrez vos réglages sous un nom, ou repartez d&apos;un agencement enregistré.</source>
        <translation>Save your settings under a name, or start again from a saved arrangement.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/tutorial_texts.py" line="389"/>
        <source>Vous pouvez passer à l&apos;étape suivante quand l&apos;aura est verte.</source>
        <translation>You can move to the next step when the glow is green.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/tutorial_texts.py" line="393"/>
        <source>Cliquez pour afficher l&apos;aide de la page. Clic droit pour revoir les visites guidées.</source>
        <translation>Click to show this page&apos;s help. Right-click to replay the guided tours.</translation>
    </message>
</context>
</TS>
