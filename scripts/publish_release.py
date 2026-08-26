#!/usr/bin/env python
"""Publie le miroir des illustrations en *release* GitHub, une archive par extension.

Le dépôt ne versionne aucune image : `cards.json` dit où les prendre, et
`fetch_cards.py` les récupère. Ce miroir vient s'ajouter pour deux raisons :

- **douze cartes ne sont reproductibles par aucune source distante** — toute
  l'extension A2a plus `PROMO-A-046`, déposées à la main dans `data/local/` ;
- les octets d'un miroir sont **identiques pour tout le monde**, là où un
  réencodage local dépend de la version de libwebp installée.

    uv run python scripts/publish_release.py --dry-run   # prépare, ne publie pas
    uv run python scripts/publish_release.py

⚠️ **Point de droit, rappelé.** Héberger ces illustrations est une rediffusion
d'œuvres protégées, contrairement au montage « chacun télécharge à la source ».
Voir `docs/SOURCES_SOURCE_FORUM.md`.

⚠️ **Ne jamais lancer `gh auth setup-git`**, et répondre *non* à « Authenticate
Git with your GitHub credentials? ». Le compte `gh` actif est unique et global :
l'y laisser gouverner les push romprait l'isolement entre le compte personnel et
le compte professionnel, que le dépôt maintient par un verrou local.
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import zipfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from pokemon_mosaic.artwork import MANIFEST_VERSION

DEFAULT_MANIFEST = "cards.json"
DEFAULT_IMAGES = os.path.join("data", "pokemoncards")
# Un dépôt **dédié**, public, sans code ni historique : le miroir y est seul.
# Le risque est ainsi cantonné — un signalement viserait ce dépôt-là, qui ne
# contient que ce qui est litigieux et se reconstruit en trente secondes depuis
# `data/pokemoncards/`. Le dépôt de code n'est pas atteint.
DEFAULT_REPO = "ArielNora/pokemoncardsmosaic-images"
# Le nom de la balise porte la version du manifeste : un changement de format
# des entrées doit produire un miroir distinct, sinon un ancien client
# téléchargerait des archives qu'il ne sait plus décrire.
TAG = f"cards-v{MANIFEST_VERSION}"


def digest_of(path: str) -> str:
    sha = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            sha.update(block)
    return sha.hexdigest()


def build_archives(manifest: dict, images: str, out: str) -> dict:
    """Une archive par extension. Renvoie la description à inscrire au manifeste.

    Le découpage par extension n'est pas cosmétique : il permet de ne
    retélécharger qu'une extension quand une seule a changé, et garde chaque
    fichier sous quelques mégaoctets.
    """
    os.makedirs(out, exist_ok=True)
    par_jeu: dict[str, list[dict]] = {}
    for card in manifest["cards"]:
        par_jeu.setdefault(card["set"], []).append(card)

    mirror = {}
    for jeu, cartes in sorted(par_jeu.items()):
        dossier = os.path.dirname(cartes[0]["path"])
        archive = os.path.join(out, f"{dossier}.zip")
        # `ZIP_STORED` et non `ZIP_DEFLATED` : le WebP est déjà compressé, et le
        # dégonfler à nouveau coûte du temps pour gagner moins de 1 %.
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_STORED) as zf:
            for card in cartes:
                source = os.path.join(images, *card["path"].split("/"))
                if not os.path.exists(source):
                    raise SystemExit(
                        f"Image absente : {card['path']}. Lancez "
                        f"`fetch_cards.py` avant de publier."
                    )
                if digest_of(source) != card["sha256"]:
                    raise SystemExit(
                        f"{card['path']} ne correspond pas au manifeste : le "
                        f"miroir doit publier exactement ce que `cards.json` "
                        f"décrit, sinon la vérification échouera chez tout le "
                        f"monde."
                    )
                zf.write(source, card["path"])
        mirror[jeu] = {
            "archive": os.path.basename(archive),
            "sha256": digest_of(archive),
            "bytes": os.path.getsize(archive),
            "cards": len(cartes),
        }
    return mirror


def release_notes(manifest: dict, mirror: dict) -> str:
    total = sum(entry["bytes"] for entry in mirror.values())
    cartes = sum(entry["cards"] for entry in mirror.values())
    lignes = [
        (f"Miroir des {cartes} illustrations décrites par `cards.json` "
         f"(version {manifest['version']}), une archive par extension."),
        "",
        ("Un `git clone` ne les rapporte pas : les fichiers d'une *release* ne "
         "sont pas dans git. `scripts/fetch_cards.py` s'en charge, vérifie "
         "l'empreinte de chaque archive puis de chaque image, et range le tout."),
        "",
        "```bash",
        "uv run python scripts/fetch_cards.py",
        "```",
        "",
        (f"Illustrations seules, sans bordure ni texte, 734x1024, WebP qualité "
         f"80, {total / 1e6:.1f} Mo au total."),
        "",
        "| Extension | Cartes | Poids |",
        "|---|---|---|",
    ]
    for jeu, entry in sorted(mirror.items()):
        lignes.append(f"| {jeu} | {entry['cards']} | {entry['bytes'] / 1e6:.1f} Mo |")
    return "\n".join(lignes) + "\n"


def gh_available() -> str | None:
    """Message expliquant pourquoi `gh` ne peut pas publier, ou None si tout va."""
    from shutil import which
    if which("gh") is None:
        return "`gh` n'est pas installé."
    result = subprocess.run(["gh", "auth", "status"], capture_output=True,
                            text=True, check=False)
    if result.returncode != 0:
        return ("`gh` n'est connecté à aucun compte. Lancez `gh auth login` "
                "vous-même, et répondez **non** à « Authenticate Git with your "
                "GitHub credentials? » — voir l'avertissement en tête de ce "
                "fichier.")
    return None


def publish(repo: str, out: str, mirror: dict, notes: str) -> int:
    archives = [os.path.join(out, entry["archive"]) for entry in mirror.values()]
    notes_path = os.path.join(out, "notes.md")
    with open(notes_path, "w", encoding="utf-8") as handle:
        handle.write(notes)

    existe = subprocess.run(["gh", "release", "view", TAG, "--repo", repo],
                            capture_output=True, text=True,
                            check=False).returncode == 0
    if existe:
        commande = ["gh", "release", "upload", TAG, *archives,
                    "--repo", repo, "--clobber"]
    else:
        commande = ["gh", "release", "create", TAG, *archives, "--repo", repo,
                    "--title", f"Illustrations — manifeste v{MANIFEST_VERSION}",
                    "--notes-file", notes_path]
    print("  " + " ".join(commande[:4]) + f" … ({len(archives)} archives)")
    return subprocess.run(commande, check=False).returncode


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--manifest", default=DEFAULT_MANIFEST)
    parser.add_argument("--images", default=DEFAULT_IMAGES)
    parser.add_argument("--out", default=os.path.join("data", "miroir"))
    parser.add_argument("--repo", default=DEFAULT_REPO)
    parser.add_argument("--dry-run", action="store_true",
                        help="construit les archives sans rien publier")
    args = parser.parse_args(argv)

    with open(args.manifest, encoding="utf-8") as handle:
        manifest = json.load(handle)
    if manifest.get("version") != MANIFEST_VERSION:
        raise SystemExit(f"Manifeste en version {manifest.get('version')}, "
                         f"attendu {MANIFEST_VERSION}.")

    print(f"Archives dans {args.out}/ …")
    mirror = build_archives(manifest, args.images, args.out)
    total = sum(e["bytes"] for e in mirror.values())
    print(f"  {len(mirror)} archives, {total / 1e6:.1f} Mo")

    # Le manifeste porte l'adresse du miroir : c'est lui qui rend les douze
    # cartes locales récupérables ailleurs que sur cette machine.
    manifest["mirror"] = {
        "tag": TAG,
        "repo": args.repo,
        "url": f"https://github.com/{args.repo}/releases/download/{TAG}",
        "sets": mirror,
    }
    with open(args.manifest, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=1, sort_keys=True)
        handle.write("\n")
    print(f"  {args.manifest} porte désormais l'adresse du miroir")

    if args.dry_run:
        print("\n--dry-run : rien n'a été publié.")
        return 0

    empeche = gh_available()
    if empeche:
        print(f"\nPublication impossible : {empeche}", file=sys.stderr)
        print("Les archives sont prêtes ; relancez sans --dry-run une fois "
              "connecté.", file=sys.stderr)
        return 1

    print(f"\nPublication sur {args.repo}, balise {TAG} …")
    return publish(args.repo, args.out, mirror, release_notes(manifest, mirror))


if __name__ == "__main__":
    raise SystemExit(main())
