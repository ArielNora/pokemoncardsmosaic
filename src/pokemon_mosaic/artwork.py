"""Illustrations de cartes : format commun et mise en forme.

Le projet compose ses mosaïques à partir de l'**illustration seule** — sans
cadre ni texte —, qui est la texture que le jeu compose à l'affichage. Ce module
porte ce que les scripts partagent : le format attendu, l'encodage, et la
préparation d'une image avant qu'elle n'entre dans le miroir.

Les illustrations viennent d'un dossier local. Le projet ne va les chercher
nulle part : elles y sont déposées, `build_manifest.py` en dresse le catalogue,
`publish_release.py` publie le tout, et l'application ne connaît que ce miroir.
Voir `docs/IMAGES.md`.
"""

import io
import unicodedata

# Les trois raretés dont l'illustration occupe toute la carte.
RARITIES = ("AR", "SAR", "IM")

# Format commun de toutes les images du miroir. Sert aussi de **filtre** : une
# image qui n'est pas à ce format est soit une autre illustration, soit un
# agrandissement — dans les deux cas elle n'a pas sa place telle quelle.
TARGET_SIZE = (734, 1024)

# Qualité d'encodage WebP. Mesuré sur les 441 illustrations : 56,5 Mo au total
# contre 541 Mo pour les sources sans perte, et un écart médian de 0,45 niveau
# sur 255 sur la moyenne RGB d'un bord — sous l'erreur des vignettes à 25 %,
# déjà acceptée. Voir `docs/IMAGES.md`.
QUALITY = 80

# Format de `cards.json`. Ici et non dans les scripts : c'est ce sur quoi le
# constructeur, le publicateur et l'application doivent s'accorder.
#
# La version 4 a retiré des entrées tout ce qui décrivait une provenance
# distante — adresse, empreinte et poids de la source, nom d'asset. Le manifeste
# ne dit plus que ce qu'il doit dire : **quelles cartes le miroir contient**.
MANIFEST_VERSION = 4


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


def process(raw: bytes, crop: dict | None = None) -> bytes:
    """Rogne si nécessaire, ramène au format commun, encode en WebP.

    **Les octets d'origine ne sont jamais conservés tels quels** : une image
    déposée arrive dans le format qu'elle a, et le miroir n'en publie qu'un.

    Le rognage est déclaré en pixels par bord, jamais deviné : un seuil
    automatique se trompe sur les illustrations naturellement claires, où rogner
    davantage rend le bord **plus** pâle et non moins. Mesuré sur Taupiqueur, où
    la luminosité des bords remonte au-delà de 5 % de rognage.

    ⚠️ **Les pixels du rognage sont ceux de `TARGET_SIZE`**, taille à laquelle
    ils ont été mesurés. L'image est donc ramenée à ce format **avant** d'être
    rognée, et non après : sur une source en 717×1000, y retirer 30 px du haut
    tomberait 2,4 % à côté sans que rien ne le signale. Sur une source déjà au
    format — le cas courant — cette mise à l'échelle ne fait rien.
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
