"""Tests des scripts de manifeste et de récupération.

Ce sont des scripts et non un module du paquet : on les charge par leur chemin.
La logique qu'ils portent — la règle de sélection, la vérification d'un fichier
déjà présent — mérite d'être verrouillée comme le reste.
"""

import hashlib
import importlib.util
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


build = load("build_manifest")
fetch = load("fetch_cards")


def card(rarity="One Star", illustrator="Yuu Nishida", category="Pokemon"):
    return {"rarity": rarity, "illustrator": illustrator, "category": category}


# --- La règle de sélection -------------------------------------------------

def test_the_three_starred_rarities_are_kept():
    for rarity in ("One Star", "Two Star", "Three Star"):
        assert build.keep(card(rarity=rarity))


@pytest.mark.parametrize("rarity", ["Crown", "Shiny", "Rare", "Common"])
def test_other_rarities_are_refused(rarity):
    """Crown et Shiny ont été écartées à l'œil : cadre normal pour les Shiny,
    fond doré pour les Crown."""
    assert not build.keep(card(rarity=rarity))


@pytest.mark.parametrize("illustrator", [
    "PLANETA CG Works", "PLANETA Igarashi", "PLANETA Tsuji",
    "PLANETA Mochizuki", "PLANETA Yamashita", "PLANETA Saito", "planeta minuscule",
])
def test_planeta_renders_are_refused(illustrator):
    """PLANETA est le studio des rendus 3D : un Pokémon modélisé sur un fond,
    pas une illustration. Les six signatures rencontrées sont écartées."""
    assert not build.keep(card(illustrator=illustrator))


def test_an_illustrator_merely_containing_planeta_is_kept():
    """Le filtre porte sur le début du nom, pas sur une inclusion : un jour où
    un illustrateur s'appellerait « Planetarium », il ne serait pas écarté."""
    assert build.keep(card(illustrator="Studio Planeta Rossa"))


def test_trainer_cards_are_refused():
    """Un personnage humain découpé sur un fond scintillant : c'est l'autre
    moitié de ce qu'il fallait exclure."""
    assert not build.keep(card(rarity="Two Star", category="Trainer"))
    assert not build.keep(card(rarity="One Star", category="Trainer"))


def test_immersive_trainer_cards_are_kept():
    """Guzma et Lilie en Three Star sont de vraies scènes, et l'utilisateur les
    garde : c'est ce qui fait tomber le compte juste sur les 12 extensions."""
    assert build.keep(card(rarity="Three Star", category="Trainer"))


def test_a_missing_illustrator_does_not_crash_the_rule():
    assert build.keep({"rarity": "One Star", "category": "Pokemon"})


# --- Le nom de fichier -----------------------------------------------------

@pytest.mark.parametrize("name,expected", [
    ("Scarabrute", "scarabrute"),
    ("Mew ex", "mew-ex"),
    ("L’Île Fabuleuse", "l-ile-fabuleuse"),
    ("Goupix d'Alola", "goupix-d-alola"),
    ("Méga-Ascension", "mega-ascension"),
])
def test_slug_strips_accents_and_punctuation(name, expected):
    """Les accents sont retirés, pas conservés : macOS stocke ses noms en NFD,
    une chaîne saisie ailleurs arrive en NFC, et la comparaison échoue sans que
    rien ne le signale."""
    assert build.slug(name) == expected


def test_slug_never_leaves_a_trailing_or_doubled_separator():
    assert build.slug("  Mew  ex !! ") == "mew-ex"


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
        assert entry_["url"].startswith("[adresse retirée]")
        assert len(entry_["sha256"]) == 64
        assert entry_["bytes"] > 0
        assert entry_["set"] in manifest["sets"]
        assert entry_["path"].startswith(manifest["sets"][entry_["set"]]["folder"] + "/")


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
    assert "manifeste" in message


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


def test_the_catalogue_language_does_not_depend_on_the_order_asked(monkeypatch):
    """`--languages en fr` mettait `fr` en langue de catalogue et faisait
    disparaître sans un mot les 87 cartes de B1, B1a et B2."""
    import inspect

    source = inspect.getsource(build.collect_cards)
    assert "CATALOGUE_LANGUAGE" in source
    assert "languages[-1]" not in source
    assert build.CATALOGUE_LANGUAGE == "en"
