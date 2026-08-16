"""Point d'entrée : génère la mosaïque et sa version réduite."""

import argparse
from pathlib import Path

from .cards import find_index, load_and_process_images
from .grid import save_grid_image
from .imaging import print_image_properties, resize_and_save
from .optimize import generate_hard_constrained_grid

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
    ("pokemoncards/serie_A/6_gardiens_astraux/solgaleo.png",
     "pokemoncards/serie_A/6_gardiens_astraux/lunala.png"),
    ("pokemoncards/serie_A/10_source_secrete/entei.png",
     "pokemoncards/serie_A/10_source_secrete/raikou.png"),
)


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Génère une mosaïque de cartes Pokémon.")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR,
                        help="Dossier racine des cartes (défaut : %(default)s)")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR,
                        help="Dossier de sortie (défaut : %(default)s)")
    parser.add_argument("--iterations", type=int, default=DEFAULT_ITERATIONS,
                        help="Itérations d'optimisation (défaut : %(default)s)")
    parser.add_argument("--strip-size", type=float, default=0.1,
                        help="Épaisseur des bandes de bord, en fraction (défaut : %(default)s)")
    parser.add_argument("--preview-percent", type=int, default=15,
                        help="Taille de l'aperçu réduit, en %% (défaut : %(default)s)")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)

    if not args.data_dir.is_dir():
        print(f"Dossier de cartes introuvable : {args.data_dir}")
        print("Voir la section « Données » du README.")
        return 1

    parts, _ = load_and_process_images(
        str(args.data_dir), DEFAULT_REMOVE_LIST, strip_size=args.strip_size
    )
    if not parts:
        print("Aucune carte chargée.")
        return 1
    print(f"{len(parts)} cartes chargées.")

    # Un groupe n'est retenu que si toutes ses cartes ont été trouvées.
    hard_groups = []
    for pair in DEFAULT_PAIRS:
        indices = [find_index(parts, fragment) for fragment in pair]
        if all(idx is not None for idx in indices):
            hard_groups.append(indices)
        else:
            missing = [f for f, idx in zip(pair, indices) if idx is None]
            print(f"Groupe ignoré, carte(s) introuvable(s) : {', '.join(missing)}")

    grid = generate_hard_constrained_grid(parts, hard_groups, iterations=args.iterations)

    name = f"mosaic_{args.iterations // 1000}k.png"
    output_path = args.output_dir / name
    save_grid_image(grid, parts, str(output_path))

    print_image_properties(str(output_path))
    preview_path = output_path.with_name(
        f"{output_path.stem}_preview{args.preview_percent}pct.png"
    )
    resize_and_save(str(output_path), str(preview_path), percent=args.preview_percent)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
