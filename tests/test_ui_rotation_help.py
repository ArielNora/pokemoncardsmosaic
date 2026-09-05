"""Tests du schéma expliquant le demi-tour.

Ce que le schéma affirme doit rester vrai du code : c'est `Link.reversed_cards`
qui décide de la rotation, et un dessin qui la décrirait autrement induirait en
erreur plus sûrement qu'une phrase floue.
"""

from PySide6.QtWidgets import QLabel


def places(bloc) -> dict:
    """Table (ligne, colonne) -> lettre, lue dans la disposition elle-même.

    ⚠️ Pas `findChildren(QFrame)` : `QLabel` **hérite** de `QFrame`, si bien
    qu'on ramasse les cases et leur contenu mélangés. Et pas l'ordre des enfants
    non plus, que rien ne garantit : la position posée dans la grille est la
    seule source sûre.
    """
    grille = bloc.layout()
    trouvees = {}
    for position in range(grille.count()):
        ligne, colonne, _, _ = grille.getItemPosition(position)
        case = grille.itemAt(position).widget()
        trouvees[(ligne, colonne)] = case.findChild(QLabel).text()
    return trouvees


def lettres(bloc) -> list[str]:
    """Les marques du bloc, en ordre de lecture."""
    return [lettre for _, lettre in sorted(places(bloc).items())]


def test_a_row_reverses(qt_app):
    from pokemon_mosaic.ui.rotation_help import block

    assert lettres(block("ABC", 3)) == list("ABC")
    assert lettres(block("CBA", 3)) == list("CBA")


def test_the_square_example_matches_what_the_code_actually_does(qt_app):
    """Le schéma montre ABCD -> DCBA. Si `reversed_cards` changeait, le dessin
    mentirait sans qu'aucun test ne s'en aperçoive."""
    from pokemon_mosaic.links import Link

    carre = Link(cards=(0, 1, 2, 3), shape=(2, 2), ordered=False)
    assert carre.reversed_cards() == (3, 2, 1, 0)


def test_the_square_diagram_sends_a_card_to_the_opposite_corner(qt_app):
    """C'est le point que le texte seul rendait mal : sur un 2×2, A ne passe pas
    à côté mais en bas à droite."""
    from pokemon_mosaic.ui.rotation_help import block

    avant, apres = places(block("ABCD", 2)), places(block("DCBA", 2))
    assert avant[(0, 0)] == "A"             # coin haut-gauche
    assert apres[(1, 1)] == "A"             # coin bas-droite, pas (0, 1)
    assert apres[(0, 1)] != "A"


def test_the_help_says_the_shape_is_preserved(qt_app):
    from pokemon_mosaic.ui.rotation_help import RotationHelp

    aide = RotationHelp()
    assert "ne change jamais" in aide._shape_note.text()


def test_the_question_button_opens_the_diagram(qt_app, monkeypatch, tmp_path):
    """Le dialogue est modal : on court-circuite `exec` pour vérifier le
    branchement du bouton."""
    from test_ui_session import card_set_in

    from pokemon_mosaic.ui import rotation_help
    from pokemon_mosaic.ui.link_dialog import LinkDialog
    from pokemon_mosaic.ui.session import Session

    ouvertures = []
    monkeypatch.setattr(rotation_help.RotationHelp, "exec",
                        lambda self: ouvertures.append(1))
    session = Session()
    session.set_cards(card_set_in(tmp_path, {"jeu": ["a", "b"]}), str(tmp_path))
    dialog = LinkDialog(session)
    dialog._explain.click()

    assert ouvertures == [1]


def test_the_checkbox_no_longer_says_turn_over(qt_app, tmp_path):
    """« retourner le bloc » se lisait comme un effet miroir."""
    from test_ui_session import card_set_in

    from pokemon_mosaic.ui.link_dialog import LinkDialog
    from pokemon_mosaic.ui.session import Session

    session = Session()
    session.set_cards(card_set_in(tmp_path, {"jeu": ["a", "b"]}), str(tmp_path))
    dialog = LinkDialog(session)

    assert "demi-tour" in dialog._ordered.text()
