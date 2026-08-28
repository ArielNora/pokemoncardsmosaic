"""Tests du thème : les deux palettes, et leur lisibilité.

Le contraste est **calculé**, pas jugé à l'œil. Une couleur choisie sur fond
clair et laissée telle quelle sur fond sombre reste parfaitement valide au sens
du code, et illisible à l'écran : seul un seuil chiffré attrape ce défaut-là.
"""

import pytest
from PySide6.QtGui import QColor, QPalette

from pokemon_mosaic.ui import theme


def luminance(couleur: str) -> float:
    """Luminance relative, au sens de la norme d'accessibilité WCAG."""
    canaux = []
    for valeur in QColor(couleur).getRgbF()[:3]:
        canaux.append(valeur / 12.92 if valeur <= 0.03928
                      else ((valeur + 0.055) / 1.055) ** 2.4)
    rouge, vert, bleu = canaux
    return 0.2126 * rouge + 0.7152 * vert + 0.0722 * bleu


def contraste(avant: str, arriere: str) -> float:
    a, b = luminance(avant), luminance(arriere)
    clair, sombre = max(a, b), min(a, b)
    return (clair + 0.05) / (sombre + 0.05)


def palette_pour(fond: str) -> QPalette:
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(fond))
    return palette


# --- Les deux tables décrivent les mêmes rôles ----------------------------

def test_both_schemes_define_exactly_the_same_roles():
    """Un rôle présent d'un seul côté produirait une feuille de style trouée
    dans l'autre mode — sans erreur, la couleur retombant sur le défaut de Qt."""
    assert set(theme.LIGHT) == set(theme.DARK)


def test_no_role_shares_its_colour_between_the_two_schemes():
    """Une valeur identique des deux côtés signale une couleur qu'on a oublié
    de décliner, ce qui est précisément le défaut qu'on corrige ici."""
    identiques = [role for role in theme.LIGHT
                  if theme.LIGHT[role] == theme.DARK[role]]
    assert identiques == []


# --- Lisibilité ------------------------------------------------------------

TEXTES = ("warning", "error")


@pytest.mark.parametrize("role", TEXTES)
def test_text_roles_are_legible_in_light_mode(role):
    assert contraste(theme.LIGHT[role], theme.REFERENCE_BG["light"]) >= 4.5


@pytest.mark.parametrize("role", TEXTES)
def test_text_roles_are_legible_in_dark_mode(role):
    assert contraste(theme.DARK[role], theme.REFERENCE_BG["dark"]) >= 4.5


def test_the_banner_is_legible_on_its_own_background():
    """Le seul cas où le fond est posé par nous : il se vérifie contre lui-même
    et non contre le fond de la fenêtre."""
    for table in (theme.LIGHT, theme.DARK):
        assert contraste(table["banner_fg"], table["banner_bg"]) >= 4.5


@pytest.mark.parametrize("role", ["cell_border", "empty_border", "empty_text"])
def test_the_editor_outlines_stand_out_from_the_background(role):
    """Une bordure n'a pas à atteindre le seuil d'un texte, mais doit se voir :
    3:1 est le seuil retenu pour les éléments non textuels."""
    assert contraste(theme.LIGHT[role], theme.REFERENCE_BG["light"]) >= 3.0
    assert contraste(theme.DARK[role], theme.REFERENCE_BG["dark"]) >= 3.0


# --- Détection du mode -----------------------------------------------------

def test_a_dark_window_selects_the_dark_table():
    assert theme.is_dark(palette_pour("#1e1e1e"))
    assert theme.colours(palette_pour("#1e1e1e")) is theme.DARK


def test_a_light_window_selects_the_light_table():
    assert not theme.is_dark(palette_pour("#efefef"))
    assert theme.colours(palette_pour("#efefef")) is theme.LIGHT


def test_the_scheme_is_read_from_the_palette_not_the_style_hints(qt_app):
    """`QStyleHints.colorScheme()` rend `Unknown` sans thème de plateforme —
    hors écran, par exemple. La clarté du fond, elle, est toujours lisible."""
    from PySide6.QtCore import Qt

    assert qt_app.styleHints().colorScheme() == Qt.ColorScheme.Unknown
    assert theme.colours(palette_pour("#101010")) is theme.DARK


# --- La feuille de style ---------------------------------------------------

def test_the_stylesheet_carries_the_colours_of_its_scheme():
    sombre = theme.stylesheet(palette_pour("#1e1e1e"))
    assert theme.DARK["warning"] in sombre
    assert theme.LIGHT["warning"] not in sombre


def test_every_role_used_by_a_widget_appears_in_the_stylesheet():
    """Un rôle posé par `mark()` mais absent de la feuille ne colorerait rien,
    en silence."""
    feuille = theme.stylesheet(palette_pour("#efefef"))
    for role in ("warning", "error", "banner", "cell", "cell-empty"):
        assert f'[role="{role}"]' in feuille


def test_marking_a_widget_sets_the_property(qt_app):
    from PySide6.QtWidgets import QLabel

    label = QLabel()
    theme.mark(label, "warning")
    assert label.property("role") == "warning"


def test_marking_again_replaces_the_previous_role(qt_app):
    """La case de l'éditeur bascule entre « remplie » et « vide » : garder
    l'ancien rôle empilerait deux styles contradictoires."""
    from PySide6.QtWidgets import QFrame

    case = QFrame()
    theme.mark(case, "cell-empty")
    theme.mark(case, "cell")
    assert case.property("role") == "cell"


def test_the_search_field_gets_breathing_room():
    """Sans calage, le champ de recherche paraît écrasé à côté de la liste
    déroulante voisine, qui se dimensionne toute seule."""
    feuille = theme.stylesheet(palette_pour("#efefef"))
    assert 'QLineEdit[role="search"]' in feuille
    assert "padding" in feuille


def test_the_empty_cell_background_is_a_role_not_a_palette_lookup():
    """`palette(alternate-base)` ne suit pas le mode sur toutes les plateformes :
    les cases vides ressortaient en gris clair au milieu d'une fenêtre sombre."""
    sombre = theme.stylesheet(palette_pour("#1e1e1e"))
    assert "palette(alternate-base)" not in sombre
    assert theme.DARK["empty_bg"] in sombre
