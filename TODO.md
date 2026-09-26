# TODO

Ce qui reste **pour la v1** est dans `SPEC.md` §9. Ce fichier ne contient que ce
qui vient **après**, et les points encore ouverts.

Revu le 2026-09-18 : trois entrées faites depuis leur écriture ont été retirées
(marges et espacement, liens en rectangles, marge automatique), voir « Fait,
retiré de cette liste » en bas. Revu le 2026-09-20 : les trois restes récents
sont faits (la fenêtre qui s'élargit, les déplacements de feuilles entre deux
formes, le retrait du fil de fer).

## Restes récents, petits

Aucun : les trois derniers ont été faits le 2026-09-20.

## Reporté après la v1 de l'application

- **Fixer une carte à des coordonnées précises.** Imposer qu'une carte occupe
  une case donnée de la grille. À rapprocher des cases vides, qui sont déjà un
  verrouillage de position. Le verrouillage se fait **carte par carte**, jamais
  par groupe, et une carte appartenant à un lien ne peut pas être figée.

## Idées d'origine

- **Forcer un placement directionnel** (imposer un sens droite-à-gauche, par exemple).

## Stockage des cartes : tranché le 2026-08-22, provenance refondue le 2026-08-27

Les 281 anciens PNG encadrés, gardés le temps de valider le nouveau jeu, ont
été supprimés le 2026-08-24.

Les images **ne sont pas versionnées** : `cards.json` décrit les 441 cartes
(56,3 Mo) et le miroir les sert. Illustrations nues 734×1024 en WebP qualité 80,
déposées à la main dans `data/pokemoncards/`.

Le projet ne va chercher aucune image sur un site tiers : ni catalogue distant,
ni adresse d'origine au manifeste, ni récupération automatique. Le miroir est la
seule provenance. Voir `docs/IMAGES.md`.

## Dettes ouvertes

- **Aucun poster n'a encore été fabriqué avec les 441 cartes.** `output/` date
  du 19 août et porte les 281 anciennes cartes encadrées. Ce n'est pas une dette
  technique mais une vérification manquante, et c'est le but du projet.

- **Empaqueter pour Linux et Windows.** Tranché le 2026-08-29 : l'application
  vise les trois systèmes. Le plus gros obstacle est levé : Fusion et nos deux
  palettes lui donnent déjà la même apparence partout, et son mode sombre ne
  dépend plus du thème de la plateforme.

  ⚠️ **PyInstaller ne sait pas produire pour un autre système que celui où il
  tourne.** Il faut donc une machine ou un exécuteur d'intégration continue de
  chaque système : pour construire, et surtout pour **essayer** : aucun rendu
  hors écran ne remplace l'ouverture réelle d'une fenêtre.

  - **Linux**, le plus simple : une recette sans `BUNDLE`, et un AppImage ou une
    archive. Aucune signature, aucun avertissement. ⚠️ Qt a besoin de
    bibliothèques du système : OpenGL, xkbcommon, xcb, qu'une distribution
    minimale n'a pas ; un AppImage les emporte.
  - **Windows** : la même recette, produisant un `.exe`. Le but est qu'elle
    tourne, pas qu'elle s'installe proprement. Pas de certificat : la marche à
    suivre est expliquée dans le README.
  - `paquet/construire.sh` et le hook `pre-commit` sont des scripts `sh` : sous
    Windows ils demandent Git Bash ou WSL.

  ⚠️ **La détection du mode sombre sur Linux.** Certains bureaux ne répondent
  pas à `colorScheme()`. Le repli lit la clarté du fond posé par le système, ce
  qui est juste **au démarrage**, mais une bascule en cours d'exécution
  passerait inaperçue, la palette lue étant devenue la nôtre. L'application
  resterait dans le mode où elle a démarré.

- **Le paquet macOS n'est pas signé valablement.** `codesign --verify` et `spctl`
  rendent tous deux 1 : défaut connu de PyInstaller sur macOS. L'application
  démarre sur la machine qui l'a construite et depuis un autre emplacement, mais
  Gatekeeper la refusera ailleurs. Une distribution propre suppose un
  **Developer ID** Apple, compte payant, et une notarisation qui imposent de
  reprendre la signature entièrement. Voir `paquet/README.md`.
- **Finir le dépôt proprement.** Un passage de mise en forme, sur tout, à faire
  d'un seul tenant plutôt que par petits bouts :

  - **les textes** : relire `README.md`, `SPEC.md` et `docs/` d'un bout à
    l'autre. Trois mois de décisions s'y sont empilées, certaines lignes
    décrivent une application qui n'existe plus, d'autres se répètent d'un
    fichier à l'autre.
  - **le code** : homogénéiser docstrings et commentaires, retirer ce qui est
    mort. Exemple connu : `data/local/` ne contient que douze illustrations
    déjà au catalogue, copiées là en août et jamais rangées.
  - **les descriptions pour les IA, en markdown.** `CLAUDE.md` dit la méthode
    de travail, pas ce qu'est le projet : il manque une carte du dépôt, qui
    dise où est quoi, ce que fait chaque module, les invariants à ne pas
    casser et par où commencer. C'est ce qu'une IA lit en arrivant, et ce
    qu'un humain neuf lirait aussi.
  - **la présentation** : licence, mention des ayants droit, ce qu'il faut
    pour que le dépôt se tienne debout tout seul.

- **Pas de skill de mise à jour.** À chaque nouvelle extension, il faut déposer
  les illustrations, lancer `build_manifest.py`, compléter à la main la rareté
  et les noms des cartes nouvelles, puis lancer `publish_release.py`. Seule la
  troisième étape demande un jugement : un skill pourrait enchaîner les autres
  et ne s'arrêter que sur les champs à remplir, que `build_manifest.py` nomme
  déjà.

## Limitations connues à corriger

- **Grille dépendante de la factorisation.** `calculate_grid_dims` cherche les deux
  facteurs les plus proches, donc un nombre premier de cartes donnerait une bande
  d'une seule ligne. Ne concerne plus que la **CLI sans `--grid`** : l'interface
  impose toujours une forme et répartit les cases vides excédentaires.

## Pistes d'amélioration

- **Vectoriser le recalcul des signatures.** `CardSet.recalculate_features` boucle
  sur les cartes une par une : mesuré à 71 à 148 ms sur 280 cartes selon
  l'épaisseur, davantage sur les 441 d'aujourd'hui, ce qui se sent quand on fait
  glisser le réglage d'épaisseur des bandes. Empiler les vignettes en un seul
  tableau permettrait de calculer toutes les moyennes d'un coup. Différer le
  calcul serait au contraire dangereux : les signatures doivent rester
  cohérentes avec le réglage affiché, sous peine de retrouver le défaut des
  signatures hétérogènes.

## Fait, retiré de cette liste

Gardé en trace pour ne pas rouvrir ces sujets sans raison.

- **Marges et espacement entre cartes** (reporté le 2026-08-16) : fait. L'écart
  entre cartes, la largeur de carte imposée ou automatique, le centrage et le
  déplacement de chaque morceau sur sa feuille se règlent à l'étape 2 et à
  l'export.
- **Les liens deviennent des rectangles pleins, 3×3 au maximum** (tranché le
  2026-08-27) : fait, éditeur de grille compris. La lignée d'Arcko et les paires
  Solgaleo/Lunala et Entei/Raikou sont fournies d'office.
- **Traitement de la marge automatique** : fait. Couleur du fond au choix,
  pourtour caméléon, centrage et déplacement de chaque morceau.
- **Noms de fichiers non normalisés**, réglé le 2026-08-24 par `artwork.slug()`.
- **Aucun test ne tourne sans fin** (2026-09-18) : délai de 60 s par test et de
  10 min par lot, voir `CLAUDE.md`.
- **La fenêtre s'élargissait après un multi-lancement** (2026-09-20) : elle
  s'ouvre à 1440 pixels de large, rognés à l'écran, au lieu de 1100.
- **Revoir la métrique de bord** (2026-09-20, corrigée le 2026-09-21) : faite,
  et débrayable. La case « Métrique améliorée » des paramètres avancés mesure
  chaque bande en cinq à dix parties recouvertes de moitié, chacune prise sur
  toute l'épaisseur du bord, comparées une à une. Décochée par défaut, dix
  parties par défaut.
- **Les déplacements de feuilles entre deux formes** (2026-09-20) : tranché,
  ils valent pour la forme courante et une autre forme les borne à sa place
  libre, comme l'export. Pour une autre forme, on redéplace.
- **`WireframeView` retirée** (2026-09-20) : ses tests sont passés sur
  `PagePreview`, l'aperçu que l'application montre vraiment, et le module ne
  garde que les pièces de dessin communes, renommé `ui/drawing.py`.
- **Recuit simulé** (vérifié le 2026-08-20) : `annealing.py`, exposé en réglage
  avancé, 67,5 % de gain à 1 M d'itérations contre 61 % pour la descente stricte.
- **Désynchronisation d'indices.** `original_index` n'existe plus. L'invariant
  « `card.index` = position dans la liste » est tenu par `select_cards()`, et
  `EdgeDistances` refuse une numérotation discontinue.
- **Double comptage d'une couture.** Corrigé : `local_score` dédoublonne les arêtes
  et reçoit toutes les cases d'un échange en un seul appel.
- **Transparence ignorée.** Mesuré, et sans effet réel. 264 cartes sur 281 sont en
  RGBA et 91 ont des pixels non opaques, mais il s'agit de l'anticrénelage du
  contour : 0,3 à 1,3 % des pixels. `convert("RGB")` laisse tomber le canal alpha
  sans composer, et l'écart qui en résulte sur une signature de bord vaut **au pire
  1 niveau de couleur sur 255, 0,1 en médiane**, du même ordre que l'erreur des
  vignettes, déjà acceptée. `cv2` a par ailleurs quitté l'application.
