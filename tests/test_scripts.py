"""Tests de la mise en forme des images et du catalogue local.

`build_manifest.py` est un script et non un module du paquet : on le charge par
son chemin. La récupération, elle, vit dans le paquet, voir `test_mirror.py`.
"""

import io
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pokemon_mosaic import artwork


def load(name):
    import importlib.util

    path = ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


build = load("build_manifest")


# --- Noms de fichiers ------------------------------------------------------

@pytest.mark.parametrize("name,expected", [
    ("Mustébouée", "mustebouee"),
    ("Méga-Jungko-ex", "mega-jungko-ex"),
    ("Farfetch'd", "farfetch-d"),
    ("Ho-Oh ex", "ho-oh-ex"),
])
def test_slug_strips_accents_and_punctuation(name, expected):
    """Les accents sont retirés et non conservés : macOS stocke ses noms en NFD
    et une chaîne saisie ailleurs arrive en NFC, ce qui faisait échouer la
    comparaison de deux noms pourtant identiques à l'œil."""
    assert artwork.slug(name) == expected


def test_slug_collapses_separators():
    assert artwork.slug("  Mew  ex !! ") == "mew-ex"


# --- La mise en forme des images -------------------------------------------

def png_bytes(size):
    """Un PNG bruité, comme les sources réelles.

    Bruité et non uni : un aplat se comprime si bien en PNG que le WebP produit
    serait plus **gros**, et le test comparerait deux artefacts de bord au lieu
    du comportement réel.
    """
    import numpy as np
    from PIL import Image

    generateur = np.random.default_rng(0)
    pixels = generateur.integers(0, 255, (size[1], size[0], 3), dtype=np.uint8)
    buffer = io.BytesIO()
    Image.fromarray(pixels).save(buffer, format="PNG")
    return buffer.getvalue()


def test_process_returns_the_common_format():
    from PIL import Image

    out = artwork.process(png_bytes(artwork.TARGET_SIZE), None)
    assert Image.open(io.BytesIO(out)).size == artwork.TARGET_SIZE


def test_process_rescales_an_off_format_source():
    from PIL import Image

    out = artwork.process(png_bytes((700, 980)), None)
    assert Image.open(io.BytesIO(out)).size == artwork.TARGET_SIZE


def test_process_returns_to_the_common_format_after_cropping():
    from PIL import Image

    out = artwork.process(png_bytes(artwork.TARGET_SIZE),
                          {"left": 10, "top": 30, "right": 6, "bottom": 10})
    assert Image.open(io.BytesIO(out)).size == artwork.TARGET_SIZE


@pytest.mark.parametrize("crop", [
    {"top": 3000},                      # au-delà de la hauteur
    {"left": 800},                      # au-delà de la largeur
    {"left": 400, "right": 334},        # ne laisse rien
    {"top": -1},                        # négatif
])
def test_an_impossible_crop_names_the_edge_and_the_value(crop):
    """Sans ce contrôle, Pillow remonte « Coordinate 'lower' is less than
    'upper' », qui ne nomme ni le bord ni la valeur fautive."""
    with pytest.raises(ValueError, match=r"[Rr]ognage"):
        artwork.process(png_bytes(artwork.TARGET_SIZE), crop)


def test_a_crop_is_expressed_in_the_common_frame_not_the_source_one():
    """Les rognages sont mesurés au pixel sur du 734×1024. Une source en
    717×1000 à qui l'on retire 30 px du haut tomberait 2,4 % à côté, et la bande
    resterait, sans que rien ne le signale, puisque l'image sortirait quand même
    au bon format."""
    import numpy as np
    from PIL import Image

    crop = {"left": 0, "top": 100, "right": 0, "bottom": 0}

    def bandeau(size):
        pixels = np.zeros((size[1], size[0], 3), np.uint8)
        pixels[:size[1] // 3] = 255
        buffer = io.BytesIO()
        Image.fromarray(pixels).save(buffer, format="PNG")
        return buffer.getvalue()

    natif = np.asarray(Image.open(io.BytesIO(
        artwork.process(bandeau(artwork.TARGET_SIZE), crop))).convert("RGB"), float)
    reduit = np.asarray(Image.open(io.BytesIO(
        artwork.process(bandeau((717, 1000)), crop))).convert("RGB"), float)
    assert abs(natif.mean() - reduit.mean()) < 3.0


# --- Le catalogue local ----------------------------------------------------

def depose(racine: Path, chemin: str, taille=(20, 28)) -> Path:
    """Range une image au format WebP à l'emplacement voulu.

    Vingt pixels de côté : le catalogue ne regarde ni la taille ni le contenu,
    seulement le poids et l'empreinte. Une vignette de carte réelle ne
    démontrerait rien de plus et coûterait de la mémoire.
    """
    from PIL import Image

    cible = racine / chemin
    cible.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", taille, (10, 20, 30)).save(cible, format="WEBP")
    return cible


def catalogue(cards, **extra):
    base = {"version": artwork.MANIFEST_VERSION, "cards": cards}
    base.update(extra)
    return base


def test_an_unknown_card_is_derived_from_its_path(tmp_path):
    depose(tmp_path, "a1-puissance-genetique/a1-227-bulbizarre.webp")
    produit, nouvelles, disparues = build.build(catalogue([]), str(tmp_path))

    (carte,) = produit["cards"]
    assert carte["id"] == "A1-227"
    assert carte["set"] == "A1"
    assert carte["number"] == 227
    assert carte["path"] == "a1-puissance-genetique/a1-227-bulbizarre.webp"
    assert nouvelles and not disparues


def test_a_derived_card_leaves_rarity_and_names_empty(tmp_path):
    """Un nom de fichier ne porte ni la rareté ni les noms officiels. Les
    deviner produirait un catalogue faux **et silencieux** ; les laisser vides
    fait qu'ils sont signalés."""
    depose(tmp_path, "a1-puissance-genetique/a1-227-bulbizarre.webp")
    produit, _, _ = build.build(catalogue([]), str(tmp_path))

    (carte,) = produit["cards"]
    assert carte["rarity"] == ""
    assert carte["names"] == {}
    assert build.trous(carte) == ["rarity", "names"]


def test_a_known_card_keeps_its_metadata(tmp_path):
    """Le catalogue accumule : rareté et noms sont saisis une fois. Les
    reconstruire à chaque passage les perdrait."""
    chemin = "a1-puissance-genetique/a1-227-bulbizarre.webp"
    depose(tmp_path, chemin)
    connue = {"path": chemin, "id": "A1-227", "set": "A1", "number": 227,
              "rarity": "AR", "language": "fr",
              "names": {"fr": "Bulbizarre", "en": "Bulbasaur"},
              "bytes": 1, "sha256": "périmée"}
    produit, nouvelles, _ = build.build(catalogue([connue]), str(tmp_path))

    (carte,) = produit["cards"]
    assert carte["rarity"] == "AR"
    assert carte["names"]["fr"] == "Bulbizarre"
    assert nouvelles == []


def test_weight_and_digest_are_recomputed_for_a_known_card(tmp_path):
    """Le fichier fait foi sur ce qui le décrit : une image remplacée doit
    changer d'empreinte au catalogue, sans quoi le miroir publierait des octets
    que personne ne saurait vérifier."""
    chemin = "a1-puissance-genetique/a1-227-bulbizarre.webp"
    fichier = depose(tmp_path, chemin)
    connue = {"path": chemin, "set": "A1", "rarity": "AR", "names": {"fr": "x"},
              "bytes": 999999, "sha256": "0" * 64}
    produit, _, _ = build.build(catalogue([connue]), str(tmp_path))

    (carte,) = produit["cards"]
    assert carte["bytes"] == fichier.stat().st_size
    assert carte["sha256"] != "0" * 64


def test_a_renamed_card_keeps_its_rarity_and_names(tmp_path):
    """⚠️ L'en-tête promettait qu'une carte garde rareté et noms « quel que soit
    son fichier ». Indexée par son seul chemin, une carte renommée passait pour
    nouvelle, et l'ancienne entrée disparaissait avec ce qu'on avait saisi à la
    main. Reproduit par l'audit."""
    from pokemon_mosaic.mirror import digest_of

    ancien = "a1-puissance-genetique/a1-227-bulbizarre.webp"
    fichier = depose(tmp_path, ancien)
    connue = {"path": ancien, "id": "A1-227", "set": "A1", "number": 227,
              "rarity": "AR", "language": "fr", "names": {"fr": "Bulbizarre"},
              "bytes": fichier.stat().st_size, "sha256": digest_of(str(fichier))}
    # Hors de la convention de nommage : aucun identifiant ne s'en déduit, seul
    # le contenu peut la reconnaître.
    nouveau = "a1-puissance-genetique/bulbizarre.webp"
    fichier.rename(tmp_path / nouveau)
    renommees = []

    produit, nouvelles, disparues = build.build(catalogue([connue]), str(tmp_path),
                                                renommees)

    (carte,) = produit["cards"]
    assert carte["path"] == nouveau
    assert carte["rarity"] == "AR" and carte["names"] == {"fr": "Bulbizarre"}
    assert nouvelles == [] and disparues == []
    assert renommees == [(ancien, nouveau)]


def test_a_reencoded_card_is_recognised_by_its_identifier(tmp_path):
    """D'autres octets, mais le même identifiant : une image réencodée sous un
    autre nom reste la même carte."""
    connue = {"path": "a1-puissance-genetique/a1-227-bulbizarre.webp",
              "id": "A1-227", "set": "A1", "rarity": "AR",
              "names": {"fr": "Bulbizarre"}, "bytes": 1, "sha256": "0" * 64}
    depose(tmp_path, "a1-puissance-genetique/a1-227-bulbizarre-v2.webp", taille=(22, 30))

    produit, nouvelles, disparues = build.build(catalogue([connue]), str(tmp_path))

    (carte,) = produit["cards"]
    assert carte["rarity"] == "AR"
    assert nouvelles == [] and disparues == []


def test_a_present_card_is_never_taken_over(tmp_path):
    """Seule une carte disparue se reprend : un second fichier au même numéro, à
    côté d'une carte toujours là, est une carte nouvelle."""
    chemin = "a1-puissance-genetique/a1-227-bulbizarre.webp"
    depose(tmp_path, chemin)
    connue = {"path": chemin, "id": "A1-227", "set": "A1", "rarity": "AR",
              "names": {"fr": "x"}, "bytes": 1, "sha256": "0" * 64}
    autre = "a1-puissance-genetique/a1-227-bulbizarre-alt.webp"
    depose(tmp_path, autre)

    produit, nouvelles, _ = build.build(catalogue([connue]), str(tmp_path))

    assert [relatif for relatif, _ in nouvelles] == [autre]
    par_chemin = {carte["path"]: carte for carte in produit["cards"]}
    assert par_chemin[chemin]["rarity"] == "AR"
    assert par_chemin[autre]["rarity"] == ""


def test_duplicate_identifiers_are_reported(tmp_path):
    """⚠️ Deux fichiers au même numéro donnaient deux cartes au même `id`, que le
    rapport ne présentait que comme « à compléter ». Reproduit par l'audit."""
    for nom in ("a1-227-bulbizarre.webp", "a1-227-bulbizarre-alt.webp"):
        depose(tmp_path, f"a1-puissance-genetique/{nom}")

    produit, _, _ = build.build(catalogue([]), str(tmp_path))

    assert build.identifiants_en_double(produit["cards"]) == {"A1-227": [
        "a1-puissance-genetique/a1-227-bulbizarre-alt.webp",
        "a1-puissance-genetique/a1-227-bulbizarre.webp",
    ]}


def test_check_fails_on_duplicate_identifiers_alone(tmp_path, capsys):
    """Cartes complètes, décrites et présentes : rien d'autre ne ferait échouer
    `--check`, dont l'échec tient donc au seul identifiant en double."""
    rarete = next(iter(artwork.RARITIES))
    images = tmp_path / "images"
    cartes = []
    for nom in ("a1-227-bulbizarre.webp", "a1-227-bulbizarre-alt.webp"):
        chemin = f"a1-puissance-genetique/{nom}"
        depose(images, chemin)
        cartes.append({"path": chemin, "id": "A1-227", "set": "A1", "number": 227,
                       "rarity": rarete, "language": "fr",
                       "names": {"fr": "Bulbizarre"}, "bytes": 1, "sha256": "0" * 64})
    fichier = tmp_path / "cards.json"
    fichier.write_text(json.dumps(catalogue(cartes)), encoding="utf-8")

    code = build.main(["--images", str(images), "--manifest", str(fichier), "--check"])

    assert code == 1
    assert "A1-227" in capsys.readouterr().err


def test_a_card_described_but_absent_is_reported(tmp_path):
    """Et non retirée en silence : une image effacée par mégarde ressemble à un
    dossier incomplet, pas à une décision."""
    connue = {"path": "a1-puissance-genetique/a1-227-bulbizarre.webp",
              "set": "A1", "bytes": 1, "sha256": "x"}
    produit, _, disparues = build.build(catalogue([connue]), str(tmp_path))

    assert produit["cards"] == []
    assert disparues == ["a1-puissance-genetique/a1-227-bulbizarre.webp"]


def test_a_file_outside_the_naming_convention_is_named_not_skipped(tmp_path):
    depose(tmp_path, "a1-puissance-genetique/illustration.webp")
    produit, nouvelles, _ = build.build(catalogue([]), str(tmp_path))

    assert produit["cards"] == []
    assert nouvelles == [("a1-puissance-genetique/illustration.webp",
                          "nom de fichier hors convention")]


def test_the_folder_decides_the_set_not_the_filename(tmp_path):
    """`sets` indexe des dossiers. Un fichier mal préfixé mais rangé au bon
    endroit reste rattachable ; l'inverse produirait une extension fantôme."""
    depose(tmp_path, "a1-puissance-genetique/a9-227-bulbizarre.webp")
    manifest = catalogue([], sets={"A1": "a1-puissance-genetique"})
    produit, _, _ = build.build(manifest, str(tmp_path))

    assert produit["cards"][0]["set"] == "A1"


def test_the_catalogue_does_not_depend_on_the_walk_order(tmp_path):
    """Sans tri, deux machines produiraient deux `cards.json` différents pour
    les mêmes images : l'ordre de `os.walk` suit le système de fichiers."""
    for chemin in ("b1-mega-ascension/b1-9-arcko.webp",
                   "a1-puissance-genetique/a1-227-bulbizarre.webp",
                   "a1-puissance-genetique/a1-3-herbizarre.webp"):
        depose(tmp_path, chemin)
    produit, _, _ = build.build(catalogue([]), str(tmp_path))

    chemins = [carte["path"] for carte in produit["cards"]]
    assert chemins == sorted(chemins)


def test_the_mirror_block_survives_a_rebuild(tmp_path):
    """Il décrit des archives que ce script ne fabrique pas. Le perdre à chaque
    passage laisserait le catalogue sans adresse jusqu'à la publication
    suivante."""
    depose(tmp_path, "a1-puissance-genetique/a1-227-bulbizarre.webp")
    manifest = catalogue([], mirror={"tag": "cards-v4", "sets": {}})
    produit, _, _ = build.build(manifest, str(tmp_path))

    assert produit["mirror"]["tag"] == "cards-v4"


def test_a_catalogue_of_another_version_is_refused(tmp_path):
    """Les entrées n'ont pas la même forme d'une version à l'autre : les
    fusionner produirait un fichier que ni l'un ni l'autre format ne décrit."""
    fichier = tmp_path / "cards.json"
    fichier.write_text(json.dumps({"version": 1, "cards": []}), encoding="utf-8")
    with pytest.raises(SystemExit, match="version 1"):
        build.read_manifest(str(fichier))


def test_a_missing_catalogue_starts_empty(tmp_path):
    manifest = build.read_manifest(str(tmp_path / "absent.json"))
    assert manifest == {"version": artwork.MANIFEST_VERSION, "cards": []}


def test_check_writes_nothing(tmp_path):
    depose(tmp_path, "a1-puissance-genetique/a1-227-bulbizarre.webp")
    fichier = tmp_path / "cards.json"
    build.main(["--images", str(tmp_path), "--manifest", str(fichier), "--check"])
    assert not fichier.exists()


def test_a_set_code_containing_a_dash_is_recognised(tmp_path):
    """Les 28 cartes promo vivent sous `promo-a` / `promo-b`. Une règle qui
    interdit le tiret dans le code d'extension les rejetait toutes comme « hors
    convention », et le catalogue les perdait en silence."""
    depose(tmp_path, "promo-a-promo-a/promo-a-009-pikachu.webp")
    produit, _, _ = build.build(catalogue([]), str(tmp_path))

    (carte,) = produit["cards"]
    assert carte["set"] == "PROMO-A"
    assert carte["number"] == 9


def test_a_new_set_keeps_the_letter_after_its_number_in_lowercase(tmp_path):
    """⚠️ Trouvé en rangeant la première extension nouvelle, le 2026-09-27.

    Le dossier connu fait foi, mais une extension qui arrive n'est décrite
    nulle part : son code se déduit du nom de dossier, et tout mettre en
    capitales donnait `B4A` là où les vingt-deux autres écrivent `A1a`, `A2b`,
    `B3b`. Le catalogue aurait porté deux écritures d'une même famille.
    """
    depose(tmp_path, "b4a-l-ambition-de-la-team-rocket/b4a-093-rattatac-ex.webp")
    produit, _, _ = build.build(catalogue([]), str(tmp_path))

    (carte,) = produit["cards"]
    assert carte["set"] == "B4a"
    assert carte["id"] == "B4a-093"


@pytest.mark.parametrize("code, attendu", [
    ("a1", "A1"),
    ("a1a", "A1a"),
    ("a2b", "A2b"),
    ("b4a", "B4a"),
    ("promo-a", "PROMO-A"),
    ("promo-b", "PROMO-B"),
])
def test_every_shape_of_set_code_is_written_as_the_catalogue_does(code, attendu):
    """Les deux familles ne suivent pas la même règle : la lettre qui suit un
    numéro reste minuscule, un code sans chiffre passe tout en capitales.

    Le code arrive du **nom de fichier**, `b4a-093-...`, et non du dossier.
    """
    assert build.code_du_jeu(code) == attendu


def test_the_identifier_keeps_the_digits_as_written(tmp_path):
    """`PROMO-A-009` et non `PROMO-A-9` : passer le numéro par `int()` casserait
    la moitié des identifiants. Le nom de fichier ayant été engendré depuis
    l'identifiant, le relire tel quel le reconstitue."""
    depose(tmp_path, "promo-a-promo-a/promo-a-009-pikachu.webp")
    depose(tmp_path, "a1-puissance-genetique/a1-227-bulbizarre.webp")
    produit, _, _ = build.build(catalogue([]), str(tmp_path))

    ids = {carte["id"] for carte in produit["cards"]}
    assert ids == {"PROMO-A-009", "A1-227"}


# --- Le lanceur de la suite, par lots bornés -------------------------------

lanceur = load("run_tests")


def test_collected_tests_are_grouped_by_file_in_order():
    """Un identifiant paramétré porte crochets, espaces ou accents : il repart
    tel quel en argument, sans être découpé."""
    sortie = (
        "tests/test_a.py::test_un\n"
        "tests/test_a.py::test_deux[_rename_current-rename_arrangement]\n"
        "tests/test_b.py::test_trois[Mustébouée ex]\n"
        "tests/test_a.py::test_quatre\n"
        "\n"
        "4 tests collected in 0.12s\n"
    )

    groupes = lanceur.grouper(sortie)

    assert list(groupes) == ["tests/test_a.py", "tests/test_b.py"]
    assert groupes["tests/test_a.py"] == [
        "tests/test_a.py::test_un",
        "tests/test_a.py::test_deux[_rename_current-rename_arrangement]",
        "tests/test_a.py::test_quatre",
    ]
    assert groupes["tests/test_b.py"] == ["tests/test_b.py::test_trois[Mustébouée ex]"]


def test_batches_never_exceed_their_bound_and_keep_the_order():
    """L'utilisateur a demandé des lots d'un nombre de tests limité, pour ne pas
    surcharger sa machine."""
    identifiants = [f"tests/test_a.py::test_{rang}" for rang in range(155)]

    decoupe = lanceur.lots(identifiants, 50)

    assert [len(lot) for lot in decoupe] == [50, 50, 50, 5]
    assert [un for lot in decoupe for un in lot] == identifiants
    assert lanceur.lots(identifiants[:3], 0) == [[un] for un in identifiants[:3]]


class FauxResultat:
    def __init__(self, returncode=0, stdout=""):
        self.returncode, self.stdout, self.stderr = returncode, stdout, ""


def test_the_runner_owns_the_verbosity(monkeypatch):
    """⚠️ Un `-q` de plus faisait écrire à la collecte un compte par fichier, un
    `-v` un arbre de modules : l'un comme l'autre faisait répondre « Aucun test
    retenu » sans en lancer un seul. L'ancien en-tête donnait `-x -q` en exemple."""
    assert lanceur.options(["-q", "-x", "-vv", "--quiet", "-k", "zoom",
                            "--verbosity", "2", "--verbosity=3", "--verbose"]) \
        == ["-x", "-k", "zoom"]

    commandes = []

    def faux_run(commande, **_):
        commandes.append(commande)
        if "--collect-only" in commande:
            return FauxResultat(0, "tests/test_a.py::test_un\n\n1 test collected\n")
        return FauxResultat(0, "1 passed in 0.01s\n")

    monkeypatch.setattr(lanceur.subprocess, "run", faux_run)

    assert lanceur.main(["-q", "-v", "-k", "un"]) == 0
    collecte, lot = commandes
    assert collecte.count("-q") == 1 and "-v" not in collecte
    assert lot.count("-q") == 1 and "-v" not in lot
    assert "tests/test_a.py::test_un" in lot


@pytest.mark.parametrize("code, sortie, attendu", [
    (5, "\nno tests collected, 3 deselected\n", 5),
    (0, "tests/test_a.py: 3\n", 1),
])
def test_an_empty_collection_is_never_green(monkeypatch, capsys, code, sortie, attendu):
    """Rien retenu par `-k` rend 5, comme pytest ; une collecte réussie dont on
    ne lit aucun identifiant est une erreur, et non « aucun test » : c'est ainsi
    que le défaut de verbosité passait pour un filtre vide."""
    monkeypatch.setattr(lanceur.subprocess, "run",
                        lambda commande, **_: FauxResultat(code, sortie))

    assert lanceur.main([]) == attendu
    assert ("illisible" in capsys.readouterr().out) == (attendu == 1)


# --- La publication du miroir ------------------------------------------------

publie = load("publish_release")


def catalogue_publiable(racine: Path) -> Path:
    """Une carte réelle sur le disque, et le `cards.json` qui la décrit."""
    from pokemon_mosaic.mirror import digest_of

    images = racine / "images"
    image = depose(images, "a1/a1-001-bulbizarre.webp")
    carte = {"path": "a1/a1-001-bulbizarre.webp", "set": "A1",
             "bytes": image.stat().st_size, "sha256": digest_of(str(image))}
    chemin = racine / "cards.json"
    chemin.write_text(json.dumps(catalogue([carte])), encoding="utf-8")
    return chemin


def arguments(racine: Path, *extra):
    return ["--manifest", str(racine / "cards.json"), "--images",
            str(racine / "images"), "--out", str(racine / "miroir"), *extra]


def test_a_dry_run_leaves_the_tracked_catalogue_alone(tmp_path):
    """⚠️ `--dry-run` réécrivait `cards.json`, suivi par git, avec les empreintes
    d'archives jamais publiées, qui dépendent en plus de la date des images. Une
    fois commité, `fetch_cards.py` jugeait altérée chaque extension en ligne."""
    suivi = catalogue_publiable(tmp_path)
    avant = suivi.read_bytes()

    assert publie.main(arguments(tmp_path, "--dry-run")) == 0

    assert suivi.read_bytes() == avant
    prepare = json.loads((tmp_path / "miroir" / publie.MANIFEST_ASSET)
                         .read_text(encoding="utf-8"))
    assert "A1" in prepare["mirror"]["sets"]


def test_without_gh_the_tracked_catalogue_is_untouched(tmp_path, monkeypatch):
    suivi = catalogue_publiable(tmp_path)
    avant = suivi.read_bytes()
    monkeypatch.setattr(publie, "gh_available", lambda: "`gh` n'est pas installé.")

    assert publie.main(arguments(tmp_path)) == 1
    assert suivi.read_bytes() == avant


@pytest.mark.parametrize("code", [0, 1])
def test_the_catalogue_changes_only_after_a_successful_publish(tmp_path, monkeypatch,
                                                              code):
    """C'est le catalogue préparé qui part, sous le nom de l'asset ; l'original ne
    le rejoint que si `gh` a réussi."""
    suivi = catalogue_publiable(tmp_path)
    avant = suivi.read_bytes()
    envoyes = []
    monkeypatch.setattr(publie, "gh_available", lambda: None)
    monkeypatch.setattr(publie, "publish",
                        lambda repo, out, mirror, notes, manifest_path:
                        envoyes.append(manifest_path) or code)

    assert publie.main(arguments(tmp_path)) == code

    (envoye,) = envoyes
    assert os.path.basename(envoye) == publie.MANIFEST_ASSET
    assert os.path.dirname(envoye) == str(tmp_path / "miroir")
    if code == 0:
        assert "mirror" in json.loads(suivi.read_text(encoding="utf-8"))
    else:
        assert suivi.read_bytes() == avant


def test_an_output_folder_holding_the_tracked_catalogue_is_refused(tmp_path):
    """Le catalogue « préparé » y serait le catalogue suivi lui-même : `--dry-run`
    le réécrivait en disant le contraire, et la copie finale d'un fichier sur
    lui-même levait après une publication réussie."""
    suivi = catalogue_publiable(tmp_path)
    avant = suivi.read_bytes()
    args = ["--manifest", str(suivi), "--images", str(tmp_path / "images"),
            "--out", str(tmp_path), "--dry-run"]

    with pytest.raises(SystemExit, match="catalogue suivi"):
        publie.main(args)
    assert suivi.read_bytes() == avant


@pytest.mark.parametrize("cartes, message", [
    ([("promo/promo-a-001-pikachu.webp", "PROMO-A"),
      ("promo/promo-b-001-mew.webp", "PROMO-B")],
     "le dossier promo mêle PROMO-A, PROMO-B"),
    ([("a1/a1-001-bulbizarre.webp", "A1"),
      ("a1-bis/a1-002-herbizarre.webp", "A1")],
     "l'extension A1 est répartie sur a1, a1-bis"),
])
def test_one_set_per_folder_or_archives_would_collide(tmp_path, cartes, message):
    """⚠️ L'archive porte le nom du dossier. Reproduit par l'audit : deux
    extensions dans `promo/` écrivaient toutes deux `promo.zip`, qui ne contenait
    plus que PROMO-B, et PROMO-A annonçait une empreinte que plus aucun fichier
    ne portait. Le refus tombe avant d'écrire la moindre archive."""
    from pokemon_mosaic.mirror import digest_of

    images = tmp_path / "images"
    fiches = []
    for chemin, jeu in cartes:
        image = depose(images, chemin)
        fiches.append({"path": chemin, "set": jeu, "bytes": image.stat().st_size,
                       "sha256": digest_of(str(image))})

    with pytest.raises(SystemExit) as refus:
        publie.build_archives(catalogue(fiches), str(images), str(tmp_path / "miroir"))

    assert message in str(refus.value)
    assert not list((tmp_path / "miroir").glob("*.zip"))


class FauxGh:
    """Rejoue `gh` sans réseau : chaque commande est notée, la release dit si
    elle existe et quels fichiers elle porte."""

    def __init__(self, existe=True, en_ligne=()):
        self.commandes, self.existe, self.en_ligne = [], existe, en_ligne

    def __call__(self, commande, **_):
        self.commandes.append(commande)
        if commande[:3] == ["gh", "release", "view"] and "--json" in commande:
            return FauxResultat(0, json.dumps(
                {"assets": [{"name": nom} for nom in self.en_ligne]}))
        if commande[:3] == ["gh", "release", "view"]:
            return FauxResultat(0 if self.existe else 1)
        return FauxResultat(0)


MIROIR_A1 = {"A1": {"archive": "a1.zip", "sha256": "0", "bytes": 1, "cards": 1}}


def test_updating_a_release_refreshes_its_notes_and_names_stale_files(
        tmp_path, monkeypatch, capsys):
    """⚠️ L'envoi `--clobber` laissait les notes de la première publication,
    cartes et poids compris, et les archives d'une extension retirée restaient
    en ligne sans que rien ne le dise. On les nomme, sans les supprimer : une
    suppression sur une release publique ne se rattrape pas."""
    gh = FauxGh(en_ligne=("a1.zip", "cards.json", "ancienne.zip"))
    monkeypatch.setattr(publie.subprocess, "run", gh)

    code = publie.publish("moi/miroir", str(tmp_path), MIROIR_A1, "notes",
                          str(tmp_path / "cards.json"))

    assert code == 0
    assert [commande[2] for commande in gh.commandes] == ["view", "upload", "edit", "view"]
    edition = gh.commandes[2]
    assert "--notes-file" in edition and "--title" in edition
    alerte = capsys.readouterr().err
    assert "ancienne.zip" in alerte and "delete-asset" in alerte
    assert "a1.zip" not in alerte and "cards.json" not in alerte


def test_a_new_release_is_created_with_its_notes(tmp_path, monkeypatch):
    gh = FauxGh(existe=False)
    monkeypatch.setattr(publie.subprocess, "run", gh)

    code = publie.publish("moi/miroir", str(tmp_path), MIROIR_A1, "notes",
                          str(tmp_path / "cards.json"))

    assert code == 0
    assert [commande[2] for commande in gh.commandes] == ["view", "create"]
    assert "--notes-file" in gh.commandes[1]


# --- La récupération : --check et le mode normal disent la même chose ------------

recupere = load("fetch_cards")


def test_check_and_fetch_agree_on_a_path_leaving_the_folder(tmp_path, capsys):
    """⚠️ Reproduit par l'audit, pour le même catalogue : `--check` sortait en 1
    en comptant la carte « à refaire », le mode normal en 0 en affirmant les
    cartes toutes présentes. Refusé à la lecture, les deux sortent en 1 et
    disent pourquoi, sans toucher au réseau."""
    fichier = tmp_path / "cards.json"
    fichier.write_text(json.dumps(catalogue([
        {"path": "../evade.webp", "set": "A1", "bytes": 1, "sha256": "0" * 64},
    ])), encoding="utf-8")
    sortie = tmp_path / "cartes"

    for mode in (["--check"], []):
        code = recupere.main(["--manifest", str(fichier), "--output", str(sortie), *mode])
        assert code == 1, mode
        assert "hors du dossier" in capsys.readouterr().err, mode


# --- Les délais : aucun test ni aucun lot ne tourne sans fin -----------------

def test_a_test_past_its_deadline_is_stopped_with_its_trace(tmp_path):
    """Demandé par l'utilisateur le 2026-09-18, après un test resté bloqué deux
    heures. Le délai tombe même dans une attente qui ne rend pas la main à
    Python, là où un signal ne ferait rien."""
    import subprocess

    fichier = tmp_path / "test_trop_long.py"
    fichier.write_text(
        "import time\n\n"
        "def test_rapide():\n    pass\n\n"
        "def test_bloque():\n    time.sleep(30)\n")
    env = dict(os.environ, TESTS_DELAI="1",
               PYTHONPATH=str(ROOT / "tests") + os.pathsep
               + os.environ.get("PYTHONPATH", ""))

    resultat = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "delai_des_tests",
         "-p", "no:cacheprovider", str(fichier)],
        cwd=tmp_path, env=env, capture_output=True, text=True, timeout=25,
        check=False)

    assert resultat.returncode != 0
    assert "Timeout" in resultat.stderr
    assert "test_bloque" in resultat.stderr


def test_a_batch_past_its_deadline_fails_the_run(monkeypatch, capsys):
    import subprocess

    def faux_run(commande, **options):
        if "--collect-only" in commande:
            return FauxResultat(0, "tests/test_a.py::test_un\n\n1 test collected\n")
        assert options["timeout"] == lanceur.DELAI_PAR_LOT
        raise subprocess.TimeoutExpired(commande, options["timeout"])

    monkeypatch.setattr(lanceur.subprocess, "run", faux_run)
    monkeypatch.delenv("TESTS_DELAI_LOT", raising=False)

    assert lanceur.main([]) == 1
    sortie = capsys.readouterr().out
    assert "DÉLAI DÉPASSÉ" in sortie and "test_a.py" in sortie


def test_a_failed_batch_shows_its_error_output(monkeypatch, capsys):
    """La trace d'un test arrêté par son délai part sur la sortie d'erreur :
    le lanceur ne montrait que la sortie standard."""
    def faux_run(commande, **_):
        if "--collect-only" in commande:
            return FauxResultat(0, "tests/test_a.py::test_un\n\n1 test collected\n")
        resultat = FauxResultat(1, "")
        resultat.stderr = "Timeout (0:01:00)!\n  File test_a.py, in test_un\n"
        return resultat

    monkeypatch.setattr(lanceur.subprocess, "run", faux_run)

    assert lanceur.main([]) == 1
    assert "Timeout (0:01:00)!" in capsys.readouterr().out
