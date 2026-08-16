"""Point d'entrée en ligne de commande : génère la mosaïque et sa version réduite."""

import argparse
import time
from pathlib import Path

from .cards import DEFAULT_SCALE, DEFAULT_STRIP_SIZE, load_cards
from .grid import save_grid_image
from .imaging import print_image_properties, resize_and_save
from .layout import GridFit, distribute_empty_cells
from .links import LinkLibrary, resolve_links
from .optimize import generate_grid

# Racine du dépôt : src/pokemon_mosaic/cli.py -> remonter de trois niveaux
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_DIR = REPO_ROOT / "data" / "pokemoncards"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "output"

DEFAULT_ITERATIONS = 1_000_000

# Retirée pour ramener le total de 281 à 280 cartes : 281 est premier, ce qui
# produirait une grille 281x1. Voir grid.calculate_grid_dims.
DEFAULT_REMOVE_LIST = ("pokemoncards/serie_B/0_promo/pikachu.png",)

# Cartes à garder côte à côte, dans l'ordre indiqué.
DEFAULT_PAIRS = (
    ("serie_A/6_gardiens_astraux/solgaleo.png",
     "serie_A/6_gardiens_astraux/lunala.png"),
    ("serie_A/10_source_secrete/entei.png",
     "serie_A/10_source_secrete/raikou.png"),
)


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Génère une mosaïque de cartes Pokémon.")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR,
                        help="Dossier racine des cartes (défaut : %(default)s)")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR,
                        help="Dossier de sortie (défaut : %(default)s)")
    parser.add_argument("--iterations", type=int, default=DEFAULT_ITERATIONS,
                        help="Itérations d'optimisation (défaut : %(default)s)")
    parser.add_argument("--strip-size", type=float, default=DEFAULT_STRIP_SIZE,
                        help="Épaisseur des bandes de bord, en fraction (défaut : %(default)s)")
    parser.add_argument("--scale", type=float, default=DEFAULT_SCALE,
                        help="Échelle des vignettes de travail (défaut : %(default)s)")
    parser.add_argument("--full-resolution", action="store_true",
                        help="Exporter en pleine résolution (relit chaque carte du disque)")
    parser.add_argument("--grid", type=str, default=None, metavar="COLSxROWS",
                        help="Grille explicite, ex. 17x17. Les cases en trop sont "
                             "laissées vides et figées.")
    parser.add_argument("--free-order", action="store_true",
                        help="Autoriser l'optimiseur à retourner les cartes liées")
    parser.add_argument("--preview-percent", type=int, default=15,
                        help="Taille de l'aperçu réduit, en %% (défaut : %(default)s)")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)

    if not args.data_dir.is_dir():
        print(f"Dossier de cartes introuvable : {args.data_dir}")
        print("Voir la section « Données » du README.")
        return 1

    start = time.time()
    cards = load_cards(
        str(args.data_dir), DEFAULT_REMOVE_LIST,
        scale=args.scale, strip_size=args.strip_size,
    )
    if not len(cards):
        print("Aucune carte chargée.")
        return 1

    thumb_mb = sum(c.thumbnail.nbytes for c in cards) / 1024 / 1024
    print(f"{len(cards)} cartes chargées en {time.time() - start:.1f} s "
          f"— vignettes {cards.thumb_size[0]}x{cards.thumb_size[1]}, {thumb_mb:.0f} Mo "
          f"(pleine résolution : {cards.full_size[0]}x{cards.full_size[1]})")

    # Un lien n'est retenu que si toutes ses cartes ont été trouvées.
    links = LinkLibrary()
    missing = resolve_links(links, cards.find, DEFAULT_PAIRS, ordered=not args.free_order)
    if missing:
        print(f"Lien ignoré, carte(s) introuvable(s) : {', '.join(missing)}")
    print(f"{len(links)} lien(s) actif(s)"
          f"{' — ordre libre' if args.free_order else ''}")

    # Grille explicite : les cases excédentaires deviennent des cases vides figées,
    # réparties régulièrement.
    shape, empty_cells = None, ()
    if args.grid:
        try:
            cols, rows = (int(v) for v in args.grid.lower().split("x"))
        except ValueError:
            print(f"Grille illisible : {args.grid} (attendu COLSxROWS, ex. 17x17)")
            return 1
        fit = GridFit(cols=cols, rows=rows, card_count=len(cards))
        print(fit.message())
        if fit.surplus:
            return 1
        shape = (cols, rows)
        empty_cells = distribute_empty_cells((rows, cols), fit.empty_cells)

    grid = generate_grid(
        cards, links, iterations=args.iterations,
        shape=shape, empty_cells=empty_cells,
    )

    output_path = args.output_dir / f"mosaic_{args.iterations // 1000}k.png"
    save_grid_image(grid, cards, str(output_path), full_resolution=args.full_resolution)

    print_image_properties(str(output_path))
    if args.preview_percent != 100:
        preview = output_path.with_name(
            f"{output_path.stem}_preview{args.preview_percent}pct.png"
        )
        resize_and_save(str(output_path), str(preview), percent=args.preview_percent)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
