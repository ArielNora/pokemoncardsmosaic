#!/usr/bin/env python
"""Récupère les illustrations depuis le miroir.

    uv run python scripts/fetch_cards.py
    uv run python scripts/fetch_cards.py --check       # vérifie sans rien écrire
    uv run python scripts/fetch_cards.py --online      # catalogue pris en ligne

Le miroir est la seule provenance : le projet ne va chercher aucune image sur un
site tiers. Relancer la commande ne récupère que ce qui manque ou ne correspond
plus à son empreinte, l'opération est donc reprenable.

C'est le même code que le bouton « Télécharger les cartes » de l'application —
`src/pokemon_mosaic/mirror.py`. Ce script n'existe que pour s'en servir sans
ouvrir la fenêtre.
"""

import argparse
import os
import sys
import time

# Le paquet porte la récupération ; ce fichier n'en est que l'habillage.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from pokemon_mosaic.mirror import (
    MirrorError,
    Outcome,
    fetch_manifest,
    fetch_mirror,
    is_current,
    load_manifest,
    missing_bytes,
    missing_cards,
    target_path,
)

DEFAULT_MANIFEST = "cards.json"
DEFAULT_OUTPUT = os.path.join("data", "pokemoncards")


def check(manifest: dict, directory: str) -> int:
    missing, damaged, ok = [], [], 0
    for card in manifest["cards"]:
        try:
            path = target_path(directory, card["path"])
        except ValueError:
            damaged.append(card["path"])
            continue
        if not os.path.exists(path):
            missing.append(card["path"])
        elif not is_current(path, card):
            damaged.append(card["path"])
        else:
            ok += 1
    print(f"{ok} conformes, {len(missing)} manquantes, {len(damaged)} à refaire")
    for label, items in (("manquantes", missing), ("à refaire", damaged)):
        for item in items[:10]:
            print(f"  {label} : {item}")
        if len(items) > 10:
            print(f"  … et {len(items) - 10} autres {label}")
    return 0 if not missing and not damaged else 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--manifest", default=DEFAULT_MANIFEST)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--workers", type=int, default=4,
                        help="archives téléchargées simultanément")
    parser.add_argument("--check", action="store_true",
                        help="vérifie ce qui est présent, sans rien télécharger")
    parser.add_argument("--online", action="store_true",
                        help="prend le catalogue publié plutôt que le fichier "
                             "local : c'est ainsi qu'on voit les cartes ajoutées")
    args = parser.parse_args(argv)

    try:
        manifest = (fetch_manifest() if args.online
                    else load_manifest(args.manifest))
    except (OSError, ValueError, MirrorError) as error:
        print(f"Catalogue illisible : {error}", file=sys.stderr)
        return 1

    cards = manifest["cards"]
    print(f"{len(cards)} cartes ({sum(c['bytes'] for c in cards) / 1e6:.1f} Mo) "
          f"— catalogue du {manifest.get('generated_at', '?')}")

    if args.check:
        return check(manifest, args.output)

    manquantes = missing_cards(manifest, args.output)
    if not manquantes:
        print(f"Rien à faire : les {len(cards)} cartes sont déjà dans "
              f"{args.output}/")
        return 0
    poids = missing_bytes(manifest, manquantes)
    print(f"{len(manquantes)} carte(s) à récupérer, {poids / 1e6:.1f} Mo "
          f"d'archives …")

    started = time.time()

    def avancement(faits, total, jeu):
        part = 100 * faits / total if total else 100
        print(f"  {part:3.0f} % — {jeu}", flush=True)

    try:
        tally, failures = fetch_mirror(manifest, args.output, args.workers,
                                       progress=avancement)
    except MirrorError as error:
        print(f"Miroir injoignable : {error}", file=sys.stderr)
        return 1

    elapsed = time.time() - started
    print(f"\nTerminé en {elapsed:.0f} s : "
          + ", ".join(f"{n} {label}" for label, n in sorted(tally.items())))
    if failures:
        print(f"\n{len(failures)} échec(s) :", file=sys.stderr)
        for path, message in failures[:15]:
            print(f"  {path} — {message}", file=sys.stderr)
        print("Relancer la commande reprendra où elle s'est arrêtée.",
              file=sys.stderr)
        return 1
    print(f"Images dans {args.output}/")
    return 0 if tally.get(Outcome.FAILED, 0) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
