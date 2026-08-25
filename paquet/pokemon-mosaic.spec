# -*- mode: python ; coding: utf-8 -*-
"""Recette d'empaquetage — un `.app` macOS autonome.

    uv sync --extra package
    uv run pyinstaller paquet/pokemon-mosaic.spec --noconfirm

Le paquet embarque **le code et les traductions, pas les illustrations**. Les
441 images pèsent 56 Mo, changent à chaque extension, et appartiennent à leurs
ayants droit : elles se récupèrent à l'usage. Au premier lancement, l'utilisateur
désigne son dossier de cartes à l'étape 1.

⚠️ Le dossier ne s'appelle pas `packaging/` : ce nom est celui d'une bibliothèque
Python installée, et un dossier homonyme à la racine peut la masquer.
"""

from PyInstaller.utils.hooks import collect_submodules

NOM = "Pokémon Mosaic"

a = Analysis(
    ["lancer.py"],
    pathex=["../src"],
    binaries=[],
    # Les traductions sont la seule ressource embarquée. `paths.resource_dir()`
    # les cherche sous `sys._MEIPASS`, où PyInstaller les déplie.
    datas=[("../translations/pokemon_mosaic_en.qm", "translations")],
    hiddenimports=collect_submodules("pokemon_mosaic"),
    hookspath=[],
    runtime_hooks=[],
    # PySide6 embarque de quoi faire un navigateur et une base de données. Rien
    # de tout cela n'est importé : les exclure allège nettement le paquet.
    excludes=[
        "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets",
        "PySide6.QtQuick", "PySide6.QtQml", "PySide6.Qt3DCore",
        "PySide6.QtMultimedia", "PySide6.QtSql",
        "PySide6.QtCharts", "PySide6.QtDataVisualization",
        "tkinter", "unittest", "pytest",
        # Le socle est numpy + Pillow ; ces quatre-là ne servent qu'à
        # `experiments/`, qui n'est pas empaqueté.
        "cv2", "scipy", "sklearn", "matplotlib",
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name=NOM,
    debug=False,
    strip=False,
    upx=False,
    console=False,
    argv_emulation=False,
)

coll = COLLECT(
    exe, a.binaries, a.datas,
    strip=False, upx=False, name=NOM,
)

app = BUNDLE(
    coll,
    name=f"{NOM}.app",
    bundle_identifier="com.arielnora.pokemonmosaic",
    version="0.1.0",
    info_plist={
        "CFBundleName": NOM,
        "CFBundleDisplayName": NOM,
        # Sans quoi macOS affiche l'interface en anglais quand le système l'est,
        # alors que la langue source du projet est le français.
        "CFBundleDevelopmentRegion": "fr_FR",
        "NSHighResolutionCapable": True,
        "LSApplicationCategoryType": "public.app-category.graphics-design",
    },
)
