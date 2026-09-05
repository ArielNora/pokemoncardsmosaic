<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE TS>
<TS version="2.1" language="en_US">
<context>
    <name>AdvancedTab</name>
    <message>
        <location filename="../src/pokemon_mosaic/ui/algorithm_tabs.py" line="85"/>
        <source>Paramètres avancés</source>
        <translation>Advanced settings</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/algorithm_tabs.py" line="305"/>
        <source>le recuit simulé</source>
        <translation>simulated annealing</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/algorithm_tabs.py" line="306"/>
        <source>la descente stricte</source>
        <translation>strict descent</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/algorithm_tabs.py" line="308"/>
        <source>Épaisseur</source>
        <translation>Thickness</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/algorithm_tabs.py" line="309"/>
        <source>&lt;b&gt;La métrique :&lt;/b&gt;</source>
        <translation>&lt;b&gt;The metric:&lt;/b&gt;</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/algorithm_tabs.py" line="311"/>
        <source>C&apos;est la part de chaque carte que l&apos;assemblage regarde : une bande le long de ses quatre bords, dont il compare la couleur moyenne à celle de sa voisine. Fine, elle ne voit que l&apos;extrême bord et laisse les motifs se contredire juste derrière ; large, elle mélange le bord au centre de l&apos;illustration et les raccords se relâchent.</source>
        <translation>The share of each card the assembly looks at: a strip along its four edges, whose average colour it compares with its neighbour&apos;s. Thin, it sees only the very edge and lets the patterns contradict each other just behind; wide, it mixes the edge with the middle of the artwork and the joins loosen.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/algorithm_tabs.py" line="318"/>
        <source>À gauche, la zone mesurée sur une carte. À droite, une petite grille d&apos;essai réoptimisée à cette épaisseur.</source>
        <translation>On the left, the area measured on a card. On the right, a small test grid re-optimised at that thickness.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/algorithm_tabs.py" line="320"/>
        <source>&lt;b&gt;Paramètres de l&apos;algorithme :&lt;/b&gt;</source>
        <translation>&lt;b&gt;Algorithm settings:&lt;/b&gt;</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/algorithm_tabs.py" line="323"/>
        <source>Les valeurs par défaut donnent presque toujours un bon résultat. Vous pouvez les changer, ou passer directement à la suite.</source>
        <translation>The default values almost always give a good result. You may change them, or move straight on.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/algorithm_tabs.py" line="328"/>
        <source>À chaque &lt;b&gt;itération&lt;/b&gt;, l&apos;algorithme tente un &lt;b&gt;échange&lt;/b&gt; : il permute deux cartes de la grille et regarde ce que devient la &lt;b&gt;métrique&lt;/b&gt;, l&apos;écart de couleur entre les bords qui se touchent. L&apos;échange est &lt;b&gt;retenu&lt;/b&gt; s&apos;il rapproche l&apos;&lt;b&gt;agencement&lt;/b&gt; du but, une mosaïque dont les bords voisins se ressemblent, et le calcul continue jusqu&apos;à ce qu&apos;un &lt;b&gt;arrêt&lt;/b&gt; tombe.</source>
        <translation>At every &lt;b&gt;iteration&lt;/b&gt; the algorithm tries a &lt;b&gt;swap&lt;/b&gt;: it exchanges two cards of the grid and looks at what becomes of the &lt;b&gt;metric&lt;/b&gt;, the colour gap between the edges that touch. The swap is &lt;b&gt;kept&lt;/b&gt; if it brings the &lt;b&gt;arrangement&lt;/b&gt; closer to the goal, a mosaic whose neighbouring edges match, and the run carries on until a &lt;b&gt;stop&lt;/b&gt; falls.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/algorithm_tabs.py" line="336"/>
        <source>L&apos;algorithme utilisé est %1</source>
        <translation>The algorithm used is %1</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/algorithm_tabs.py" line="338"/>
        <source>Le recuit accepte au départ %1 d&apos;échanges qui dégradent la métrique, puis devient de plus en plus exigeant.</source>
        <translation>Annealing accepts %1 of swaps that worsen the metric to begin with, then grows steadily more demanding.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/algorithm_tabs.py" line="341"/>
        <source>&lt;b&gt;L&apos;algorithme s&apos;arrête&lt;/b&gt; lorsque :</source>
        <translation>&lt;b&gt;The algorithm stops&lt;/b&gt; when:</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/algorithm_tabs.py" line="342"/>
        <source>il a fait %1 itérations (toujours actif)</source>
        <translation>it has run %1 iterations (always on)</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/algorithm_tabs.py" line="344"/>
        <source>la métrique ne s&apos;améliore plus depuis %1 itérations</source>
        <translation>the metric has not improved for %1 iterations</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/algorithm_tabs.py" line="345"/>
        <source>il a calculé pendant %1</source>
        <translation>it has run for %1</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/algorithm_tabs.py" line="346"/>
        <source>la métrique descend sous %1</source>
        <translation>the metric falls below %1</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/algorithm_tabs.py" line="349"/>
        <source>Un agencement sera enregistré tous les %1 échanges retenus.</source>
        <translation>An arrangement is saved every %1 kept swaps.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/algorithm_tabs.py" line="451"/>
        <source>Durée estimée : %1, gain attendu : environ %2 %, timeline : entre %3 et %4 clichés</source>
        <translation>Estimated duration: %1, expected gain: about %2%, timeline: between %3 and %4 snapshots</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/algorithm_tabs.py" line="457"/>
        <source>trop peu pour naviguer, resserrez la cadence</source>
        <translation>too few to navigate, tighten the cadence</translation>
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
    <name>CardSizeTab</name>
    <message>
        <location filename="../src/pokemon_mosaic/ui/layout_tabs.py" line="602"/>
        <source>Taille des cartes et écarts</source>
        <translation>Card size and gaps</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/layout_tabs.py" line="717"/>
        <source>automatique</source>
        <translation>automatic</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/layout_tabs.py" line="719"/>
        <source>La plus grande taille qui fasse tenir la grille, recalculée à chaque changement.</source>
        <translation>The largest size that lets the grid fit, recomputed on every change.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/layout_tabs.py" line="722"/>
        <source>Taille d&apos;une vraie carte</source>
        <translation>Real card size</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/layout_tabs.py" line="724"/>
        <source>Fixe la largeur à %1 mm, celle d&apos;une carte qu&apos;on tient en main. Ne touche à rien d&apos;autre.</source>
        <translation>Sets the width to %1 mm, that of a card you hold in your hand. Touches nothing else.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/layout_tabs.py" line="728"/>
        <source>Grilles qui tiendraient</source>
        <translation>Grids that would fit</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/layout_tabs.py" line="715"/>
        <source>Largeur d&apos;une carte (mm)</source>
        <translation>Card width (mm)</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/layout_tabs.py" line="716"/>
        <source>Écart entre cartes (mm)</source>
        <translation>Gap between cards (mm)</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/layout_tabs.py" line="729"/>
        <location filename="../src/pokemon_mosaic/ui/layout_tabs.py" line="812"/>
        <source>Double-cliquez pour appliquer</source>
        <translation>Double-click to apply</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/layout_tabs.py" line="731"/>
        <source>Ajoutez des feuilles pour qu&apos;aucune carte ne reste en trop.</source>
        <translation>Add sheets so that no card is left out.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/layout_tabs.py" line="783"/>
        <source>pile poil</source>
        <translation>exact fit</translation>
    </message>
    <message numerus="yes">
        <location filename="../src/pokemon_mosaic/ui/layout_tabs.py" line="785"/>
        <source>%n case(s) vide(s)</source>
        <translation>
            <numerusform>%n blank cell</numerusform>
            <numerusform>%n blank cells</numerusform>
        </translation>
    </message>
    <message numerus="yes">
        <location filename="../src/pokemon_mosaic/ui/layout_tabs.py" line="787"/>
        <source>%n carte(s) en trop</source>
        <translation>
            <numerusform>%n card too many</numerusform>
            <numerusform>%n cards too many</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/layout_tabs.py" line="813"/>
        <source>Aucune grille ne tiendrait à cette taille de carte.</source>
        <translation>No grid would fit at this card size.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/layout_tabs.py" line="845"/>
        <source>Cartes de &lt;b&gt;%1 × %2 mm&lt;/b&gt;, %3 par feuille. La grille tient.</source>
        <translation>Cards of &lt;b&gt;%1 × %2 mm&lt;/b&gt;, %3 per sheet. The grid fits.</translation>
    </message>
    <message numerus="yes">
        <location filename="../src/pokemon_mosaic/ui/layout_tabs.py" line="852"/>
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
        <location filename="../src/pokemon_mosaic/ui/cards_step.py" line="273"/>
        <source>Dossiers</source>
        <translation>Folders</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/cards_step.py" line="744"/>
        <source>Tout inclure</source>
        <translation>Include all</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/cards_step.py" line="745"/>
        <source>Tout exclure</source>
        <translation>Exclude all</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/cards_step.py" line="277"/>
        <source>Choisir le dossier de cartes…</source>
        <translation>Choose card folder…</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/cards_step.py" line="276"/>
        <source>Afficher tous les dossiers</source>
        <translation>Show all folders</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/cards_step.py" line="278"/>
        <source>Mettre à jour le catalogue</source>
        <translation>Update the card list</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/cards_step.py" line="280"/>
        <source>Relit la liste des cartes publiée et récupère celles qui manquent au dossier.</source>
        <translation>Re-reads the published card list and fetches whatever the folder is missing.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/cards_step.py" line="282"/>
        <source>Annuler</source>
        <translation>Cancel</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/cards_step.py" line="285"/>
        <source>Les illustrations ne sont pas fournies avec l&apos;application. Téléchargez-les, ou désignez un dossier qui les contient déjà.</source>
        <translation>The artwork does not ship with the application. Download it, or point to a folder that already holds it.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/cards_step.py" line="288"/>
        <source>Télécharger les cartes…</source>
        <translation>Download the cards…</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/cards_step.py" line="289"/>
        <source>J&apos;ai déjà les cartes : choisir le dossier…</source>
        <translation>I already have the cards: choose the folder…</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/cards_step.py" line="292"/>
        <source>Cliquez une carte pour l&apos;inclure ou l&apos;exclure. Sélectionnez un dossier pour n&apos;afficher que ses cartes.</source>
        <translation>Click a card to include or exclude it. Select a folder to show only its cards.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/cards_step.py" line="295"/>
        <source>Rechercher une carte par nom…</source>
        <translation>Search a card by name…</translation>
    </message>
    <message numerus="yes">
        <location filename="../src/pokemon_mosaic/ui/cards_step.py" line="376"/>
        <source>, et %n autre(s) format(s)</source>
        <translation>
            <numerusform>, and %n other size</numerusform>
            <numerusform>, and %n other sizes</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/cards_step.py" line="379"/>
        <source>%1 carte(s) ne sont pas au format %2 : %3. Elles seront étirées à ce format, ce qui déforme l&apos;illustration et fausse les couleurs de bord dont l&apos;assemblage se sert.</source>
        <translation>%1 card(s) are not %2: %3. They will be stretched to that size, which distorts the artwork and skews the edge colours the assembly relies on.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/cards_step.py" line="386"/>
        <source>%1 fichier(s) illisibles, ignorés : %2</source>
        <translation>%1 unreadable file(s), skipped: %2</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/cards_step.py" line="396"/>
        <source>Dossier contenant les cartes</source>
        <translation>Folder containing the cards</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/cards_step.py" line="426"/>
        <source>Chargement des cartes…</source>
        <translation>Loading cards…</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/cards_step.py" line="455"/>
        <source>Où déposer les cartes</source>
        <translation>Where to put the cards</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/cards_step.py" line="474"/>
        <source>Lecture du catalogue…</source>
        <translation>Reading the card list…</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/cards_step.py" line="489"/>
        <source>Arrêt demandé…</source>
        <translation>Stopping…</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/cards_step.py" line="493"/>
        <source>Le dossier est déjà complet.</source>
        <translation>The folder is already complete.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/cards_step.py" line="498"/>
        <source>%1 carte(s) à récupérer, %2 Mo…</source>
        <translation>%1 card(s) to fetch, %2 MB…</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/cards_step.py" line="506"/>
        <source>Téléchargement : %1</source>
        <translation>Downloading: %1</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/cards_step.py" line="526"/>
        <source>%1 échec(s), dont %2 : %3</source>
        <translation>%1 failure(s), including %2: %3</translation>
    </message>
    <message numerus="yes">
        <location filename="../src/pokemon_mosaic/ui/cards_step.py" line="531"/>
        <source>%n carte(s) récupérée(s).</source>
        <translation>
            <numerusform>%n card fetched.</numerusform>
            <numerusform>%n cards fetched.</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/cards_step.py" line="549"/>
        <source>Téléchargement impossible : %1</source>
        <translation>Download failed: %1</translation>
    </message>
    <message numerus="yes">
        <location filename="../src/pokemon_mosaic/ui/cards_step.py" line="582"/>
        <source>%n carte(s) chargée(s).</source>
        <translation>
            <numerusform>%n card loaded.</numerusform>
            <numerusform>%n cards loaded.</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/cards_step.py" line="593"/>
        <source>Échec du chargement : %1</source>
        <translation>Loading failed: %1</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/cards_step.py" line="622"/>
        <source>Arrêt en cours : le chargement ne répond pas encore.</source>
        <translation>Stopping: the loading is not responding yet.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/cards_step.py" line="652"/>
        <source>Série %1  (%2)</source>
        <translation>Series %1  (%2)</translation>
    </message>
    <message numerus="yes">
        <location filename="../src/pokemon_mosaic/ui/cards_step.py" line="740"/>
        <source>Inclure les %n affichée(s)</source>
        <translation>
            <numerusform>Include the %n shown</numerusform>
            <numerusform>Include the %n shown</numerusform>
        </translation>
    </message>
    <message numerus="yes">
        <location filename="../src/pokemon_mosaic/ui/cards_step.py" line="742"/>
        <source>Exclure les %n affichée(s)</source>
        <translation>
            <numerusform>Exclude the %n shown</numerusform>
            <numerusform>Exclude the %n shown</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/cards_step.py" line="749"/>
        <source>Inverser</source>
        <translation>Invert</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/cards_step.py" line="751"/>
        <source>Les cartes affichées changent de camp : les incluses sortent, les exclues rentrent.</source>
        <translation>The shown cards swap sides: the included ones drop out, the excluded ones come back.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/cards_step.py" line="754"/>
        <source>Toutes les cartes changent de camp : les incluses sortent, les exclues rentrent.</source>
        <translation>Every card swaps sides: the included ones drop out, the excluded ones come back.</translation>
    </message>
    <message numerus="yes">
        <location filename="../src/pokemon_mosaic/ui/cards_step.py" line="792"/>
        <source>%n carte(s) trouvée(s)</source>
        <translation>
            <numerusform>%n card found</numerusform>
            <numerusform>%n cards found</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/cards_step.py" line="283"/>
        <location filename="../src/pokemon_mosaic/ui/cards_step.py" line="778"/>
        <source>Aucune carte chargée</source>
        <translation>No cards loaded</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/cards_step.py" line="274"/>
        <source>Inclure l&apos;extension</source>
        <translation>Include the set</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/cards_step.py" line="275"/>
        <source>Exclure l&apos;extension</source>
        <translation>Exclude the set</translation>
    </message>
    <message numerus="yes">
        <location filename="../src/pokemon_mosaic/ui/cards_step.py" line="539"/>
        <source>Téléchargement interrompu : %n carte(s) récupérée(s).</source>
        <translation>
            <numerusform>Download interrupted: %n card retrieved.</numerusform>
            <numerusform>Download interrupted: %n cards retrieved.</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/cards_step.py" line="780"/>
        <source>%1 cartes retenues sur %2</source>
        <translation>%1 of %2 cards kept</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/cards_step.py" line="786"/>
        <source>filtré sur %1</source>
        <translation>filtered on %1</translation>
    </message>
    <message numerus="yes">
        <location filename="../src/pokemon_mosaic/ui/cards_step.py" line="788"/>
        <source>filtré sur %n dossiers</source>
        <translation>
            <numerusform>filtered on %n folder</numerusform>
            <numerusform>filtered on %n folders</numerusform>
        </translation>
    </message>
</context>
<context>
    <name>ExportDialog</name>
    <message>
        <location filename="../src/pokemon_mosaic/ui/export_dialog.py" line="144"/>
        <source>Exporter le poster</source>
        <translation>Export the poster</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/export_dialog.py" line="145"/>
        <source>Mise en page</source>
        <translation>Layout</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/export_dialog.py" line="146"/>
        <source>Format</source>
        <translation>Format</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/export_dialog.py" line="147"/>
        <source>Finesse (DPI)</source>
        <translation>Resolution (DPI)</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/export_dialog.py" line="149"/>
        <source>Combien de points par pouce l&apos;imprimante recevra. Elle ne change rien aux dimensions du poster, seulement au poids du fichier et à la netteté.</source>
        <translation>How many dots per inch the printer receives. It changes nothing to the poster&apos;s dimensions, only the file size and the sharpness.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/export_dialog.py" line="153"/>
        <source>Résolution</source>
        <translation>Resolution</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/export_dialog.py" line="154"/>
        <source>Qualité JPEG</source>
        <translation>JPEG quality</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/export_dialog.py" line="155"/>
        <source>Chevauchement</source>
        <translation>Overlap</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/export_dialog.py" line="156"/>
        <source>Repères de coupe</source>
        <translation>Crop marks</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/export_dialog.py" line="157"/>
        <source>Fichier</source>
        <translation>File</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/export_dialog.py" line="158"/>
        <source>Parcourir…</source>
        <translation>Browse…</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/export_dialog.py" line="160"/>
        <source>Pleine résolution (relit les images d&apos;origine)</source>
        <translation>Full resolution (re-reads the original images)</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/export_dialog.py" line="162"/>
        <source>Tracer les repères aux angles</source>
        <translation>Draw marks at the corners</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/export_dialog.py" line="194"/>
        <source>Enregistrer le poster</source>
        <translation>Save the poster</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/export_dialog.py" line="239"/>
        <source>paysage</source>
        <translation>landscape</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/export_dialog.py" line="240"/>
        <source>portrait</source>
        <translation>portrait</translation>
    </message>
    <message numerus="yes">
        <location filename="../src/pokemon_mosaic/ui/export_dialog.py" line="241"/>
        <source>%n panneau(x)</source>
        <translation>
            <numerusform>%n panel</numerusform>
            <numerusform>%n panels</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/export_dialog.py" line="260"/>
        <source>images d&apos;origine</source>
        <translation>original images</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/export_dialog.py" line="261"/>
        <source>vignettes, rendu rapide et flou à l&apos;impression</source>
        <translation>thumbnails, fast to render and blurry in print</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/export_dialog.py" line="263"/>
        <source>%1 × %2 cartes de %3 × %4 px : %5 × %6 px par panneau, %7 Mpx au total (%8)</source>
        <translation>%1 × %2 cards of %3 × %4 px, %5 × %6 px per panel, %7 Mpx in total (%8)</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/export_dialog.py" line="289"/>
        <source>Fichier(s) : %1</source>
        <translation>File(s): %1</translation>
    </message>
    <message numerus="yes">
        <location filename="../src/pokemon_mosaic/ui/export_dialog.py" line="291"/>
        <source>%n fichier(s) seront écrasés</source>
        <translation>
            <numerusform>%n file will be overwritten</numerusform>
            <numerusform>%n files will be overwritten</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/export_dialog.py" line="300"/>
        <source>Choisissez un fichier de destination.</source>
        <translation>Choose a destination file.</translation>
    </message>
</context>
<context>
    <name>GridSizeTab</name>
    <message>
        <location filename="../src/pokemon_mosaic/ui/layout_tabs.py" line="124"/>
        <source>Taille et cases vides</source>
        <translation>Size and blank cells</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/layout_tabs.py" line="279"/>
        <source>Colonnes</source>
        <translation>Columns</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/layout_tabs.py" line="280"/>
        <source>Lignes</source>
        <translation>Rows</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/layout_tabs.py" line="281"/>
        <source>Recommandations de grilles</source>
        <translation>Grid recommendations</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/layout_tabs.py" line="282"/>
        <source>Double-cliquez pour appliquer</source>
        <translation>Double-click to apply</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/layout_tabs.py" line="283"/>
        <source>Placer les vides automatiquement</source>
        <translation>Place the blanks automatically</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/layout_tabs.py" line="285"/>
        <source>Répartit régulièrement les cases vides qui manquent, sans défaire celles que vous avez posées.</source>
        <translation>Spreads the missing blank cells evenly, without undoing the ones you placed.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/layout_tabs.py" line="288"/>
        <source>Tout retirer</source>
        <translation>Remove them all</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/layout_tabs.py" line="326"/>
        <source>pile poil</source>
        <translation>exact fit</translation>
    </message>
    <message numerus="yes">
        <location filename="../src/pokemon_mosaic/ui/layout_tabs.py" line="328"/>
        <source>%n case(s) vide(s)</source>
        <translation>
            <numerusform>%n blank cell</numerusform>
            <numerusform>%n blank cells</numerusform>
        </translation>
    </message>
    <message numerus="yes">
        <location filename="../src/pokemon_mosaic/ui/layout_tabs.py" line="330"/>
        <source>%n carte(s) en trop</source>
        <translation>
            <numerusform>%n card too many</numerusform>
            <numerusform>%n cards too many</numerusform>
        </translation>
    </message>
    <message numerus="yes">
        <location filename="../src/pokemon_mosaic/ui/layout_tabs.py" line="368"/>
        <source>&lt;b&gt;%n&lt;/b&gt; carte(s) ne tiennent pas dans la grille : agrandissez-la, ou retirez-les à l&apos;étape précédente.</source>
        <translation>
            <numerusform>&lt;b&gt;%n&lt;/b&gt; card does not fit in the grid: enlarge it, or drop it at the previous step.</numerusform>
            <numerusform>&lt;b&gt;%n&lt;/b&gt; cards do not fit in the grid: enlarge it, or drop them at the previous step.</numerusform>
        </translation>
    </message>
    <message numerus="yes">
        <location filename="../src/pokemon_mosaic/ui/layout_tabs.py" line="372"/>
        <source>Il reste &lt;b&gt;%n&lt;/b&gt; case(s) vide(s) à placer : cliquez dans la grille pour choisir où.</source>
        <translation>
            <numerusform>&lt;b&gt;%n&lt;/b&gt; blank cell left to place: click in the grid to choose where.</numerusform>
            <numerusform>&lt;b&gt;%n&lt;/b&gt; blank cells left to place: click in the grid to choose where.</numerusform>
        </translation>
    </message>
    <message numerus="yes">
        <location filename="../src/pokemon_mosaic/ui/layout_tabs.py" line="376"/>
        <source>Les &lt;b&gt;%n&lt;/b&gt; case(s) vide(s) sont placées.</source>
        <translation>
            <numerusform>The &lt;b&gt;%n&lt;/b&gt; blank cell is placed.</numerusform>
            <numerusform>The &lt;b&gt;%n&lt;/b&gt; blank cells are placed.</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/layout_tabs.py" line="379"/>
        <source>La grille a exactement autant de cases que de cartes retenues.</source>
        <translation>The grid has exactly as many cells as selected cards.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/layout_tabs.py" line="383"/>
        <source>Des cartes sortent des pages : réduisez la grille, ajoutez une feuille, ou diminuez la taille des cartes à l&apos;onglet suivant.</source>
        <translation>Some cards fall outside the pages: shrink the grid, add a sheet, or reduce the card size in the next tab.</translation>
    </message>
</context>
<context>
    <name>LayoutStep</name>
    <message>
        <location filename="../src/pokemon_mosaic/ui/layout_step.py" line="394"/>
        <source>Grille</source>
        <translation>Grid</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/layout_step.py" line="435"/>
        <source>Cliquez « Suivant » sur les parties précédentes pour ouvrir celle-ci.</source>
        <translation>Click “Next” on the earlier parts to open this one.</translation>
    </message>
</context>
<context>
    <name>LinkDialog</name>
    <message>
        <location filename="../src/pokemon_mosaic/ui/link_dialog.py" line="134"/>
        <source>Modifier le lien</source>
        <translation>Edit link</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/link_dialog.py" line="135"/>
        <source>Nouveau lien</source>
        <translation>New link</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/link_dialog.py" line="136"/>
        <source>Le lien</source>
        <translation>The link</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/link_dialog.py" line="137"/>
        <source>Cartes disponibles</source>
        <translation>Available cards</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/link_dialog.py" line="138"/>
        <source>Filtrer par nom…</source>
        <translation>Filter by name…</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/link_dialog.py" line="141"/>
        <source>Ordre imposé (sinon l&apos;optimiseur peut le pivoter d&apos;un demi-tour)</source>
        <translation>Fixed order (otherwise the optimiser may turn it half way round)</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/link_dialog.py" line="144"/>
        <source>Montrer ce qu&apos;est ce demi-tour</source>
        <translation>Show what that half turn does</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/link_dialog.py" line="172"/>
        <source>Toutes les extensions</source>
        <translation>All sets</translation>
    </message>
    <message numerus="yes">
        <location filename="../src/pokemon_mosaic/ui/link_dialog.py" line="223"/>
        <source>Toutes les cases doivent être remplies : il en reste %n vide(s). Faites glisser une carte depuis la droite.</source>
        <translation>
            <numerusform>Every cell must be filled: %n is still empty. Drag a card in from the right.</numerusform>
            <numerusform>Every cell must be filled: %n are still empty. Drag a card in from the right.</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/link_dialog.py" line="227"/>
        <source>Un lien groupe au moins deux cartes : ajoutez une ligne ou une colonne.</source>
        <translation>A link groups at least two cards: add a row or a column.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/link_dialog.py" line="229"/>
        <source>Rectangle %1 × %2, complet.</source>
        <translation>Rectangle %1 × %2, complete.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/link_dialog.py" line="139"/>
        <source>Nom (facultatif)</source>
        <translation>Name (optional)</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/link_dialog.py" line="164"/>
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
        <location filename="../src/pokemon_mosaic/ui/main_window.py" line="53"/>
        <source>Cartes</source>
        <translation>Cards</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/main_window.py" line="54"/>
        <source>Paramètres</source>
        <translation>Parameters</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/main_window.py" line="55"/>
        <source>Exécution</source>
        <translation>Run</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/main_window.py" line="299"/>
        <source>Fermeture forcée : un traitement de fond n&apos;a pas répondu.</source>
        <translation>Closing anyway: a background task did not respond.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/main_window.py" line="306"/>
        <source>Pokémon Mosaic</source>
        <translation>Pokémon Mosaic</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/main_window.py" line="309"/>
        <source>Précédent</source>
        <translation>Back</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/main_window.py" line="310"/>
        <source>Suivant</source>
        <translation>Next</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/main_window.py" line="311"/>
        <source>Langue</source>
        <translation>Language</translation>
    </message>
</context>
<context>
    <name>PagePreview</name>
    <message>
        <location filename="../src/pokemon_mosaic/ui/page_preview.py" line="114"/>
        <source>Ajouter une feuille à droite</source>
        <translation>Add a sheet on the right</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/page_preview.py" line="115"/>
        <source>Ajouter une ligne de feuilles</source>
        <translation>Add a row of sheets</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/page_preview.py" line="117"/>
        <location filename="../src/pokemon_mosaic/ui/page_preview.py" line="151"/>
        <source>Retirer une feuille</source>
        <translation>Remove a sheet</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/page_preview.py" line="119"/>
        <location filename="../src/pokemon_mosaic/ui/page_preview.py" line="155"/>
        <source>Retirer une ligne de feuilles</source>
        <translation>Remove a row of sheets</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/page_preview.py" line="586"/>
        <source>carte réelle
%1 × %2 cm</source>
        <translation>real card
%1 × %2 cm</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/page_preview.py" line="618"/>
        <location filename="../src/pokemon_mosaic/ui/page_preview.py" line="633"/>
        <source>%1 cm</source>
        <translation>%1 cm</translation>
    </message>
</context>
<context>
    <name>PaperTab</name>
    <message>
        <location filename="../src/pokemon_mosaic/ui/layout_tabs.py" line="497"/>
        <source>Format de la feuille</source>
        <translation>Sheet format</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/layout_tabs.py" line="498"/>
        <source>Format</source>
        <translation>Format</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/layout_tabs.py" line="499"/>
        <source>Largeur (cm)</source>
        <translation>Width (cm)</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/layout_tabs.py" line="500"/>
        <source>Hauteur (cm)</source>
        <translation>Height (cm)</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/layout_tabs.py" line="504"/>
        <source>Choisissez le format de la feuille, et appuyez sur les boutons + ou − pour ajouter ou enlever des feuilles.</source>
        <translation>Choose the sheet format, then press the + or − buttons to add or remove sheets.</translation>
    </message>
    <message numerus="yes">
        <location filename="../src/pokemon_mosaic/ui/layout_tabs.py" line="558"/>
        <source>%n feuille(s) de %1 × %2 cm : surface totale de %3 × %4 cm.</source>
        <translation>
            <numerusform>%n sheet of %1 × %2 cm, %3 × %4 cm in total.</numerusform>
            <numerusform>%n sheets of %1 × %2 cm, %3 × %4 cm in total.</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/layout_tabs.py" line="412"/>
        <source>Pages</source>
        <translation>Pages</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/layout_tabs.py" line="501"/>
        <source>Paysage</source>
        <translation>Landscape</translation>
    </message>
</context>
<context>
    <name>PlacementTab</name>
    <message>
        <location filename="../src/pokemon_mosaic/ui/layout_tabs.py" line="882"/>
        <source>Emplacement de la grille</source>
        <translation>Grid placement</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/layout_tabs.py" line="923"/>
        <source>Cliquez dans la mosaïque et tirez pour la déplacer. Chaque feuille porte son morceau et le déplace pour son compte : un morceau ne passe jamais sur la feuille voisine, sans quoi une coupe tomberait en pleine carte.</source>
        <translation>Click inside the mosaic and drag to move it. Each sheet carries its own piece and moves it independently: a piece never crosses onto the neighbouring sheet, which would put a cut through a card.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/layout_tabs.py" line="928"/>
        <source>Centrer</source>
        <translation>Centre</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/layout_tabs.py" line="930"/>
        <source>Pose chaque morceau au milieu de sa feuille, dans les deux sens. Les feuilles sans carte sont laissées de côté.</source>
        <translation>Puts every piece in the middle of its sheet, both ways. Sheets without cards are left alone.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/layout_tabs.py" line="933"/>
        <source>Remettre en place</source>
        <translation>Put back</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/layout_tabs.py" line="935"/>
        <source>Ramène tous les morceaux à leur emplacement par défaut : calés à gauche, centrés en hauteur.</source>
        <translation>Brings every piece back to its default spot: flush left, vertically centred.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/layout_tabs.py" line="952"/>
        <source>Les morceaux sont centrés dans leur feuille.</source>
        <translation>Every piece is centred in its sheet.</translation>
    </message>
    <message numerus="yes">
        <location filename="../src/pokemon_mosaic/ui/layout_tabs.py" line="954"/>
        <source>&lt;b&gt;%n&lt;/b&gt; feuille(s) déplacée(s).</source>
        <translation>
            <numerusform>&lt;b&gt;%n&lt;/b&gt; sheet moved.</numerusform>
            <numerusform>&lt;b&gt;%n&lt;/b&gt; sheets moved.</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/layout_tabs.py" line="956"/>
        <source>Les morceaux sont à leur emplacement par défaut.</source>
        <translation>Every piece is at its default spot.</translation>
    </message>
</context>
<context>
    <name>PresetsBar</name>
    <message>
        <location filename="../src/pokemon_mosaic/ui/presets_bar.py" line="65"/>
        <source>Préréglage</source>
        <translation>Preset</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/presets_bar.py" line="66"/>
        <source>Charger</source>
        <translation>Load</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/presets_bar.py" line="67"/>
        <source>Enregistrer…</source>
        <translation>Save…</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/presets_bar.py" line="68"/>
        <source>Supprimer</source>
        <translation>Delete</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/presets_bar.py" line="70"/>
        <source>Enregistre la sélection, les liens actifs, la grille et les réglages sous un nom.</source>
        <translation>Saves the selection, the active links, the grid and the settings under a name.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/presets_bar.py" line="101"/>
        <source>Enregistrer le préréglage</source>
        <translation>Save the preset</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/presets_bar.py" line="101"/>
        <source>Nom</source>
        <translation>Name</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/presets_bar.py" line="116"/>
        <source>Échec de l&apos;enregistrement : %1</source>
        <translation>Saving failed: %1</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/presets_bar.py" line="121"/>
        <source>Préréglage « %1 » enregistré.</source>
        <translation>Preset “%1” saved.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/presets_bar.py" line="126"/>
        <source>Remplacer le préréglage</source>
        <translation>Replace the preset</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/presets_bar.py" line="127"/>
        <source>« %1 » existe déjà. Le remplacer ?</source>
        <translation>“%1” already exists. Replace it?</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/presets_bar.py" line="139"/>
        <source>Préréglage illisible : %1</source>
        <translation>Unreadable preset: %1</translation>
    </message>
    <message numerus="yes">
        <location filename="../src/pokemon_mosaic/ui/presets_bar.py" line="148"/>
        <source>Préréglage « %1 » chargé : %n carte(s) introuvable(s).</source>
        <translation>
            <numerusform>Preset “%1” loaded: %n card not found.</numerusform>
            <numerusform>Preset “%1” loaded: %n cards not found.</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/presets_bar.py" line="153"/>
        <source>Préréglage « %1 » chargé.</source>
        <translation>Preset “%1” loaded.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/presets_bar.py" line="161"/>
        <source>Supprimer le préréglage</source>
        <translation>Delete the preset</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/presets_bar.py" line="162"/>
        <source>Supprimer « %1 » ? La bibliothèque de liens n&apos;est pas touchée.</source>
        <translation>Delete “%1”? The link library is left untouched.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/presets_bar.py" line="171"/>
        <source>Échec de la suppression : %1</source>
        <translation>Deletion failed: %1</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/presets_bar.py" line="176"/>
        <source>Préréglage « %1 » supprimé.</source>
        <translation>Preset “%1” deleted.</translation>
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
        <location filename="../src/pokemon_mosaic/ui/run_step.py" line="216"/>
        <source>Lancer</source>
        <translation>Start</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/run_step.py" line="217"/>
        <source>Arrêter</source>
        <translation>Stop</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/run_step.py" line="218"/>
        <source>Dernier</source>
        <translation>Latest</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/run_step.py" line="219"/>
        <source>Prolonger</source>
        <translation>Extend</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/run_step.py" line="220"/>
        <source>Repartir de ce cliché</source>
        <translation>Restart from this snapshot</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/run_step.py" line="222"/>
        <source>Poursuit le calcul depuis le dernier cliché, en conservant toute la timeline.</source>
        <translation>Continues from the latest snapshot, keeping the whole timeline.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/run_step.py" line="226"/>
        <source>Relance le calcul depuis le cliché affiché. Les clichés suivants sont abandonnés.</source>
        <translation>Restarts from the displayed snapshot. Later snapshots are discarded.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/run_step.py" line="229"/>
        <source>Exporter ce cliché…</source>
        <translation>Export this snapshot…</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/run_step.py" line="230"/>
        <source>Annuler l&apos;export</source>
        <translation>Cancel the export</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/run_step.py" line="231"/>
        <source>Ajuster</source>
        <translation>Fit</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/run_step.py" line="232"/>
        <source>Dézoomer (touche −)</source>
        <translation>Zoom out (− key)</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/run_step.py" line="233"/>
        <source>Zoomer (touche +)</source>
        <translation>Zoom in (+ key)</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/run_step.py" line="234"/>
        <source>Revenir à l&apos;image entière</source>
        <translation>Back to the whole image</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/run_step.py" line="236"/>
        <source>Flèches gauche et droite pour parcourir les clichés.</source>
        <translation>Left and right arrows step through the snapshots.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/run_step.py" line="242"/>
        <source>Lancez le calcul pour voir la mosaïque se construire.</source>
        <translation>Start the run to watch the mosaic take shape.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/run_step.py" line="259"/>
        <source>Calcul en cours…</source>
        <translation>Running…</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/run_step.py" line="381"/>
        <source>Export en cours…</source>
        <translation>Exporting…</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/run_step.py" line="398"/>
        <source>Panneau %1 / %2 : %3</source>
        <translation>Panel %1 / %2: %3</translation>
    </message>
    <message numerus="yes">
        <location filename="../src/pokemon_mosaic/ui/run_step.py" line="414"/>
        <source>%n fichier(s) écrit(s) : %1</source>
        <translation>
            <numerusform>%n file written: %1</numerusform>
            <numerusform>%n files written: %1</numerusform>
        </translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/run_step.py" line="421"/>
        <source>Export annulé ; les fichiers partiels ont été effacés.</source>
        <translation>Export cancelled; the partial files were removed.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/run_step.py" line="427"/>
        <source>Échec de l&apos;export : %1</source>
        <translation>Export failed: %1</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/run_step.py" line="449"/>
        <source>le calcul</source>
        <translation>the run</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/run_step.py" line="450"/>
        <source>l&apos;export</source>
        <translation>the export</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/run_step.py" line="468"/>
        <source>Arrêt en cours : %1 ne répond pas encore.</source>
        <translation>Stopping: %1 is not responding yet.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/run_step.py" line="521"/>
        <source>itérations épuisées</source>
        <translation>iterations exhausted</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/run_step.py" line="522"/>
        <source>score atteint</source>
        <translation>target score reached</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/run_step.py" line="523"/>
        <source>stagnation</source>
        <translation>stagnation</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/run_step.py" line="524"/>
        <source>budget de temps</source>
        <translation>time budget</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/run_step.py" line="525"/>
        <source>arrêt demandé</source>
        <translation>stopped by user</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/run_step.py" line="532"/>
        <source>Score %1 → %2 (%3 % de gain), arrêt : %4</source>
        <translation>Score %1 → %2 (%3% gain), stopped: %4</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/run_step.py" line="538"/>
        <source>Calcul terminé.</source>
        <translation>Run finished.</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/run_step.py" line="544"/>
        <source>Échec du calcul : %1</source>
        <translation>Run failed: %1</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/run_step.py" line="785"/>
        <source>Reprendre</source>
        <translation>Resume</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/run_step.py" line="785"/>
        <source>Pause</source>
        <translation>Pause</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/run_step.py" line="791"/>
        <source>aucun cliché</source>
        <translation>no snapshot</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/run_step.py" line="794"/>
        <source>cliché %1 / %2</source>
        <translation>snapshot %1 of %2</translation>
    </message>
</context>
<context>
    <name>StripPreview</name>
    <message>
        <location filename="../src/pokemon_mosaic/ui/strip_preview.py" line="114"/>
        <source>pas assez de cartes</source>
        <translation>not enough cards</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/strip_preview.py" line="161"/>
        <source>Aucune carte chargée</source>
        <translation>No cards loaded</translation>
    </message>
    <message>
        <location filename="../src/pokemon_mosaic/ui/strip_preview.py" line="167"/>
        <source>Aucune carte retenue</source>
        <translation>No cards kept</translation>
    </message>
</context>
</TS>
