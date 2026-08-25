"""Point d'entrée du paquet.

⚠️ `ui/app.py` ne peut **pas** servir de script principal : il importe par
chemins relatifs (`from ..paths import …`), ce qui exige un paquet parent.
Lancé directement, il échoue sur `attempted relative import with no known
parent package`. Ce fichier-ci importe le module normalement, et l'appelle.
"""

from pokemon_mosaic.ui.app import main

if __name__ == "__main__":
    raise SystemExit(main())
