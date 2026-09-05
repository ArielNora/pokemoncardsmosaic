"""Les couleurs que Qt ne fournit pas, en version claire et sombre.

Qt adapte déjà tout seul `Window`, `Text`, `Base` et le reste : l'application
suit le mode du système sans qu'on écrive une ligne. Ce qui manque à sa palette,
c'est une notion d'**avertissement** et d'**erreur**, il n'existe pas de rôle
pour ça. Chercher une teinte unique qui tienne sur du blanc **et** sur du
quasi-noir donne un compromis médiocre des deux côtés : c'est précisément la
raison d'être des thèmes sombres.

D'où deux tables des mêmes **cinq rôles**, et non deux chartes graphiques.

Les widgets ne posent plus leur propre couleur : ils se marquent d'une propriété
`role`, et une feuille de style **globale** fait le reste. Un changement de mode
n'a donc qu'un seul endroit à toucher, au lieu d'aller réveiller chaque widget.
"""

from PySide6.QtCore import QEvent, QObject, Qt, QTimer
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

# Chaque rôle vaut dans les deux modes. Contraste vérifié par les tests : au
# moins 4,5:1 pour tout ce qui porte du texte, le seuil de lisibilité courant.
#
# ⚠️ `empty_bg` est posé en dur et non pris de `palette(alternate-base)` : ce
# rôle-là ne suit pas le mode sur toutes les plateformes, et les cases vides
# ressortaient en gris clair au milieu d'une fenêtre sombre.
LIGHT = {
    "warning": "#8a5a00",           # ambre foncé, sur fond clair
    "error": "#a03030",
    "ok": "#1b6b2a",                # 5,7:1, #2e7d32 n'atteignait que 4,5:1
    "banner_bg": "#fff8e1",
    "banner_fg": "#5a4500",
    "banner_border": "#e0c060",
    "cell_border": "#666666",
    "empty_border": "#828282",   # 3,2:1, #999 n'atteignait que 2,5:1
    "empty_text": "#6e6e6e",
    "empty_bg": "#e4e4e4",
    "button_bg": "#fbfbfb",
    "button_border": "#b6b6b6",
    "button_hover_bg": "#e9f0f8",
    "button_hover_border": "#4a86c8",
    "button_pressed_bg": "#d8e2ee",
    "button_off_bg": "#f1f1f1",
    "button_off_border": "#d6d6d6",
    "bar_bg": "#f4f4f4",
    "bar_border": "#c8c8c8",
}

DARK = {
    "warning": "#f0b429",           # ambre vif, sur fond sombre
    "error": "#ff7a7a",
    "ok": "#6ecb85",
    "banner_bg": "#3a3220",
    "banner_fg": "#f2dda0",
    "banner_border": "#6b5a2a",
    "cell_border": "#9a9a9a",
    "empty_border": "#7a7a7a",
    "empty_text": "#a8a8a8",
    "empty_bg": "#2b2b2b",
    "button_bg": "#3b3b3b",
    "button_border": "#5c5c5c",
    "button_hover_bg": "#4c525a",
    "button_hover_border": "#7fb0e8",
    "button_pressed_bg": "#2d3138",
    "button_off_bg": "#303030",
    "button_off_border": "#464646",
    "bar_bg": "#323232",
    "bar_border": "#4d4d4d",
}

# Les rôles que Qt, lui, connaît. On les pose nous-mêmes plutôt que de laisser
# le style les choisir : `setStyle("Fusion")` remplace la palette du système, et
# l'application perdrait son mode sombre. Les poser garantit aussi le **même
# rendu sur macOS, Windows et Linux**, qui est le but.
PALETTE_LIGHT = {
    "window": "#efefef", "window_text": "#1a1a1a",
    "base": "#ffffff", "alt_base": "#f5f5f5",
    "text": "#1a1a1a", "placeholder": "#8a8a8a",
    "button": "#fbfbfb", "button_text": "#1a1a1a",
    "highlight": "#3573b9", "highlight_text": "#ffffff",
    "tooltip_bg": "#fdfdf2", "tooltip_text": "#1a1a1a",
    "link": "#1a5fb4", "disabled_text": "#9a9a9a",
}

PALETTE_DARK = {
    "window": "#252525", "window_text": "#e6e6e6",
    "base": "#1c1c1c", "alt_base": "#232323",
    "text": "#e6e6e6", "placeholder": "#7d7d7d",
    "button": "#3b3b3b", "button_text": "#e6e6e6",
    "highlight": "#3a78c2", "highlight_text": "#ffffff",
    "tooltip_bg": "#2f2f2f", "tooltip_text": "#e6e6e6",
    "link": "#7fb0e8", "disabled_text": "#6b6b6b",
}

# Fonds de référence pour la vérification de contraste : ce sont désormais les
# fonds réels, puisque c'est nous qui les posons.
REFERENCE_BG = {"light": PALETTE_LIGHT["window"], "dark": PALETTE_DARK["window"]}


def is_dark(palette: QPalette) -> bool:
    """Le mode sombre est-il actif ?

    Déduit de la **clarté du fond** plutôt que de `QStyleHints.colorScheme()` :
    celle-ci rend `Unknown` dès qu'il n'y a pas de thème de plateforme, hors
    écran, par exemple, et il faudrait alors deviner quand même.

    ⚠️ **Un fond transparent ne dit rien du mode.** Une feuille de style qui
    pose `background: transparent` fait porter au widget un `Window` noir
    d'alpha nul : sa clarté vaut zéro, et le mode clair se lisait sombre. On
    retombe alors sur la palette de l'application, qui est celle qu'on a posée.
    """
    couleur = palette.color(QPalette.Window)
    if couleur.alpha() == 0:
        application = QApplication.instance()
        if application is not None:
            couleur = application.palette().color(QPalette.Window)
    return couleur.lightness() < 128


def colours(palette: QPalette) -> dict:
    return DARK if is_dark(palette) else LIGHT


def mix(base: str, other: str, part: float) -> str:
    """`part` de `other` versé dans `base`, en hexadécimal.

    De quoi teinter un fond sans quitter le mode : la couleur d'un état posée
    telle quelle ferait un aplat vif au milieu d'une fenêtre sombre, et le texte
    n'y tiendrait plus. Diluée, elle **colore** sans repeindre.
    """
    fond, teinte = QColor(base), QColor(other)
    part = max(0.0, min(1.0, part))
    return QColor(
        round(fond.red() + (teinte.red() - fond.red()) * part),
        round(fond.green() + (teinte.green() - fond.green()) * part),
        round(fond.blue() + (teinte.blue() - fond.blue()) * part),
    ).name()


# Ce qu'un onglet emprunte à la couleur de son état : peu pour le fond, beaucoup
# pour le contour. ⚠️ **Le contour porte la couleur, le fond la rappelle**, un
# fond aussi franc que le trait ferait un bandeau coloré où le texte, noir ou
# blanc selon le mode, perdrait son contraste.
# ⚠️ **Les parts sont mesurées, pas choisies à l'œil.** À 34 % sur l'onglet
# ouvert, la pastille rouge tombait à 2,6:1 sur son propre fond rouge, sous le
# seuil de 3:1 des éléments non textuels. À 24 % elle tient à 3,1:1, et le fond
# de l'onglet ouvert reste **le double** de celui des autres : c'est le contour,
# plein et plus épais, qui dit surtout la sélection.
TAB_FILL, TAB_BORDER = 0.12, 0.70
TAB_FILL_ON, TAB_BORDER_ON = 0.24, 1.0


def tab_box(state: str, palette: QPalette, selected: bool = False,
            locked: bool = False) -> tuple[str, str, float]:
    """Fond, contour et épaisseur du cadre d'un onglet, selon son état.

    Verrouillé, l'onglet garde le gris des choses inertes : sa couleur dirait
    un état sur lequel on ne peut rien.
    """
    c = colours(palette)
    if locked:
        return c["button_off_bg"], c["button_off_border"], 1.0
    teinte = c[state]
    if selected:
        return (mix(c["button_bg"], teinte, TAB_FILL_ON),
                mix(c["button_border"], teinte, TAB_BORDER_ON), 2.0)
    return (mix(c["button_bg"], teinte, TAB_FILL),
            mix(c["button_border"], teinte, TAB_BORDER), 1.4)


def qt_palette(dark: bool) -> QPalette:
    """La palette Qt du mode voulu, construite de bout en bout.

    Les rôles désactivés sont posés à part : sans eux, Fusion grise un libellé
    en le mélangeant au fond, ce qui donne un texte à peine plus pâle et non un
    texte visiblement inerte.
    """
    from PySide6.QtGui import QColor

    c = PALETTE_DARK if dark else PALETTE_LIGHT
    palette = QPalette()
    for role, cle in (
        (QPalette.Window, "window"), (QPalette.WindowText, "window_text"),
        (QPalette.Base, "base"), (QPalette.AlternateBase, "alt_base"),
        (QPalette.Text, "text"), (QPalette.PlaceholderText, "placeholder"),
        (QPalette.Button, "button"), (QPalette.ButtonText, "button_text"),
        (QPalette.BrightText, "highlight_text"),
        (QPalette.Highlight, "highlight"),
        (QPalette.HighlightedText, "highlight_text"),
        (QPalette.ToolTipBase, "tooltip_bg"), (QPalette.ToolTipText, "tooltip_text"),
        (QPalette.Link, "link"),
    ):
        palette.setColor(role, QColor(c[cle]))
    for role in (QPalette.Text, QPalette.WindowText, QPalette.ButtonText):
        palette.setColor(QPalette.Disabled, role, QColor(c["disabled_text"]))
    return palette


# Palette que le système avait posée, retenue au premier passage. Voir
# `remember_system` pour la raison.
_SYSTEM_PALETTE: QPalette | None = None


def remember_system(app) -> None:
    """Retient la palette du système, avant que nous ne posions la nôtre.

    ⚠️ Sans elle, le repli de `system_is_dark` relit `app.palette()` : devenue
    **la nôtre** dès le premier `apply`, et confirme donc toujours le mode
    courant. Sur un bureau où `colorScheme()` rend `Unknown`, une bascule en
    cours d'exécution ne pouvait plus être détectée : l'application restait
    définitivement dans le mode où elle avait démarré.
    """
    global _SYSTEM_PALETTE
    if _SYSTEM_PALETTE is None:
        _SYSTEM_PALETTE = QPalette(app.palette())


def forget_system() -> None:
    """Oublie la palette retenue. Pour les tests, qui partagent une QApplication."""
    global _SYSTEM_PALETTE
    _SYSTEM_PALETTE = None


def system_is_dark(app) -> bool:
    """Le système est-il en mode sombre ?

    `colorScheme()` d'abord, qui est la réponse directe et suit les bascules.
    À défaut : certains bureaux, et le mode hors écran, ne répondent pas, la
    clarté du fond que le système avait posé **avant** notre palette.
    """
    from PySide6.QtCore import Qt

    scheme = app.styleHints().colorScheme()
    if scheme == Qt.ColorScheme.Dark:
        return True
    if scheme == Qt.ColorScheme.Light:
        return False
    reference = _SYSTEM_PALETTE if _SYSTEM_PALETTE is not None else app.palette()
    return is_dark(reference)


# L'aura d'un élément prêt, et celle d'un élément qui attend encore quelque
# chose. ⚠️ **Le rouge est moins fort que le vert** : il dit « il reste à
# faire », pas « c'est cassé ». Vu aussi vif que l'invitation à continuer, il
# donnerait à tout le parcours l'air d'une suite d'erreurs.
GLOW_RADIUS, GLOW_ALPHA = 26, 220
GLOW_RADIUS_WAITING, GLOW_ALPHA_WAITING = 16, 130
# La place à laisser autour d'un élément pour que son aura ne soit pas rognée.
GLOW_ROOM = 10


def set_glow(effect, palette: QPalette, ready: bool) -> None:
    """Pose sur `effect` l'aura de l'état demandé.

    ⚠️ **Une couleur figée dans un effet ne suit pas le mode.** Tout ce qui se
    lit au moment du dessin change de mode tout seul ; l'aura, elle, garde la
    teinte qu'on lui a posée. Les appelants la reposent donc sur
    `PaletteChange`.
    """
    c = colours(palette)
    couleur = QColor(c["ok"] if ready else c["error"])
    couleur.setAlpha(GLOW_ALPHA if ready else GLOW_ALPHA_WAITING)
    effect.setColor(couleur)
    effect.setBlurRadius(GLOW_RADIUS if ready else GLOW_RADIUS_WAITING)


def stylesheet(palette: QPalette) -> str:
    """La feuille globale, écrite pour les propriétés `role` des widgets."""
    c = colours(palette)
    return f"""
QLabel[role="warning"] {{ color: {c["warning"]}; }}
QLabel[role="error"] {{ color: {c["error"]}; }}
QLabel[role="ok"] {{ color: {c["ok"]}; }}
QLabel[role="banner"] {{
    background: {c["banner_bg"]};
    color: {c["banner_fg"]};
    border: 1px solid {c["banner_border"]};
    border-radius: 4px;
    padding: 6px;
}}
/* Une ligne d'arrêt porte l'aura de son état : verte cochée, rouge sinon.
   ⚠️ **Il lui faut un fond opaque.** Une aura posée sur un cadre transparent
   ne halo que les lettres, une par une, au lieu d'entourer la ligne. */
QFrame[role="stop-line"] {{
    background: palette(window);
    border: 1px solid {c["cell_border"]};
    border-radius: 6px;
}}
QFrame[role="cell"] {{ border: 1px solid {c["cell_border"]}; }}
QFrame[role="cell-empty"] {{
    border: 1px dashed {c["empty_border"]};
    background: {c["empty_bg"]};
}}
QFrame[role="cell"] QLabel {{ border: none; }}
QFrame[role="cell-empty"] QLabel {{ border: none; color: {c["empty_text"]}; }}

/* Mise en forme, pas couleur : la feuille globale reste le seul endroit d'où
   un widget reçoit son habillage. Sans ce calage, le champ de recherche paraît
   écrasé à côté de la liste déroulante voisine, qui se dimensionne seule. */
QLineEdit[role="search"] {{ padding: 5px 7px; }}

/* ⚠️ Décrire les boutons **entièrement**, et pas seulement leur survol.
   Une règle `:hover` isolée fait dessiner cet état-là par la feuille pendant que
   les autres restent natifs : le bouton change de forme en passant dessus, ce
   qui est pire que pas de survol du tout. En les décrivant en entier, on assume
   leur apparence, et le survol devient une simple variation de la même.
   Le texte, lui, reste `palette(button-text)` : il suit le système. */
QPushButton, QToolButton {{
    background: {c["button_bg"]};
    border: 1px solid {c["button_border"]};
    border-radius: 5px;
    padding: 4px 12px;
}}
QPushButton:hover, QToolButton:hover {{
    background: {c["button_hover_bg"]};
    border-color: {c["button_hover_border"]};
}}
QPushButton:pressed, QToolButton:pressed {{
    background: {c["button_pressed_bg"]};
}}
QPushButton:disabled, QToolButton:disabled {{
    background: {c["button_off_bg"]};
    border-color: {c["button_off_border"]};
}}

/* Les boutons minuscules posés sur un dessin, ajouter, retirer une feuille.
   Le calage ordinaire des boutons leur mange toute leur largeur : sur trente
   pixels, douze de marge de chaque côté ne laissent rien au signe. */
QPushButton[role="mini"] {{
    padding: 0px;
    font-weight: bold;
}}

/* Les parties d'une étape, à gauche. Des lignes de liste ordinaires ne se
   lisaient pas comme des onglets : hautes de dix-huit pixels et collées les
   unes aux autres, elles ressemblaient à un contenu à faire défiler. On leur
   donne la taille d'un bouton, un fond, et de l'air entre elles. */
QListWidget[role="tabs"] {{
    background: transparent;
    border: none;
    outline: none;
}}
/* ⚠️ La marge basse est reprise par `layout_step.BOX_BOTTOM_MARGIN` : le trait
   qui relie les onglets de second rang s'arrête au bas du dessin du dernier, et
   non au bas de sa ligne. La changer ici sans l'y changer le ferait dépasser. */
/* ⚠️ **Ni fond ni contour ici** : c'est `layout_step.TabDelegate` qui les
   dessine, chaque onglet portant la couleur de son état, une feuille de style
   ne sait pas viser une ligne en particulier. Ne restent que les mesures, qui
   ne peignent rien, et la couleur du texte : noire ou blanche selon le mode,
   dans tous les états. */
QListWidget[role="tabs"]::item {{
    background: transparent;
    border: none;
    padding: 14px 12px;
    margin: 0px 2px 8px 2px;
}}
QListWidget[role="tabs"]::item:selected {{
    color: palette(text);
}}

/* La barre d'actions posée sur la galerie. Opaque et bordée : par-dessus des
   illustrations, un fond translucide laisse lire la carte au travers et les
   boutons deviennent illisibles. */
QWidget[role="floating-bar"] {{
    background: {c["bar_bg"]};
    border: 1px solid {c["bar_border"]};
    border-radius: 6px;
}}
"""


def apply(app) -> None:
    """Pose la palette du mode courant, puis la feuille globale par-dessus."""
    remember_system(app)
    app.setPalette(qt_palette(system_is_dark(app)))
    app.setStyleSheet(stylesheet(app.palette()))


def follow_system(app) -> None:
    """Suit les bascules clair/sombre pendant que l'application tourne.

    ⚠️ Le recalcul est **différé d'un tour de boucle**. `colorSchemeChanged` peut
    précéder la mise à jour de la palette, et décider à ce moment-là relirait
    l'ancien fond : l'application resterait dans les couleurs du mode qu'on vient
    de quitter jusqu'à la bascule suivante.
    """
    app.styleHints().colorSchemeChanged.connect(
        lambda _=None: QTimer.singleShot(0, lambda: apply(app))
    )


def mark(widget, role: str) -> None:
    """Attribue un rôle à un widget, et le fait repeindre, **descendants
    compris**.

    Qt n'évalue les sélecteurs de propriété qu'au « polish » : changer la
    propriété ensuite ne repeint rien tant qu'on ne le lui demande pas.

    Les descendants sont repolis aussi. La feuille porte des règles qui les
    visent : `QFrame[role="cell-empty"] QLabel`, donc leur style dépend d'une
    propriété que l'ancêtre porte, et Qt ne les repolit pas de lui-même.

    Aujourd'hui l'effet visible est le même sans ce parcours : une case remplie
    n'affiche aucun texte, donc sa couleur ne se voit pas. C'est un accident de
    la mise en forme actuelle, pas une garantie, afficher un jour le nom sous
    la vignette suffirait à faire ressortir le style de l'état précédent.
    """
    from PySide6.QtWidgets import QWidget

    widget.setProperty("role", role)
    style = widget.style()
    for cible in (widget, *widget.findChildren(QWidget)):
        style.unpolish(cible)
        style.polish(cible)


class ClickableCursor(QObject):
    """Donne à tout bouton le curseur en main, et le retire quand il est inerte.

    Posé à l'échelle de l'application plutôt que bouton par bouton : il y en a
    une quarantaine, répartis sur cinq écrans et trois dialogues, et en oublier
    un ne se verrait pas.

    Le curseur est un signal que la feuille de style ne sait pas donner, Qt
    n'admet pas de propriété `cursor`, et il vient **en plus** du survol coloré,
    pas à sa place.
    """

    def eventFilter(self, watched, event):
        from PySide6.QtWidgets import QAbstractButton

        if isinstance(watched, QAbstractButton) and event.type() in (
                QEvent.Polish, QEvent.EnabledChange):
            # Rien sur un bouton inerte : promettre un clic qui ne se produira
            # pas est pire que de ne rien promettre.
            watched.setCursor(Qt.PointingHandCursor if watched.isEnabled()
                              else Qt.ArrowCursor)
        return super().eventFilter(watched, event)
