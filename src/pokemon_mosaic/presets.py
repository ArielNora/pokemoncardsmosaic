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
    ordered: bool = True
    name: str = ""

    def to_dict(self) -> dict:
        return {"cards": list(self.cards), "ordered": self.ordered,
                "name": self.name}

    @classmethod
    def from_dict(cls, payload) -> "LinkRef":
        return cls(cards=tuple(payload["cards"]),
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
        return cls(
            name=payload["name"],
            excluded=tuple(payload.get("excluded", ())),
            active_links=tuple(LinkRef.from_dict(link)
                               for link in payload.get("active_links", ())),
            layout=payload.get("layout", {}),
            algorithm=payload.get("algorithm", {}),
        )


def safe_filename(name: str) -> str:
    """Nom de fichier tiré du nom donné par l'utilisateur.

    Deux noms différents ne doivent jamais donner le même fichier, sous peine
    d'écraser un préréglage en croyant en créer un autre : les caractères
    interdits sont remplacés par leur code, pas simplement effacés.
    """
    cleaned = _UNSAFE.sub(lambda m: f"_{ord(m.group()):x}", name).strip()
    if not cleaned or cleaned in (".", ".."):
        raise ValueError(f"Nom de préréglage inutilisable : {name!r}")
    return cleaned + EXTENSION


def save_preset(directory: str, preset: Preset) -> str:
    """Écrit le préréglage et renvoie le chemin du fichier."""
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, safe_filename(preset.name))
    # Écriture puis remplacement : une interruption laisse l'ancien préréglage
    # intact au lieu d'un fichier tronqué qui ne se rechargerait plus.
    temporary = path + ".tmp"
    with open(temporary, "w", encoding="utf-8") as handle:
        handle.write(preset.to_json())
    os.replace(temporary, path)
    return path


def load_preset(directory: str, name: str) -> Preset:
    path = os.path.join(directory, safe_filename(name))
    with open(path, encoding="utf-8") as handle:
        return Preset.from_json(handle.read())


def delete_preset(directory: str, name: str) -> None:
    os.remove(os.path.join(directory, safe_filename(name)))


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
