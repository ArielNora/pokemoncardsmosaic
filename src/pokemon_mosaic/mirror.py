"""Récupération des illustrations depuis le miroir GitHub.

Ce module vit dans le paquet, et non dans `scripts/`, parce que **l'application
empaquetée s'en sert** : un `.app` n'embarque que `src/`. Le bouton « Télécharger
les cartes » de l'étape 1 et la ligne de commande `scripts/fetch_cards.py`
appellent exactement le même code.

Le miroir est la **seule** provenance du projet. Rien ici ne va chercher une
image ailleurs : ni site tiers, ni catalogue distant, ni adresse d'origine
inscrite au manifeste. Les illustrations entrent dans le miroir par dépôt
manuel, et en ressortent par ce module.

Le manifeste `cards.json` est publié **avec** les archives. L'application n'en
embarque donc aucune copie : elle va le chercher, et sait du même coup si des
cartes ont été ajoutées depuis la dernière fois.
"""

import hashlib
import io
import json
import os
import urllib.error
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed

from .artwork import MANIFEST_VERSION

# GitHub accepte un client sans navigateur, mais veut savoir à qui il parle.
USER_AGENT = ("Mozilla/5.0 (compatible; pokemon-mosaic/0.1; "
              "+https://github.com/ArielNora/pokemoncardsmosaic)")

# Un dépôt dédié, public, sans code ni historique. Ces deux constantes sont la
# seule chose que l'application sait d'avance : tout le reste, les 441 cartes,
# les empreintes, l'adresse des archives, vient du manifeste qu'elle télécharge.
MIRROR_REPO = "ArielNora/pokemoncardsmosaic-images"
# La balise porte la version du manifeste : un changement de format des entrées
# produit un miroir distinct, sinon un ancien client téléchargerait des archives
# qu'il ne sait plus décrire.
MIRROR_TAG = f"cards-v{MANIFEST_VERSION}"
MANIFEST_ASSET = "cards.json"


class MirrorError(Exception):
    """Le miroir n'a pas pu être joint, ou n'a pas répondu ce qu'on attendait."""


class Outcome:
    KEPT = "déjà là"
    FETCHED = "téléchargé"
    FAILED = "échec"


# Ce dont la récupération a besoin pour chaque carte. Contrôlé une fois au
# chargement plutôt qu'indexé à l'aveugle dans un fil : `cards.json` peut être
# amputé par une édition à la main ou une fusion malheureuse, et un `KeyError`
# remontant d'un fil arrête **toute** la récupération sans nommer la carte fautive.
CHAMPS_REQUIS = ("path", "bytes", "sha256")


def target_path(directory: str, relative: str) -> str:
    """Chemin local d'une carte, garanti à l'intérieur du dossier de sortie.

    Le manifeste vient du réseau. Un chemin contenant `..` écrirait ailleurs sur
    le disque : on refuse plutôt que de faire confiance.
    """
    root = os.path.abspath(directory)
    path = os.path.abspath(os.path.join(root, *relative.split("/")))
    if path != root and not path.startswith(root + os.sep):
        raise ValueError(f"Chemin hors du dossier de sortie : {relative!r}")
    return path


def digest_of(path: str) -> str:
    sha = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            sha.update(block)
    return sha.hexdigest()


def is_current(path: str, card: dict) -> bool:
    """Le fichier présent est-il bien celui qu'annonce le manifeste ?

    La taille d'abord : elle écarte l'immense majorité des cas sans lire le
    fichier. L'empreinte ensuite, seule preuve réelle.
    """
    if not os.path.exists(path):
        return False
    if os.path.getsize(path) != card["bytes"]:
        return False
    return digest_of(path) == card["sha256"]


# --- Manifeste ------------------------------------------------------------


def validate_manifest(manifest) -> dict:
    """Contrôle la forme d'un manifeste. Rend le manifeste, ou lève `ValueError`."""
    if not isinstance(manifest, dict):
        raise ValueError("Manifeste illisible : ce n'est pas un objet.")  # noqa: TRY004
    if manifest.get("version") != MANIFEST_VERSION:
        raise ValueError(f"Manifeste en version {manifest.get('version')}, "
                         f"attendu {MANIFEST_VERSION}.")
    cards = manifest.get("cards")
    if not isinstance(cards, list):
        # `ValueError` et non `TypeError` malgré la règle : c'est un fichier
        # mal formé, pas un mauvais argument, et les appelants n'attrapent que
        # `(OSError, ValueError)` : un `TypeError` ressortirait en trace nue.
        raise ValueError("Manifeste sans liste de cartes.")  # noqa: TRY004
    for position, card in enumerate(cards):
        manquants = [champ for champ in CHAMPS_REQUIS if champ not in card]
        if manquants:
            nom = card.get("id", f"en position {position}")
            raise ValueError(
                f"Carte {nom} : champ(s) manquant(s) {', '.join(manquants)}."
            )
    return manifest


def load_manifest(path: str) -> dict:
    """Lit un manifeste sur le disque."""
    with open(path, encoding="utf-8") as handle:
        return validate_manifest(json.load(handle))


def manifest_url(repo: str = MIRROR_REPO, tag: str = MIRROR_TAG) -> str:
    return f"https://github.com/{repo}/releases/download/{tag}/{MANIFEST_ASSET}"


def fetch_manifest(repo: str = MIRROR_REPO, tag: str = MIRROR_TAG,
                   timeout: float = 45) -> dict:
    """Télécharge le catalogue publié avec les archives.

    C'est ce qui permet la mise à jour : le manifeste en ligne décrit les cartes
    du jour, et la comparaison avec le disque dit ce qu'il manque.
    """
    url = manifest_url(repo, tag)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
    except urllib.error.HTTPError as error:
        if error.code == 404:
            raise MirrorError(
                f"Catalogue introuvable à {url} (HTTP 404)."
            ) from error
        raise MirrorError(f"{url} : {error}") from error
    except (OSError, TimeoutError) as error:
        raise MirrorError(f"{url} : {error}") from error
    try:
        return validate_manifest(json.loads(raw.decode("utf-8")))
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        raise MirrorError(f"Catalogue illisible : {error}") from error


# --- État local -----------------------------------------------------------


def missing_cards(manifest: dict, directory: str) -> list[dict]:
    """Cartes du manifeste absentes du dossier, ou qui n'y correspondent plus.

    Sert autant à préparer un téléchargement qu'à répondre « rien à faire » sans
    toucher au réseau.
    """
    manquantes = []
    for card in manifest["cards"]:
        try:
            path = target_path(directory, card["path"])
        except ValueError:
            continue
        if not is_current(path, card):
            manquantes.append(card)
    return manquantes


def missing_bytes(manifest: dict, cards: list[dict]) -> int:
    """Poids à télécharger pour ces cartes, en archives, pas en images.

    Une archive est indivisible : il manquerait une seule carte de l'extension A1
    que ses 4,8 Mo partiraient quand même. C'est ce chiffre-là qu'il faut
    annoncer, pas la somme des images manquantes.
    """
    sets = manifest.get("mirror", {}).get("sets", {})
    jeux = {card["set"] for card in cards if "set" in card}
    return sum(entry["bytes"] for jeu, entry in sets.items() if jeu in jeux)


# --- Téléchargement -------------------------------------------------------


def _token() -> str | None:
    """Jeton GitHub, s'il y en a un dans l'environnement."""
    return os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or None


def _assets_by_name(repo: str, tag: str, token: str) -> dict | None:
    """Table `nom d'archive -> identifiant d'asset`, via l'API.

    ⚠️ Sur un dépôt **privé**, l'adresse publique de téléchargement répond 404
    même munie du jeton : seul l'endpoint `releases/assets/{id}` sert le
    fichier, et il faut donc résoudre l'identifiant d'abord. Mesuré le
    2026-08-24 : 404 contre 200 pour 1,2 Mo sur la même archive.
    """
    url = f"https://api.github.com/repos/{repo}/releases/tags/{tag}"
    request = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    })
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            data = json.load(response)
    except (OSError, TimeoutError, ValueError):
        return None
    return {asset["name"]: asset["id"] for asset in data.get("assets", ())}


class _Cancelled(Exception):
    """Signal interne : la récupération a été interrompue à la demande."""


def fetch_mirror(manifest: dict, directory: str, workers: int = 4,
                 progress=None, cancelled=None) -> tuple[dict, list]:
    """Récupère les images depuis le miroir, une archive par extension.

    C'est la voie normale : les octets d'un miroir sont **identiques pour tout
    le monde**, là où un réencodage local dépend de la version de libwebp
    installée. C'est aussi la seule qui rende les douze cartes déposées à la
    main récupérables ailleurs que sur la machine qui les a produites.

    Seules les extensions auxquelles il manque quelque chose sont téléchargées :
    le découpage par extension existe pour ça.

    `progress(octets_faits, octets_total, extension)` est appelé après chaque
    archive : depuis un fil de travail, donc l'appelant graphique doit passer par
    un signal Qt. `cancelled()` est consulté avant chaque archive et rend vrai
    pour arrêter.
    """
    if not manifest.get("mirror"):
        raise MirrorError("Le manifeste ne décrit aucun miroir.")
    mirror = manifest["mirror"]
    par_jeu: dict[str, list[dict]] = {}
    for card in missing_cards(manifest, directory):
        par_jeu.setdefault(card["set"], []).append(card)

    tally: dict[str, int] = {}
    failures: list[tuple[str, str]] = []
    manquantes = sum(len(cartes) for cartes in par_jeu.values())
    deja = len(manifest["cards"]) - manquantes
    if deja:
        tally[Outcome.KEPT] = deja
    if not par_jeu:
        return tally, failures

    total_octets = sum(mirror["sets"][jeu]["bytes"]
                       for jeu in par_jeu if jeu in mirror["sets"])
    faits = 0

    # Un jeton, s'il y en a un, ouvre les dépôts privés, par un autre chemin.
    token = _token()
    assets = None
    if token and mirror.get("repo"):
        assets = _assets_by_name(mirror["repo"], mirror["tag"], token)

    def un_jeu(jeu: str, cartes: list[dict]) -> tuple[str, list, int]:
        if cancelled is not None and cancelled():
            raise _Cancelled
        entry = mirror["sets"].get(jeu)
        if entry is None:
            return jeu, [(f"{jeu} ({len(cartes)} cartes)",
                          "extension absente du miroir")], 0
        # Un échec d'archive vaut pour toutes ses cartes : on le dit **une
        # fois**. Quatre cent quarante et une lignes « 404 » identiques
        # noieraient la seule information utile, la cause.
        def echec(message):
            return jeu, [(f"{jeu} ({len(cartes)} cartes)", message)], 0

        if assets is not None and entry["archive"] in assets:
            url = (f"https://api.github.com/repos/{mirror['repo']}"
                   f"/releases/assets/{assets[entry['archive']]}")
            entetes = {"User-Agent": USER_AGENT,
                       "Authorization": f"Bearer {token}",
                       "Accept": "application/octet-stream"}
        else:
            url = f"{mirror['url']}/{entry['archive']}"
            entetes = {"User-Agent": USER_AGENT}
        try:
            request = urllib.request.Request(url, headers=entetes)
            with urllib.request.urlopen(request, timeout=120) as response:
                raw = response.read()
        except urllib.error.HTTPError as error:
            if error.code == 404:
                return echec(
                    f"{entry['archive']} introuvable (HTTP 404). Si le dépôt "
                    f"est privé, posez un jeton dans GH_TOKEN, l'adresse "
                    f"publique reste refusée même authentifiée."
                )
            return echec(f"{entry['archive']} : {error}")
        except (OSError, TimeoutError) as error:
            return echec(f"{entry['archive']} : {error}")
        if hashlib.sha256(raw).hexdigest() != entry["sha256"]:
            return echec(f"{entry['archive']} altérée")

        echecs, ecrites = [], 0
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            noms = set(zf.namelist())
            for card in cartes:
                if cancelled is not None and cancelled():
                    raise _Cancelled
                if card["path"] not in noms:
                    echecs.append((card["path"], "absente de l'archive"))
                    continue
                # Le chemin vient du manifeste, jamais de l'archive : une entrée
                # nommée `../../evade.webp` n'a donc aucun effet.
                contenu = zf.read(card["path"])
                if hashlib.sha256(contenu).hexdigest() != card["sha256"]:
                    echecs.append((card["path"], "empreinte différente du manifeste"))
                    continue
                destination = target_path(directory, card["path"])
                os.makedirs(os.path.dirname(destination), exist_ok=True)
                temporaire = destination + ".part"
                with open(temporaire, "wb") as handle:
                    handle.write(contenu)
                os.replace(temporaire, destination)
                ecrites += 1
        return jeu, echecs, ecrites

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(un_jeu, jeu, cartes)
                   for jeu, cartes in sorted(par_jeu.items())]
        for future in as_completed(futures):
            try:
                jeu, echecs, ecrites = future.result()
            except _Cancelled:
                continue
            tally[Outcome.FETCHED] = tally.get(Outcome.FETCHED, 0) + ecrites
            failures.extend(echecs)
            faits += mirror["sets"].get(jeu, {}).get("bytes", 0)
            if progress is not None:
                progress(faits, total_octets, jeu)
    if failures:
        tally[Outcome.FAILED] = len(failures)
    return tally, failures
