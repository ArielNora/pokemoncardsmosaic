"""Préréglages nommés : une configuration complète, enregistrée et rechargeable.

Un préréglage couvre la sélection de cartes, les liens **actifs**, la grille et les
réglages d'algorithme. Il ne contient pas la bibliothèque de liens : un lien est un
travail durable, un préréglage un essai de mise en page. Voir SPEC.md §3.

⚠️ **Tout est désigné par chemin, jamais par indice.** Les cartes sont numérotées par
leur position dans le dossier, trié : l'arrivée d'une extension décale tout ce qui la
suit alphabétiquement. Un préréglage indexé deviendrait alors silencieusement faux —
il retiendrait d'autres cartes que celles choisies, et les liens colleraient des
paires que personne n'a formées. Or c'est précisément après une nouvelle extension
qu'on veut retrouver sa configuration.

Le format est du JSON : lisible, modifiable à la main, comparable dans git.
"""

import contextlib
import json
import os
import re
from dataclasses import asdict, dataclass, field

FORMAT_VERSION = 1
EXTENSION = ".json"

# Ce qui reste d'un nom une fois retirés les caractères qu'un système de fichiers
# refuse ou interprète. On garde les accents : le projet est francophone.
_UNSAFE = re.compile(r"[^\w \-.()\[\]']", re.UNICODE)


@dataclass(frozen=True)
class LinkRef:
    """Un lien actif, désigné par les chemins de ses cartes."""

    cards: tuple[str, ...]
    shape: tuple[int, int] = ()
    ordered: bool = True
    name: str = ""

    def to_dict(self) -> dict:
        return {"cards": list(self.cards), "shape": list(self.shape),
                "ordered": self.ordered, "name": self.name}

    @classmethod
    def from_dict(cls, payload) -> "LinkRef":
        # Forme absente : le préréglage précède les rectangles, et tout lien y
        # tenait sur une seule rangée. `Link` en déduit alors (n, 1), ce qui
        # reproduit exactement l'ancien comportement.
        shape = tuple(payload.get("shape") or ())
        return cls(cards=tuple(payload["cards"]), shape=shape,
                   ordered=bool(payload.get("ordered", True)),
                   name=payload.get("name", ""))


@dataclass(frozen=True)
class Preset:
    """Une configuration complète, désignée par chemins relatifs au dossier de cartes."""

    name: str
    # Cartes **retirées**, et non retenues : ainsi les cartes d'une extension
    # arrivée après coup sont incluses d'office, ce qu'on veut presque toujours.
    excluded: tuple[str, ...] = ()
    # Liens actifs. Chacun porte la suite ordonnée des chemins de ses cartes, plus
    # de quoi le **recréer à l'identique** s'il a disparu de la bibliothèque : sans
    # `ordered`, un lien à ordre libre reviendrait imposé, ce qui change la
    # contrainte donnée à l'optimiseur sans le dire. Le préréglage ne possède pas
    # les liens pour autant — il ne fait que décrire ceux qu'il active.
    active_links: tuple["LinkRef", ...] = ()
    layout: dict = field(default_factory=dict)
    algorithm: dict = field(default_factory=dict)

    def to_json(self) -> str:
        payload = asdict(self)
        payload["version"] = FORMAT_VERSION
        payload["excluded"] = list(self.excluded)
        payload["active_links"] = [link.to_dict() for link in self.active_links]
        return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)

    @classmethod
    def from_json(cls, text: str) -> "Preset":
        payload = json.loads(text)
        version = payload.get("version")
        if version != FORMAT_VERSION:
            raise ValueError(
                f"Préréglage en version {version}, attendu {FORMAT_VERSION}."
            )
        # L'en-tête de ce module présente le JSON comme modifiable à la main.
        # Une ligne retirée par mégarde doit donc dire ce qui manque, et non
        # remonter un `KeyError` nu qui ne nomme ni le champ ni le fichier.
        try:
            return cls(
                name=payload["name"],
                excluded=tuple(payload.get("excluded", ())),
                active_links=tuple(LinkRef.from_dict(link)
                                   for link in payload.get("active_links", ())),
                layout=payload.get("layout", {}),
                algorithm=payload.get("algorithm", {}),
            )
        except KeyError as manquant:
            raise ValueError(
                f"Préréglage incomplet : champ {manquant} manquant."
            ) from manquant
        except TypeError as erreur:
            raise ValueError(f"Préréglage mal formé : {erreur}") from erreur


def _encode(caractere: str) -> str:
    """Un caractère interdit, codé de façon **auto-délimitée**.

    Le terminateur n'est pas décoratif : `ord()` en hexadécimal fait de un à six
    chiffres, et sans borne `_5` suivi d'un « f » littéral se confondrait avec
    `_5f`, le code de `_` lui-même.
    """
    return f"_{ord(caractere):x}_"


def safe_filename(name: str) -> str:
    """Nom de fichier tiré du nom donné par l'utilisateur.

    Deux noms différents ne doivent jamais donner le même fichier, sous peine
    d'écraser un préréglage en croyant en créer un autre : les caractères
    interdits sont remplacés par leur code, pas simplement effacés.

    Trois pièges, tous rencontrés :

    - **Le caractère d'échappement doit être échappé lui-même.** `_` étant
      autorisé, `a/b` et `a_2fb` donnaient le même fichier.
    - **Les espaces de bord se codent, ils ne se rognent pas.** Un `.strip()`
      final faisait de « Essai 1 » et « Essai 1 » le même fichier : le second
      enregistrement écrasait le premier, sans confirmation ni trace.
    - **Le code doit être auto-délimité**, sa longueur variant de un à six
      chiffres.
    """
    # Refusé avant tout codage : un nom vide, ou fait des seuls caractères que
    # le système réserve, reste inutilisable une fois codé — et le coder en
    # ferait un fichier d'apparence valide portant un nom que personne ne peut
    # relire. Aucune collision n'en découle : ces noms n'ont pas de fichier.
    if not name.strip() or name.strip() in (".", ".."):
        raise ValueError(f"Nom de préréglage inutilisable : {name!r}")

    escaped = _UNSAFE.sub(lambda m: _encode(m.group()), name.replace("_", _encode("_")))
    # Beaucoup de systèmes de fichiers rognent eux-mêmes les espaces de bord :
    # les laisser tels quels reviendrait à ne rien avoir corrigé.
    noyau = escaped.strip(" ")
    tete = len(escaped) - len(escaped.lstrip(" "))
    queue = (len(escaped) - len(escaped.rstrip(" "))) if noyau else 0
    cleaned = _encode(" ") * tete + noyau + _encode(" ") * queue
    if not cleaned or cleaned in (".", ".."):
        raise ValueError(f"Nom de préréglage inutilisable : {name!r}")
    return cleaned + EXTENSION


def _legacy_filename(name: str) -> str:
    """L'ancien nom de fichier, non injectif, gardé pour relire l'existant.

    Les préréglages enregistrés avant le 2026-08-24 portent ce nom-là. Sans ce
    recours, tout préréglage dont le nom contient un `_` deviendrait
    introuvable : `list_presets` lit le nom dans le **contenu** du fichier, et
    le nom de fichier recalculé ne correspondrait plus.
    """
    return _UNSAFE.sub(lambda m: f"_{ord(m.group()):x}", name).strip() + EXTENSION


def _existing_path(directory: str, name: str) -> str:
    """Chemin du préréglage : le nom courant, ou l'ancien s'il existe encore."""
    path = os.path.join(directory, safe_filename(name))
    if os.path.exists(path):
        return path
    ancien = os.path.join(directory, _legacy_filename(name))
    return ancien if os.path.exists(ancien) else path


def save_preset(directory: str, preset: Preset) -> str:
    """Écrit le préréglage et renvoie le chemin du fichier.

    Un fichier portant l'ancien nom est retiré au passage : `load_preset` sait
    encore le lire, mais le laisser en place ferait apparaître le préréglage
    **deux fois** dans la liste — celle-ci lisant le nom dans le contenu — dont
    une fois avec la configuration d'avant. La migration se fait donc au premier
    enregistrement.
    """
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, safe_filename(preset.name))
    ancien = os.path.join(directory, _legacy_filename(preset.name))
    # ⚠️ L'ancien nom n'est **pas injectif** — c'est précisément ce qui a motivé
    # le changement. Effacer sur la seule foi du nom de fichier détruirait le
    # préréglage du voisin : « Essai 1 » et « Essai 1 » se ramenaient au même
    # fichier. On ne retire donc que si le contenu porte bien ce nom-là.
    if ancien != path and os.path.exists(ancien):
        with contextlib.suppress(OSError, ValueError, json.JSONDecodeError), \
                open(ancien, encoding="utf-8") as handle:
            if Preset.from_json(handle.read()).name == preset.name:
                os.remove(ancien)
    # Écriture puis remplacement : une interruption laisse l'ancien préréglage
    # intact au lieu d'un fichier tronqué qui ne se rechargerait plus.
    temporary = path + ".tmp"
    with open(temporary, "w", encoding="utf-8") as handle:
        handle.write(preset.to_json())
    os.replace(temporary, path)
    return path


def load_preset(directory: str, name: str) -> Preset:
    path = _existing_path(directory, name)
    with open(path, encoding="utf-8") as handle:
        return Preset.from_json(handle.read())


def delete_preset(directory: str, name: str) -> None:
    os.remove(_existing_path(directory, name))


def list_presets(directory: str) -> list[str]:
    """Noms des préréglages enregistrés, triés, illisibles exclus.

    Le nom vient du contenu du fichier et non de son nom : ils diffèrent dès que
    le nom donné contient un caractère qu'un système de fichiers refuse.
    """
    if not os.path.isdir(directory):
        return []
    names = []
    for entry in sorted(os.listdir(directory)):
        if not entry.endswith(EXTENSION):
            continue
        try:
            with open(os.path.join(directory, entry), encoding="utf-8") as handle:
                names.append(Preset.from_json(handle.read()).name)
        except (OSError, ValueError, KeyError, json.JSONDecodeError):
            # Un fichier abîmé ou d'une autre version ne doit pas rendre la liste
            # entière inutilisable.
            continue
    return sorted(names)
