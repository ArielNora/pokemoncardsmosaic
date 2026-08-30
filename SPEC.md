# Pokémon Mosaic — Spécification

> Document vivant. Mis à jour à chaque précision apportée.
> Statut : **définition en cours** — les technologies ne sont pas encore choisies.
>
> Légende : ✅ confirmé · ❓ **à confirmer** (déduction de ma part) · ⬜ **question ouverte**

---

## 1. Objectif

✅ Assembler des cartes Pokémon en une seule grande image, en plaçant côte à côte les
cartes dont les bords ont les couleurs les plus proches, pour que l'ensemble se lise
comme une image continue.

✅ **Le but final est l'impression d'un poster.** Deux formes possibles :
- un seul grand poster contenant toutes les cartes ;
- deux posters accolés formant un grand poster horizontal.

✅ C'est cette contrainte d'impression qui motivait les essais de formes de grille
(20×14, 31×9…) : il s'agissait de trouver un format imprimable.

✅ Les cartes exclues jusqu'ici (`pikachu.png`) l'étaient **arbitrairement**, juste
pour ajuster le nombre total de cartes à une valeur bien factorisable. Aucun sens
éditorial.

---

## 2. Forme du produit

✅ Un **exécutable avec interface graphique**, organisé en 3 étapes de configuration
suivies d'une vue d'exécution.

### Distribution

✅ **Développé pour un usage personnel d'abord**, mais sans fermer la porte à une
distribution ultérieure. Deux décisions sont prises dès maintenant pour cela :

1. **Framework graphique multiplateforme obligatoire.** C'est le seul vrai point de
   non-retour : changer de framework plus tard signifie réécrire l'interface.
2. **Le dossier de cartes est choisi par l'utilisateur**, jamais codé en dur, dès la
   première version. Sert déjà à l'usage personnel (partage entre machines) et évite
   un rattrapage coûteux touchant l'étape 1, la configuration et la gestion d'erreurs.

Le reste (signature Apple, installateur, icône, polissage des erreurs) relève de
l'empaquetage et reste reportable sans coût.

📌 Note : les visuels de cartes Pokémon appartiennent à The Pokémon Company.
Distribuer l'application ne pose pas de problème, distribuer les images avec, si.
Le point 2 ci-dessus règle la question par construction.

### Langue

✅ **Interface bilingue français / anglais**, avec un sélecteur de langue.

⚠️ À prévoir **dès le départ** : externaliser tous les textes de l'interface. Rajouter
la traduction après coup imposerait de reprendre chaque écran un par un.

---

## 3. Étape 1 — Sélection des cartes

✅ Galerie affichant les cartes avec un aperçu réduit.
✅ L'utilisateur peut **garder ou retirer** chaque carte de l'image finale.
✅ Il peut aussi **retirer un dossier entier** d'un coup.
✅ L'écran affiche les **liens entre cartes** (paires à garder côte à côte).
✅ L'utilisateur peut **créer, modifier et désactiver** des liens depuis l'interface.
✅ Une **liste de liens par défaut** est fournie : ce sont ceux du code actuel
(Solgaleo–Lunala, Entei–Raikou).

✅ Un « lien » signifie : ces cartes restent **adjacentes horizontalement**.

✅ **L'ordre est optionnel, lien par lien.** Chaque lien porte une case « ordre
imposé » : cochée, la séquence saisie est respectée à la lettre (utile quand le sens
a une signification, comme Solgaleo puis Lunala) ; décochée, l'optimiseur peut
retourner le bloc et dispose donc de deux fois plus de placements possibles.

✅ **Les liens vivent dans une bibliothèque séparée**, indépendante des préréglages.
Un préréglage mémorise seulement **lesquels sont actifs**. Rationnel : un lien est un
travail durable (Solgaleo–Lunala restera vrai indéfiniment) alors qu'un préréglage est
un essai de mise en page, jetable. Les mélanger obligerait à ressaisir tous les liens
à chaque nouvelle mise en page.

✅ Un lien peut regrouper **plus de 2 cartes** (trio et au-delà). Le code gère déjà
des blocs de taille quelconque.

📌 **Reportés après la v1** (voir `TODO.md`) : liens verticaux, blocs rectangulaires,
et fixation d'une carte à des coordonnées précises.

✅ **Préréglages nommés** : l'utilisateur enregistre et recharge des configurations
complètes sous un nom (« poster A2 17×17 », « double A3 »). Une configuration couvre
la sélection de cartes, les liens, la grille et les réglages. Permet de comparer
plusieurs mises en page sans tout ressaisir, et de retrouver une config après
l'arrivée d'une nouvelle extension.

⭐ **Tout y est désigné par chemin, jamais par indice.** Les cartes sont numérotées
par leur position dans le dossier trié : l'arrivée d'une extension décale tout ce qui
la suit alphabétiquement. Un préréglage indexé deviendrait alors silencieusement
faux — il retiendrait d'autres cartes, et les liens colleraient des paires que
personne n'a formées. Or c'est **précisément après une nouvelle extension** qu'on
veut retrouver sa configuration. Ce sont les cartes **retirées** qui sont
mémorisées, et non les retenues : une carte arrivée depuis est ainsi incluse
d'office.

✅ Un préréglage nomme les liens **actifs** ; la bibliothèque détient les liens. Il
porte tout de même de quoi **recréer** un lien disparu de la bibliothèque, ordre
libre ou imposé compris : le recréer aux valeurs par défaut changerait la contrainte
donnée à l'optimiseur sans le dire.

✅ Le fichier est du **JSON**, assumé modifiable à la main. Les formulaires écrêtent
donc ce qu'ils reçoivent et **renvoient à la session la valeur retenue**, sans quoi
un champ afficherait une valeur pendant qu'une autre serait calculée. Emplacement :
`QStandardPaths.AppConfigLocation` — Qt sait déjà le dire, et ajouter `platformdirs`
pour cela seul alourdirait un socle tenu à trois dépendances.

---

## 4. Étape 2 — Grille et format d'impression

✅ Choix de la **taille de l'image finale**, avec des **presets de formats
d'impression** (A4, A5, et d'autres formats plus grands ou plus petits).
✅ Choix de la **taille des cartes** et des **dimensions de la grille**, les deux
ajustables.
✅ **Aperçu en fil de fer** : montre la disposition et les proportions du résultat,
avec de simples contours à la place des images de cartes.

### Grandeur maître

✅ **Le format d'impression commande.** L'utilisateur choisit un format (A2, A3…) et
des dimensions de grille ; la **taille des cartes en pixels se calcule** pour remplir
la feuille au DPI voulu. On part du papier, puisque la finalité est l'impression.

✅ **Résolution d'impression : 300 DPI par défaut, modifiable au moment de
l'export, avec alerte au plafond.**

Les cartes sources faisant 734 px de large, il existe un DPI au-delà duquel l'app
interpole sans ajouter de détail. L'app calcule ce plafond pour le format choisi et
prévient l'utilisateur s'il le dépasse — dans le dialogue d'export, à côté du
nombre de mégapixels que la valeur choisie donne.

| Format | Carte imprimée (grille 17×17) | DPI max utile | Image à 300 DPI |
|---|---|---|---|
| A3 | 17,5 mm | 1065 | 17 Mpx |
| A2 | 24,7 mm | 755 | 35 Mpx |
| A1 | 34,9 mm | 534 | 70 Mpx |
| A0 | 49,5 mm | **377** | 139 Mpx |

300 DPI passe donc partout, y compris en A0, mais avec peu de marge sur ce dernier.

### Grilles compatibles avec les formats d'impression

📐 Les cartes font **0,717** de rapport largeur/hauteur (734 × 1024), les formats de la
série A font **0,707**. Une grille **carrée en nombre de cartes** a donc exactement le
rapport d'une carte, soit **1,37 % d'écart** avec le papier — quelle que soit sa
taille. Les grilles allongées essayées jusqu'ici (20×14, 31×9) en sont très loin.

⚠️ Les tableaux de grilles ci-dessous raisonnent encore sur **281 cartes**, le jeu
d'origine. Le jeu compte désormais **441 cartes**, et 21×21 = 441 les place
exactement, sans une case vide. À reprendre.

**Cas A — un seul poster, feuille portrait.** Grille carrée N×N, écart 2,47 %.

| Grille | Cartes | Écart vs 281 |
|---|---|---|
| 16×16 | 256 | −25 |
| 17×17 | 289 | +8 |
| 18×18 | 324 | +43 |

Bande blanche résiduelle correspondante, si l'image occupe toute la largeur :

| Format | Image | Blanc total | Par côté |
|---|---|---|---|
| A3 | 297×410 mm | 10,1 mm | 5,1 mm |
| A2 | 420×580 mm | 14,4 mm | 7,2 mm |
| A1 | 594×820 mm | 21,2 mm | 10,6 mm |
| A0 | 841×1161 mm | 28,3 mm | 14,2 mm |

**Cas B1 — deux feuilles portrait collées.** Chaque moitié devant remplir sa feuille,
elle doit être carrée : la grille est donc forcément 2R×R, écart 2,47 %.

| Grille | Cartes | Écart vs 281 | Coupe |
|---|---|---|---|
| 22×11 | 242 | −39 | 2 × 11×11 |
| 24×12 | 288 | +7 | 2 × 12×12 |
| 26×13 | 338 | +57 | 2 × 13×13 |

**Cas B2 — une seule feuille paysage, sans coupe.** Meilleur ajustement possible, mais
un nombre impair de colonnes interdit la coupe en deux.

| Grille | Cartes | Écart vs 281 | Écart format |
|---|---|---|---|
| 23×12 | 276 | −5 | 1,80 % |
| 25×13 | 325 | +44 | 1,47 % |
| 27×14 | 378 | +97 | 1,19 % |

⚠️ `23×12 = 276` tombe à 5 cartes près du stock actuel et ajuste mieux le format, mais
ses 23 colonnes interdisent la coupe nette. Pour une coupe propre, c'est `24×12 = 288`
(+7 cartes) ; pour un poster simple, `17×17 = 289` (+8 cartes).

### Découpage en plusieurs posters

✅ **Vraie fonction d'export** : l'utilisateur choisit un découpage en N panneaux, et
l'app produit **un fichier par panneau**, chacun au format d'impression choisi.

✅ **La coupe tombe toujours sur un bord de carte**, jamais au milieu. Quand le
découpage est activé, l'app ne propose donc que les grilles dont le nombre de colonnes
est divisible par N.
✅ **Chevauchement réglable** entre panneaux, pour rattraper les imprécisions au
collage.
✅ **Repères de coupe** discrets en bord de panneau, pour faciliter l'alignement.

### Cases vides

✅ **Les cases vides sont autorisées.** C'est ce qui libère définitivement du problème
de factorisation : n'importe quelle grille devient choisissable.

✅ **Avertissements** aux étapes 2 ou 3 : si le nombre de cartes ne tombe pas juste,
l'app indique **combien de cartes ajouter ou retirer** pour atteindre un compte qui
remplit la grille ; sinon elle prévient explicitement qu'il y aura des cases vides.

✅ **Placement manuel des cases vides** : l'utilisateur clique sur la grille d'aperçu
pour désigner l'emplacement de chaque case vide, jusqu'à les avoir toutes placées.

✅ **Les cases vides sont figées** : elles ne bougent jamais, quel que soit le nombre
d'époques, et se retrouvent au même endroit sur l'image finale.

⚠️ **Conséquence sur l'algorithme** : il faut un mécanisme de cases verrouillées que
l'optimiseur ne peut ni déplacer ni remplir. Bonne nouvelle — ce mécanisme existe
déjà sous le nom de `locked_mask` dans `experiments/soft_adjacency_penalty.py`, qui
verrouille des positions fixes. À récupérer plutôt qu'à réinventer.

✅ **La couleur des cases vides est réglable** (étape 3, réglages de base).

✅ **Placement automatique par défaut** : les cases vides sont réparties régulièrement
sur la grille. L'utilisateur peut ensuite les déplacer une par une s'il le souhaite —
le placement manuel reste possible mais n'est jamais obligatoire.

### Reste à définir

✅ **Marge automatique** pour absorber l'écart de 2,47 % : les cartes gardent leurs
proportions exactes et l'image est centrée sur la feuille, laissant une fine bordure
(7 mm par côté sur A2, 10 mm sur A1). Ni déformation ni rognage.
📌 **Reporté après la v1** : laisser l'utilisateur décider quoi faire de cette marge
(couleur au choix, ou autre traitement). Consigné dans `TODO.md`.

✅ **Cartes collées bord à bord, sans marge entre elles**, pour cette version. C'est ce qui donne
l'effet de continuité le plus fort.
📌 **Reporté après la v1** : marges de page et espacement entre cartes réglables.
Consigné dans `TODO.md`, à traiter une fois tout le reste terminé.

---

## 5. Étape 3 — Paramètres de l'algorithme

✅ Nombre d'étapes de l'algorithme.
✅ Fréquence de rafraîchissement de l'aperçu (par défaut toutes les 10 époques,
réglable ici).

✅ **Les quatre seuils sont retenus** :
- **Arrêt sur score atteint** — stopper dès que le score global passe sous une valeur.
- **Arrêt sur stagnation** — stopper si rien ne s'améliore depuis N époques.
- **Tolérance d'acceptation** — écart minimum pour retenir un échange, ou tolérance
  pour accepter un échange légèrement moins bon afin de sortir des minima locaux.
- **Budget de temps** — plafond en minutes.

⚠️ La *tolérance d'acceptation* dans son sens « accepter un peu moins bon » change la
nature de l'algorithme : ce n'est plus une descente stricte mais un recuit simulé.
C'est précisément ce qu'il faut pour dépasser le plateau mesuré ci-dessous.

✅ **Les réglages sont répartis en « de base » et « avancés »**, les choix les plus
techniques étant rangés dans les avancés.

✅ Réglages retenus, en plus des étapes et des seuils : épaisseur des bandes de bord,
choix de l'algorithme, résolution d'impression, couleur des cases vides.

❓ Répartition proposée, **à confirmer ou corriger** :

| De base | Avancés |
|---|---|
| Nombre d'époques | Choix de l'algorithme (descente stricte / recuit simulé) |
| Cadence de rafraîchissement de l'aperçu | Épaisseur des bandes de bord (`strip_size`) |
| Arrêt sur stagnation | Tolérance d'acceptation |
| Budget de temps | Arrêt sur score atteint |
| Couleur des cases vides | |

Principe retenu : en **base**, ce qui se décide par intention (combien de temps, à
quelle fréquence, quelle couleur) ; en **avancés**, ce qui exige de comprendre le
fonctionnement interne (température de recuit, épaisseur de bande, seuil exprimé dans
une échelle de score qui n'a de sens qu'en relatif).

### Principe d'aperçu des réglages

✅ **Chaque réglage dont l'effet est montrable doit être accompagné d'un aperçu en
temps réel**, sur le modèle de l'aperçu de format à l'étape 2. Les réglages purement
techniques (température, seuils d'arrêt) en sont dispensés : leur effet n'est pas
visualisable.

Trois niveaux, selon ce que le réglage permet de montrer :

| Niveau | Réglages | Ce que voit l'utilisateur |
|---|---|---|
| **Aperçu visuel** | Format, grille, découpage, chevauchement, repères de coupe | Fil de fer de la mise en page |
| | **Épaisseur des bandes de bord** | Les bandes surlignées sur une carte, **plus** une petite grille d'essai réoptimisée en direct |
| | Couleur des cases vides | Le fil de fer, colorié |
| | DPI | Netteté réelle à la taille imprimée |
| **Projection chiffrée** | Nombre d'époques | Durée estimée et % du gain attendu |
| | Cadence de rafraîchissement | Nombre de clichés qui en résultera |
| **Aucun aperçu** | Température, tolérance, seuils d'arrêt, budget de temps | — |

✅ L'**épaisseur des bandes de bord reste en avancé**, mais gagne un aperçu direct.

📐 **Faisabilité vérifiée.** Changer l'épaisseur impose de recalculer les signatures
des 280 cartes : 387 ms à 3557 ms en pleine résolution, donc trop lent pour un
curseur. Sur des copies réduites à 25 %, c'est **25 à 211 ms**, avec une erreur
moyenne inférieure à **0,3 niveau de couleur sur 255** (0,1 %) — négligeable, car
réduire une image est déjà un moyennage. Une petite grille d'essai (20 cartes,
1000 itérations) se réoptimise en **37 ms**.

✅ La **résolution d'impression est à l'étape 2**, pas ici : c'est elle qui convertit
le format en taille de cartes en pixels, affichée sur ce même écran. La placer à
l'étape 3 ferait dépendre l'affichage de l'étape 2 d'un réglage situé sur un écran
pas encore vu.

### Comportement mesuré de l'algorithme

Mesuré sur les 280 cartes, grille 20×14, descente stricte, 300 000 itérations :

| Itérations | Score | % du gain total | Échanges retenus | Taux d'acceptation |
|---|---|---|---|---|
| 1 000 | 44 485 | **30,2 %** | 190 | 19,0 % |
| 5 000 | 35 568 | 44,2 % | 365 | 7,3 % |
| 25 000 | 28 823 | 54,8 % | 562 | 2,3 % |
| 100 000 | 25 277 | 60,3 % | 712 | 0,7 % |
| 300 000 | 23 584 | 63,0 % | 822 | **0,3 %** |

Débit : **~24 000 itérations/s**. Score initial 63 727.

Trois enseignements structurants pour l'interface :

1. **Presque tout se joue au début.** 30 % du gain total est acquis en 1 000
   itérations, soit **moins d'un dixième de seconde**. Le reste du calcul grappille.
2. **Le taux d'acceptation s'effondre** de 19 % à 0,3 %. Sur 300 000 tentatives,
   seules **822** aboutissent à un échange.
3. **Conséquence directe sur la timeline** : espacer les snapshots à intervalle
   d'itérations régulier concentrerait la quasi-totalité de la timeline sur une
   période où plus rien ne bouge visuellement.

✅ **Le choix de l'algorithme est exposé** (réglages avancés) : descente stricte ou
recuit simulé. Le plateau mesuré à 63 % confirme que la descente stricte se bloque
dans un minimum local, et que le recuit simulé a un intérêt réel ici.

---

## 6. Vue d'exécution

✅ L'image s'affiche et l'algorithme démarre.
✅ Toutes les N époques, l'aperçu est **mis à jour** avec l'état courant.
✅ Une **timeline en bas de l'image** permet de naviguer d'avant en arrière entre
tous les états enregistrés, **pendant que l'algorithme continue de tourner**.
✅ Les états sont stockés **sous forme de grille d'indices, pas de PNG**, pour
économiser la place. L'image est reconstruite à la demande, en résolution réduite
mais suffisante pour reconnaître les cartes.
✅ À la fin, l'utilisateur **choisit quel état exporter** ; les autres sont jetés.
C'est le cliché **affiché** que le bouton exporte, la timeline servant à le choisir.
Le dialogue ne propose que ce qui relève de l'écriture du fichier — format, pleine
résolution ou vignettes, chevauchement, repères de coupe — et rappelle sans le
rendre modifiable ce qui vient de l'étape 2. L'export tourne en fond, avec
progression par panneau et annulation : 7,3 s mesurées pour un A3 en deux panneaux
à 300 DPI, soit bien assez pour figer la fenêtre.

✅ **Prolonger** poursuit le calcul depuis le dernier cliché en conservant toute
la timeline : les compteurs d'itérations, d'échanges retenus et de temps repartent
de là où ils s'étaient arrêtés. **Repartir d'un cliché** relance depuis l'état
affiché et **abandonne les clichés suivants**, qui ne descendent plus de l'état
courant. Les deux commandes s'éteignent dès que la sélection, les liens ou la
grille changent : les cartes retenues étant renumérotées de 0 à n-1, les mêmes
indices désigneraient d'autres cartes sans que rien ne le signale.

✅ **Navigation au clavier** : flèches gauche et droite pour reculer et avancer
d'un cliché, Origine et Fin pour les extrémités.

✅ **Zoom sur l'aperçu.** Par défaut l'image tient **entière** dans le cadre, haut
et bas compris — l'ajustement se calcule sur les deux dimensions, borner la seule
largeur laissait un poster en portrait dépasser. Les touches `+` et `−`,
Ctrl+molette et les boutons zooment jusqu'à la résolution des vignettes, jamais
au-delà : agrandir davantage n'ajouterait aucun détail. Le **zoom appartient à
l'écran, pas au cliché** : parcourir la timeline le conserve, ce qui permet de
comparer deux états au même endroit du poster. Le rendu du zoom passe par la même
cadence bornée que le reste, une rafale de molette produisant des dizaines de
crans par seconde pour un rendu qui coûte 55 ms.

### Coût de stockage — distinguer la grille de son rendu

⚠️ Le raisonnement « un snapshot ne pèse rien » n'est vrai **que pour la grille**, pas
pour l'image correspondante :

| Ce qu'on stocke | Par snapshot | Pour 800 snapshots |
|---|---|---|
| Grille d'indices | 1,1 Ko | **1,1 Mo** — négligeable |
| Aperçu rendu à 10 % (A1) | 2,0 Mo | **1,6 Go** — impossible |
| Aperçu rendu à 15 % (A1) | 4,5 Mo | **3,5 Go** — impossible |

✅ **Conserver toutes les grilles sans jamais purger.**
✅ **Ne pas mettre les aperçus en cache** : reconstruire l'image à la demande lors de
la navigation, avec un cache limité aux quelques derniers snapshots consultés.

✅ **Contrainte de fluidité levée par la mesure.** Reconstruire un aperçu 17×17 à
partir de vignettes prend **1,5 à 5,3 ms**, très en deçà du budget de 16 ms d'une
image à 60 images/s. Le défilement de la timeline sera fluide.

### Décision d'architecture : travailler sur des vignettes

⭐ **Les images pleine résolution ne servent qu'à l'export.** Tout le reste —
signatures, score, optimisation, aperçus, timeline — se contente de copies réduites
à 25 % (178×246).

| | Pleine résolution | Vignettes à 25 % |
|---|---|---|
| Mémoire pour 280 cartes | **562 Mo** | **35 Mo** |
| Recalcul des signatures (strip 0,1) | 713 ms | 46 ms |
| Reconstruction d'un aperçu 17×17 | — | 5,3 ms |

Justification : les signatures ne sont que des moyennes de larges bandes, et l'erreur
introduite par la réduction est inférieure à 0,3 niveau de couleur sur 255. À l'export
seulement, les cartes d'origine sont relues depuis le disque.

Cette seule décision divise l'empreinte mémoire par **16** et rend simultanément
possibles l'aperçu temps réel des réglages et le défilement fluide de la timeline.

✅ **Export en pleine résolution** d'impression : réassemblage à partir des cartes
d'origine, alors que la timeline n'affiche que des aperçus légers.
✅ **Option d'export de la version aperçu** en plus : l'image pleine résolution étant
très lourde, une version légère est bien plus commode dès qu'on ne veut pas imprimer.

✅ **Cadence des snapshots : par échanges retenus.** 1 époque = N échanges
effectivement acceptés, et non N tentatives. Sur le run mesuré (822 échanges pour
300 000 tentatives), cela donne ~82 snapshots bien répartis du début à la fin,
chacun montrant un changement réellement visible.

✅ **Contrôle complet de l'exécution**, les quatre commandes sont retenues :
- **Arrêter définitivement** — la timeline reste consultable, l'export reste possible.
- **Mettre en pause et reprendre** — pour examiner la timeline tranquillement.
- **Repartir d'un snapshot choisi** — relancer depuis un état antérieur en jetant les
  suivants. Particulièrement utile avec un recuit simulé.
- **Prolonger après la fin** — demander des étapes supplémentaires sans recommencer.

✅ **Snapshots temporaires** : ils vivent le temps de la session et sont jetés à la
fermeture, cohérent avec « l'utilisateur choisit l'image à garder, les autres sont
jetées ».

✅ **Formats d'export : PNG, JPEG (qualité réglable) et PDF.** Le PDF porte les
dimensions physiques et le DPI, ce qui lève toute ambiguïté chez l'imprimeur ; le
JPEG reste bien plus léger que le PNG à cette taille.

---

## 7. Points hérités à traiter

Repris du diagnostic du code existant, ils deviennent structurants pour l'app :

- La forme de grille actuelle dépend de la factorisation première du nombre de cartes
  (281 cartes ⇒ bande 281×1). L'étape 2 rend la grille explicite, ce qui **supprime
  ce problème** — mais impose de décider quoi faire des cases vides.
- La transparence des cartes RGBA est aujourd'hui ignorée silencieusement.
- Le stockage partagé des ~350 Mo d'images entre plusieurs machines reste à définir
  (voir `TODO.md`).

---

## 8. Technologies

### Couche graphique : PySide6 (Qt)

✅ Le **cœur de calcul reste en Python** : il fonctionne, il est mesuré, et les
décisions d'architecture tiennent dans quelques centaines de lignes de numpy.

✅ **PySide6** pour l'interface. Chaque besoin de la spec correspond à un composant
éprouvé :

| Besoin | Composant |
|---|---|
| Galerie de 280 vignettes sélectionnables | `QListView` en mode icônes (virtualisé) |
| Grille en fil de fer, cliquable | `QGraphicsView` |
| Image live + curseur de timeline | `QGraphicsView` + `QSlider`, via signaux |
| Calcul en fond, pause/stop/reprise | `QThread` + signaux |
| Bilingue FR/EN | `tr()` + Qt Linguist, **intégré au framework** |
| Empaquetage macOS + Windows | PyInstaller |

Argument décisif : l'internationalisation est une exigence dure, et Qt est le seul
candidat à la fournir nativement plutôt que via une bibliothèque tierce à câbler.

### Dépendances : numpy + Pillow uniquement

✅ **opencv et scipy sortent de l'application.** Mesuré sur l'environnement actuel :

| Paquet | Poids | Sort ? |
|---|---|---|
| opencv | 99 Mo | ✂️ Pillow fait ouvrir / redimensionner / écrire |
| scipy | 75 Mo | ✂️ `cdist` remplacé par 2 matrices précalculées |
| scikit-learn | 32 Mo | ✂️ dépendance optionnelle des seules `experiments/` |
| numpy | 24 Mo | conservé |
| Pillow | 13 Mo | conservé |

**245 Mo aujourd'hui, dont 206 Mo inutiles à l'application.** Socle de calcul ramené
à 37 Mo — une différence sensible sur un exécutable distribuable.

Vérifié : une matrice de distances en numpy pur est **bit à bit identique** à celle de
scipy (écart max 0,00).

### Bibliothèques d'appoint

- **img2pdf** — export PDF : intègre le JPEG sans recompression et fixe la taille de
  page en millimètres. Exactement ce qu'attend un imprimeur.
- ~~platformdirs~~ — écarté le 2026-08-20 : `QStandardPaths` de Qt donne le même
  emplacement sans quatrième dépendance.
- **JSON** — persistance : lisible, modifiable à la main, comparable dans git.
- **pytest** — tests.

⚠️ Réserve : un export A0 fait 139 Mpx, soit 418 Mo en mémoire. Si ça coince,
**pyvips** traite les très grandes images en flux — mais il ajoute une dépendance
native qui complique l'empaquetage. À ne sortir qu'en cas de besoin avéré.

### Optimisation du cœur : matrices de distances précalculées

⭐ Deux matrices 280×280 (droite↔gauche et bas↔haut) remplacent tous les appels à
`cdist`. Mesuré :

| | Débit | Coût |
|---|---|---|
| Via `cdist` (actuel) | 473 000 coutures/s | — |
| Via matrices précalculées | **10 084 000 coutures/s** | 1,2 Mo, 4 ms de précalcul |

**Gain ×21.** C'est ce qui rend le recuit simulé praticable, puisqu'il demande
beaucoup plus d'itérations que la descente stricte.

✅ **À intégrer avant l'interface**, pour que l'UI se branche sur une base stable.

## 9. Avancement

État au 2026-08-29. À tenir à jour : c'est ce document qui fait foi si la
conversation est perdue.

### Fait

**Cœur de calcul** — chargement en vignettes, matrices de distances précalculées,
liens à ordre optionnel, cases vides figées, recuit simulé, seuils d'arrêt,
timeline de clichés, export poster en PNG/JPEG/PDF avec découpage en panneaux.

**Interface** — une barre de préréglages, puis les quatre écrans :
1. Sélection des cartes : galerie, filtrage par dossier, chargement progressif,
   bibliothèque de liens (créer, modifier, activer, liens par défaut)
2. Grille et format : presets d'impression, aperçu fil de fer, cases vides cliquables
3. Réglages de base et avancés, avec aperçus et projections chiffrées
4. Vue d'exécution : image live, timeline navigable au clavier, zoom,
   lancer/pause/arrêter, prolonger, repartir d'un cliché, export du cliché
   affiché

**Outillage** — hook `pre-commit` (ruff + pytest fichier par fichier), interface bilingue FR/EN,
754 tests. Interface auditée en entier, en deux lots — `ui/` d'abord, puis la vue
d'exécution, la mise en page, les réglages et l'export.

### Les deux derniers chantiers de la v1 — faits

| Sujet | État |
|---|---|
| **Empaquetage** | ✅ `.app` macOS autonome, 118 Mo, construit par `paquet/construire.sh`. ⚠️ Non signé valablement : démarre sur vos machines, refusé par Gatekeeper ailleurs. Voir `paquet/README.md`. |
| **Images des cartes** | ✅ **441/441**, illustrations nues 734×1024 en WebP q80 (56,4 Mo). Miroir public dans un dépôt dédié, récupération anonyme depuis l'application elle-même. Voir `docs/IMAGES.md`. |

## 10. Journal des décisions

| Date | Décision |
|---|---|
| 2026-08-16 | Objectif poster confirmé ; forme exécutable + UI en 3 étapes actée ; définition avant technologies |
| 2026-08-16 | Étape 2 : le format d'impression est la grandeur maître, la taille des cartes en découle |
| 2026-08-16 | Export multi-panneaux retenu comme vraie fonction (N fichiers) |
| 2026-08-16 | Cases vides autorisées, placées manuellement par l'utilisateur, et **figées** pendant toute l'optimisation |
| 2026-08-16 | Liens créables et modifiables par l'utilisateur, avec une liste par défaut reprise du code actuel |
| 2026-08-16 | Les 4 seuils retenus ; export pleine résolution **et** version aperçu |
| 2026-08-16 | Cadence des snapshots par **échanges retenus**, pas par tentatives |
| 2026-08-16 | Contrôle d'exécution complet : stop, pause/reprise, reprise depuis un snapshot, prolongation |
| 2026-08-16 | Cartes collées sans marge en v1 ; liens verticaux, blocs rectangulaires et cartes à coordonnées fixes reportés après v1 |
| 2026-08-16 | Marge automatique pour absorber l'écart de format (ni déformation ni rognage) |
| 2026-08-16 | Snapshots temporaires ; export PNG + JPEG + PDF |
| 2026-08-16 | Usage personnel d'abord, mais framework multiplateforme et dossier de cartes configurable **dès le départ** |
| 2026-08-16 | Préréglages nommés pour la configuration complète |
| 2026-08-16 | Découpage sur bords de cartes, avec chevauchement réglable et repères de coupe |
| 2026-08-16 | Réglages séparés en « de base » et « avancés » |
| 2026-08-16 | Interface bilingue FR/EN — à prévoir dès le départ |
| 2026-08-16 | Cases vides réparties automatiquement par défaut, ajustables à la main |
| 2026-08-16 | Ordre d'un lien **optionnel, lien par lien** (case « ordre imposé ») |
| 2026-08-16 | Liens dans une **bibliothèque séparée** ; un préréglage ne mémorise que les liens actifs |
| 2026-08-16 | DPI à 300 par défaut, modifiable, avec alerte au plafond utile ; placé à l'étape 2 |
| 2026-08-16 | Grilles conservées sans purge, mais **aperçus reconstruits à la demande** (pas de cache complet) |
| 2026-08-16 | Répartition base/avancés validée ; l'épaisseur des bandes reste en avancé mais gagne un aperçu |
| 2026-08-16 | **Principe général : tout réglage dont l'effet est montrable reçoit un aperçu temps réel** |
| 2026-08-16 | **Architecture : travail sur vignettes à 25 %**, pleine résolution réservée à l'export (562 Mo → 35 Mo) |
| 2026-08-16 | **PySide6 (Qt)** retenu pour l'interface — l'i18n native emporte la décision |
| 2026-08-16 | **opencv et scipy sortent** de l'application : socle ramené à numpy + Pillow (245 Mo → 37 Mo) |
| 2026-08-16 | **Matrices de distances précalculées** (gain ×21), à intégrer **avant** l'interface |
| 2026-08-20 | Liens composés dans un **dialogue à deux listes** (cartes disponibles / séquence) : une case à cocher n'a pas de rang, une ligne de liste en a un |
| 2026-08-20 | Les traductions Qt (`qtbase`) sont chargées **aussi en français** : sans elles un dialogue affiche « Cancel » en pleine interface française |
| 2026-08-20 | Aperçu d'exécution : ajustement sur les **deux** dimensions, zoom plafonné à la résolution des vignettes, et zoom conservé d'un cliché à l'autre |
| 2026-08-20 | L'export porte sur le **cliché affiché** ; format, orientation, DPI et panneaux restent à l'étape 2, seules les décisions d'écriture sont dans le dialogue |
| 2026-08-20 | Chaque panneau est **écrit avant que le suivant ne soit rendu**, et un export annulé efface ses fichiers partiels |
| 2026-08-20 | Préréglages **désignés par chemin** et non par indice, pour survivre à l'arrivée d'une extension ; ce sont les cartes **retirées** qui sont mémorisées |
| 2026-08-20 | `platformdirs` écarté : `QStandardPaths` suffit, le socle reste à trois dépendances |
| 2026-08-20 | Les formulaires **renvoient à la session** la valeur qu'ils ont écrêtée, un préréglage étant modifiable à la main |
| 2026-08-24 | **La récupération automatique est abandonnée.** Trois cents lignes ont été bâties sur des images jamais regardées, qui se sont révélées encadrées et non nues ; une autre voie refusait 438 requêtes sur 438. Les illustrations sont désormais **déposées à la main**, et le projet n'interroge plus aucun site |
| 2026-08-29 | **Pas de certificat de signature, sur aucun système.** Un certificat OV, le moins cher, ne supprime pas l'avertissement Windows tant que la signature n'a pas de réputation ; seul un EV le fait, bien plus cher. Pour un outil personnel, deux clics expliqués dans le README règlent mieux le problème. Écarte la distribution à des inconnus, où l'avertissement ferait abandonner |
| 2026-08-29 | **Le dossier de sortie n'est plus deviné une fois empaquetée.** `~/Pictures` n'existe qu'en anglais ; la ligne de commande réclame désormais `--output-dir` plutôt que de créer un dossier à côté du bon |
| 2026-08-29 | **L'application quitte le style natif pour Fusion**, et pose elle-même ses deux palettes Qt. Mesuré : le style macOS dessine exactement les mêmes pixels qu'une souris soit dessus ou non — 0 sur 3600 —, parce que macOS n'a pas de convention de survol pour les boutons ; Fusion en change 3307. Le renoncement au rendu natif est assumé : l'application vise aussi Windows et Linux, et Fusion lui donne la même apparence sur les trois. Les palettes sont les nôtres parce que changer de style remplace celle du système, ce qui ferait perdre le mode sombre |
| 2026-08-29 | **L'étape 2 se parcourt par onglets**, à la manière d'une création de personnage : la liste des parties à gauche, le détail à droite, une coche verte quand la partie est réglée et un avertissement sinon. Un seul formulaire portait tout — dimensions, format, orientation, finesse, panneaux, cases vides — sans dire par quoi commencer. Une partie est **prête** quand l'utilisateur l'a validée par « Suivant » **et** que son contenu tient toujours debout : revenir en arrière ne défait rien, mais casser un réglage rallume l'avertissement. « Suivant » reste **unique** : il déroule les parties avant de changer d'étape, deux boutons du même nom à l'écran ne disant pas lequel quitte l'étape |
| 2026-08-29 | **Onglet 1 — les seules dimensions de la grille.** Pas un mot du format d'impression, qui se décide à l'onglet suivant : le mêler obligeait à tout arbitrer d'un coup. Deux champs, cinq propositions, la grille en grand, et une ligne d'état d'une seule couleur — rouge des cartes ne tiennent pas, jaune il reste des vides à placer, vert c'est prêt. On ne passe qu'au vert |
| 2026-08-29 | **Les cases vides ne se placent plus d'office.** L'application en répartissait une d'office, quitte à la remplacer : la grille s'ouvrait déjà trouée, à des endroits que personne n'avait choisis, et rien ne disait qu'on pouvait les déplacer. C'est désormais un geste, que l'étape 2 compte et réclame. La répartition régulière reste offerte sur un bouton, qui **achève** un placement commencé sans défaire ce qui a été posé |
| 2026-08-30 | ⚠️ **Une feuille se définit par ses deux côtés ; le nom en découle.** Sept feuilles ont un nom, toutes ont deux côtés : `Session.paper_size_mm` — toujours en portrait — devient la vérité, et `paper` le nom qui lui correspond, vide s'il n'y en a aucun. Les deux ne peuvent pas diverger, `set_layout` recalculant toujours l'un depuis l'autre ; un nom inconnu venu d'un préréglage écrit à la main ne laisse plus ni le nom ni des dimensions fausses, et la correction ne dépend plus de l'écran, qui pouvait n'avoir jamais été ouvert. `PosterSettings` et les préréglages portent la taille en plus du nom, sans quoi une feuille hors catalogue s'imprimait en A2. Écarte l'idée d'un format nommé comme seule définition |
| 2026-08-30 | **L'onglet des pages se coupe en deux, et ne montre plus la mosaïque.** À gauche, « Format de la feuille » : trois grands champs — le format nommé, en liste et sans flèches puisque les valeurs ne se suivent pas, puis la largeur et la hauteur **en centimètres**, ce qu'on lit sur une rame de papier. Les deux dimensions sont celles de la feuille **telle qu'elle s'imprime** : la case « Paysage » échange les deux nombres sous les yeux, sans que « A4 paysage » cesse d'être un A4. À droite, une phrase, et rien d'autre. ⚠️ La mosaïque n'y est plus dessinée : cet onglet ne décide que du papier, et une grille posée dessus se lisait comme un aperçu du résultat alors qu'elle n'était réglée nulle part encore. **Conséquence** : le résumé ne chiffre plus que la surface — les cartes ne se règlent pas ici, ne s'y voient plus, et un format sans nom y laissait un trou |
| 2026-08-30 | **Le second rang se retire par la gauche, et un trait l'y rattache.** Trois onglets décalés se lisent comme trois onglets décalés : un trait unique qui les longe dit qu'ils sortent tous du même. Le retrait est **géométrique** — un délégué rogne le rectangle avant de le confier au style — et non quatre espaces dans le libellé, qui décalaient le texte sans décaler l'onglet. Le bord **droit** reste aligné sur les primaires : décalé des deux côtés, le second rang aurait flotté au milieu de la colonne sans se rattacher à rien. Le clic porte toujours sur la ligne entière, retrait compris — viser à côté de l'onglet ne doit pas rester sans effet. Replié, le trait disparaît avec ce qu'il reliait |
| 2026-08-30 | ⚠️ **La finesse d'impression se choisit à l'export, et nulle part ailleurs.** Elle était demandée à l'étape 2 depuis le 2026-08-16 : elle n'y change **rien de visible** — tout s'y mesure désormais en millimètres — et il fallait trancher une question d'impression avant même d'avoir posé la mosaïque. Elle passe au dialogue d'export, à côté du nombre de mégapixels et du plafond utile qu'elle décide, et son choix est **écrit dans la session** pour que les aperçus arrondissent leurs pixels comme le fichier et qu'un préréglage le retrouve. **Conséquence** : l'onglet des pages ne parle plus en pixels — cartes et mosaïque en millimètres — et l'avertissement de mégapixels le quitte, l'export le portant déjà |
| 2026-08-30 | **L'intitulé « Grille » plie ses trois onglets**, en accordéon. Muet, il passait pour un onglet en panne : il est cliquable sans être sélectionnable, n'ayant aucun contenu à montrer. ⚠️ Replier depuis l'un des trois **ramène aux pages** — garder affiché un onglet dont la ligne vient d'être cachée laisserait un écran que plus aucune sélection ne désigne, et un « Suivant » qui avance depuis un endroit invisible. Replié, il porte la pastille d'état de ses trois onglets, et « Suivant » le déplie de lui-même |
| 2026-08-30 | **La largeur d'une carte et l'écart entre cartes se posent en grand**, comme les dimensions de la grille : ce sont deux réglages du même ordre — ce qu'on met dans la case, après la taille de la grille —, et deux `QDoubleSpinBox` de vingt pixels les faisaient passer pour des détails de formulaire. `BigSpin` se dédouble en un `BigFloatSpin` qui relit lui-même son nombre : un `QDoubleValidator` suit la langue du système et refuserait le point décimal sur une machine française. Le bouton « taille d'une vraie carte » passe **sous** le champ qu'il remplit, se lisant comme une de ses valeurs possibles |
| 2026-08-30 | **La liste des grilles qui tiendraient monte en haut, et ne se referme plus.** Elle s'effaçait dès que la grille tenait, c'est-à-dire juste après le double-clic qui l'appliquait : comparer deux propositions demandait de la rouvrir entre chacune. Elle reste ouverte, et le bouton reste actif même quand la grille tient — on peut vouloir en essayer une autre. Elle n'apparaît toutefois qu'au premier clic : vide, elle laissait un rectangle noir sur un quart du panneau. En bas, elle poussait la grille hors de l'écran au moment précis où l'on voulait la regarder changer. Quand aucune forme ne tient — une carte de 2 000 mm sur un A5 —, elle le dit au lieu d'ouvrir un cadre vide. ⚠️ **Les écarts entrent enfin dans la taille annoncée de la mosaïque** : omis, ils ne se voyaient pas tant que le chiffre était en pixels ; en millimètres, c'est une dimension qu'on mesure à la règle sur le poster |
| 2026-08-30 | **L'étape 2 suit l'ordre des décisions** : d'abord les **Pages** — format, orientation, nombre de feuilles, finesse —, puis la famille **Grille**, dont l'intitulé n'est pas cliquable et coiffe trois onglets de second rang : la taille et les cases vides, la taille des cartes et leurs écarts, l'emplacement. L'algorithme reste l'étape 3. Tous les onglets de la famille ont la **même présentation** : les réglages en haut, les pages avec la mosaïque au milieu — carte étalon comprise —, les messages en bas. La bascule « montrer la mosaïque » disparaît : elle est montrée partout. Les cases vides se posent désormais **dans les pages**, au clic et au glissement, et seul l'onglet des tailles l'autorise — ailleurs, un clic qui creuse la mosaïque serait une surprise |
| 2026-08-30 | **La taille des cartes et l'écart qui les sépare deviennent réglables**, tous deux en millimètres — la même unité que la carte et la feuille, seule mesurable sur le poster imprimé. La taille reste **automatique** tant qu'on n'y touche pas : la plus grande qui fasse tenir la grille, recalculée à chaque changement. La fixer inverse le rapport, et c'est à la grille de s'adapter : l'écran le refuse en attendant, chiffre ce qui tiendrait, et propose deux gestes — la taille d'une vraie carte (63 mm), et la liste des **grilles qui tiendraient**, classées par nombre de cartes placées puis par écart à la grille actuelle |
| 2026-08-30 | ⚠️ **Une coupe tombe toujours entre deux cartes — c'est la carte qui se plie à la feuille.** La règle avait été relâchée le matin même ; elle revient, mais autrement. On exigeait que le nombre de colonnes se divise par le nombre de feuilles, ce qui interdisait des grilles parfaitement bonnes pour une raison qui n'était pas la leur. `panel_card_size` fixe désormais un nombre **entier** de cartes par feuille, et `PosterPlan.column_x` fait **repartir chaque feuille de son propre bord** : la coupe tombe entre deux cartes par construction, quel que soit le nombre de colonnes. Le reste de feuille — moins d'une carte — sort blanc et disparaît au raboutage, les repères de coupe étant là pour le rogner. Ajouter une feuille agrandit donc les cartes quand la largeur contraignait (42 → 74 → 99 px mesurés) |
| 2026-08-30 | **Les aperçus calculent à la résolution de la session**, jamais à 72 dpi. Les arrondis en pixels ne donnaient pas le même nombre de cartes par feuille — **49 161 combinaisons en désaccord** sur les sept formats — et l'on jugeait la mise en page sur un dessin qui n'était pas celui du poster |
| 2026-08-30 | **Cinq feuilles au plus** (six auparavant) : cinq A2 font déjà deux mètres de large. **L'aperçu de la mosaïque est décoché d'office** — c'est une idée de ce que ça donnerait, pas la décision de l'onglet — et **les cases vides s'y voient**, comme partout ailleurs : sans elles, la mosaïque dessinée n'était pas celle qu'on venait de composer. **L'orientation passe à l'onglet du format**, dont elle décrit la feuille ; l'onglet suivant ne garde que la finesse d'impression et le récapitulatif |
| 2026-08-30 | ⚠️ **Plusieurs feuilles, c'est une seule surface — et la coupe n'est plus contrainte.** Le calcul découpait la grille feuille par feuille et exigeait que les colonnes s'y divisent, pour que la coupe tombe toujours sur un bord de carte (décision du 2026-08-20, **abandonnée**). Des feuilles côte à côte ne sont qu'une façon d'avoir **plus de place** : la carte se dimensionne sur la surface entière, la coupe tombe où elle tombe — c'est du papier qu'on raboute, et le chevauchement et les repères de coupe existent pour ça. `suggest_grids` perd son paramètre `panels` |
| 2026-08-30 | **La mosaïque est calée contre le bord gauche**, non centrée : la place en trop est ce qu'apporte la feuille suivante, elle doit se voir d'un bloc, du côté où l'on ajoutera la prochaine. Répartie de part et d'autre, elle donnait deux demi-marges qui ne disaient rien. La marge verticale ne dépend d'aucune feuille et reste centrée. L'onglet du format ne décide donc que de la **taille du papier et du nombre de feuilles** ; la façon dont la grille s'y installe — marges, centrage — viendra à un onglet suivant |
| 2026-08-30 | **L'avertissement de couverture ne juge plus.** Il conseillait d'allonger la grille pour mieux remplir : depuis qu'ajouter une feuille veut dire « avoir plus de place », ce blanc est l'état normal, et l'onglet précédent l'annonce comme tel. Deux écrans disaient le contraire du même blanc, et le conseil poussait à défaire ce que le « + » venait de faire. On donne le chiffre et ce qu'il coûte à l'impression, en ambre et non en rouge : ce sont des mises en page valides |
| 2026-08-29 | **Les feuilles s'ajoutent et se retirent depuis l'aperçu** : un « + » à droite de la page, un « − » sous chaque feuille — la même grammaire que l'éditeur de liens. L'étalon passe **à gauche**, la droite revenant au bouton d'ajout : il y aurait été poussé plus loin à chaque clic. Les « − » entrent dans l'écart existant entre la feuille et sa cote, qui n'est pas agrandi : l'élargir éloignerait la cote de ce qu'elle mesure pour loger un bouton qu'on ne regarde pas. La cote de largeur reste **unique et globale**, quel que soit le nombre de feuilles : c'est la largeur du poster qu'on lit, pas celle d'un morceau. ⚠️ Une grille que le nombre de feuilles ne divise pas **bloque les deux onglets** qui règlent ce nombre : la faute passait ou bloquait selon l'endroit où elle était commise, et l'on pouvait quitter l'étape avec une coupe en pleine carte |
| 2026-08-29 | **Les parties de l'étape 2 deviennent de gros onglets.** Des lignes de liste de dix-huit pixels, collées les unes aux autres, se lisaient comme un contenu à faire défiler et non comme une navigation : elles prennent la taille d'un bouton, avec fond, bordure et de l'air entre elles. Il n'y en aura jamais plus de cinq ou six |
| 2026-08-29 | **La mosaïque se pose sur la feuille**, sur une bascule, pour voir ce qu'elle laisse de marge. Un avertissement l'accompagne : l'ajustement montré n'est pas définitif, l'orientation et le nombre de panneaux se règlent à l'onglet suivant et les dimensions restent modifiables au premier. Les cartes y sont dessinées toutes pareilles — ce panneau répond à « combien de papier reste autour », et y marquer les cases vides empiéterait sur l'onglet des dimensions |
| 2026-08-29 | **La colonne de l'étalon est large du plus large de ses deux contenus.** L'étiquette était centrée sur la seule carte : dès qu'un grand format la réduisait, le texte débordait des deux côtés et passait sous la feuille. La largeur de la colonne n'étant pas connue d'avance, l'échelle se résout dans les deux cas et garde le plus petit facteur. ⚠️ La feuille est **calée**, non centrée dans le cadre entier : centrée, la moitié de la réserve partait vers le haut où elle ne sert à rien, et il ne restait que 37 px sous la feuille pour une cote qui en réclame 42 |
| 2026-08-29 | **Les cases vides se dessinent pleines et rouges**, et non plus seulement cernées : un contour rouge sur fond blanc se perdait au milieu des cartes dès que la grille passait la centaine de cases. ⚠️ **Conséquence** : le trait de coupe entre panneaux portait presque le même rouge — huit d'écart sur 765, là où une case vide et une carte en ont 315 — et passait pour une colonne de trous. Il devient un gris sombre tiré, convention des traits de coupe. La ligne d'état passe de 9 à 12 points et met son décompte en gras : c'est le verdict de l'onglet, il doit se lire depuis l'autre bout de l'écran |
| 2026-08-29 | **Les deux dimensions se posent en grand.** Un compteur par dimension, côte à côte : intitulé, flèche haut, nombre, flèche bas, les flèches aussi larges que le nombre. Une paire de `QSpinBox` de vingt pixels ne disait pas que c'était **la** décision de l'onglet. Le nombre reste saisissable — passer de 4 à 21 à la flèche demanderait dix-sept clics. Les propositions perdent leur cadre et leur titre : cinq lignes qui se lisent seules n'avaient pas besoin d'un intitulé, d'une bordure et de douze pixels de marge, et la place gagnée va en largeur |
| 2026-08-29 | **Les cases vides se posent aussi au glissement.** Ce que le geste pose est décidé par sa **première** case : basculer case par case ferait clignoter tout ce sur quoi on repasse, un aller-retour du curseur défaisant ce que l'aller vient de poser. Le quota **borne** la pose sans rien chasser — évincer les plus anciennes ferait courir les trous derrière le curseur. Un geste d'une seule case reste un clic, avec son éviction : c'est ainsi qu'on déplace un trou sur une grille déjà complète. Bouton gauche seul |
| 2026-08-29 | **Onglet 2 — le format montré plutôt que nommé.** La feuille à l'échelle, cotée en centimètres par des flèches, et **une carte Pokémon à ses dimensions réelles posée à côté**, au même rapport. Un rectangle seul n'a pas d'échelle : sur un écran, un A6 et un A0 sont le même dessin. L'étalon est le seul des deux objets qu'on ait déjà tenu en main |
| 2026-08-29 | **Les grilles proposées ne sont plus carrées, et il y en a dix.** Le format cessait d'être un filtre à 5 % pour devenir un simple départage : une carte fait 0,725 de rapport, une feuille A 0,707, si bien que la grille idéale avait toujours autant de lignes que de colonnes à 2,5 % près, et que **seuls des carrés étaient proposés**. Vingt cartes n'avaient alors aucune grille de vingt cases — on offrait 4×4 en en abandonnant quatre, ou 5×5 en laissant cinq trous, quand 4×5 tombe pile. Ce qui borne la forme est désormais l'écart entre les deux côtés, **trois cases au plus** : au-delà la mosaïque devient une bande. ⚠️ **Conséquence sur plusieurs panneaux** : une feuille double est 1,41 fois plus large que haute et aucune grille quasi carrée ne la suit — mesuré, 441 cartes en 20×23 sur deux A4 ne couvrent que 43,9 % du papier contre 96,9 % pour un 30×15. L'écran le dit désormais en clair sous les 75 % de couverture, la grille restant valide et modifiable à la main |
| 2026-08-29 | **La grille de l'étape 2 se propose toute seule au premier passage**, ajustée au nombre de cartes retenues. Elle se calcule à l'entrée sur l'écran et non au chargement : le nombre retenu n'est arrêté qu'une fois l'étape 1 quittée. ⚠️ **On écarte les grilles qui perdent des cartes**, même mieux classées : sur A4 seules des grilles presque carrées passent le seuil de 5 %, et 20 cartes n'ont pas de grille de 20 cases admissible — la plus proche, 4×4, en abandonnerait quatre en silence juste après l'écran où on vient de les choisir une par une. On prend 5×5. Tout choix explicite — à la main, par suggestion ou par préréglage — désarme l'ajustement définitivement ; un nouveau jeu de cartes le réarme |
| 2026-08-29 | **Cliquer une carte ne laisse plus de surlignage bleu.** La sélection de la galerie n'est qu'un outil de passage — désigner un lot avant de le basculer —, pas un état à montrer : posée, elle recouvrait le seul signal qui compte, l'inclusion dite par l'opacité. Le rectangle de sélection garde le sien, `clicked` ne partant pas sur un glissé |
| 2026-08-29 | **Un bouton « Inverser »**, de même portée que ses deux voisins : les cartes affichées changent de camp. Il passe par `Session.invert_excluded` et non par deux `set_excluded` — celui-ci ne prévient que si le **nombre** d'exclues a changé, et une inversion peut le laisser identique |
| 2026-08-29 | **Recherche par nom dans la galerie de l'étape 1.** Un champ au-dessus de la galerie filtre sur le nom de fichier, sans casse ni accents — les noms sont normalisés par `artwork.slug()`, ce qu'on tape ne l'est pas. Le nom porte le code d'extension en préfixe, donc `a3-` et `dracaufeu` marchent tous deux. Le filtre se **cumule** avec la sélection de dossier au lieu de la remplacer : chercher un nom à l'intérieur d'une extension est le geste attendu. Coût mesuré : 3 à 4 ms par frappe sur 441 cartes, donc pas d'anti-rebond |
| 2026-08-29 | **« Tout inclure » et « Tout exclure » portent sur ce que la galerie affiche**, filtres compris, et non plus sur tout le jeu chargé. C'est ce que leur position sur la galerie laisse entendre, et le seul geste de masse à portée quand une recherche a réduit l'affichage. Mesuré avant correction : chercher « dracaufeu » puis cliquer « Tout exclure » excluait les 40 cartes au lieu des 10 affichées, effaçant la sélection entière sans confirmation. Le libellé se chiffre dès qu'un filtre est actif — « Exclure les 10 affichées » — pour qu'on ne les lise plus comme globaux. Écarte le geste « tout exclure sauf ce que je regarde », qui n'a plus de bouton dédié |
| 2026-08-29 | **Le curseur en main sur tout bouton actif**, retiré dès qu'il est inerte. Un signal que la feuille de style ne sait pas donner — Qt n'admet pas de propriété `cursor` — posé par un filtre à l'échelle de l'application, les boutons étant trop nombreux pour être marqués un par un |
| 2026-08-29 | **La lignée d'Arcko est un lien fourni d'office**, en colonne 1×3 : Méga-Jungko-ex en haut, Massko au milieu, Arcko en bas — la plus évoluée domine, comme sur un arbre généalogique. Les liens par défaut portent désormais leur forme, et un lien dont une seule carte manque est écarté en entier : un rectangle plein n'a pas de version amputée |
| 2026-08-29 | **Deux palettes, cinq rôles.** Qt adapte déjà `Window`, `Text` et `Base` au mode du système ; il lui manque une notion d'avertissement et d'erreur. Les six couleurs codées en dur, choisies pour un fond clair, deviennent des rôles déclinés en clair et en sombre — `ui/theme.py`. Les widgets portent une propriété `role`, une feuille de style **globale** les colore, et une bascule du système la repose. Le mode se déduit de la clarté de `palette(Window)` et non de `colorScheme()`, qui rend `Unknown` sans thème de plateforme. Contrastes **vérifiés par calcul** : 4,5:1 pour un texte, 3:1 pour un trait |
| 2026-08-27 | **Le lien se compose dans une grille, au glisser-déposer.** Deux panneaux : le rectangle à gauche, les cartes à droite, filtrables par nom et par extension. La grille part d'une case et grandit par ses bords — un « + » au-dessus et à droite, un « − » en regard de chaque rangée et colonne dès qu'il y en a plus d'une. On ne valide qu'un rectangle **plein**. Double-clic pour vider une case : une croix par-dessus mangerait l'illustration |
| 2026-08-27 | **Les liens deviennent des rectangles pleins, 3×3 au maximum.** Un seul concept remplace horizontal, vertical et groupe : une ligne de 3 est un 1×3, une colonne un 3×1. Jamais de forme trouée ni de rectangle incomplet. Mesuré sur la grille 21×21 : un 3×3 a 361 ancrages contre 399 pour la barre actuelle, l'optimiseur ne voit pas la différence — un 9×9 n'en aurait eu 169, pour 18 % du poster figé d'un coup |
| 2026-08-27 | **Une carte liée ne peut pas être figée**, et réciproquement. Les deux mécanismes sont disjoints. La règle inverse — figer une carte immobilise tout son rectangle, qui ne se déplace que d'un tenant — était logique mais illisible : huit cartes cessent de bouger sans raison visible. Écarte le placement d'un bloc à des coordonnées choisies |
| 2026-08-27 | **L'application obtient les cartes elle-même.** L'étape 1 s'ouvre sur deux boutons — télécharger, ou désigner un dossier —, le dossier retenu est mémorisé, et « Mettre à jour le catalogue » relit `cards.json` au miroir. Une installation neuve n'avait jusque-là aucun moyen d'obtenir d'images |
| 2026-08-27 | **Les écarts de format sont dits à l'écran** et non imprimés : depuis un `.app`, la sortie standard ne va nulle part, et une carte hors format est étirée, ce qui fausse les couleurs de bord dont l'assemblage se sert |
| 2026-08-27 | **Le miroir est la seule provenance.** Tout ce qui désignait un site tiers — scripts d'acquisition, adresses au manifeste, notes de source — est retiré du code, du catalogue et de l'historique. `cards.json` passe en version 4 : il ne dit plus que ce que le miroir contient |
| 2026-08-24 | **Stockage en WebP qualité 80** : 56,3 Mo contre 541 Mo pour les sources PNG. Écart médian de 0,45 niveau sur 255 sur la moyenne RGB d'un bord, sous l'erreur des vignettes à 25 % déjà acceptée. Différences montrées et validées à l'œil |
| 2026-08-22 | Sélection reconstituée par règle : trois raretés étoilées, hors illustrateur `PLANETA*` (rendus 3D), hors Dresseur sauf en Three Star. Reproduit la sélection existante sur **12 extensions sur 12** |
| 2026-08-22 | Français avec repli anglais ; l'image dépendant de la langue, le manifeste note celle retenue par carte pour ne retélécharger que les cartes concernées quand le français se complétera |
| 2026-08-20 | Prolonger **poursuit la timeline** ; repartir d'un cliché **tronque** ce qui suit. Une timeline non vide passée à `optimize_grid` signifie « reprise » et reporte les compteurs |
