"""Tests de l'animation d'attente."""


def test_the_spinner_only_turns_while_shown(qt_app):
    """⚠️ Cachée, la minuterie réveillerait le processeur soixante fois par
    seconde pour dessiner ce que personne ne voit."""
    from pokemon_mosaic.ui.spinner import Spinner

    roue = Spinner()
    assert not roue._timer.isActive()

    roue.show()
    assert roue._timer.isActive()
    avant = roue.angle()
    roue._timer.timeout.emit()
    assert roue.angle() != avant, "elle tourne"

    roue.hide()
    assert not roue._timer.isActive()
