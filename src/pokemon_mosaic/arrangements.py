"""Agencements gardés : un résultat de calcul, enregistré et partageable.

Un agencement dit **quelles cartes** composent la mosaïque et **où** chacune se
pose, plus l'habillage réglé pour l'imprimer. C'est le résultat lui-même, non la
recette : le rejouer ne demande ni de refaire le calcul, ni d'avoir la même
machine, ni de retrouver le même hasard. C'est ce qui a remplacé l'idée d'une
graine, qui exigeait tout cela à la fois.

⚠️ **Les cartes sont désignées par chemin, jamais par indice.** Elles sont
numérotées par leur position dans le dossier trié : l'arrivée d'une extension
décale tout ce qui la suit alphabétiquement, et un agencement indexé montrerait
alors d'autres cartes sans que rien ne le signale. C'est la même règle que pour
les préréglages, et pour la même raison.

Le fichier liste les cartes **une fois**, et la grille les référence par leur
rang dans cette liste : 441 cartes en 21×21 tiennent ainsi en 25 Ko au lieu de
la centaine que coûterait un chemin par case.

Le format est du JSON : lisible, modifiable à la main, comparable dans git.
"""

import contextlib
import json
import os
from dataclasses import dataclass, field
from datetime import datetime

from .presets import EXTENSION, safe_filename
from .scoring import EMPTY

FORMAT_VERSION = 1


@dataclass(frozen=True)
class Arrangement:
    """Une mosaïque trouvée, et de quoi la réimprimer telle quelle."""

    name: str
    # Chemins relatifs au dossier de cartes, dans l'ordre où la grille les
    # numérote. C'est **la liste des cartes utilisées**, celle que le menu
    # affiche et confronte au catalogue de qui ouvre le fichier.
    cards: tuple[str, ...] = ()
    # Une ligne par rangée, un rang de `cards` par case, `-1` pour une case
    # vide. Le nombre de colonnes et de lignes s'en déduit : le noter à part
    # ferait deux vérités à tenir d'accord.
    grid: tuple[tuple[int, ...], ...] = ()
    # L'habillage : papier, feuilles, tailles, couleurs, finesse. Celui qui
    # ouvre voit le poster tel qu'il a été réglé, et reste libre de tout
    # changer à l'étape d'export.
    presentation: dict = field(default_factory=dict)
    score: float = 0.0
    saved_at: str = ""

    @property
    def shape(self) -> tuple[int, int]:
        """(colonnes, lignes), la convention de tout le projet."""
        if not self.grid:
            return (0, 0)
        return (len(self.grid[0]), len(self.grid))

    def to_json(self) -> str:
        return json.dumps({
            "version": FORMAT_VERSION,
            "name": self.name,
            "saved_at": self.saved_at,
            "score": self.score,
            "cards": list(self.cards),
            "grid": [list(row) for row in self.grid],
            "presentation": self.presentation,
        }, ensure_ascii=False, indent=2, sort_keys=True)

    @classmethod
    def from_json(cls, text: str) -> "Arrangement":
        payload = json.loads(text)
        version = payload.get("version")
        if version != FORMAT_VERSION:
            raise ValueError(
                f"Agencement en version {version}, attendu {FORMAT_VERSION}."
            )
        # Le fichier est présenté comme modifiable à la main : une ligne retirée
        # par mégarde doit nommer ce qui manque, et non remonter un `KeyError`
        # nu qui ne dit ni le champ ni le fichier.
        try:
            grille = tuple(tuple(int(case) for case in ligne)
                           for ligne in payload["grid"])
            cartes = tuple(payload["cards"])
        except KeyError as manquant:
            raise ValueError(
                f"Agencement incomplet : champ {manquant} manquant."
            ) from manquant
        except (TypeError, ValueError) as erreur:
            raise ValueError(f"Agencement mal formé : {erreur}") from erreur

        largeurs = {len(ligne) for ligne in grille}
        if len(largeurs) > 1:
            raise ValueError("Agencement mal formé : les rangées n'ont pas "
                             "toutes la même longueur.")
        for ligne in grille:
            for case in ligne:
                if case != EMPTY and not (0 <= case < len(cartes)):
                    raise ValueError(
                        f"Agencement mal formé : la case {case} ne désigne "
                        f"aucune des {len(cartes)} cartes listées."
                    )
        return cls(
            name=payload.get("name", ""),
            cards=cartes,
            grid=grille,
            presentation=payload.get("presentation", {}) or {},
            score=float(payload.get("score", 0.0)),
            saved_at=payload.get("saved_at", ""),
        )


def default_name(shape: tuple[int, int], score: float,
                 moment: datetime | None = None) -> str:
    """Le nom posé sans rien demander : la forme, la date, le score.

    Enregistrer reste un seul clic pendant qu'on regarde le calcul tourner ; le
    menu permet de renommer ensuite.
    """
    # L'heure locale : c'est celle que l'utilisateur lit sur sa pendule,
    # et ce nom n'est qu'un repère pour retrouver son essai.
    moment = moment or datetime.now().astimezone()
    return (f"{shape[0]} × {shape[1]}, {moment.strftime('%Y-%m-%d %H:%M')}, "
            f"score {score:.0f}")


def unique_name(directory: str, name: str) -> str:
    """Le nom demandé, suffixé s'il est déjà pris.

    Deux calculs peuvent tomber dans la même minute sur la même forme et le même
    score arrondi : sans cela, le second écraserait le premier en silence.
    """
    pris = {existant.name for existant in list_arrangements(directory)}
    if name not in pris:
        return name
    numero = 2
    while f"{name} ({numero})" in pris:
        numero += 1
    return f"{name} ({numero})"


def path_of(directory: str, name: str) -> str:
    return os.path.join(directory, safe_filename(name))


def save_arrangement(directory: str, arrangement: Arrangement) -> str:
    """Écrit l'agencement dans la bibliothèque et rend le chemin du fichier."""
    os.makedirs(directory, exist_ok=True)
    return write_arrangement(path_of(directory, arrangement.name), arrangement)


def write_arrangement(path: str, arrangement: Arrangement) -> str:
    """Écrit l'agencement à l'endroit demandé, pour la bibliothèque ou l'export.

    Écriture puis remplacement : une interruption laisse le fichier précédent
    intact au lieu d'un JSON tronqué qui ne se rechargerait plus.
    """
    temporaire = path + ".tmp"
    with open(temporaire, "w", encoding="utf-8") as fichier:
        fichier.write(arrangement.to_json())
    os.replace(temporaire, path)
    return path


def read_arrangement(path: str) -> Arrangement:
    with open(path, encoding="utf-8") as fichier:
        return Arrangement.from_json(fichier.read())


def delete_arrangement(directory: str, name: str) -> None:
    os.remove(path_of(directory, name))


def rename_arrangement(directory: str, name: str, nouveau: str) -> str:
    """Renomme un agencement, fichier compris.

    Le nom vit dans le contenu **et** donne le nom du fichier : les changer
    séparément laisserait deux vérités, et la liste, qui lit le contenu,
    montrerait un agencement introuvable par son fichier.
    """
    ancien = read_arrangement(path_of(directory, name))
    nouveau_chemin = save_arrangement(
        directory, Arrangement(
            name=nouveau, cards=ancien.cards, grid=ancien.grid,
            presentation=ancien.presentation, score=ancien.score,
            saved_at=ancien.saved_at))
    if nouveau != name:
        with contextlib.suppress(OSError):
            os.remove(path_of(directory, name))
    return nouveau_chemin


def list_arrangements(directory: str) -> list[Arrangement]:
    """Les agencements de la bibliothèque, du plus récent au plus ancien.

    Un fichier abîmé ou d'une autre version est passé : il ne doit pas rendre la
    bibliothèque entière inutilisable.
    """
    if not os.path.isdir(directory):
        return []
    trouves = []
    for entree in sorted(os.listdir(directory)):
        if not entree.endswith(EXTENSION):
            continue
        with contextlib.suppress(OSError, ValueError, json.JSONDecodeError):
            trouves.append(read_arrangement(os.path.join(directory, entree)))
    return sorted(trouves, key=lambda un: un.saved_at, reverse=True)
