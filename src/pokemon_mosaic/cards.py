"""Chargement des cartes et calcul de leurs signatures de bord.

Architecture : tout le travail se fait sur des **vignettes réduites**. Les images
pleine résolution ne sont relues du disque qu'au moment de l'export. Voir SPEC.md §8.
"""

import os
from collections import Counter
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass, field, replace

import numpy as np
from PIL import Image

# `.webp` est le format du miroir, donc celui de tout jeu récupéré par
# `scripts/fetch_cards.py` : sans lui, le chargement ne trouverait aucune carte.
VALID_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff")

# Les mosaïques dépassent la limite anti-décompression-bomb de Pillow.
Image.MAX_IMAGE_PIXELS = None

DEFAULT_SCALE = 0.25
DEFAULT_STRIP_SIZE = 0.1
# Le nombre de parties de la métrique améliorée. Chaque partie prend toute
# l'épaisseur du bord et recouvre la moitié de la suivante. **Dix par défaut**,
# choisi par l'utilisateur le 2026-09-21 sur mesure : plus il y a de parties,
# plus le classement des raccords ressemble au vrai, corrélation de rangs avec
# l'écart de pixels à la couture 0,799 à une partie, 0,852 à cinq, 0,875 à dix.
# Le surcoût ne se sent pas, mesuré sur 441 cartes : signatures 92 -> 175 ms,
# table des distances 12 -> 71 ms, pic de mémoire 7,9 -> 14,5 Mo, et les deux
# tables gardent leur taille, 3,1 Mo.
EDGE_PARTS = 10
# Ce que le champ laisse choisir, bornes comprises. En deçà de cinq, la
# métrique n'a plus grand-chose d'amélioré ; au-delà de dix, chaque partie
# devient trop étroite pour qu'on la voie sur l'aperçu.
EDGE_PARTS_RANGE = (5, 10)


def edge_windows(length: int, parts: int) -> list[tuple[int, int]]:
    """Les bornes des parties d'un bord, chacune à moitié couverte par la suivante.

    Les parties avancent d'un demi-pas : les deux du bout ne sont recouvertes
    que d'un côté, les autres le sont des deux, si bien que `parts` parties
    couvrent la longueur entière. D'où la largeur : `2 * length / (parts + 1)`.

    ⚠️ **Une seule définition**, lue par le calcul des signatures **et** par
    l'aperçu qui les montre : deux découpages finiraient par diverger, et
    l'écran désignerait des parties que le score ne mesure pas.
    """
    pas = length / (parts + 1)
    bornes = []
    for rang in range(parts):
        debut = round(rang * pas)
        # Au moins un pixel : sur une vignette très courte, deux bornes
        # arrondies tombent au même endroit et la moyenne n'aurait rien à lire.
        fin = max(debut + 1, min(length, round((rang + 2) * pas)))
        bornes.append((debut, fin))
    return bornes


def _edge_means(bande: np.ndarray, parts: int) -> np.ndarray:
    """La signature d'un bord : une moyenne, ou une par partie recouvrante.

    `bande` porte sa **longueur en premier axe**, pour que le découpage soit le
    même dans les quatre sens. Les parties sont rangées dans l'ordre de cette
    longueur, de gauche à droite ou de haut en bas : c'est ce qui les fait
    correspondre d'une carte à sa voisine.
    """
    if parts <= 1:
        return bande.mean(axis=(0, 1))
    return np.array([bande[debut:fin].mean(axis=(0, 1))
                     for debut, fin in edge_windows(bande.shape[0], parts)])


@dataclass
class Card:
    """Une carte, représentée par sa vignette et les couleurs de ses quatre bords.

    `top`/`bottom`/`left`/`right` sont la signature d'une bande occupant
    `strip_size` de la hauteur (ou largeur) de la vignette : un vecteur RGB, sa
    moyenne, ou **une moyenne par partie** quand la métrique améliorée est
    demandée, `(parties, 3)`. C'est toute la signature utilisée pour juger si
    deux cartes se raccordent.

    `path` permet de relire l'original en pleine résolution à l'export.
    """

    path: str
    index: int
    thumbnail: np.ndarray

    # Indice qu'avait la carte dans l'ensemble d'origine, quand elle provient d'un
    # sous-ensemble renuméroté. Sert à retrouver la sélection de l'utilisateur.
    source_index: int | None = None

    top: np.ndarray = field(default=None, repr=False)
    bottom: np.ndarray = field(default=None, repr=False)
    left: np.ndarray = field(default=None, repr=False)
    right: np.ndarray = field(default=None, repr=False)

    @property
    def name(self) -> str:
        """Nom lisible de la carte, sans dossier ni extension."""
        return os.path.splitext(os.path.basename(self.path))[0]

    @property
    def folder(self) -> str:
        """Dossier contenant la carte, utile pour les sélections par groupe."""
        return os.path.basename(os.path.dirname(self.path))

    def calculate_features(self, strip_size: float = DEFAULT_STRIP_SIZE,
                           parts: int = 1) -> None:
        """Mesure les quatre bords, d'un bloc ou partie par partie.

        `parts` à 1 donne la moyenne d'une bande entière, la métrique d'origine.
        Au-delà, la bande est découpée dans sa longueur en parties qui se
        recouvrent de moitié : deux bords de moyennes identiques mais de
        contenus différents cessent alors de passer pour compatibles.
        """
        h, w = self.thumbnail.shape[:2]
        strip_h = max(1, int(h * strip_size))
        strip_w = max(1, int(w * strip_size))

        # Les bandes du haut et du bas se découpent dans leur largeur : on les
        # tourne pour que leur longueur soit le premier axe, comme les autres.
        self.top = _edge_means(np.swapaxes(self.thumbnail[:strip_h, :], 0, 1), parts)
        self.bottom = _edge_means(
            np.swapaxes(self.thumbnail[h - strip_h :, :], 0, 1), parts)
        self.left = _edge_means(self.thumbnail[:, :strip_w], parts)
        self.right = _edge_means(self.thumbnail[:, w - strip_w :], parts)


@dataclass
class SizeWarning:
    """Un format rencontré qui n'est pas celui retenu, et combien de cartes."""

    size: tuple[int, int]
    count: int


@dataclass
class CardSet:
    """L'ensemble des cartes chargées, plus les dimensions nécessaires à l'export."""

    cards: list[Card]
    full_size: tuple[int, int]
    thumb_size: tuple[int, int]
    # Ce que le chargement a trouvé d'anormal. **Porté et non imprimé** : depuis
    # un paquet `.app`, la sortie standard ne va nulle part que l'utilisateur
    # puisse lire, et ces écarts déforment silencieusement toutes les cartes.
    odd_sizes: list[SizeWarning] = field(default_factory=list)
    unreadable: list[str] = field(default_factory=list)

    @property
    def has_warnings(self) -> bool:
        return bool(self.odd_sizes or self.unreadable)

    def __len__(self) -> int:
        return len(self.cards)

    def __iter__(self) -> Iterator[Card]:
        return iter(self.cards)

    def __getitem__(self, i: int) -> Card:
        """Accès par indice de carte.

        L'ensemble garantit `card.index == position dans la liste` : c'est ce qui
        permet aux matrices de distances, à la grille et au rendu de partager la
        même numérotation. Utilisez `subset()` pour construire une sélection, il
        rétablit cette propriété.
        """
        return self.cards[i]

    def subset(self, indices: Sequence[int]) -> "CardSet":
        """Nouvel ensemble limité à ces cartes, **renuméroté** de 0 à n-1.

        Indispensable dès qu'on ne travaille que sur une partie des cartes : les
        indices d'origine sont discontinus, alors que les matrices de distances
        sont indexées par position. Sans renumérotation, les distances seraient
        lues à la mauvaise ligne et la mosaïque assemblée avec les mauvaises
        cartes, sans que rien ne le signale.

        Les vignettes ne sont pas recopiées : les tableaux sont partagés. Les
        avertissements non plus : ils portent sur un **chargement**, pas sur une
        sélection, et les recopier ferait accuser des cartes qu'on vient
        justement d'écarter.
        """
        chosen = sorted(set(indices))
        cards = [
            replace(self.cards[index], index=position,
                    source_index=self.cards[index].source_index
                    if self.cards[index].source_index is not None
                    else self.cards[index].index)
            for position, index in enumerate(chosen)
        ]
        return CardSet(cards=cards, full_size=self.full_size,
                       thumb_size=self.thumb_size)

    def recalculate_features(self, strip_size: float, parts: int = 1) -> None:
        """Recalcule toutes les signatures : utilisé par l'aperçu temps réel.

        Mesuré à ~46 ms pour 280 cartes sur vignettes à 25 %, contre 713 ms en
        pleine résolution. C'est ce qui rend le réglage interactif.
        """
        for card in self.cards:
            card.calculate_features(strip_size, parts)

    def index_mapping(self) -> dict:
        """Table « indice d'origine -> indice courant », pour traduire les liens.

        À passer à `LinkLibrary.remapped()` chaque fois qu'on construit un
        sous-ensemble : les cartes sont renumérotées, les liens doivent suivre.
        """
        return {
            (card.source_index if card.source_index is not None else card.index):
                card.index
            for card in self.cards
        }

    def find(self, path_fragment: str) -> int | None:
        """Retrouve l'indice d'une carte à partir d'un fragment de son chemin."""
        return next((c.index for c in self.cards if path_fragment in c.path), None)


def iter_image_paths(root_dir: str, exclude: Sequence[str] = ()) -> Iterator[str]:
    """Parcourt récursivement les fichiers image, en ordre stable.

    L'ordre est trié pour que deux chargements successifs donnent les mêmes indices,
    condition nécessaire pour que les préréglages restent valides d'une session à
    l'autre.
    """
    for dirpath, dirnames, filenames in os.walk(root_dir):
        dirnames.sort()
        for filename in sorted(filenames):
            if os.path.splitext(filename)[1].lower() not in VALID_EXTENSIONS:
                continue
            path = os.path.join(dirpath, filename)
            if any(fragment in path for fragment in exclude):
                continue
            yield path


def load_cards(
    root_dir: str,
    exclude: Sequence[str] = (),
    scale: float = DEFAULT_SCALE,
    strip_size: float = DEFAULT_STRIP_SIZE,
    parts: int = 1,
    progress: Callable[[int, int], None] | None = None,
    on_folder: Callable[[str, list["Card"]], None] | None = None,
    check_cancelled: Callable[[], None] | None = None,
) -> CardSet:
    """Charge les cartes sous forme de vignettes et calcule leurs signatures.

    Deux passes : la première ne lit que les en-têtes pour trouver la plus petite
    taille commune (Pillow donne `.size` sans décoder les pixels) ; la seconde décode
    et réduit directement à la taille de vignette. Les images pleine résolution ne
    sont donc jamais toutes en mémoire : 35 Mo au lieu de 562 Mo.

    `on_folder` est appelé dès qu'un dossier est entièrement traité, avec son
    chemin et ses cartes. Cela permet à une interface d'afficher les extensions les
    unes après les autres au lieu d'attendre la fin : la première passe ne lit que
    les en-têtes et ne coûte que ~80 ms, contre ~3,5 s pour le décodage complet.

    `check_cancelled` est appelé à chaque fichier, dans les **deux** passes. Il
    n'a rien à renvoyer : à charge pour l'appelant de lever s'il veut interrompre.
    Le couvrir dès la première passe importe, elle est purement séquentielle et
    peut durer sur une arborescence fournie ou un disque réseau, laissant sinon
    un fil impossible à arrêter.

    `progress` est appelé avec (traitées, total) pendant la seconde passe. Le
    chargement prenant ~4 s pour 280 cartes, une interface graphique doit pouvoir
    rendre compte de l'avancement plutôt que de rester figée.

    Note : les cartes en RGBA voient leur canal alpha écarté, sans composition sur un
    fond. Comportement identique à l'ancien chargement OpenCV. Voir TODO.md.
    """
    paths = list(iter_image_paths(root_dir, exclude))
    if not paths:
        return CardSet(cards=[], full_size=(0, 0), thumb_size=(0, 0))

    # Passe 1 : en-têtes seulement, pour établir le format commun.
    sizes: Counter = Counter()
    readable: list[str] = []
    unreadable: list[str] = []
    for path in paths:
        if check_cancelled is not None:
            check_cancelled()
        try:
            with Image.open(path) as img:
                size = img.size
        except Exception as e:  # noqa: BLE001 - un fichier abîmé ne doit pas
            # interrompre le chargement des 280 autres cartes.
            # Pillow répète le chemin absolu dans son message ; le garder
            # produirait une ligne de 200 caractères là où le nom du fichier
            # suffit à le retrouver.
            raison = str(e).replace(path, os.path.basename(path))
            unreadable.append(f"{os.path.basename(path)} : {raison}")
            continue
        readable.append(path)
        sizes[size] += 1

    if not readable:
        return CardSet(cards=[], full_size=(0, 0), thumb_size=(0, 0),
                       unreadable=unreadable)

    # ⚠️ Le format **le plus fréquent**, et non la largeur et la hauteur
    # minimales prises séparément. Ces deux minima donnaient un couple que
    # personne ne portait : trois fichiers en 734×1024, 717×1050 et 734×1024
    # produisaient un `full_size` de 717×1024, de rapport d'aspect étranger aux
    # trois, et **toutes** les cartes étaient déformées de 2,3 %, sans un mot.
    # Le défaut s'est produit le 2026-08-22 avec deux fichiers retouchés à la
    # main. Le format retenu est désormais celui d'une carte réelle, et les
    # écarts se signalent au lieu d'être absorbés.
    # Ex aequo départagés par la **plus petite surface** : à égalité de
    # fréquence, mieux vaut réduire que d'agrandir sans gagner de détail. Sans
    # règle explicite, l'ordre de rencontre des fichiers déciderait.
    full_size = min(sizes, key=lambda taille: (-sizes[taille], taille[0] * taille[1]))
    odd_sizes = [SizeWarning(size=taille, count=n)
                 for taille, n in sizes.most_common() if taille != full_size]
    min_w, min_h = full_size
    thumb_size = (max(1, round(min_w * scale)), max(1, round(min_h * scale)))

    # Passe 2 : décodage et réduction directe à la taille de vignette.
    # BOX est une moyenne de blocs : c'est exactement l'opération qui justifie de
    # calculer les signatures sur les vignettes plutôt qu'en pleine résolution.
    cards: list[Card] = []
    batch: list[Card] = []
    batch_folder: str | None = None

    def flush() -> None:
        if on_folder is not None and batch:
            on_folder(batch_folder, list(batch))
        batch.clear()

    # Les fichiers traités, réussis ou non : c'est ce que compte la progression,
    # sans quoi une carte sautée l'empêchait d'atteindre son total.
    traitees = 0
    for path in readable:
        if check_cancelled is not None:
            check_cancelled()
        # `readable` est trié, donc les cartes d'un même dossier se suivent : on
        # peut livrer un dossier complet dès qu'on en croise un nouveau.
        folder = os.path.dirname(path)
        if batch_folder is not None and folder != batch_folder:
            flush()
        batch_folder = folder

        try:
            with Image.open(path) as img:
                thumb = np.asarray(
                    img.convert("RGB").resize(thumb_size, Image.Resampling.BOX)
                )
        except Exception as e:  # noqa: BLE001 - idem : on saute la carte.
            # ⚠️ **Porté, et non imprimé**, comme à la première passe. Un fichier
            # dont l'en-tête se lit mais dont les données sont tronquées, un
            # téléchargement interrompu, passait la première passe et
            # disparaissait ici : un `print` que personne ne lit depuis le
            # paquet, `has_warnings` faux, et une carte en moins sans un mot.
            raison = str(e).replace(path, os.path.basename(path))
            unreadable.append(f"{os.path.basename(path)} : {raison}")
            traitees += 1
            if progress is not None:
                progress(traitees, len(readable))
            continue
        card = Card(path=path, index=len(cards), thumbnail=thumb)
        card.calculate_features(strip_size, parts)
        cards.append(card)
        batch.append(card)
        traitees += 1
        if progress is not None:
            progress(traitees, len(readable))

    flush()
    return CardSet(cards=cards, full_size=full_size, thumb_size=thumb_size,
                   odd_sizes=odd_sizes, unreadable=unreadable)


def load_full_image(card: Card, size: tuple[int, int]) -> np.ndarray:
    """Relit une carte en pleine résolution, pour l'export uniquement."""
    with Image.open(card.path) as img:
        return np.asarray(img.convert("RGB").resize(size, Image.Resampling.LANCZOS))
