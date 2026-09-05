"""Tests de la récupération depuis le miroir.

C'est le code que l'application appelle au bouton « Télécharger les cartes ».
Rien ici ne touche au réseau : le miroir est servi par une fausse `urlopen`, qui
rend exactement ce que GitHub rendrait.
"""

import hashlib
import io
import json
import sys
import urllib.error
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pokemon_mosaic import mirror

# --- Un miroir de laboratoire ---------------------------------------------

def image(nom: str) -> bytes:
    """Des octets reconnaissables, pas une vraie image : le miroir ne décode
    rien, il compare des empreintes."""
    return f"illustration {nom}".encode()


def archive(chemins: dict) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_STORED) as zf:
        for chemin, contenu in chemins.items():
            zf.writestr(chemin, contenu)
    return buffer.getvalue()


def manifeste(jeux: dict) -> tuple[dict, dict]:
    """Rend (manifeste, table adresse -> octets) pour un miroir donné.

    `jeux` associe un code d'extension à une liste de chemins de cartes.
    """
    cartes, sets, servi = [], {}, {}
    for jeu, chemins in jeux.items():
        contenus = {chemin: image(chemin) for chemin in chemins}
        for chemin, contenu in contenus.items():
            cartes.append({
                "path": chemin, "set": jeu,
                "bytes": len(contenu),
                "sha256": hashlib.sha256(contenu).hexdigest(),
            })
        brut = archive(contenus)
        nom = f"{jeu.lower()}.zip"
        sets[jeu] = {"archive": nom, "cards": len(chemins),
                     "bytes": len(brut),
                     "sha256": hashlib.sha256(brut).hexdigest()}
        servi[f"https://miroir.test/{nom}"] = brut

    manifest = {
        "version": mirror.MANIFEST_VERSION,
        "cards": cartes,
        "mirror": {"tag": "cards-test", "repo": "essai/miroir",
                   "url": "https://miroir.test", "sets": sets},
    }
    return manifest, servi


@pytest.fixture
def sert(monkeypatch):
    """Installe une fausse `urlopen`. Rend la fonction qui pose la table."""
    def poser(table: dict, erreurs: dict | None = None):
        erreurs = erreurs or {}

        class Reponse:
            def __init__(self, raw):
                self._raw = raw

            def read(self):
                return self._raw

            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

        def faux_urlopen(request, timeout=None):
            url = request.full_url if hasattr(request, "full_url") else request
            if url in erreurs:
                raise erreurs[url]
            if url not in table:
                raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)
            return Reponse(table[url])

        monkeypatch.setattr(mirror.urllib.request, "urlopen", faux_urlopen)
        # Un jeton d'environnement ferait passer par l'API : les tests décrivent
        # le dépôt public, qui est le cas de tout le monde.
        monkeypatch.delenv("GH_TOKEN", raising=False)
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    return poser


# --- Chemins ---------------------------------------------------------------

@pytest.mark.parametrize("relatif", [
    "../evade.webp",
    "a1/../../evade.webp",
])
def test_a_path_climbing_out_of_the_output_folder_is_refused(tmp_path, relatif):
    """Le manifeste vient du réseau. Un chemin qui remonte écrirait ailleurs sur
    le disque : on refuse plutôt que de faire confiance."""
    with pytest.raises(ValueError, match="hors du dossier"):
        mirror.target_path(str(tmp_path), relatif)


def test_an_absolute_path_is_neutralised_not_refused(tmp_path):
    """Le chemin est **découpé sur `/` puis rejoint sous la racine** : la barre
    de tête ne devient qu'un fragment vide, sans effet. Refuser serait aussi
    correct, mais ce test dit ce que le code fait, et prouve qu'un `/etc/passwd`
    au manifeste retombe dans le dossier de sortie."""
    assert (mirror.target_path(str(tmp_path), "/absolu.webp")
            == str(tmp_path / "absolu.webp"))


def test_a_normal_path_stays_inside(tmp_path):
    attendu = tmp_path / "a1" / "carte.webp"
    assert mirror.target_path(str(tmp_path), "a1/carte.webp") == str(attendu)


# --- Fichier déjà présent --------------------------------------------------

def test_a_matching_file_is_current(tmp_path):
    contenu = b"des octets"
    fichier = tmp_path / "c.webp"
    fichier.write_bytes(contenu)
    card = {"bytes": len(contenu),
            "sha256": hashlib.sha256(contenu).hexdigest()}
    assert mirror.is_current(str(fichier), card)


def test_a_file_of_the_right_size_but_wrong_content_is_not_current(tmp_path):
    """La taille écarte l'immense majorité des cas sans lire le fichier, mais
    seule l'empreinte prouve quoi que ce soit."""
    fichier = tmp_path / "c.webp"
    fichier.write_bytes(b"AAAAAAAAAA")
    card = {"bytes": 10, "sha256": hashlib.sha256(b"BBBBBBBBBB").hexdigest()}
    assert not mirror.is_current(str(fichier), card)


def test_an_absent_file_is_not_current(tmp_path):
    assert not mirror.is_current(str(tmp_path / "rien.webp"),
                                 {"bytes": 0, "sha256": ""})


# --- Forme du catalogue ----------------------------------------------------

def test_a_catalogue_of_another_version_is_refused():
    with pytest.raises(ValueError, match="version 1"):
        mirror.validate_manifest({"version": 1, "cards": []})


def test_a_catalogue_without_a_card_list_is_refused():
    with pytest.raises(ValueError, match="liste de cartes"):
        mirror.validate_manifest({"version": mirror.MANIFEST_VERSION})


def test_a_card_missing_a_required_field_names_the_card():
    """Un `KeyError` remontant d'un fil arrêterait toute la récupération sans
    dire quelle carte est fautive."""
    manifest = {"version": mirror.MANIFEST_VERSION,
                "cards": [{"id": "A1-227", "path": "a1/c.webp"}]}
    with pytest.raises(ValueError, match="A1-227"):
        mirror.validate_manifest(manifest)


# --- Ce qui manque ---------------------------------------------------------

def test_missing_cards_ignores_what_is_already_there(tmp_path):
    manifest, _ = manifeste({"A1": ["a1/un.webp", "a1/deux.webp"]})
    cible = tmp_path / "a1"
    cible.mkdir()
    (cible / "un.webp").write_bytes(image("a1/un.webp"))

    manquantes = mirror.missing_cards(manifest, str(tmp_path))
    assert [c["path"] for c in manquantes] == ["a1/deux.webp"]


def test_missing_bytes_counts_whole_archives(tmp_path):
    """Une archive est indivisible : il manquerait une seule carte de A1 que
    tout son poids partirait quand même. Annoncer la somme des images
    manquantes sous-estimerait le téléchargement."""
    manifest, _ = manifeste({"A1": ["a1/un.webp", "a1/deux.webp"],
                             "A2": ["a2/trois.webp"]})
    une_seule = [manifest["cards"][0]]
    assert (mirror.missing_bytes(manifest, une_seule)
            == manifest["mirror"]["sets"]["A1"]["bytes"])


# --- Récupération ----------------------------------------------------------

def test_fetching_writes_every_card(tmp_path, sert):
    manifest, table = manifeste({"A1": ["a1/un.webp", "a1/deux.webp"]})
    sert(table)

    tally, failures = mirror.fetch_mirror(manifest, str(tmp_path), workers=1)

    assert failures == []
    assert tally[mirror.Outcome.FETCHED] == 2
    assert (tmp_path / "a1" / "un.webp").read_bytes() == image("a1/un.webp")


def test_only_incomplete_sets_are_downloaded(tmp_path, sert):
    """Le découpage par extension existe pour ça : une extension complète ne
    doit rien coûter à la relance."""
    manifest, table = manifeste({"A1": ["a1/un.webp"], "A2": ["a2/deux.webp"]})
    (tmp_path / "a1").mkdir()
    (tmp_path / "a1" / "un.webp").write_bytes(image("a1/un.webp"))
    demandees = []
    sert({url: brut for url, brut in table.items()})
    vraie = mirror.urllib.request.urlopen

    def espion(request, timeout=None):
        demandees.append(request.full_url)
        return vraie(request, timeout=timeout)

    mirror.urllib.request.urlopen = espion
    try:
        mirror.fetch_mirror(manifest, str(tmp_path), workers=1)
    finally:
        mirror.urllib.request.urlopen = vraie

    assert demandees == ["https://miroir.test/a2.zip"]


def test_nothing_missing_costs_no_request(tmp_path, sert):
    manifest, _ = manifeste({"A1": ["a1/un.webp"]})
    (tmp_path / "a1").mkdir()
    (tmp_path / "a1" / "un.webp").write_bytes(image("a1/un.webp"))
    sert({})  # aucune adresse servie : toute requête lèverait un 404

    tally, failures = mirror.fetch_mirror(manifest, str(tmp_path), workers=1)
    assert failures == []
    assert tally[mirror.Outcome.KEPT] == 1


def test_a_tampered_archive_is_refused_whole(tmp_path, sert):
    """Une archive dont l'empreinte ne correspond pas ne doit rien écrire du
    tout : ses entrées ne sont pas plus dignes de confiance que son en-tête."""
    manifest, table = manifeste({"A1": ["a1/un.webp"]})
    table["https://miroir.test/a1.zip"] = archive({"a1/un.webp": b"autre chose"})
    sert(table)

    tally, failures = mirror.fetch_mirror(manifest, str(tmp_path), workers=1)

    assert not (tmp_path / "a1" / "un.webp").exists()
    assert failures and "altérée" in failures[0][1]
    assert tally.get(mirror.Outcome.FETCHED, 0) == 0


def test_an_archive_failure_is_reported_once_not_per_card(tmp_path, sert):
    """Quatre cent quarante et une lignes « 404 » identiques noieraient la seule
    information utile, la cause."""
    manifest, _ = manifeste({"A1": [f"a1/{n}.webp" for n in range(30)]})
    sert({})

    _, failures = mirror.fetch_mirror(manifest, str(tmp_path), workers=1)

    assert len(failures) == 1
    assert "30 cartes" in failures[0][0]


def test_a_set_absent_from_the_mirror_is_named(tmp_path, sert):
    manifest, table = manifeste({"A1": ["a1/un.webp"]})
    del manifest["mirror"]["sets"]["A1"]
    sert(table)

    _, failures = mirror.fetch_mirror(manifest, str(tmp_path), workers=1)
    assert failures and "absente du miroir" in failures[0][1]


def test_a_card_absent_from_its_archive_is_named(tmp_path, sert):
    manifest, table = manifeste({"A1": ["a1/un.webp"]})
    manifest["cards"].append({"path": "a1/fantome.webp", "set": "A1",
                              "bytes": 1, "sha256": "0" * 64})
    sert(table)

    _, failures = mirror.fetch_mirror(manifest, str(tmp_path), workers=1)
    assert ("a1/fantome.webp", "absente de l'archive") in failures


def test_an_entry_named_to_escape_the_folder_has_no_effect(tmp_path, sert):
    """Le chemin d'écriture vient du manifeste, jamais de l'archive."""
    manifest, table = manifeste({"A1": ["a1/un.webp"]})
    contenus = {"a1/un.webp": image("a1/un.webp"),
                "../../evade.webp": b"charge"}
    brut = archive(contenus)
    manifest["mirror"]["sets"]["A1"].update(
        bytes=len(brut), sha256=hashlib.sha256(brut).hexdigest())
    table["https://miroir.test/a1.zip"] = brut
    sert(table)

    mirror.fetch_mirror(manifest, str(tmp_path), workers=1)

    assert (tmp_path / "a1" / "un.webp").exists()
    assert not (tmp_path.parent.parent / "evade.webp").exists()


def test_a_manifest_without_a_mirror_says_so(tmp_path):
    manifest, _ = manifeste({"A1": ["a1/un.webp"]})
    del manifest["mirror"]
    with pytest.raises(mirror.MirrorError, match="aucun miroir"):
        mirror.fetch_mirror(manifest, str(tmp_path))


def test_progress_is_reported_per_archive(tmp_path, sert):
    manifest, table = manifeste({"A1": ["a1/un.webp"], "A2": ["a2/deux.webp"]})
    sert(table)
    vus = []

    mirror.fetch_mirror(manifest, str(tmp_path), workers=1,
                        progress=lambda faits, total, jeu: vus.append(
                            (faits, total, jeu)))

    assert len(vus) == 2
    faits, total, _ = vus[-1]
    assert faits == total  # la barre finit pleine


def test_cancelling_stops_before_the_remaining_archives(tmp_path, sert):
    manifest, table = manifeste({f"A{n}": [f"a{n}/c.webp"] for n in range(1, 6)})
    sert(table)
    appels = []

    def annule():
        appels.append(1)
        return len(appels) > 1  # la première archive passe, pas les suivantes

    mirror.fetch_mirror(manifest, str(tmp_path), workers=1, cancelled=annule)

    ecrites = list(tmp_path.glob("*/c.webp"))
    assert len(ecrites) < 5


# --- Catalogue en ligne ----------------------------------------------------

def test_fetch_manifest_validates_what_it_receives(sert):
    manifest, _ = manifeste({"A1": ["a1/un.webp"]})
    url = mirror.manifest_url()
    sert({url: json.dumps(manifest).encode()})

    assert mirror.fetch_manifest()["cards"][0]["path"] == "a1/un.webp"


def test_an_absent_catalogue_is_an_explicit_error(sert):
    sert({})
    with pytest.raises(mirror.MirrorError, match="introuvable"):
        mirror.fetch_manifest()


def test_an_unreadable_catalogue_is_an_explicit_error(sert):
    sert({mirror.manifest_url(): b"ceci n'est pas du JSON"})
    with pytest.raises(mirror.MirrorError, match="illisible"):
        mirror.fetch_manifest()


def test_a_catalogue_of_another_version_is_refused_online(sert):
    """La balise porte la version : recevoir autre chose signifie que le miroir
    a bougé sous les pieds de l'application."""
    sert({mirror.manifest_url(): json.dumps({"version": 1, "cards": []}).encode()})
    with pytest.raises(mirror.MirrorError, match="version 1"):
        mirror.fetch_manifest()


def test_a_network_failure_is_an_explicit_error(sert):
    url = mirror.manifest_url()
    sert({}, erreurs={url: OSError("réseau coupé")})
    with pytest.raises(mirror.MirrorError, match="réseau coupé"):
        mirror.fetch_manifest()
