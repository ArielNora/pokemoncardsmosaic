# TODO

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
  facteurs les plus proches, donc 281 cartes (nombre premier) donnent une bande
  281×1. Contourné aujourd'hui en excluant une carte. Corriger en autorisant des
  cases vides, ou en choisissant le rectangle le plus proche du carré quitte à
  laisser quelques trous.
- **Transparence ignorée.** Lire en `IMREAD_UNCHANGED` et composer l'alpha sur un
  fond défini, plutôt que de laisser `cv2` écarter le canal.
- **Désynchronisation d'indices.** `original_index` suit l'indice d'entrée et non la
  position dans `parts` ; une carte écartée au redimensionnement décale les deux.
- **Double comptage d'une couture** dans le delta de score quand les deux zones
  échangées sont adjacentes.

## Pistes d'amélioration

- **Vectoriser le recalcul des signatures.** `CardSet.recalculate_features` boucle
  sur les 280 cartes et coûte 71 à 148 ms selon l'épaisseur, ce qui se sent quand on
  fait glisser le curseur de l'étape 3. Empiler les vignettes en un seul tableau
  permettrait de calculer toutes les moyennes d'un coup. Différer le calcul serait
  au contraire dangereux : les signatures doivent rester cohérentes avec le réglage
  affiché, sous peine de retrouver le défaut des signatures hétérogènes.

- L'optimisation est une descente stricte : elle n'accepte jamais un coup perdant et
  se bloque donc dans un minimum local. Un recuit simulé donnerait probablement un
  meilleur résultat à budget d'itérations égal.
- Normaliser les noms de fichiers : 4 cartes ont des accents (`mustébouée`,
  `guérilande`, `météno`, `silvallié`) et une garde un nom de capture d'écran
  (`mew 13.27.50.png`).
