from adjacency_constraints_and_match import (
    load_and_process_images,
    generate_hard_constrained_grid,
    save_grid_image
)
from look_at_image import print_image_properties, resize_and_save


# --- EXECUTION ---
ITERATIONS = 1000000
DATA_FOLDER = '/Users/arielnora/Documents/personalfolder/pokemoncards'
OUTPUT_IMAGE = 'output/mega_hard_constraints_'+str(int(ITERATIONS/1000))+'k.png'

def main():

    remove_list = ["pokemoncards/serie_B/0_promo/pikachu.png"]
    parts, _ = load_and_process_images(DATA_FOLDER,remove_list)
    print(f"Loaded {len(parts)} image parts.")


    if parts and len(parts) > 5:
        # EXAMPLE HARD CONSTRAINTS
        # 1. Indices 0 and 1 must be [0, 1] horizontal
        # 2. Indices 3, 4, 5 must be [3, 4, 5] horizontal
        # Note: These indices refer to the order loaded from the folder.

        lunala = "pokemoncards/serie_A/6_gardiens_astraux/lunala.png"
        solgaleo = "pokemoncards/serie_A/6_gardiens_astraux/solgaleo.png"
        entei = "pokemoncards/serie_A/10_source_secrete/entei.png"
        raikou = "pokemoncards/serie_A/10_source_secrete/raikou.png"

        lunala_idx = next((p.original_index for p in parts if lunala in p.path), None)
        solgaleo_idx = next((p.original_index for p in parts if solgaleo in p.path), None)
        entei_idx = next((p.original_index for p in parts if entei in p.path), None)
        raikou_idx = next((p.original_index for p in parts if raikou in p.path), None)
        print(f"Lunala Index: {lunala_idx}, Solgaleo Index: {solgaleo_idx}, Entei Index: {entei_idx}, Raikou Index: {raikou_idx}")

        my_groups = [
            [solgaleo_idx, lunala_idx],
            [entei_idx, raikou_idx]
        ]

        grid = generate_hard_constrained_grid(parts, hard_groups=my_groups, iterations=ITERATIONS)
        save_grid_image(grid, parts, OUTPUT_IMAGE)
    elif parts:
        # Just run normal
        grid = generate_hard_constrained_grid(parts, hard_groups=[])
        save_grid_image(grid, parts, OUTPUT_IMAGE)
    else:
        print("No images found.")

    if parts :
        print_image_properties(OUTPUT_IMAGE)

        output_filename = OUTPUT_IMAGE.replace(".png", "_resized15%.png")
        resize_and_save(OUTPUT_IMAGE, output_filename, 800, 600, percent = 15)

main()