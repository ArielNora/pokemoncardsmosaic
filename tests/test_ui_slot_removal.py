"""La confirmation de retrait d'une case ne dit plus l'agencement perdu.

Trouvé par l'audit du 2026-09-18 : garder un agencement l'écrit aussi dans la
bibliothèque, et le message annonçait pourtant qu'il « ne se retrouve pas ».
"""

import numpy as np
import pytest


@pytest.fixture
def session(qt_app):
    from pokemon_mosaic.cards import Card, CardSet
    from pokemon_mosaic.ui.session import Session

    cartes = []
    for i in range(4):
        carte = Card(path=f"/fake/s/{i}.webp", index=i,
                     thumbnail=np.full((16, 12, 3), 90, np.uint8))
        carte.top = carte.bottom = carte.left = carte.right = np.zeros(3)
        cartes.append(carte)
    jeu = CardSet(cards=cartes, full_size=(713, 984), thumb_size=(12, 16))
    s = Session()
    s.set_cards(jeu, "/fake")
    s.set_layout(cols=2, rows=2)
    return s, jeu


def test_removing_a_slot_says_the_arrangement_stays_in_the_library(qt_app,
                                                                  session,
                                                                  monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    from pokemon_mosaic.ui import saved_column
    from pokemon_mosaic.ui.saved_column import SavedColumn

    s, jeu = session
    s.save_grid(np.arange(4).reshape(2, 2), jeu, iteration=1, score=1.0)
    colonne = SavedColumn(s)
    textes = []

    def question(_parent, _titre, texte, *_args):
        textes.append(texte)
        return QMessageBox.No

    monkeypatch.setattr(saved_column.QMessageBox, "question", question)
    colonne._confirm_remove(0)

    assert "bibliothèque" in textes[0]
    assert "ne se retrouve pas" not in textes[0]
    assert s.saved[0] is not None
