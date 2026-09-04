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


def test_a_transparent_background_says_nothing_of_the_mode(qt_app):
    """⚠️ Une feuille de style qui pose `background: transparent` fait porter au
    widget un `Window` noir d'alpha nul : sa clarté vaut zéro, et le mode clair
    se lisait **sombre** — les onglets sortaient teintés pour l'autre mode."""
    from PySide6.QtGui import QColor, QPalette

    from pokemon_mosaic.ui import theme

    qt_app.setPalette(theme.qt_palette(False))
    invisible = QPalette()
    invisible.setColor(QPalette.Window, QColor(0, 0, 0, 0))
    assert not theme.is_dark(invisible)

    qt_app.setPalette(theme.qt_palette(True))
    assert theme.is_dark(invisible)


def test_a_tinted_tab_keeps_its_text_readable():
    """⚠️ Le cadre d'un onglet emprunte la couleur de son état : le texte, lui,
    reste celui du mode. On vérifie qu'il tient sur les trois fonds teintés,
    sélectionné compris — une teinte trop franche ferait un bandeau coloré où le
    noir ou le blanc se perdrait."""
    from pokemon_mosaic.ui import theme

    for mode, table, palette_table in (("light", theme.LIGHT, theme.PALETTE_LIGHT),
                                       ("dark", theme.DARK, theme.PALETTE_DARK)):
        palette = theme.qt_palette(mode == "dark")
        for role in ("error", "warning", "ok"):
            for selection in (False, True):
                fond, contour, _ = theme.tab_box(role, palette, selection)
                assert contraste(palette_table["text"], fond) >= 4.5, (
                    mode, role, selection, fond)
                # Le contour doit aussi se détacher du fond de la fenêtre.
                assert contraste(contour, palette_table["window"]) >= 3.0, (
                    mode, role, contour)
                assert fond != table[role], "la teinte pure ferait un aplat"


def test_the_state_badge_stands_out_on_its_tinted_tab():
    """La pastille est le seul signe non textuel de l'état : elle se pose sur le
    fond teinté du même état, celui-là même qui la tire vers lui. Seuil des
    éléments non textuels, 3:1."""
    from pokemon_mosaic.ui import theme

    for mode, table in (("light", theme.LIGHT), ("dark", theme.DARK)):
        palette = theme.qt_palette(mode == "dark")
        for role in ("error", "warning", "ok"):
            for selection in (False, True):
                fond, _, _ = theme.tab_box(role, palette, selection)
                assert contraste(table[role], fond) >= 3.0, (
                    mode, role, selection, fond)


def test_the_tint_is_stronger_on_the_border_than_on_the_fill():
    """Le contour porte la couleur, le fond la rappelle."""
    from pokemon_mosaic.ui import theme

    assert theme.TAB_BORDER > theme.TAB_FILL
    assert theme.TAB_BORDER_ON > theme.TAB_FILL_ON


def test_mixing_stays_between_the_two_colours():
    from pokemon_mosaic.ui import theme

    assert theme.mix("#000000", "#ffffff", 0.0) == "#000000"
    assert theme.mix("#000000", "#ffffff", 1.0) == "#ffffff"
    assert theme.mix("#000000", "#ffffff", 0.5) == "#808080"
    # Bornée : une part hors [0, 1] rendrait une couleur hors des deux.
    assert theme.mix("#000000", "#ffffff", 5.0) == "#ffffff"


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

TEXTES = ("warning", "error", "ok")


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
    for role in ("warning", "error", "ok", "banner", "cell", "cell-empty"):
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


# --- La palette Qt, posée par nous ----------------------------------------

def test_both_qt_palettes_define_the_same_roles():
    assert set(theme.PALETTE_LIGHT) == set(theme.PALETTE_DARK)


def test_the_two_qt_palettes_really_differ():
    from PySide6.QtGui import QPalette

    clair, sombre = theme.qt_palette(False), theme.qt_palette(True)
    assert clair.color(QPalette.Window) != sombre.color(QPalette.Window)
    assert clair.color(QPalette.Text) != sombre.color(QPalette.Text)


def test_disabled_text_is_visibly_weaker_than_normal_text():
    """Sans rôle désactivé posé, Fusion mélange le libellé au fond : on obtient
    un texte à peine plus pâle, pas un texte visiblement inerte."""
    for table in (theme.PALETTE_LIGHT, theme.PALETTE_DARK):
        fort = contraste(table["text"], table["window"])
        faible = contraste(table["disabled_text"], table["window"])
        assert faible < fort / 1.8


@pytest.mark.parametrize("table", [theme.PALETTE_LIGHT, theme.PALETTE_DARK])
def test_the_ordinary_text_is_legible_on_its_own_window(table):
    assert contraste(table["text"], table["window"]) >= 4.5


@pytest.mark.parametrize("table", [theme.PALETTE_LIGHT, theme.PALETTE_DARK])
def test_the_selection_text_is_legible_on_the_highlight(table):
    assert contraste(table["highlight_text"], table["highlight"]) >= 4.5


def test_the_scheme_is_decided_before_our_palette_replaces_the_system_one(qt_app):
    """Sinon la question se mord la queue : on lirait le fond qu'on vient
    justement de poser."""
    from PySide6.QtGui import QPalette

    original = qt_app.palette()
    try:
        qt_app.setPalette(theme.qt_palette(dark=True))
        assert theme.is_dark(qt_app.palette())
        assert theme.colours(qt_app.palette()) is theme.DARK
    finally:
        qt_app.setPalette(original)
    assert original.color(QPalette.Window).isValid()


# --- Le curseur des boutons -----------------------------------------------

def test_a_button_gets_the_pointing_cursor(qt_app):
    """Un second signal, que la feuille de style ne sait pas donner : Qt
    n'admet pas de propriété `cursor`."""
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QPushButton

    filtre = theme.ClickableCursor()
    qt_app.installEventFilter(filtre)
    try:
        bouton = QPushButton("essai")
        bouton.show()
        qt_app.processEvents()
        assert bouton.cursor().shape() == Qt.PointingHandCursor
    finally:
        qt_app.removeEventFilter(filtre)


def test_a_disabled_button_loses_the_pointing_cursor(qt_app):
    """Promettre un clic qui ne se produira pas est pire que ne rien promettre."""
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QPushButton

    filtre = theme.ClickableCursor()
    qt_app.installEventFilter(filtre)
    try:
        bouton = QPushButton("essai")
        bouton.show()
        qt_app.processEvents()
        bouton.setEnabled(False)
        qt_app.processEvents()
        assert bouton.cursor().shape() == Qt.ArrowCursor
    finally:
        qt_app.removeEventFilter(filtre)


def test_the_stylesheet_gives_buttons_a_hover_state():
    """C'est ce qui manquait : le style natif de macOS dessine exactement les
    mêmes pixels survolé ou non — mesuré, 0 sur 3600."""
    feuille = theme.stylesheet(palette_pour("#1e1e1e"))
    assert "QPushButton:hover" in feuille
    assert theme.DARK["button_hover_bg"] in feuille
    assert theme.DARK["button_hover_border"] in feuille


def test_a_scheme_change_is_still_detectable_after_our_palette_is_installed(qt_app):
    """Sans mémoriser la palette du système, le repli relit la nôtre et confirme
    toujours le mode courant : sur un bureau où `colorScheme()` rend `Unknown`,
    une bascule ne pouvait plus être vue et l'application restait définitivement
    dans le mode où elle avait démarré."""
    from PySide6.QtGui import QColor, QPalette

    original = qt_app.palette()
    theme.forget_system()
    try:
        clair = QPalette()
        clair.setColor(QPalette.Window, QColor("#efefef"))
        qt_app.setPalette(clair)
        theme.remember_system(qt_app)

        # Notre palette sombre s'installe : le repli ne doit pas la relire.
        qt_app.setPalette(theme.qt_palette(dark=True))
        assert not theme.system_is_dark(qt_app), \
            "le repli a relu notre propre palette"
    finally:
        theme.forget_system()
        qt_app.setPalette(original)


def test_the_remembered_palette_is_the_first_one_seen(qt_app):
    """Retenue une fois : la rafraîchir à chaque `apply` reviendrait au défaut."""
    from PySide6.QtGui import QColor, QPalette

    original = qt_app.palette()
    theme.forget_system()
    try:
        clair = QPalette()
        clair.setColor(QPalette.Window, QColor("#efefef"))
        qt_app.setPalette(clair)
        theme.remember_system(qt_app)
        qt_app.setPalette(theme.qt_palette(dark=True))
        theme.remember_system(qt_app)          # second appel : sans effet
        assert not theme.system_is_dark(qt_app)
    finally:
        theme.forget_system()
        qt_app.setPalette(original)
