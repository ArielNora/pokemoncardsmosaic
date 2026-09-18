#!/usr/bin/env python
"""Lance la suite **par lots de tests bornés**, un processus par lot, l'un après l'autre.

    scripts/run_tests.sh                    # ce que lance le hook pre-commit
    scripts/run_tests.sh -x                 # options pytest supplémentaires
    TESTS_PAR_LOT=25 scripts/run_tests.sh   # lots plus petits

Des processus séparés : en un seul, la QApplication partagée, les widgets, les
vignettes et les images d'export s'accumulent (177 Mo de pic d'un bloc contre
142 Mo fichier par fichier, mesuré en août).

Des lots bornés : l'utilisateur l'a demandé, pour ne pas surcharger sa machine.
⚠️ Mesuré le 2026-09-12 sur le plus gros fichier, 155 tests : 117 Mo d'un bloc,
113 à 114 Mo par lots de 50. Le socle d'un processus en fait déjà 108 : la
taille du lot change peu, et ce qui charge vraiment la machine, c'est de lancer
plusieurs choses **en même temps**. Ce script n'en lance jamais deux.

La collecte se fait une fois, dans un seul processus qui importe les fichiers
sans exécuter un test. Un fichier dont aucun test n'est retenu, par `-k`, ne
lance rien : pytest sortait alors en code 5, que l'ancien script comptait comme
un échec.
"""

import os
import re
import subprocess
import sys

LOT_PAR_DEFAUT = 50
# Ce qu'on garde de la sortie d'un lot en échec : la fin, où pytest résume.
LIGNES_D_ECHEC = 30
# ⚠️ **Un lot ne tourne jamais sans fin.** Demandé par l'utilisateur le
# 2026-09-18, après un test resté bloqué deux heures. Chaque test a déjà son
# délai (`tests/delai_des_tests.py`) ; celui du lot rattrape ce qui y
# échapperait, la collecte ou un processus figé avant le premier test. Dix
# minutes pour cinquante tests, quand le plus lent en prend deux et demie.
DELAI_PAR_LOT = 600
DELAI_DE_COLLECTE = 300
# ⚠️ **La verbosité appartient au lanceur.** Un `-q` de plus fait écrire à la
# collecte un compte par fichier au lieu des identifiants, un `-v` un arbre de
# modules : l'un comme l'autre faisait répondre « Aucun test retenu » sans en
# lancer un seul, alors que l'ancien en-tête donnait `-x -q` en exemple.
# Les grappes d'options courtes (`-xq`) ne sont pas découpées : `-kqueue` en
# serait une aussi.
VERBOSITE = re.compile(r"-q+|-v+|--quiet|--verbose|--verbosity=.*")


def grouper(sortie_de_collecte: str) -> dict[str, list[str]]:
    """Les identifiants de tests collectés, rangés par fichier, dans l'ordre.

    Un identifiant paramétré porte des crochets, parfois des espaces ou des
    accents : on le garde tel quel, il repart en argument et non en ligne de
    commande à découper.
    """
    par_fichier: dict[str, list[str]] = {}
    for ligne in sortie_de_collecte.splitlines():
        if "::" not in ligne or not ligne.startswith("tests/"):
            continue
        fichier = ligne.split("::", 1)[0]
        par_fichier.setdefault(fichier, []).append(ligne)
    return par_fichier


def options(argv: list[str]) -> list[str]:
    """Les options de l'utilisateur, moins celles de verbosité, que le lanceur fixe."""
    gardees, sauter = [], False
    for option in argv:
        if sauter:
            sauter = False
        elif option == "--verbosity":
            sauter = True                   # sa valeur suit
        elif not VERBOSITE.fullmatch(option):
            gardees.append(option)
    return gardees


def lots(identifiants: list[str], taille: int) -> list[list[str]]:
    """Découpe en lots d'au plus `taille` tests, sans changer l'ordre."""
    taille = max(1, taille)
    return [identifiants[debut:debut + taille]
            for debut in range(0, len(identifiants), taille)]


def _pytest() -> list[str]:
    local = os.path.join(".venv", "bin", "pytest")
    return [local] if os.access(local, os.X_OK) else ["uv", "run", "pytest"]


def main(argv: list[str]) -> int:
    taille = int(os.environ.get("TESTS_PAR_LOT", LOT_PAR_DEFAUT))
    pytest = _pytest()
    argv = options(argv)

    try:
        collecte = subprocess.run(
            [*pytest, "tests", "--collect-only", "-q", *argv],
            capture_output=True, text=True, check=False,
            timeout=int(os.environ.get("TESTS_DELAI_COLLECTE", DELAI_DE_COLLECTE)))
    except subprocess.TimeoutExpired:
        print("Collecte arrêtée : délai dépassé.")
        return 1
    if collecte.returncode not in (0, 5):
        print("Collecte impossible :")
        print("\n".join(collecte.stdout.splitlines()[-LIGNES_D_ECHEC:]))
        print(collecte.stderr[-2000:])
        return 1
    par_fichier = grouper(collecte.stdout)
    if collecte.returncode == 5:
        print("Aucun test retenu.")
        return 5
    if not par_fichier:
        # Une collecte réussie sans un identifiant n'est pas « aucun test » :
        # c'est une sortie qu'on ne sait pas lire. Le dire, plutôt que de
        # passer pour vert sans avoir rien lancé.
        print("Collecte illisible, aucun identifiant de test reconnu :")
        print("\n".join(collecte.stdout.splitlines()[-LIGNES_D_ECHEC:]))
        return 1

    delai_lot = int(os.environ.get("TESTS_DELAI_LOT", DELAI_PAR_LOT))
    total, en_echec = 0, []
    for fichier, identifiants in par_fichier.items():
        print(f"{fichier:36s}", end="", flush=True)
        passes, decoupe = 0, lots(identifiants, taille)
        for rang, lot in enumerate(decoupe, start=1):
            suffixe = f" (lot {rang}/{len(decoupe)})" if len(decoupe) > 1 else ""
            try:
                resultat = subprocess.run(
                    [*pytest, *lot, "-q", "--no-header", *argv],
                    capture_output=True, text=True, check=False, timeout=delai_lot)
            except subprocess.TimeoutExpired:
                print(f"DÉLAI DÉPASSÉ{suffixe} : lot arrêté au bout de {delai_lot} s")
                en_echec.append(fichier)
                break
            if resultat.returncode != 0:
                print(f"ÉCHEC{suffixe}")
                print("\n".join(resultat.stdout.splitlines()[-LIGNES_D_ECHEC:]))
                # ⚠️ **La sortie d'erreur aussi** : c'est là qu'un test arrêté
                # par son délai écrit où il était bloqué.
                erreurs = (resultat.stderr or "").splitlines()[-LIGNES_D_ECHEC:]
                if erreurs:
                    print("\n".join(erreurs))
                en_echec.append(fichier)
                break
            compte = re.search(r"(\d+) passed", resultat.stdout)
            passes += int(compte.group(1)) if compte else 0
        else:
            detail = f", {len(decoupe)} lots" if len(decoupe) > 1 else ""
            print(f"{passes} passed{detail}")
            total += passes

    if en_echec:
        print(f"\nFichiers en échec : {' '.join(en_echec)}")
        return 1
    print(f"\n{total} tests passés.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
