#!/usr/bin/env python
"""Publie le miroir des illustrations en *release* GitHub.

Une archive par extension, plus `cards.json`. Le dépôt ne versionne aucune
image : le miroir est le seul endroit d'où le projet les sert, et le catalogue
est publié **avec** les archives pour que l'application n'ait pas à en embarquer
une copie : elle le télécharge, et sait du même coup ce qui a été ajouté.

    uv run python scripts/publish_release.py --dry-run   # prépare, ne publie pas
    uv run python scripts/publish_release.py

Les octets d'un miroir sont **identiques pour tout le monde**, là où un
réencodage local dépend de la version de libwebp installée.

⚠️ **Point de droit, rappelé.** Héberger ces illustrations est une rediffusion
d'œuvres protégées. Voir `docs/IMAGES.md`.

⚠️ **Ne jamais lancer `gh auth setup-git`**, et répondre *non* à « Authenticate
Git with your GitHub credentials? ». Le compte `gh` actif est unique et global :
l'y laisser gouverner les push romprait l'isolement entre le compte personnel et
le compte professionnel, que le dépôt maintient par un verrou local.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import zipfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from pokemon_mosaic.artwork import MANIFEST_VERSION
from pokemon_mosaic.mirror import MANIFEST_ASSET, MIRROR_REPO, MIRROR_TAG, digest_of

DEFAULT_MANIFEST = "cards.json"
DEFAULT_IMAGES = os.path.join("data", "pokemoncards")
# Dépôt et balise viennent du paquet : c'est ce que l'application connaît, et
# publier ailleurs la laisserait sans miroir. Le dépôt est **dédié**, public,
# sans code ni historique : un signalement ne viserait que lui.
DEFAULT_REPO = MIRROR_REPO
TAG = MIRROR_TAG


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

    # ⚠️ **Une extension, un dossier, une archive.** L'archive porte le nom du
    # dossier : deux extensions rangées ensemble écrivaient la même, la seconde
    # écrasant la première, et le catalogue publié annonçait pour la première
    # une empreinte que plus aucun fichier ne portait. Chez tous les clients, la
    # récupération la jugeait alors altérée. Une extension répartie sur deux
    # dossiers, elle, aurait une archive nommée d'après un seul. Les deux cas
    # sont refusés avant d'écrire quoi que ce soit.
    dossiers_de: dict[str, set[str]] = {}
    jeux_de: dict[str, set[str]] = {}
    for jeu, cartes in par_jeu.items():
        for card in cartes:
            dossier = os.path.dirname(card["path"])
            dossiers_de.setdefault(jeu, set()).add(dossier)
            jeux_de.setdefault(dossier, set()).add(jeu)
    lignes = [f"  l'extension {jeu} est répartie sur {', '.join(sorted(dossiers))}"
              for jeu, dossiers in sorted(dossiers_de.items()) if len(dossiers) > 1]
    lignes += [f"  le dossier {dossier} mêle {', '.join(sorted(jeux))}"
               for dossier, jeux in sorted(jeux_de.items()) if len(jeux) > 1]
    if lignes:
        raise SystemExit("Une extension par dossier, sans quoi deux archives "
                         "porteraient le même nom :\n" + "\n".join(lignes))

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
         "sont pas dans git. L'application les récupère elle-même, vérifie "
         "l'empreinte de chaque archive puis de chaque image, et range le tout."),
        "",
        (f"`{MANIFEST_ASSET}` publié ici décrit les cartes du miroir : c'est ce "
         f"fichier que l'application relit pour savoir ce qui a été ajouté."),
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
                "GitHub credentials? » : voir l'avertissement en tête de ce "
                "fichier.")
    return None


def publish(repo: str, out: str, mirror: dict, notes: str,
            manifest_path: str) -> int:
    """Téléverse les archives **et le catalogue**.

    Le catalogue part en dernier dans la liste mais dans le même appel : une
    release qui porterait les archives sans lui laisserait l'application
    incapable de dire ce qu'elles contiennent.

    ⚠️ **Une release existante se met à jour en entier.** L'envoi `--clobber`
    remplaçait les fichiers sans toucher aux notes : les chiffres de la première
    publication, cartes et poids, restaient affichés. Titre et notes suivent donc
    l'envoi. Les archives d'une extension retirée restaient en ligne sans que
    rien ne le dise : elles sont listées avec la commande qui les retire, et non
    retirées d'office, une suppression sur une release publique ne se
    rattrapant pas.
    """
    archives = [os.path.join(out, entry["archive"]) for entry in mirror.values()]
    archives.append(manifest_path)
    notes_path = os.path.join(out, "notes.md")
    with open(notes_path, "w", encoding="utf-8") as handle:
        handle.write(notes)
    titre = f"Illustrations : manifeste v{MANIFEST_VERSION}"

    existe = subprocess.run(["gh", "release", "view", TAG, "--repo", repo],
                            capture_output=True, text=True,
                            check=False).returncode == 0
    if existe:
        commande = ["gh", "release", "upload", TAG, *archives,
                    "--repo", repo, "--clobber"]
    else:
        commande = ["gh", "release", "create", TAG, *archives, "--repo", repo,
                    "--title", titre, "--notes-file", notes_path]
    print("  " + " ".join(commande[:4])
          + f" … ({len(archives) - 1} archives + le catalogue)")
    code = subprocess.run(commande, check=False).returncode
    if code != 0 or not existe:
        return code

    edition = subprocess.run(["gh", "release", "edit", TAG, "--repo", repo,
                              "--title", titre, "--notes-file", notes_path],
                             check=False).returncode
    if edition != 0:
        # Les fichiers sont en ligne : la publication compte comme faite, et le
        # catalogue suivi doit les rejoindre. Seules les notes sont en retard.
        print(f"⚠️ Fichiers envoyés, mais titre et notes n'ont pas pu être mis à "
              f"jour (code {edition}).", file=sys.stderr)
    _signal_stale_assets(repo, archives)
    return 0


def _signal_stale_assets(repo: str, envoyes: list[str]) -> None:
    """Nomme les fichiers en ligne que ce catalogue ne décrit plus."""
    vue = subprocess.run(["gh", "release", "view", TAG, "--repo", repo,
                          "--json", "assets"],
                         capture_output=True, text=True, check=False)
    if vue.returncode != 0:
        return
    try:
        en_ligne = {asset["name"] for asset in json.loads(vue.stdout)["assets"]}
    except (ValueError, TypeError, KeyError):
        return
    perimes = sorted(en_ligne - {os.path.basename(chemin) for chemin in envoyes})
    if not perimes:
        return
    print(f"\n⚠️ {len(perimes)} fichier(s) en ligne ne correspondent plus au "
          f"catalogue. Pour les retirer :", file=sys.stderr)
    for nom in perimes:
        print(f"  gh release delete-asset {TAG} {nom} --repo {repo} --yes",
              file=sys.stderr)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--manifest", default=DEFAULT_MANIFEST)
    parser.add_argument("--images", default=DEFAULT_IMAGES)
    parser.add_argument("--out", default=os.path.join("data", "miroir"))
    parser.add_argument("--repo", default=DEFAULT_REPO)
    parser.add_argument("--dry-run", action="store_true",
                        help="construit archives et catalogue dans --out, sans "
                             "rien publier ni toucher au catalogue suivi")
    args = parser.parse_args(argv)

    with open(args.manifest, encoding="utf-8") as handle:
        manifest = json.load(handle)
    if manifest.get("version") != MANIFEST_VERSION:
        raise SystemExit(f"Manifeste en version {manifest.get('version')}, "
                         f"attendu {MANIFEST_VERSION}.")

    if args.repo != MIRROR_REPO:
        # L'application prend le **catalogue** à l'adresse codée dans le paquet,
        # et les **archives** à celle qu'il annonce. Publier ailleurs sans
        # reconstruire le paquet fait diverger les deux, et les clients
        # existants ne verraient jamais ce qui vient d'être publié.
        print(f"⚠️ Publication sur {args.repo}, alors que l'application "
              f"interroge {MIRROR_REPO}. Les clients déjà installés ne verront "
              f"pas ce catalogue.", file=sys.stderr)

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
    # ⚠️ **Le catalogue suivi par git ne change qu'après une publication
    # réussie.** Il était réécrit d'office, avant `--dry-run` et avant le
    # contrôle de `gh` : il annonçait alors des empreintes d'archives jamais
    # publiées, qui dépendent en plus de la date des images. Une fois commité,
    # `fetch_cards.py` jugeait altérée chaque extension en ligne. Il se prépare
    # donc à côté des archives, sous le nom de l'asset, part de là, et ne
    # remplace l'original qu'au retour de `gh`.
    prepare = os.path.join(args.out, MANIFEST_ASSET)
    # Un `--out` qui contiendrait le catalogue suivi ferait de lui le catalogue
    # « préparé » : `--dry-run` le réécrirait en disant le contraire, et la copie
    # finale d'un fichier sur lui-même lèverait après une publication réussie.
    # Nom comparé casse repliée : le disque de macOS confond les deux.
    if (os.path.samefile(os.path.dirname(os.path.abspath(args.manifest)), args.out)
            and os.path.basename(args.manifest).casefold()
            == MANIFEST_ASSET.casefold()):
        raise SystemExit(f"--out ({args.out}) contient le catalogue suivi : "
                         f"choisissez un autre dossier pour les archives.")
    with open(prepare, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=1, sort_keys=True)
        handle.write("\n")
    print(f"  catalogue préparé : {prepare}")

    if args.dry_run:
        print(f"\n--dry-run : rien n'a été publié, et {args.manifest} n'a pas changé.")
        return 0

    empeche = gh_available()
    if empeche:
        print(f"\nPublication impossible : {empeche}", file=sys.stderr)
        print(f"Archives et catalogue sont prêts dans {args.out}/ ; {args.manifest} "
              f"n'a pas changé. Relancez une fois connecté.", file=sys.stderr)
        return 1

    print(f"\nPublication sur {args.repo}, balise {TAG} …")
    code = publish(args.repo, args.out, mirror, release_notes(manifest, mirror),
                   prepare)
    if code != 0:
        print(f"\nPublication échouée (code {code}) : {args.manifest} n'a pas "
              f"changé.", file=sys.stderr)
        return code
    shutil.copyfile(prepare, args.manifest)
    print(f"  {args.manifest} porte désormais l'adresse du miroir")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
