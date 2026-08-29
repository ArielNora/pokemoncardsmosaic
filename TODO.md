# TODO

Ce qui reste **pour la v1** est dans `SPEC.md` §9. Ce fichier ne contient que ce
qui vient **après**, et les points encore ouverts.

## Reporté explicitement après la v1 de l'application

Tous décidés le 2026-08-16. À traiter **une fois toute la v1 terminée**, pas avant.

- **Marges et espacement entre cartes.** La v1 colle les cartes bord à bord. Ajouter
  ensuite des réglages de marge de page et d'espacement entre cartes (c'est ce qui
  motivait l'idée de rendre la taille des cartes ajustable indépendamment).
  Voir `SPEC.md` §4.
- ⭐ **Les liens deviennent des rectangles pleins, 3×3 au maximum** — tranché le
  2026-08-27, **fait**. Un seul concept **remplace** horizontal, vertical et
  groupe : une ligne de 3 est un 1×3, une colonne un 3×1. Le cas d'usage demandé
  le 2026-08-22 — Arcko `B3-156` en bas, Massko `B3-157` au milieu,
  Méga-Jungko-ex `B3-194` en haut — est **fourni d'office**, comme les deux
  paires Solgaleo/Lunala et Entei/Raikou.

  Formes admises : 1×2, 1×3, 2×1, 3×1, 2×2, 2×3, 3×2, 3×3. Jamais de forme
  trouée ni de rectangle incomplet. Le lien porte sa forme et ses cartes, rien
  de plus : ni coordonnées, ni verrou.

  **Une carte liée ne peut pas être figée**, et réciproquement.

  Ce qui reste à écrire : `Link` gagne une forme ; `_locate_block` balaie une
  fenêtre 2D ; `_try_move` vise une zone 2D ; `build_initial_grid` prend le
  premier ancrage qui tient ; `check_links_fit` doit vérifier **la hauteur**,
  qu'il ne regarde nulle part aujourd'hui. `local_score` est déjà générique et
  ne change pas. Le gros du travail est le dialogue de création, qui construit
  une liste ordonnée et doit devenir un éditeur de grille.

  ⚠️ `distribute_empty_cells` disperse les trous, et un 3×3 veut neuf cases
  contiguës : dans une grille lâche le placement peut échouer là où une
  solution existe. La parade est un message clair, pas un algorithme plus malin.
- **Fixer une carte à des coordonnées précises.** Permettre d'imposer qu'une carte
  donnée occupe une case donnée de la grille. À rapprocher du mécanisme de cases vides
  figées de la v1 : c'est le même verrouillage de position. Le verrouillage se fait
  **carte par carte**, jamais par groupe — et une carte appartenant à un lien ne
  peut pas être figée.
- **Traitement de la marge automatique.** La v1 centre l'image et laisse une bordure
  neutre pour absorber l'écart de 2,47 % entre grille et feuille. Laisser ensuite
  l'utilisateur décider quoi en faire : couleur au choix, ou autre traitement.

## Idées d'origine

- **Forcer un placement directionnel** (imposer un sens droite-à-gauche, par exemple).
- **Revoir la métrique de bord.** Aujourd'hui une bande entière est réduite à une
  seule moyenne, soit 3 nombres : deux bords très différents mais de moyennes
  identiques semblent donc parfaitement compatibles. Piste : découper chaque bord en
  plusieurs sous-bandes avec recouvrement, et sommer les distances.

## Stockage des cartes — tranché le 2026-08-22, provenance refondue le 2026-08-27

Les 281 anciens PNG encadrés, gardés le temps de valider le nouveau jeu, ont
été supprimés le 2026-08-24.

Les images **ne sont pas versionnées** : `cards.json` décrit les 441 cartes
(56,3 Mo) et le miroir les sert. Illustrations nues 734×1024 en WebP qualité 80,
déposées à la main dans `data/pokemoncards/`.

Le projet ne va chercher aucune image sur un site tiers : ni catalogue distant,
ni adresse d'origine au manifeste, ni récupération automatique. Le miroir est la
seule provenance. Voir `docs/IMAGES.md`.

## Dettes ouvertes

- **Empaqueter pour Linux et Windows.** Tranché le 2026-08-29 : l'application
  vise les trois systèmes. Le plus gros obstacle est levé — Fusion et nos deux
  palettes lui donnent déjà la même apparence partout, et son mode sombre ne
  dépend plus du thème de la plateforme.

  ⚠️ **PyInstaller ne sait pas produire pour un autre système que celui où il
  tourne.** Il faut donc une machine ou un exécuteur d'intégration continue de
  chaque système — pour construire, et surtout pour **essayer** : aucun rendu
  hors écran ne remplace l'ouverture réelle d'une fenêtre.

  - **Linux**, le plus simple : une recette sans `BUNDLE`, et un AppImage ou une
    archive. Aucune signature, aucun avertissement. ⚠️ Qt a besoin de
    bibliothèques du système — OpenGL, xkbcommon, xcb — qu'une distribution
    minimale n'a pas ; un AppImage les emporte.
  - **Windows** : la même recette, produisant un `.exe`. Le but est qu'elle
    tourne, pas qu'elle s'installe proprement. Pas de certificat : la marche à
    suivre est expliquée dans le README.
  - `paquet/construire.sh` et le hook `pre-commit` sont des scripts `sh` : sous
    Windows ils demandent Git Bash ou WSL.

  ⚠️ **La détection du mode sombre sur Linux.** Certains bureaux ne répondent
  pas à `colorScheme()`. Le repli lit la clarté du fond posé par le système, ce
  qui est juste **au démarrage** — mais une bascule en cours d'exécution
  passerait inaperçue, la palette lue étant devenue la nôtre. L'application
  resterait dans le mode où elle a démarré.

- **Le paquet macOS n'est pas signé valablement.** `codesign --verify` et `spctl`
  rendent tous deux 1 : défaut connu de PyInstaller sur macOS. L'application
  démarre sur la machine qui l'a construite et depuis un autre emplacement, mais
  Gatekeeper la refusera ailleurs. Une distribution propre suppose un
  **Developer ID** Apple, compte payant, et une notarisation qui imposent de
  reprendre la signature entièrement. Voir `paquet/README.md`.
- **Pas de skill de mise à jour.** À chaque nouvelle extension, il faut déposer
  les illustrations, lancer `build_manifest.py`, compléter à la main la rareté
  et les noms des cartes nouvelles, puis lancer `publish_release.py`. Seule la
  troisième étape demande un jugement : un skill pourrait enchaîner les autres
  et ne s'arrêter que sur les champs à remplir, que `build_manifest.py` nomme
  déjà.

## Limitations connues à corriger

- **Grille dépendante de la factorisation.** `calculate_grid_dims` cherche les deux
  facteurs les plus proches, donc 281 cartes (nombre premier) donneraient une bande
  281×1. Ne concerne plus que la **CLI sans `--grid`** : l'interface impose toujours
  une forme et répartit les cases vides excédentaires.
- ✅ **Noms de fichiers non normalisés** — réglé le 2026-08-24. Les noms sont
  désormais produits par `artwork.slug()`, qui retire les accents : plus de
  `mustébouée` ni de `mew 13.27.50.png`, donc plus de sensibilité à la
  normalisation Unicode dans les liens décrits par fragment de chemin.

## Pistes d'amélioration

- **Vectoriser le recalcul des signatures.** `CardSet.recalculate_features` boucle
  sur les 280 cartes et coûte 71 à 148 ms selon l'épaisseur, ce qui se sent quand on
  fait glisser le curseur de l'étape 3. Empiler les vignettes en un seul tableau
  permettrait de calculer toutes les moyennes d'un coup. Différer le calcul serait
  au contraire dangereux : les signatures doivent rester cohérentes avec le réglage
  affiché, sous peine de retrouver le défaut des signatures hétérogènes.

## Retiré de cette liste — vérifié le 2026-08-20

Gardé en trace pour ne pas rouvrir ces sujets sans raison.

- **Recuit simulé.** Fait : `annealing.py`, exposé en réglage avancé, 67,5 % de gain
  à 1 M d'itérations contre 61 % pour la descente stricte.
- **Désynchronisation d'indices.** `original_index` n'existe plus. L'invariant
  « `card.index` = position dans la liste » est tenu par `select_cards()`, et
  `EdgeDistances` refuse une numérotation discontinue.
- **Double comptage d'une couture.** Corrigé : `local_score` dédoublonne les arêtes
  et reçoit toutes les cases d'un échange en un seul appel.
- **Transparence ignorée.** Mesuré, et sans effet réel. 264 cartes sur 281 sont en
  RGBA et 91 ont des pixels non opaques, mais il s'agit de l'anticrénelage du
  contour : 0,3 à 1,3 % des pixels. `convert("RGB")` laisse tomber le canal alpha
  sans composer, et l'écart qui en résulte sur une signature de bord vaut **au pire
  1 niveau de couleur sur 255, 0,1 en médiane** — du même ordre que l'erreur des
  vignettes, déjà acceptée. `cv2` a par ailleurs quitté l'application.
