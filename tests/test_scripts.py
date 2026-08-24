"""Tests des scripts de manifeste et de récupération.

Ce sont des scripts et non un module du paquet : on les charge par leur chemin.
La logique qu'ils portent — la règle de sélection, la vérification d'un fichier
déjà présent — mérite d'être verrouillée comme le reste.
"""

import hashlib
import importlib.util
import io
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    path = ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


sys.path.insert(0, str(ROOT / "src"))
from pokemon_mosaic import artwork

fetch = load("fetch_cards")
build = load("build_manifest")


def card(rarity="One Star", illustrator="Yuu Nishida", category="Pokemon"):
    return {"rarity": rarity, "illustrator": illustrator, "category": category}


# --- Rapprochement des sources ---------------------------------------------

@pytest.mark.parametrize("a,b", [
    ("Ho-Oh ex", "Ho-oh ex"),
    ("Farfetch'd", "Farfetchd"),
    ("Alolan Ninetales", "alolan ninetales"),
    ("Mega Charizard Y ex", "mega charizard y ex"),
])
def test_match_key_reconciles_spelling_between_sources(a, b):
    """Trois catalogues indépendants n'orthographient pas pareil. Sans cette
    normalisation, « Ho-Oh ex » et « Ho-oh ex » désignent deux cartes."""
    assert artwork.match_key(a) == artwork.match_key(b)


def test_match_key_still_separates_distinct_cards():
    assert artwork.match_key("Pikachu ex") != artwork.match_key("Pikachu")
    assert artwork.match_key("Mew ex") != artwork.match_key("Mewtwo ex")


def test_the_forum_index_prefers_the_numbered_entry(monkeypatch):
    """Le forum publie deux fois les cartes Immersive : une fois dans la galerie,
    numérotée, et une fois dans « Extended Immersive », qui est une **autre
    illustration** en 1080×1885. Sans cette préférence, une carte sur vingt-cinq
    reçoit la mauvaise image, à la bonne taille de nom près."""
    cooked = (
        '<a class="lightbox" href="https://efour.example/original/etendue.webp"'
        ' title="A3 Guzma">x</a>'
        '<a class="lightbox" href="https://efour.example/original/normale.webp"'
        ' title="A3 0001 Guzma">x</a>')
    monkeypatch.setattr(build, "fetch_json",
                        lambda url: {"post_stream": {"posts": [
                            {"post_number": 1, "cooked": cooked}]}})
    index = build.load_forum()
    url = build.forum_url({"set": "A3", "name_en": "Guzma"}, index)
    assert url.endswith("normale.webp")


def test_the_forum_falls_back_when_nothing_is_numbered():
    index = {("A3", artwork.match_key("Guzma")): [(False, "https://x/seule.webp")]}
    assert build.forum_url({"set": "A3", "name_en": "Guzma"}, index) \
        == "https://x/seule.webp"


def test_an_unknown_card_has_no_forum_url():
    assert build.forum_url({"set": "Z9", "name_en": "Personne"}, {}) is None


# --- Association des extensions --------------------------------------------

def test_sets_are_associated_by_number_and_name_not_by_number_alone():
    """Les numéros se recouvrent d'une extension à l'autre : apparier sur le
    seul numéro laisserait une extension nombreuse l'emporter par hasard."""
    cards = [{"set": "A1", "number": 227, "name_en": "Bulbasaur"},
             {"set": "A1", "number": 229, "name_en": "Pinsir"}]
    la source = {
        # Beaucoup de numéros en commun, mais aucun nom qui corresponde.
        99: {227: ("u", "Rattata"), 229: ("u", "Raticate"), 230: ("u", "Spearow")},
        384: {227: ("bon", "Bulbasaur"), 229: ("bon", "Pinsir")},
    }
    assert build.associate_sets(cards, la source)["A1"] == 384


# --- Le nom de fichier -----------------------------------------------------

@pytest.mark.parametrize("name,expected", [
    ("Scarabrute", "scarabrute"),
    ("Mew ex", "mew-ex"),
    ("L\u2019Île Fabuleuse", "l-ile-fabuleuse"),
    ("Méga-Jungko-ex", "mega-jungko-ex"),
])
def test_slug_strips_accents_and_punctuation(name, expected):
    """Les accents sont retirés : macOS stocke en NFD, une chaîne saisie
    ailleurs arrive en NFC, et la comparaison échoue sans rien signaler."""
    assert artwork.slug(name) == expected


def test_slug_never_leaves_a_doubled_separator():
    assert artwork.slug("  Mew  ex !! ") == "mew-ex"


# --- La mise en forme des images -------------------------------------------

def image_bytes(size, colour=(120, 60, 30)):
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", size, colour).save(buffer, format="WEBP", quality=80)
    return buffer.getvalue()


def png_bytes(size):
    """Un PNG bruité, comme les sources réelles.

    Bruité et non uni : un aplat se comprime si bien en PNG que le WebP produit
    serait plus **gros**, et le test comparerait deux artefacts de bord au lieu
    du comportement réel.
    """
    import numpy as np
    from PIL import Image

    rng = np.random.default_rng(0)
    pixels = rng.integers(0, 256, (size[1], size[0], 3), dtype=np.uint8)
    buffer = io.BytesIO()
    Image.fromarray(pixels).save(buffer, format="PNG")
    return buffer.getvalue()


def test_an_untouched_image_is_reencoded_all_the_same():
    """La source est désormais un PNG sans perte de plus d'un mégaoctet : il
    faut toujours réencoder. L'ancien raccourci — rendre les octets d'origine
    tels quels — ne valait que pour une source déjà en WebP avec perte."""
    from PIL import Image

    raw = png_bytes(artwork.TARGET_SIZE)
    out = artwork.process(raw, None)
    assert out is not raw
    image = Image.open(io.BytesIO(out))
    assert image.format == "WEBP"
    assert image.size == artwork.TARGET_SIZE
    assert len(out) < len(raw)


def test_a_cropped_image_comes_back_at_the_common_size():
    from PIL import Image

    raw = png_bytes(artwork.TARGET_SIZE)
    out = artwork.process(raw, {"left": 10, "top": 30, "right": 6, "bottom": 10})
    assert Image.open(io.BytesIO(out)).size == artwork.TARGET_SIZE
    assert out != raw


def test_an_image_of_another_size_is_brought_back_to_the_common_one():
    """Sinon une seule carte plus petite ferait rétrécir tout le jeu :
    `load_cards` aligne sur la plus petite largeur et la plus petite hauteur,
    prises séparément, ce qui déforme jusqu'aux cartes intactes."""
    from PIL import Image

    out = artwork.process(image_bytes((700, 980)), None)
    assert Image.open(io.BytesIO(out)).size == artwork.TARGET_SIZE


def test_the_crop_removes_the_declared_pixels():
    """Le rognage est déclaré en pixels retirés sur chaque bord, pas en boîte."""
    from PIL import Image

    image = Image.open(io.BytesIO(image_bytes((100, 100))))
    coupe = image.crop((10, 20, 100 - 30, 100 - 5))
    assert coupe.size == (60, 75)


def test_declared_crops_match_the_repository_file():
    """`crops.json` porte les deux rognages retrouvés au pixel sur les fichiers
    d'origine de l'utilisateur. Les valeurs sont mesurées, pas choisies."""
    with open(ROOT / "crops.json", encoding="utf-8") as handle:
        crops = json.load(handle)
    assert crops["A1-242"]["top"] == 30, "Nosferalto : bande blanche de 27 px en haut"
    assert crops["A1-238"]["left"] == 10, "Taupiqueur : blanc sur les quatre bords"
    for key, value in crops.items():
        if key.startswith("_"):
            continue
        assert {"left", "top", "right", "bottom"} <= set(value)


# --- La vérification d'un fichier déjà présent -----------------------------

def entry(raw: bytes, path="a1-x/a1-001-test.webp"):
    return {"path": path, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def test_a_correct_file_is_recognised(tmp_path):
    raw = b"une image"
    target = tmp_path / "carte.webp"
    target.write_bytes(raw)
    assert fetch.is_current(str(target), entry(raw))


def test_a_file_of_the_wrong_size_is_refused(tmp_path):
    target = tmp_path / "carte.webp"
    target.write_bytes(b"tronquee")
    assert not fetch.is_current(str(target), entry(b"une image complete"))


def test_a_file_of_the_right_size_but_wrong_content_is_refused(tmp_path):
    """La taille seule ne prouve rien : deux images différentes peuvent peser
    pareil, et c'est exactement le cas qu'un contrôle paresseux laisserait
    passer."""
    target = tmp_path / "carte.webp"
    target.write_bytes(b"AAAAAAAAA")
    assert not fetch.is_current(str(target), entry(b"une image"))


def test_an_absent_file_is_refused(tmp_path):
    assert not fetch.is_current(str(tmp_path / "jamais.webp"), entry(b"x"))


# --- Le manifeste ----------------------------------------------------------

def test_a_manifest_of_another_version_is_refused(tmp_path):
    path = tmp_path / "cards.json"
    path.write_text(json.dumps({"version": 99, "cards": []}))
    with pytest.raises(ValueError, match="version 99"):
        fetch.load_manifest(str(path))


def test_the_repository_manifest_is_readable_and_coherent():
    """Le manifeste versionné doit rester lisible par le script qui le lit."""
    manifest = fetch.load_manifest(str(ROOT / "cards.json"))
    assert manifest["cards"], "manifeste vide"
    paths = [c["path"] for c in manifest["cards"]]
    assert len(paths) == len(set(paths)), "deux cartes partagent un chemin"
    for entry_ in manifest["cards"]:
        assert entry_["source"] in ("la source", "forum", "local")
        assert entry_["url"].startswith(("[adresse retirée]",
                                         "https://efour.b-cdn.net/",
                                         "[adresse retirée]"))
        # Une carte déposée à la main porte l'adresse de sa provenance, qui
        # n'est reprenable par personne : le miroir est le seul chemin.
        assert (entry_["url"].startswith("[adresse retirée]")) \
            == bool(entry_.get("local"))
        assert len(entry_["sha256"]) == 64
        assert len(entry_["source_sha256"]) == 64
        assert entry_["bytes"] > 0
        assert entry_["set"] in manifest["sets"]
        assert entry_["path"].startswith(manifest["sets"][entry_["set"]] + "/")


# --- Non-régressions de la revue -------------------------------------------

@pytest.mark.parametrize("evasion", [
    "../evade.webp", "../../evade.webp", "a1-x/../../evade.webp",
])
def test_a_manifest_path_cannot_escape_the_output_directory(tmp_path, evasion):
    """Le manifeste est un fichier du dépôt, donc modifiable par une
    contribution, et ce script est fait pour être lancé par quiconque clone le
    projet : un chemin remontant écrirait ailleurs sur le disque."""
    with pytest.raises(ValueError, match="hors du dossier"):
        fetch.target_path(str(tmp_path), evasion)


def test_an_absolute_path_is_neutralised_rather_than_refused(tmp_path):
    """Découper sur « / » puis rejoindre transforme « /tmp/x » en « tmp/x » :
    le chemin reste dans le dossier de sortie, il n'y a rien à refuser."""
    resolved = fetch.target_path(str(tmp_path), "/tmp/evade.webp")
    assert resolved == str(tmp_path / "tmp" / "evade.webp")


def test_a_normal_path_stays_inside(tmp_path):
    resolved = fetch.target_path(str(tmp_path), "a1-jeu/a1-001-carte.webp")
    assert resolved.startswith(str(tmp_path))
    assert resolved.endswith("a1-001-carte.webp")


def test_an_escaping_path_is_reported_not_written(tmp_path):
    outcome, message = fetch.download(
        {"path": "../evade.webp", "bytes": 1, "sha256": "0" * 64,
         "url": "https://example.invalid/x.webp"},
        str(tmp_path),
    )
    assert outcome == fetch.Outcome.FAILED
    assert "hors du dossier" in message
    assert not (tmp_path.parent / "evade.webp").exists()


def test_a_permanent_http_error_is_not_retried(tmp_path, monkeypatch):
    """Trois tentatives sur un 404 coûtaient 10 s par carte : un manifeste
    périmé de cent entrées aurait fait attendre un quart d'heure."""
    import urllib.error

    attempts = []

    def always_404(request, timeout=None):
        attempts.append(request.full_url)
        raise urllib.error.HTTPError(request.full_url, 404, "Not Found", {}, None)

    monkeypatch.setattr(fetch.urllib.request, "urlopen", always_404)
    outcome, message = fetch.download(
        {"path": "a/b.webp", "bytes": 1, "sha256": "0" * 64,
         "url": "https://example.invalid/x.webp"},
        str(tmp_path),
    )
    assert outcome == fetch.Outcome.FAILED
    assert len(attempts) == 1, "un 404 est définitif, inutile de réessayer"
    assert "hors cache" in message


def test_a_transient_error_is_still_retried(tmp_path, monkeypatch):
    import urllib.error

    attempts = []

    def flaky(request, timeout=None):
        attempts.append(1)
        raise urllib.error.HTTPError(request.full_url, 503, "Unavailable", {}, None)

    monkeypatch.setattr(fetch.urllib.request, "urlopen", flaky)
    monkeypatch.setattr(fetch.time, "sleep", lambda _: None)
    outcome, _ = fetch.download(
        {"path": "a/b.webp", "bytes": 1, "sha256": "0" * 64,
         "url": "https://example.invalid/x.webp"},
        str(tmp_path),
    )
    assert outcome == fetch.Outcome.FAILED
    assert len(attempts) == 3, "une panne passagère mérite d'être réessayée"




def test_a_present_file_costs_no_delay(tmp_path, monkeypatch):
    """La pause ménage le serveur ; l'appliquer à un fichier déjà correct ne
    ménage rien et transforme la reprise — l'usage courant — en minute d'attente."""
    raw = b"une image"
    target = tmp_path / "a1-x" / "carte.webp"
    target.parent.mkdir()
    target.write_bytes(raw)
    card = entry(raw, path="a1-x/carte.webp")
    card["url"] = "https://example.invalid/x.webp"

    dormi = []
    monkeypatch.setattr(fetch.time, "sleep", lambda s: dormi.append(s))
    outcome, _ = fetch.download(card, str(tmp_path), delay=5.0)
    assert outcome == fetch.Outcome.KEPT
    assert dormi == [], "aucune pause pour un fichier déjà conforme"


def test_a_real_download_does_observe_the_delay(tmp_path, monkeypatch):
    import urllib.error

    dormi = []
    monkeypatch.setattr(fetch.time, "sleep", lambda s: dormi.append(s))
    monkeypatch.setattr(
        fetch.urllib.request, "urlopen",
        lambda *a, **k: (_ for _ in ()).throw(
            urllib.error.HTTPError("u", 404, "x", {}, None)))
    fetch.download({"path": "a/b.webp", "bytes": 1, "sha256": "0" * 64,
                    "url": "https://example.invalid/x.webp"},
                   str(tmp_path), delay=5.0)
    assert dormi == [5.0]


def test_both_scripts_share_one_manifest_version():
    """La version doit vivre dans le module partagé : déclarée deux fois, elle
    dérive et le lecteur refuse ce que le constructeur produit."""
    assert fetch.MANIFEST_VERSION == artwork.MANIFEST_VERSION
    source = (ROOT / "scripts" / "build_manifest.py").read_text(encoding="utf-8")
    assert "MANIFEST_VERSION = " not in source


# --- La cascade de sources -------------------------------------------------

def carte_type():
    return {"id": "A2a-076", "set": "A2a", "number": 76, "rarity": "AR",
            "asset": "cPK_20_004360_00_HELLGAR_AR", "name_fr": "Démolosse", "name_en": "Houndoom"}


def sert(monkeypatch, table):
    """Fait répondre `fetch` d'après un dictionnaire URL -> octets."""
    monkeypatch.setattr(build, "fetch", lambda url, attempts=3: table.get(url))


def test_an_extended_immersive_is_refused_on_its_aspect_ratio(monkeypatch):
    """Le forum publie sous le même nom une version « Extended Immersive » en
    1080×1885, qui est une autre illustration. La retenir donnerait une carte
    fausse sans qu'aucun contrôle ne bronche : le nom, l'extension et la rareté
    concordent, seule la forme trahit."""
    sert(monkeypatch, {"u": png_bytes((1080, 1885))})
    entry, erreur = build.resolve(carte_type(), [("forum", "u")], {}, "a2a-x", None)
    assert entry is None
    assert "autre cadrage" in erreur


def test_the_native_size_wins_even_when_it_comes_second(monkeypatch):
    """Une partie du catalogue est publiée en 717×1000 — même rapport d'aspect,
    simple réduction. Prendre la première source venue perdrait 2,4 % de
    définition sur 89 cartes."""
    sert(monkeypatch, {"reduite": png_bytes((717, 1000)),
                       "native": png_bytes(artwork.TARGET_SIZE)})
    entry, _ = build.resolve(carte_type(), [("la source", "reduite"),
                                            ("forum", "native")], {}, "a2a-x", None)
    assert entry["source"] == "forum"
    assert entry["url"] == "native"
    assert "upscaled" not in entry


def test_a_reduced_source_is_kept_as_a_fallback_and_flagged(monkeypatch):
    """Quand aucune source n'a le format natif, on agrandit — mais un
    agrandissement ne crée aucun détail, et il faut que ça se voie."""
    from PIL import Image

    reduite = png_bytes((717, 1000))
    sert(monkeypatch, {"a": reduite})
    entry, _ = build.resolve(carte_type(), [("la source", "a")], {}, "a2a-x", None)
    assert entry["upscaled"] is True
    # ramenée au format commun malgré tout : un jeu de tailles mêlées ferait
    # rétrécir toutes les cartes sur la plus petite largeur et la plus petite
    # hauteur, prises séparément.
    assert Image.open(io.BytesIO(artwork.process(reduite))).size == artwork.TARGET_SIZE


def test_the_largest_reduction_wins_among_fallbacks(monkeypatch):
    sert(monkeypatch, {"petite": png_bytes((367, 512)),
                       "grande": png_bytes((717, 1000))})
    entry, _ = build.resolve(carte_type(), [("la source", "petite"),
                                            ("forum", "grande")], {}, "a2a-x", None)
    assert entry["url"] == "grande"
    assert entry["upscaled"] is True


def test_a_refused_source_falls_through_to_the_next(monkeypatch):
    sert(monkeypatch, {"bonne": png_bytes(artwork.TARGET_SIZE)})   # "morte" absente
    entry, _ = build.resolve(carte_type(), [("la source", "morte"),
                                            ("forum", "bonne")], {}, "a2a-x", None)
    assert entry["source"] == "forum"


def test_a_card_with_no_usable_source_is_reported_not_invented(monkeypatch):
    sert(monkeypatch, {})
    entry, erreur = build.resolve(carte_type(), [("la source", "morte")], {}, "a2a-x", None)
    assert entry is None and erreur


def test_the_written_file_matches_the_manifest_entry(tmp_path, monkeypatch):
    """Le manifeste décrit le fichier **après** traitement : les deux doivent
    sortir du même encodage, sinon la vérification échouerait sur tout le jeu.

    L'image est déposée en `.part` et ne prend sa place qu'en fin de course, si
    la construction est complète — voir
    `test_images_are_written_only_when_the_build_is_complete`.
    """
    sert(monkeypatch, {"u": png_bytes(artwork.TARGET_SIZE)})
    entry, _ = build.resolve(carte_type(), [("la source", "u")], {}, "a2a-x",
                             str(tmp_path))
    ecrit = tmp_path / "a2a-x" / (entry["path"].split("/")[-1] + ".part")
    assert ecrit.exists()
    assert ecrit.stat().st_size == entry["bytes"]
    assert hashlib.sha256(ecrit.read_bytes()).hexdigest() == entry["sha256"]


# --- Non-régressions de la revue du 2026-08-24 -----------------------------

def test_a_crop_is_expressed_in_the_common_frame_not_the_source_one():
    """Les rognages de `crops.json` ont été mesurés au pixel sur du 734×1024.
    Une partie du catalogue est publiée en 717×1000 : retirer 30 px du haut de
    celle-là tomberait 2,4 % à côté, et la bande blanche resterait — sans que
    rien ne le signale, puisque l'image sortirait quand même au bon format."""
    import numpy as np
    from PIL import Image

    crop = {"left": 0, "top": 100, "right": 0, "bottom": 0}
    # Bande blanche sur exactement le tiers haut, dans les deux résolutions.
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
    # Le même rognage doit retirer la même part de bandeau des deux côtés.
    assert abs(natif.mean() - reduit.mean()) < 3.0


def test_crops_notes_are_not_counted_as_cards(tmp_path):
    """`crops.json` porte un `_note` qui explique la méthode."""
    fichier = tmp_path / "crops.json"
    fichier.write_text(json.dumps({"_note": "explication", "A1-242": {"top": 30}}),
                       encoding="utf-8")
    crops = build.load_crops(str(fichier))
    assert list(crops) == ["A1-242"]


def test_an_absent_crops_file_is_not_an_error(tmp_path):
    assert build.load_crops(str(tmp_path / "absent.json")) == {}


def test_pagination_does_not_stop_when_the_total_is_missing(monkeypatch):
    """`total` ne sert qu'à borner. Le remplacer par 0 quand le champ disparaît
    arrêterait la pagination dès la première page, et les cartes restantes
    basculeraient silencieusement sur le forum."""
    pages = {
        0: {"data": [{"setLang": "pocket", "setId": 1, "cardNumber": "001",
                      "imageUrl": "u1", "cardName": "Un"}]},
        artwork.SOURCE_PAGE: {"data": [{"setLang": "pocket", "setId": 1,
                                        "cardNumber": "002", "imageUrl": "u2",
                                        "cardName": "Deux"}]},
        artwork.SOURCE_PAGE * 2: {"data": []},
    }
    def faux(url):
        return pages[int(url.split("offset=")[1])]
    monkeypatch.setattr(build, "fetch_json", faux)
    index = build.load_source()
    assert sorted(index[1]) == [1, 2]


def test_a_response_that_is_not_json_yields_none_rather_than_raising(monkeypatch):
    """Une page de maintenance rendue en HTML avec un code 200 ne doit pas faire
    tomber toute la construction sur une trace."""
    monkeypatch.setattr(build, "fetch", lambda url, attempts=3: b"<html>oups</html>")
    assert build.fetch_json("https://x") is None


def test_a_dead_url_yields_none_too(monkeypatch):
    monkeypatch.setattr(build, "fetch", lambda url, attempts=3: None)
    assert build.fetch_json("https://x") is None


def build_avec(monkeypatch, resultats):
    """Fait tourner `build_manifest.main` hors réseau.

    `resultats` associe un identifiant de carte au couple rendu par `resolve`.
    """
    cartes = [{"id": ident, "set": ident.split("-")[0], "number": i,
               "rarity": "AR", "asset": "cPK_X",
               "name_fr": ident, "name_en": ident}
              for i, ident in enumerate(resultats, 1)]
    monkeypatch.setattr(build, "load_catalogue",
                        lambda: (cartes, {"A1": {"name": {"fr": "Test"}}}))
    monkeypatch.setattr(build, "load_source", dict)
    monkeypatch.setattr(build, "load_forum", dict)
    monkeypatch.setattr(build, "associate_sets", lambda c, p: {})
    monkeypatch.setattr(build, "forum_url", lambda card, forum: "https://x/" + card["id"])
    monkeypatch.setattr(build, "resolve",
                        lambda card, cand, crops, folder, images: resultats[card["id"]])
    return build


def entree_valide(ident):
    return ({"id": ident, "set": ident.split("-")[0], "number": 1, "rarity": "AR",
             "names": {"fr": ident}, "language": "fr", "source": "forum",
             "url": "https://x", "source_sha256": "a" * 64, "source_bytes": 10,
             "sha256": "b" * 64, "bytes": 10,
             "path": f"a1-test/{ident.lower()}.webp"}, "")


def test_an_incomplete_run_never_overwrites_the_repository_manifest(tmp_path,
                                                                   monkeypatch):
    """Une coupure réseau sur quelques cartes produirait sinon un manifeste
    amputé — cartes **et** clé `sets` — qui écraserait le fichier versionné
    complet avant même que le message d'erreur ne s'affiche."""
    sortie = tmp_path / "cards.json"
    sortie.write_text('{"version": 3, "cards": ["intact"]}', encoding="utf-8")
    build_avec(monkeypatch, {"A1-001": entree_valide("A1-001"),
                             "A1-002": (None, "coupure réseau")})

    code = build.main(["--output", str(sortie), "--crops", str(tmp_path / "rien.json")])

    assert code == 1
    assert json.loads(sortie.read_text(encoding="utf-8"))["cards"] == ["intact"]
    partiel = json.loads((tmp_path / "cards.json.partiel").read_text(encoding="utf-8"))
    assert [c["id"] for c in partiel["cards"]] == ["A1-001"]


def test_a_complete_run_does_write_the_manifest(tmp_path, monkeypatch):
    sortie = tmp_path / "cards.json"
    build_avec(monkeypatch, {"A1-001": entree_valide("A1-001"),
                             "A1-002": entree_valide("A1-002")})

    code = build.main(["--output", str(sortie), "--crops", str(tmp_path / "rien.json")])

    assert code == 0
    manifest = json.loads(sortie.read_text(encoding="utf-8"))
    assert [c["id"] for c in manifest["cards"]] == ["A1-001", "A1-002"]
    assert manifest["version"] == artwork.MANIFEST_VERSION
    assert not (tmp_path / "cards.json.partiel").exists()


def test_a_rate_limited_response_is_retried_not_abandoned(monkeypatch):
    """Discourse répond **422** — et non 429 — pour « trop de requêtes ».
    Traité comme les autres 4xx, il faisait perdre les deux galeries d'un coup
    et neuf cartes se retrouvaient sans source."""
    import urllib.error

    appels = []

    def faux_urlopen(request, timeout=None):
        appels.append(1)
        if len(appels) < 3:
            raise urllib.error.HTTPError(request.full_url, 422, "trop", {}, None)
        class Reponse:
            def read(self): return b"ok"
            def __enter__(self): return self
            def __exit__(self, *a): return False
        return Reponse()

    monkeypatch.setattr(build.urllib.request, "urlopen", faux_urlopen)
    monkeypatch.setattr(build.time, "sleep", lambda s: None)
    assert build.fetch("https://x") == b"ok"
    assert len(appels) == 3


def test_a_not_found_is_still_abandoned_at_once(monkeypatch):
    """Réessayer un 404 ne fait qu'attendre : mesuré, 10 s par carte."""
    import urllib.error

    appels = []

    def faux_urlopen(request, timeout=None):
        appels.append(1)
        raise urllib.error.HTTPError(request.full_url, 404, "absent", {}, None)

    monkeypatch.setattr(build.urllib.request, "urlopen", faux_urlopen)
    monkeypatch.setattr(build.time, "sleep", lambda s: None)
    assert build.fetch("https://x") is None
    assert len(appels) == 1


# --- Les illustrations déposées à la main ----------------------------------

def test_local_files_are_indexed_by_card_id(tmp_path):
    (tmp_path / "A2a-076.webp").write_bytes(b"x")
    (tmp_path / "promo-a-046.png").write_bytes(b"x")
    (tmp_path / "notes.txt").write_text("pas une image", encoding="utf-8")
    index = build.load_local(str(tmp_path))
    assert sorted(index) == ["A2A-076", "PROMO-A-046"]


def test_an_absent_local_directory_is_not_an_error(tmp_path):
    assert build.load_local(str(tmp_path / "absent")) == {}


def test_a_local_file_takes_precedence_over_the_remote_sources(tmp_path,
                                                               monkeypatch):
    """Douze illustrations ne sont publiées au format natif par aucune des deux
    sources : toute l'extension A2a, plus PROMO-A-046."""
    fichier = tmp_path / "A2a-076.webp"
    fichier.write_bytes(png_bytes(artwork.TARGET_SIZE))
    monkeypatch.setattr(build, "fetch",
                        lambda url, attempts=3: pytest.fail("le réseau a été sollicité"))
    entry, _ = build.resolve(carte_type(), [("local", str(fichier)),
                                            ("la source", "distante")], {}, "a2a-x", None)
    assert entry["source"] == "local"
    assert entry["local"] is True
    # L'adresse inscrite dit **d'où vient** le fichier, pas où le reprendre :
    # aucune source distante ne le publie à ce format.
    assert entry["url"].startswith("[adresse retirée]")
    assert "upscaled" not in entry


def test_a_local_file_of_the_wrong_size_lets_the_remote_source_win(tmp_path,
                                                                  monkeypatch):
    """Un fichier déposé par erreur ne doit pas dégrader la carte en silence."""
    fichier = tmp_path / "A2a-076.webp"
    fichier.write_bytes(png_bytes((717, 1000)))
    sert(monkeypatch, {"distante": png_bytes(artwork.TARGET_SIZE)})
    entry, _ = build.resolve(carte_type(), [("local", str(fichier)),
                                            ("la source", "distante")], {}, "a2a-x", None)
    assert entry["source"] == "la source"
    assert "local" not in entry


def test_an_unreadable_local_file_falls_through(tmp_path, monkeypatch):
    sert(monkeypatch, {"distante": png_bytes(artwork.TARGET_SIZE)})
    entry, _ = build.resolve(carte_type(), [("local", str(tmp_path / "absent.webp")),
                                            ("la source", "distante")], {}, "a2a-x", None)
    assert entry["source"] == "la source"


def test_the_repository_manifest_has_no_upscaled_card_left():
    """Les douze qui l'étaient ont été remplacées le 2026-08-24 par des fichiers
    natifs déposés dans `data/local/`. Netteté regagnée : 1,17× à 1,49×."""
    manifest = fetch.load_manifest(str(ROOT / "cards.json"))
    agrandies = [c["id"] for c in manifest["cards"] if c.get("upscaled")]
    assert agrandies == []


def test_a_malformed_asset_name_yields_no_address_rather_than_raising():
    """L'adresse n'est qu'une note de provenance, et le nom vient d'un catalogue
    tiers. Une exception remonterait d'un fil et ferait tomber la construction."""
    assert artwork.asset_url("cPK_X") == ""
    assert artwork.asset_url("") == ""
    assert artwork.asset_url("cPK_20_00") == ""


def test_a_trainer_card_still_lives_under_its_own_path():
    """Les cartes Dresseur portent `cTR` et vivent sous `Face/TR/`. Coder `PK`
    en dur rendait Guzma, Lilie et Pepper introuvables par construction."""
    assert "/Face/TR/20/000000/" in artwork.asset_url("cTR_20_000550_01_GUZUMA_IM")
    assert "/Face/PK/20/004000/" in artwork.asset_url("cPK_20_004360_00_HELLGAR_AR")


# --- Non-régressions relevées par la revue du 2026-08-24 --------------------

def test_a_set_code_cannot_escape_the_images_directory(tmp_path, monkeypatch):
    """Le code d'extension vient du catalogue tiers et n'est pas assaini :
    `slug()` ne s'applique qu'au nom de l'extension, pas à son code. Vérifié
    avant correction — l'image atterrissait deux niveaux au-dessus."""
    sortie = tmp_path / "sortie"
    sortie.mkdir()
    sert(monkeypatch, {"distante": png_bytes(artwork.TARGET_SIZE)})
    carte = dict(carte_type(), id="../../evade-001", set="../..")
    entry, erreur = build.resolve(carte, [("la source", "distante")], {},
                                  build.set_folder("../..", {}), str(sortie))
    assert entry is None
    assert "hors du dossier" in erreur
    assert list(tmp_path.rglob("*.webp")) == []


def test_target_path_accepts_a_normal_path(tmp_path):
    attendu = tmp_path / "a1-puissance-genetique" / "a1-227-bulbizarre.webp"
    assert build.target_path(str(tmp_path),
                             "a1-puissance-genetique/a1-227-bulbizarre.webp") == str(attendu)


def test_an_unreadable_image_fails_one_card_and_not_the_whole_run(tmp_path,
                                                                  monkeypatch):
    """Sans filet, l'exception remonte du fil, `future.result()` la relève, et
    la récupération entière tombe — y compris les cartes déjà obtenues."""
    tronque = b"\x89PNG\r\n\x1a\n" + b"\x00" * 40
    class Reponse:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return tronque
    monkeypatch.setattr(fetch.urllib.request, "urlopen",
                        lambda *a, **k: Reponse())
    carte = {"id": "X-001", "path": "jeu/x-001.webp", "url": "http://x",
             "sha256": "0" * 64, "bytes": 10,
             "source_sha256": hashlib.sha256(tronque).hexdigest()}
    issue, message = fetch.download(carte, str(tmp_path))
    assert issue == fetch.Outcome.FAILED
    assert "illisible" in message
    assert list(tmp_path.rglob("*.webp")) == []


def test_two_local_files_claiming_one_card_resolve_the_same_way(tmp_path):
    """Sinon l'ordre du système de fichiers déciderait, et deux constructions
    du même dossier ne donneraient pas le même manifeste."""
    (tmp_path / "A2a-076.webp").write_bytes(b"a")
    (tmp_path / "A2A-076.png").write_bytes(b"b")
    choisis = {build.load_local(str(tmp_path))["A2A-076"] for _ in range(5)}
    assert len(choisis) == 1


def test_an_impossible_crop_names_the_edge_and_the_value():
    """Les valeurs de `crops.json` sont écrites à la main : une erreur de saisie
    est un risque réel. Pillow remontait « Coordinate 'lower' is less than
    'upper' », qui ne nomme ni la carte, ni le bord, ni la valeur."""
    image = png_bytes(artwork.TARGET_SIZE)
    with pytest.raises(ValueError, match=r"top=3000 px impossible.*1024 px"):
        artwork.process(image, {"top": 3000})
    with pytest.raises(ValueError, match=r"left=800 px impossible.*734 px"):
        artwork.process(image, {"left": 800})
    with pytest.raises(ValueError, match="ne laisse rien"):
        artwork.process(image, {"left": 400, "right": 334})
    with pytest.raises(ValueError, match="top=-1 px impossible"):
        artwork.process(image, {"top": -1})


def test_a_legitimate_crop_still_goes_through():
    """Les deux rognages du dépôt : Nosferalto et Taupiqueur."""
    from PIL import Image

    image = png_bytes(artwork.TARGET_SIZE)
    with open(ROOT / "crops.json", encoding="utf-8") as handle:
        crops = json.load(handle)
    # `_note` en tête du fichier porte une explication, pas un rognage.
    for crop in (v for v in crops.values() if isinstance(v, dict)):
        sortie = artwork.process(image, crop)
        assert Image.open(io.BytesIO(sortie)).size == artwork.TARGET_SIZE


# --- Non-régressions du /verif-code du 2026-08-24 ---------------------------

def _index_source(entrees):
    """`{setId: {numéro: (url, nom)}}`, la forme que rend `load_source`."""
    index = {}
    for set_id, cartes in entrees.items():
        index[set_id] = {n: (f"http://x/{set_id}/{n}", nom) for n, nom in cartes}
    return index


def test_a_set_name_must_match_exactly_not_as_a_substring():
    """« Exeggutor » est contenu dans « Alolan Exeggutor ». Cette seule
    indulgence rattachait A1a à Promo-A quand A1a manquait, et huit cartes sur
    neuf recevaient l'illustration d'autres cartes, sans le moindre signe."""
    cartes = [{"set": "A1a", "number": n, "name_en": nom} for n, nom in
              ((69, "Exeggutor"), (70, "Serperior"), (71, "Salandit"))]
    la source = _index_source({443: [(69, "Alolan Exeggutor"), (70, "Alolan Ninetales"),
                                  (71, "Crabrawler")]})
    assert build.associate_sets(cartes, la source)["A1a"] is None


def test_an_extension_absent_from_source_is_not_associated_by_accident():
    """Le cas de chaque sortie : le catalogue est à jour avant le miroir."""
    cartes = [{"set": "B5", "number": n, "name_en": f"Carte{n}"} for n in range(1, 11)]
    # une seule correspondance fortuite sur dix
    la source = _index_source({999: [(1, "Carte1")] + [(n, "Autre") for n in range(2, 11)]})
    assert build.associate_sets(cartes, la source)["B5"] is None


def test_a_well_covered_extension_is_still_associated():
    cartes = [{"set": "A1", "number": n, "name_en": f"Carte{n}"} for n in range(1, 11)]
    la source = _index_source({384: [(n, f"Carte{n}") for n in range(1, 10)]})
    assert build.associate_sets(cartes, la source)["A1"] == 384


def test_an_impossible_crop_skips_one_card_and_not_the_whole_build(monkeypatch):
    """`crops.json` s'écrit à la main. Sans filet, l'exception remonte du fil,
    `future.result()` la relève, et les 441 cartes s'arrêtent."""
    sert(monkeypatch, {"distante": png_bytes(artwork.TARGET_SIZE)})
    entry, erreur = build.resolve(carte_type(), [("la source", "distante")],
                                  {"A2a-076": {"top": 3000}}, "a2a-x", None)
    assert entry is None
    assert "traitement impossible" in erreur and "top=3000" in erreur


def test_images_are_written_only_when_the_build_is_complete(tmp_path, monkeypatch):
    """Sinon la collection mêlerait ancien et nouveau pendant que `cards.json`
    resterait à la version précédente, sans que personne l'ait demandé."""
    sert(monkeypatch, {"distante": png_bytes(artwork.TARGET_SIZE)})
    entry, _ = build.resolve(carte_type(), [("la source", "distante")], {},
                             "a2a-x", str(tmp_path))
    # `resolve` dépose un `.part` ; la promotion n'a lieu qu'en fin de course.
    assert list(tmp_path.rglob("*.part"))
    assert not list(tmp_path.rglob("*.webp"))
    assert entry["path"].endswith(".webp")


def test_a_manifest_missing_a_field_names_the_card(tmp_path):
    """`cards.json` est un fichier du dépôt. Un `KeyError` remontant d'un fil
    arrêtait toute la récupération sans nommer la carte fautive."""
    manifest = fetch.load_manifest(str(ROOT / "cards.json"))
    del manifest["cards"][3]["source_sha256"]
    chemin = tmp_path / "ampute.json"
    chemin.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match=r"champ\(s\) manquant\(s\) source_sha256"):
        fetch.load_manifest(str(chemin))


def test_a_locally_deposited_card_says_the_mirror_is_the_only_way():
    """Leur adresse note d'où elles viennent, pas où les reprendre : annoncer
    « hors cache » laisserait croire qu'il suffit de réessayer."""
    assert "miroir" in fetch._pourquoi({"local": True})
    assert "hors cache" in fetch._pourquoi({})


# --- Le miroir --------------------------------------------------------------

def _miroir(tmp_path, manifest, cartes):
    """Une archive par extension, comme `publish_release.py` les produit."""
    import zipfile
    dossier = tmp_path / "miroir"
    dossier.mkdir()
    sets = {}
    par_jeu = {}
    for card in cartes:
        par_jeu.setdefault(card["set"], []).append(card)
    for jeu, lot in par_jeu.items():
        nom = lot[0]["path"].rsplit("/", 1)[0] + ".zip"
        chemin = dossier / nom
        with zipfile.ZipFile(chemin, "w") as zf:
            for card in lot:
                zf.writestr(card["path"], card["_contenu"])
        sets[jeu] = {"archive": nom,
                     "sha256": hashlib.sha256(chemin.read_bytes()).hexdigest(),
                     "bytes": chemin.stat().st_size, "cards": len(lot)}
    manifest["mirror"] = {"tag": "cards-v3", "url": dossier.as_uri(), "sets": sets}
    return dossier


def _manifeste_jouet(tmp_path):
    cartes = []
    for numero in (1, 2):
        contenu = png_bytes((8, 12)) + bytes([numero])
        cartes.append({
            "id": f"A1-{numero:03d}", "set": "A1", "number": numero,
            "path": f"a1-jeu/a1-{numero:03d}-carte.webp",
            "url": "https://example.invalid/x", "bytes": len(contenu),
            "sha256": hashlib.sha256(contenu).hexdigest(),
            "source_sha256": hashlib.sha256(contenu).hexdigest(),
            "source_bytes": len(contenu), "_contenu": contenu,
        })
    manifest = {"version": artwork.MANIFEST_VERSION, "cards": cartes}
    return manifest, cartes


def test_the_mirror_delivers_every_card_and_is_idempotent(tmp_path):
    manifest, cartes = _manifeste_jouet(tmp_path)
    _miroir(tmp_path, manifest, cartes)
    sortie = tmp_path / "sortie"

    tally, echecs = fetch.fetch_mirror(manifest, str(sortie), workers=1)
    assert echecs == []
    assert tally[fetch.Outcome.FETCHED] == 2
    for card in cartes:
        ecrit = sortie / card["path"]
        assert hashlib.sha256(ecrit.read_bytes()).hexdigest() == card["sha256"]

    tally, echecs = fetch.fetch_mirror(manifest, str(sortie), workers=1)
    assert echecs == [] and tally[fetch.Outcome.KEPT] == 2


def test_a_tampered_archive_is_refused_whole(tmp_path):
    """L'empreinte de l'archive fait foi avant toute extraction : une archive
    modifiée ne doit pas livrer même ses fichiers intacts."""
    manifest, cartes = _manifeste_jouet(tmp_path)
    dossier = _miroir(tmp_path, manifest, cartes)
    archive = dossier / manifest["mirror"]["sets"]["A1"]["archive"]
    archive.write_bytes(archive.read_bytes() + b"X")

    sortie = tmp_path / "sortie"
    tally, echecs = fetch.fetch_mirror(manifest, str(sortie), workers=1)
    # Un échec d'archive est rapporté **une fois**, pour toutes ses cartes.
    assert len(echecs) == 1
    libelle, message = echecs[0]
    assert "2 cartes" in libelle and "altérée" in message
    assert tally.get(fetch.Outcome.FETCHED, 0) == 0
    assert not list(sortie.rglob("*.webp"))


def test_an_archive_entry_cannot_write_outside_the_output(tmp_path):
    """Les chemins viennent du manifeste, jamais de l'archive : une entrée
    nommée `../../evade.webp` n'a aucun effet."""
    import zipfile
    manifest, cartes = _manifeste_jouet(tmp_path)
    dossier = _miroir(tmp_path, manifest, cartes)
    archive = dossier / manifest["mirror"]["sets"]["A1"]["archive"]
    with zipfile.ZipFile(archive, "a") as zf:
        zf.writestr("../../evade.webp", b"pas la bonne carte")
    manifest["mirror"]["sets"]["A1"]["sha256"] = hashlib.sha256(
        archive.read_bytes()).hexdigest()

    sortie = tmp_path / "sortie"
    fetch.fetch_mirror(manifest, str(sortie), workers=1)
    assert not (tmp_path / "evade.webp").exists()
    assert not (tmp_path.parent / "evade.webp").exists()


def test_an_unreachable_archive_is_reported_once_not_once_per_card(tmp_path,
                                                                   monkeypatch):
    """441 lignes « 404 » identiques noieraient la seule information utile :
    la cause. Un échec d'archive vaut pour toutes ses cartes."""
    import urllib.error

    manifest, cartes = _manifeste_jouet(tmp_path)
    _miroir(tmp_path, manifest, cartes)
    monkeypatch.setattr(
        fetch.urllib.request, "urlopen",
        lambda *a, **k: (_ for _ in ()).throw(
            urllib.error.HTTPError("u", 404, "Not Found", {}, None)))

    _, echecs = fetch.fetch_mirror(manifest, str(tmp_path / "sortie"), workers=1)
    assert len(echecs) == 1, echecs
    libelle, message = echecs[0]
    assert "2 cartes" in libelle
    assert "GH_TOKEN" in message, "la cause probable doit être nommée"


def test_a_private_mirror_is_read_through_the_asset_endpoint(tmp_path, monkeypatch):
    """Sur un dépôt privé, l'adresse publique répond 404 **même munie du
    jeton** : seul `releases/assets/{id}` sert le fichier. Mesuré le 2026-08-24."""
    manifest, cartes = _manifeste_jouet(tmp_path)
    dossier = _miroir(tmp_path, manifest, cartes)
    manifest["mirror"]["repo"] = "ArielNora/pokemoncardsmosaic"
    manifest["mirror"]["url"] = "https://example.invalid/publique"
    monkeypatch.setenv("GH_TOKEN", "jeton-de-test")
    monkeypatch.setattr(fetch, "_assets_by_name", lambda repo, tag, token: {
        entry["archive"]: 4242 for entry in manifest["mirror"]["sets"].values()})

    demandes = []

    def faux_urlopen(request, timeout=None):
        demandes.append((request.full_url, request.headers))
        nom = manifest["mirror"]["sets"]["A1"]["archive"]
        return io.BytesIO((dossier / nom).read_bytes())

    monkeypatch.setattr(fetch.urllib.request, "urlopen", faux_urlopen)
    _, echecs = fetch.fetch_mirror(manifest, str(tmp_path / "sortie"), workers=1)

    assert echecs == []
    url, entetes = demandes[0]
    assert url.endswith("/releases/assets/4242")
    assert entetes["Accept"] == "application/octet-stream"
    assert "example.invalid" not in url, "l'adresse publique ne sert à rien ici"
