"""Tests de la mise en forme des images et du catalogue local.

`build_manifest.py` est un script et non un module du paquet : on le charge par
son chemin. La récupération, elle, vit dans le paquet, voir `test_mirror.py`.
"""

import io
import json
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


def test_the_identifier_keeps_the_digits_as_written(tmp_path):
    """`PROMO-A-009` et non `PROMO-A-9` : passer le numéro par `int()` casserait
    la moitié des identifiants. Le nom de fichier ayant été engendré depuis
    l'identifiant, le relire tel quel le reconstitue."""
    depose(tmp_path, "promo-a-promo-a/promo-a-009-pikachu.webp")
    depose(tmp_path, "a1-puissance-genetique/a1-227-bulbizarre.webp")
    produit, _, _ = build.build(catalogue([]), str(tmp_path))

    ids = {carte["id"] for carte in produit["cards"]}
    assert ids == {"PROMO-A-009", "A1-227"}
