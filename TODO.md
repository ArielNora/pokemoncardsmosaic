# TODO

Ce qui reste **pour la v1** est dans `SPEC.md` §9. Ce fichier ne contient que ce
qui vient **après**, et les points encore ouverts.

## Reporté explicitement après la v1 de l'application

Tous décidés le 2026-08-16. À traiter **une fois toute la v1 terminée**, pas avant.

- **Marges et espacement entre cartes.** La v1 colle les cartes bord à bord. Ajouter
  ensuite des réglages de marge de page et d'espacement entre cartes (c'est ce qui
  motivait l'idée de rendre la taille des cartes ajustable indépendamment).
  Voir `SPEC.md` §4.
- **Liens verticaux.** La v1 ne gère que des blocs horizontaux (une carte à gauche
  d'une autre). Permettre d'imposer qu'une carte soit au-dessus d'une autre.
- **Blocs rectangulaires.** Grouper des cartes en carré ou rectangle (ex. 2×2 pour une
  illustration qui s'étale). C'est l'extension la plus lourde de l'algorithme.
- **Fixer une carte à des coordonnées précises.** Permettre d'imposer qu'une carte
  donnée occupe une case donnée de la grille. À rapprocher du mécanisme de cases vides
  figées de la v1 : c'est le même verrouillage de position.
- **Traitement de la marge automatique.** La v1 centre l'image et laisse une bordure
  neutre pour absorber l'écart de 2,47 % entre grille et feuille. Laisser ensuite
  l'utilisateur décider quoi en faire : couleur au choix, ou autre traitement.

## Idées d'origine

- **Forcer un placement directionnel** (imposer un sens droite-à-gauche, par exemple).
- **Revoir la métrique de bord.** Aujourd'hui une bande entière est réduite à une
  seule moyenne, soit 3 nombres : deux bords très différents mais de moyennes
  identiques semblent donc parfaitement compatibles. Piste : découper chaque bord en
  plusieurs sous-bandes avec recouvrement, et sommer les distances.

## Stockage des cartes (à trancher)

Les ~350 Mo d'images sont hors dépôt. Il faut un moyen de les partager entre
plusieurs machines, sachant qu'une nouvelle extension sort plusieurs fois par an
(ajouts groupés, jamais de modification des cartes existantes).

Piste privilégiée : **une archive zip par extension, attachée à une *release*
GitHub**, plus un petit script `fetch_cards.py` qui lit un manifeste et télécharge ce
qui manque. Gratuit, pas de compte supplémentaire, limite de 2 Go par fichier, et le
rythme « un lot par sortie d'extension » colle exactement au modèle des releases.

Alternatives écartées ou à reconsidérer :
- *Git LFS* — bien intégré, mais 1 Go de quota gratuit seulement, vite atteint.
- *Google Drive / rclone* — pratique manuellement, mais scriptable moins proprement
  et pas versionné.

## Limitations connues à corriger

- **Grille dépendante de la factorisation.** `calculate_grid_dims` cherche les deux
  facteurs les plus proches, donc 281 cartes (nombre premier) donneraient une bande
  281×1. Ne concerne plus que la **CLI sans `--grid`** : l'interface impose toujours
  une forme et répartit les cases vides excédentaires.
- **Noms de fichiers non normalisés.** Trois cartes portent des accents
  (`mustébouée`, `silvallié`, `guérilande`) et une garde un nom de capture d'écran
  (`mew 13.27.50.png`). Sans conséquence aujourd'hui, mais un lien décrit par
  fragment de chemin accentué serait sensible à la normalisation Unicode : macOS
  stocke en NFD, une chaîne saisie ailleurs arrive en NFC, et la comparaison de
  sous-chaîne échoue sans rien signaler.

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
