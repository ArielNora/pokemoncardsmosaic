"""Les couleurs que Qt ne fournit pas, en version claire et sombre.

Qt adapte déjà tout seul `Window`, `Text`, `Base` et le reste : l'application
suit le mode du système sans qu'on écrive une ligne. Ce qui manque à sa palette,
c'est une notion d'**avertissement** et d'**erreur** — il n'existe pas de rôle
pour ça. Chercher une teinte unique qui tienne sur du blanc **et** sur du
quasi-noir donne un compromis médiocre des deux côtés : c'est précisément la
raison d'être des thèmes sombres.

D'où deux tables des mêmes **cinq rôles**, et non deux chartes graphiques.

Les widgets ne posent plus leur propre couleur : ils se marquent d'une propriété
`role`, et une feuille de style **globale** fait le reste. Un changement de mode
n'a donc qu'un seul endroit à toucher, au lieu d'aller réveiller chaque widget.
"""

from PySide6.QtCore import QTimer
from PySide6.QtGui import QPalette

# Chaque rôle vaut dans les deux modes. Contraste vérifié par les tests : au
# moins 4,5:1 pour tout ce qui porte du texte, le seuil de lisibilité courant.
#
# ⚠️ `empty_bg` est posé en dur et non pris de `palette(alternate-base)` : ce
# rôle-là ne suit pas le mode sur toutes les plateformes, et les cases vides
# ressortaient en gris clair au milieu d'une fenêtre sombre.
LIGHT = {
    "warning": "#8a5a00",           # ambre foncé, sur fond clair
    "error": "#a03030",
    "banner_bg": "#fff8e1",
    "banner_fg": "#5a4500",
    "banner_border": "#e0c060",
    "cell_border": "#666666",
    "empty_border": "#828282",   # 3,2:1 — #999 n'atteignait que 2,5:1
    "empty_text": "#6e6e6e",
    "empty_bg": "#e4e4e4",
}

DARK = {
    "warning": "#f0b429",           # ambre vif, sur fond sombre
    "error": "#ff7a7a",
    "banner_bg": "#3a3220",
    "banner_fg": "#f2dda0",
    "banner_border": "#6b5a2a",
    "cell_border": "#9a9a9a",
    "empty_border": "#7a7a7a",
    "empty_text": "#a8a8a8",
    "empty_bg": "#2b2b2b",
}

# Fonds de référence pour la vérification de contraste. Ce ne sont pas des
# valeurs utilisées à l'affichage — le vrai fond vient de la palette système —
# mais les pires cas plausibles de chaque mode.
REFERENCE_BG = {"light": "#efefef", "dark": "#1e1e1e"}


def is_dark(palette: QPalette) -> bool:
    """Le mode sombre est-il actif ?

    Déduit de la **clarté du fond** plutôt que de `QStyleHints.colorScheme()` :
    celle-ci rend `Unknown` dès qu'il n'y a pas de thème de plateforme — hors
    écran, par exemple —, et il faudrait alors deviner quand même.
    """
    return palette.color(QPalette.Window).lightness() < 128


def colours(palette: QPalette) -> dict:
    return DARK if is_dark(palette) else LIGHT


def stylesheet(palette: QPalette) -> str:
    """La feuille globale, écrite pour les propriétés `role` des widgets."""
    c = colours(palette)
    return f"""
QLabel[role="warning"] {{ color: {c["warning"]}; }}
QLabel[role="error"] {{ color: {c["error"]}; }}
QLabel[role="banner"] {{
    background: {c["banner_bg"]};
    color: {c["banner_fg"]};
    border: 1px solid {c["banner_border"]};
    border-radius: 4px;
    padding: 6px;
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
"""


def apply(app) -> None:
    """Pose la feuille globale, et la repose quand le système change de mode."""
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
    """Attribue un rôle à un widget, et le fait repeindre — **descendants
    compris**.

    Qt n'évalue les sélecteurs de propriété qu'au « polish » : changer la
    propriété ensuite ne repeint rien tant qu'on ne le lui demande pas.

    Les descendants sont repolis aussi. La feuille porte des règles qui les
    visent — `QFrame[role="cell-empty"] QLabel` —, donc leur style dépend d'une
    propriété que l'ancêtre porte, et Qt ne les repolit pas de lui-même.

    Aujourd'hui l'effet visible est le même sans ce parcours : une case remplie
    n'affiche aucun texte, donc sa couleur ne se voit pas. C'est un accident de
    la mise en forme actuelle, pas une garantie — afficher un jour le nom sous
    la vignette suffirait à faire ressortir le style de l'état précédent.
    """
    from PySide6.QtWidgets import QWidget

    widget.setProperty("role", role)
    style = widget.style()
    for cible in (widget, *widget.findChildren(QWidget)):
        style.unpolish(cible)
        style.polish(cible)
