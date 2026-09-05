#!/usr/bin/env python
"""Dresse `cards.json` à partir du dossier d'images, sans réseau.

    uv run python scripts/build_manifest.py
    uv run python scripts/build_manifest.py --check     # signale sans écrire

Le catalogue **décrit le miroir, il ne le remplit pas**. Les illustrations
entrent dans `data/pokemoncards/` par un dépôt manuel, chacun les obtient comme
il l'entend, et ce script se contente de dire ce qui s'y trouve : identifiant,
extension, numéro, rareté, noms, poids et empreinte.

Il **conserve les métadonnées déjà connues**. Une carte déjà décrite garde sa
rareté et ses noms, quel que soit son fichier ; seuls le poids et l'empreinte
sont recalculés. Une carte nouvelle est déduite de son chemin autant que
possible, et ce qui ne se déduit pas, rareté, noms, est signalé à remplir à la
main. Rien n'est inventé en silence.

Enchaînement d'une mise à jour :

1. déposer les nouvelles illustrations dans `data/pokemoncards/<extension>/` ;
2. `build_manifest.py` : le catalogue est mis à jour, les trous sont nommés ;
3. compléter rareté et noms dans `cards.json` ;
4. `publish_release.py` : archives et catalogue partent au miroir.
"""

import argparse
import datetime
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from pokemon_mosaic.artwork import (
    MANIFEST_VERSION,
    RARITIES,
    TARGET_SIZE,
)
from pokemon_mosaic.mirror import digest_of

DEFAULT_MANIFEST = "cards.json"
DEFAULT_IMAGES = os.path.join("data", "pokemoncards")
EXTENSION = ".webp"

# `a1-227-bulbizarre.webp` : code d'extension, numéro, puis le nom en clair, qui
# ne sert qu'à la lisibilité et n'est pas relu.
#
# ⚠️ Le code peut lui-même contenir un tiret, `promo-a-009-pikachu`, d'où
# `[a-z0-9-]+?` et non `[a-z0-9]+` : la première version rejetait les 28 cartes
# promo comme « hors convention ». Le quantificateur est **paresseux** pour que
# le premier groupe de chiffres rencontré soit pris pour le numéro.
NOM_FICHIER = re.compile(r"^([a-z0-9-]+?)-(\d+)-.+$")


def read_manifest(path: str) -> dict:
    """Catalogue existant, ou catalogue vide s'il n'y en a pas encore.

    Un manifeste d'une version antérieure est refusé plutôt que fusionné : les
    entrées n'ont pas la même forme, et les mélanger produirait un fichier que
    ni l'ancien ni le nouveau format ne décrit.
    """
    if not os.path.exists(path):
        return {"version": MANIFEST_VERSION, "cards": []}
    with open(path, encoding="utf-8") as handle:
        manifest = json.load(handle)
    if manifest.get("version") != MANIFEST_VERSION:
        raise SystemExit(f"{path} est en version {manifest.get('version')}, "
                         f"attendu {MANIFEST_VERSION}.")
    return manifest


def scan(images: str) -> list[tuple[str, str]]:
    """Images présentes, en couples (chemin relatif, chemin absolu), triés.

    Le tri porte sur le chemin relatif et non sur l'ordre de `os.walk`, qui
    dépend du système de fichiers : sans lui, deux machines produiraient deux
    `cards.json` différents pour les mêmes images.
    """
    trouvees = []
    for racine, _, fichiers in os.walk(images):
        for fichier in fichiers:
            if not fichier.endswith(EXTENSION):
                continue
            absolu = os.path.join(racine, fichier)
            relatif = os.path.relpath(absolu, images).replace(os.sep, "/")
            trouvees.append((relatif, absolu))
    return sorted(trouvees)


def derive(relative: str, dossiers: dict) -> dict:
    """Ce qu'un chemin dit d'une carte encore inconnue.

    Volontairement partiel : le nom de fichier porte l'extension et le numéro,
    jamais la rareté ni les noms officiels. Les champs manquants sont laissés
    vides pour que `trous()` les nomme, plutôt que devinés.
    """
    dossier = os.path.dirname(relative)
    fichier = os.path.basename(relative).removesuffix(EXTENSION)
    correspondance = NOM_FICHIER.match(fichier)
    if correspondance is None:
        return {}
    code, numero = correspondance.groups()
    # Le dossier fait foi sur l'extension : c'est lui que `sets` indexe, et un
    # fichier mal préfixé rangé au bon endroit reste rattachable.
    jeu = dossiers.get(dossier) or code.upper()
    # ⚠️ L'identifiant garde les chiffres **tels qu'écrits**, zéros de tête
    # compris : `A1-227` mais `PROMO-A-009`. Passer par `int()` produirait
    # `PROMO-A-9`, qui ne correspond à rien. Le nom de fichier ayant été
    # engendré depuis l'identifiant, le relire ainsi le reconstitue exactement,
    # vérifié sur les 441 cartes.
    return {
        "id": f"{jeu}-{numero}",
        "set": jeu,
        "number": int(numero),
        "rarity": "",
        "language": "fr",
        "names": {},
    }


def trous(card: dict) -> list[str]:
    """Champs qu'un dépôt manuel laisse vides et qu'il faut compléter."""
    manquants = []
    if card.get("rarity") not in RARITIES:
        manquants.append("rarity")
    if not card.get("names"):
        manquants.append("names")
    return manquants


def build(manifest: dict, images: str) -> tuple[dict, list, list]:
    """Rend (manifeste, cartes nouvelles, cartes disparues)."""
    connues = {card["path"]: card for card in manifest.get("cards", [])}
    dossiers = {dossier: jeu
                for jeu, dossier in (manifest.get("sets") or {}).items()}

    presentes = scan(images)
    cartes, nouvelles = [], []
    for relatif, absolu in presentes:
        card = dict(connues.get(relatif) or derive(relatif, dossiers))
        if not card:
            nouvelles.append((relatif, "nom de fichier hors convention"))
            continue
        if relatif not in connues:
            nouvelles.append((relatif, ", ".join(trous(card)) or "complète"))
        card["path"] = relatif
        card["bytes"] = os.path.getsize(absolu)
        card["sha256"] = digest_of(absolu)
        cartes.append(card)

    disparues = sorted(set(connues) - {relatif for relatif, _ in presentes})

    # Le tri final est celui du chemin, comme le balayage : le fichier produit
    # ne doit pas dépendre de l'ordre dans lequel les cartes ont été ajoutées.
    cartes.sort(key=lambda card: card["path"])
    jeux = {card["set"]: os.path.dirname(card["path"])
            for card in cartes if card.get("set")}

    # Le bloc `mirror` est écrit par `publish_release.py`, pas ici : il décrit
    # des archives qui n'existent pas encore. Le conserver tel quel le laisse
    # valable tant que les images n'ont pas changé, et `publish_release.py` le
    # remplace dès qu'elles changent.
    produit = dict(manifest)
    produit.update({
        "version": MANIFEST_VERSION,
        "generated_at": datetime.datetime.now(datetime.UTC)
                                .strftime("%Y-%m-%dT%H:%M:%SZ"),
        "target_size": list(TARGET_SIZE),
        "rarities": list(RARITIES),
        "sets": dict(sorted(jeux.items())),
        "cards": cartes,
    })
    return produit, nouvelles, disparues


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--manifest", default=DEFAULT_MANIFEST)
    parser.add_argument("--images", default=DEFAULT_IMAGES)
    parser.add_argument("--check", action="store_true",
                        help="dit ce qui changerait, sans écrire")
    args = parser.parse_args(argv)

    if not os.path.isdir(args.images):
        print(f"Dossier d'images introuvable : {args.images}", file=sys.stderr)
        return 1

    manifest = read_manifest(args.manifest)
    ancien = len(manifest.get("cards", []))
    produit, nouvelles, disparues = build(manifest, args.images)

    print(f"{len(produit['cards'])} cartes dans {args.images}/ "
          f"({ancien} au catalogue précédent)")
    for relatif, raison in nouvelles:
        print(f"  + {relatif} : à compléter : {raison}")
    for relatif in disparues:
        print(f"  - {relatif} : décrite au catalogue, absente du dossier")

    incompletes = [card for card in produit["cards"] if trous(card)]
    if incompletes:
        print(f"\n⚠️ {len(incompletes)} carte(s) sans rareté ni noms. Complétez "
              f"{args.manifest} avant de publier : l'interface les affichera "
              f"sans nom.", file=sys.stderr)

    if args.check:
        print("\n--check : rien n'a été écrit.")
        return 1 if incompletes or disparues else 0

    with open(args.manifest, "w", encoding="utf-8") as handle:
        json.dump(produit, handle, ensure_ascii=False, indent=1, sort_keys=True)
        handle.write("\n")
    print(f"\n{args.manifest} écrit.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
