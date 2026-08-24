"""Illustrations de cartes : sélection, sources, et mise en forme.

Le projet compose ses mosaïques à partir de l'**illustration seule** — sans
cadre ni texte —, qui est la texture que le jeu compose à l'affichage. Ce module
porte ce que `scripts/build_manifest.py` et `scripts/fetch_cards.py` partagent :
quelles cartes retenir, où trouver leur image, et comment la préparer.

Voir `docs/SOURCES_SOURCE_FORUM.md` : format attendu, mesures d'encodage, et
provenance.
"""

import io
import re
import unicodedata

# Catalogue des cartes : quelles cartes existent, leur rareté et leurs noms.
CATALOGUE = ("[adresse retirée]"
             "pokemon-tcg-pocket-database/main/dist")

# Source principale des illustrations. API publique, sans clé, plafonnée à
# 120 entrées par requête.
SOURCE_API = "[adresse retirée]"
SOURCE_PAGE = 120

# Source de complément : deux fils Discourse, un par série. Ajouter `.json` à
# l'adresse d'un fil renvoie tous ses messages en une requête.
FORUM_THREADS = (
    "[adresse retirée]",
    "[adresse retirée]",
)

# Source de dernier recours, pour les illustrations qu'aucune des deux autres ne
# publie au format natif. Elle ne se laisse pas récupérer par script — elle
# refuse toute image absente de son cache —, mais elle sert de **provenance** :
# le manifeste garde l'adresse de ce qui a été déposé à la main.
ZONE_ASSETS = "[adresse retirée]"

# Les trois raretés dont l'illustration occupe toute la carte.
RARITIES = ("AR", "SAR", "IM")

# Format commun de toutes les images produites. Sert aussi de **filtre** : le
# forum publie à côté des versions « Extended Immersive » en 1080×1885, qui
# sont une autre illustration et non un agrandissement. Refuser tout ce qui
# n'est pas à ce format écarte ces doublons sans avoir à les reconnaître.
TARGET_SIZE = (734, 1024)

# Qualité d'encodage WebP. Mesuré sur les 441 illustrations : 56,5 Mo au total
# contre 541 Mo pour les sources, et un écart médian de 0,45 niveau sur 255 sur
# la moyenne RGB d'un bord — sous l'erreur des vignettes à 25 %, déjà acceptée.
# Voir `docs/SOURCES_SOURCE_FORUM.md` §6.
QUALITY = 80

# Format de `cards.json`. Ici et non dans les scripts : c'est ce sur quoi le
# constructeur et le récupérateur doivent s'accorder, comme les sources et le
# traitement des images.
MANIFEST_VERSION = 3


def slug(text: str) -> str:
    """Fragment de nom de fichier : sans accent, sans espace, en minuscules.

    Les accents sont retirés et non conservés : macOS stocke ses noms en NFD et
    une chaîne saisie ailleurs arrive en NFC, ce qui fait échouer la comparaison
    de deux noms pourtant identiques à l'œil.
    """
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return "-".join(p for p in "".join(
        c if c.isalnum() else "-" for c in text).split("-") if p)


def match_key(text: str) -> str:
    """Clé de rapprochement d'un nom de carte entre deux sources.

    Plus agressive que `slug` : tout ce qui n'est ni lettre ni chiffre saute,
    ce qui réconcilie « Ho-Oh ex » et « Ho-oh ex », ou « Farfetch'd » et
    « Farfetchd ».
    """
    text = unicodedata.normalize("NFKD", (text or "").lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "", text)


def asset_url(asset: str) -> str:
    """Adresse le serveur d'origine d'une illustration, déduite de son nom d'asset.

    `cPK_20_017890_01_ARMORGAex_SAR` donne quatre choses : le **type** de carte
    (`cPK` -> `PK`), l'extension (20), le numéro (017890), et par les trois
    premiers chiffres de celui-ci le dossier de regroupement (017000).

    ⚠️ Le type ne se devine pas : les cartes Dresseur portent `cTR` et vivent
    sous `Face/TR/`, pas `Face/PK/`. Coder `PK` en dur rendait Guzma, Lilie et
    Pepper **introuvables par construction**, sans que rien ne distingue cet
    échec du défaut de cache qui frappe par ailleurs.

    Ne sert plus à récupérer quoi que ce soit — le serveur refuse les images
    hors cache — mais à inscrire au manifeste d'où vient un fichier déposé à la
    main dans `data/local/`.

    Rend `""` si le nom ne suit pas la règle, plutôt que de lever : cette
    adresse n'est qu'une note de provenance, et le catalogue dont vient le nom
    est une source tierce. Une exception ici remonterait d'un fil d'exécution
    et ferait tomber toute la construction pour une simple annotation.
    """
    name = asset.removesuffix(".webp")
    parts = name.split("_")
    if len(parts) < 3 or len(parts[2]) < 3:
        return ""
    kind = parts[0].removeprefix("c")
    return (f"{ZONE_ASSETS}/{kind}/{parts[1]}/{parts[2][:3]}000/{name}"
            f"/L/Textures/{name}_L_ILL.webp")


def process(raw: bytes, crop: dict | None = None) -> bytes:
    """Rogne si nécessaire, ramène au format commun, encode en WebP.

    Contrairement à la version précédente, **les octets d'origine ne sont jamais
    conservés tels quels** : la source est désormais un PNG sans perte de plus
    d'un mégaoctet par carte, qu'il faut réencoder. L'ancien raccourci existait
    parce que la source était déjà un WebP avec perte, qu'il aurait été absurde
    de redécoder pour le recompresser.

    Le rognage est déclaré en pixels par bord, jamais deviné : un seuil
    automatique se trompe sur les illustrations naturellement claires, où rogner
    davantage rend le bord **plus** pâle et non moins. Mesuré sur Taupiqueur, où
    la luminosité des bords remonte au-delà de 5 % de rognage.

    ⚠️ **Les pixels du rognage sont ceux de `TARGET_SIZE`**, taille à laquelle
    ils ont été mesurés. L'image est donc ramenée à ce format **avant** d'être
    rognée, et non après : une partie du catalogue est publiée en 717×1000, et
    y retirer 30 px du haut tomberait 2,4 % à côté sans que rien ne le signale.
    Sur une source déjà au format — le cas courant — cette mise à l'échelle ne
    fait rien.
    """
    from PIL import Image

    image = Image.open(io.BytesIO(raw))
    image.load()
    if image.mode != "RGB":
        image = image.convert("RGB")
    if crop and image.size != TARGET_SIZE:
        image = image.resize(TARGET_SIZE, Image.LANCZOS)
    if crop:
        width, height = image.size
        # Les valeurs sont écrites à la main dans `crops.json` : une erreur de
        # saisie est un risque réel, pas théorique. Sans ce contrôle, Pillow
        # remonte « Coordinate 'lower' is less than 'upper' », qui ne nomme ni
        # la carte, ni le bord, ni la valeur fautive.
        for bord, limite in (("left", width), ("right", width),
                             ("top", height), ("bottom", height)):
            valeur = crop.get(bord, 0)
            if valeur < 0 or valeur >= limite:
                raise ValueError(
                    f"Rognage {bord}={valeur} px impossible sur une image "
                    f"de {limite} px"
                )
        if crop.get("left", 0) + crop.get("right", 0) >= width:
            raise ValueError(
                f"Rognage left+right = {crop.get('left', 0) + crop.get('right', 0)} px "
                f"ne laisse rien d'une image de {width} px"
            )
        if crop.get("top", 0) + crop.get("bottom", 0) >= height:
            raise ValueError(
                f"Rognage top+bottom = {crop.get('top', 0) + crop.get('bottom', 0)} px "
                f"ne laisse rien d'une image de {height} px"
            )
        image = image.crop((crop.get("left", 0), crop.get("top", 0),
                            width - crop.get("right", 0),
                            height - crop.get("bottom", 0)))
    if image.size != TARGET_SIZE:
        image = image.resize(TARGET_SIZE, Image.LANCZOS)
    buffer = io.BytesIO()
    image.save(buffer, format="WEBP", quality=QUALITY)
    return buffer.getvalue()
