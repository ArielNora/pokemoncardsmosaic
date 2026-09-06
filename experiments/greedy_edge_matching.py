"""EXPÉRIENCE : placement greedy, remplacé par src/pokemon_mosaic/.

Remplit la grille case par case en choisissant à chaque fois la meilleure carte
restante. Rapide mais myope : les dernières cases héritent des rebuts. C'est ce
défaut qui a motivé le passage à l'optimisation par échanges.

Conservé pour référence. Non maintenu.
"""

import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np
from scipy.spatial.distance import cdist

# --- Data Structure for Edge Matching ---
@dataclass
class ImagePart:
    """
    Represents an image and its feature vectors (average colors) 
    for the top, bottom, left, and right 20% edge strips.
    """
    full_image: np.ndarray
    original_index: int
    strip_size: float = 0.2  # 20% strip for edge features
    
    # Feature vectors (e.g., average BGR color of the 20% strip)
    # Stored as a 3-element NumPy array (B, G, R)
    top: np.ndarray = None
    bottom: np.ndarray = None
    left: np.ndarray = None
    right: np.ndarray = None

    def calculate_features(self):
        """
        Calculates the average BGR color for the 20% strips 
        of the image edges. This is used as the feature vector for matching.
        """
        h, w, _ = self.full_image.shape
        
        # Calculate 20% strip size
        # We ensure a minimum of 1 pixel if the image is very small
        strip_h = max(1, int(h * 0.3))
        strip_w = max(1, int(w * 0.3))

        # 1. Top Strip (full width, 30% height)
        self.top = np.mean(self.full_image[0:strip_h, :], axis=(0, 1))

        # 2. Bottom Strip
        self.bottom = np.mean(self.full_image[h - strip_h:h, :], axis=(0, 1))

        # 3. Left Strip (full height, 20% width)
        self.left = np.mean(self.full_image[:, 0:strip_w], axis=(0, 1))

        # 4. Right Strip
        self.right = np.mean(self.full_image[:, w - strip_w:w], axis=(0, 1))

# --- Helper: Load Images and Create ImagePart Objects ---
def load_and_process_images(root_dir: str, strip_size: float=0.2) -> Tuple[List[ImagePart], Optional[Tuple[int, int]]]:
    """
    Recursively loads images, resizes them all to the smallest dimensions found,
    and returns a list of ImagePart objects with calculated edge features.
    """
    valid_extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff']
    
    images_data: List[Tuple[np.ndarray, int]] = []
    min_h, min_w = float('inf'), float('inf')
    
    # 1. First Pass: Load all and find min size
    print(f"Starting pass 1 (loading and finding minimum size) from: {root_dir}")
    for idx, (dirpath, _, filenames) in enumerate(os.walk(root_dir)):
        for filename in filenames:
            file_ext = os.path.splitext(filename)[1].lower()
            if file_ext in valid_extensions:
                image_path = os.path.join(dirpath, filename)
                try:
                    img = cv2.imread(image_path, cv2.IMREAD_COLOR) 
                    if img is not None:
                        images_data.append((img, len(images_data))) 
                        h, w = img.shape[:2]
                        if h < min_h: min_h = h
                        if w < min_w: min_w = w
                except Exception:
                    continue

    if not images_data:
        print("No images found.")
        return [], None
    
    smallest_shape = (int(min_w), int(min_h))
    print(f"Found {len(images_data)} images. Smallest shape: {smallest_shape}")
    
    # 2. Second Pass: Resize, create ImagePart objects, and calculate features
    image_parts: List[ImagePart] = []
    print("Starting pass 2 (resizing and calculating features)...")
    for img, original_idx in images_data:
        try:
            img_resized = cv2.resize(img, smallest_shape, interpolation=cv2.INTER_AREA)
            part = ImagePart(full_image=img_resized, original_index=original_idx, strip_size=strip_size)
            part.calculate_features()
            image_parts.append(part)
        except Exception:
            continue

    print(f"Finished processing {len(image_parts)} images.")
    return image_parts, smallest_shape

# --- Helper: Grid Calculation (Factor Method) ---
def calculate_grid_dims(num_images: int, method: str = 'factor') -> Tuple[int, int]:
    """
    Calculates grid dimensions that fit the number of images exactly 
    by finding the two closest factors.
    """
    if num_images <= 0: return (0, 0)
    
    if method == 'factor':
        start = int(math.isqrt(num_images))
        for i in range(start, 0, -1):
            if num_images % i == 0:
                # We prioritize wider strips (e.g., 37x7 instead of 7x37 for 259)
                return (num_images // i, i) 
        return (num_images, 1) # Fallback for prime numbers
    
    # Default is the same as the 'complete' method for this complex task
    cols = int(math.ceil(math.sqrt(num_images)))
    rows = int(math.ceil(num_images / cols))
    return (cols, rows)


# --- EDGE MATCHING COLLAGE LOGIC (IMPLEMENTATION) ---
def create_edge_matching_grid(
    image_parts: List[ImagePart], 
    grid_method: str = 'factor'
) -> np.ndarray:
    """
    Builds the final collage grid using a GREEDY algorithm to match 
    adjacent image edges (based on color features).
    """
    
    if not image_parts:
        return np.array([])
        
    num_images = len(image_parts)
    grid_cols, grid_rows = calculate_grid_dims(num_images, method=grid_method)
    
    print(f"\n--- Edge Matching Grid Generation ---")
    print(f"Grid: {grid_cols}x{grid_rows} ({grid_cols*grid_rows} slots) for {num_images} images.")

    # List of available image indices (start with all indices)
    available_indices = list(range(num_images))
    
    # 2D array to hold the index of the ImagePart placed in each grid slot
    # Initialized with -1 (unassigned)
    grid_indices = np.full((grid_rows, grid_cols), -1, dtype=int)

    # Get tile size from the first resized image
    tile_h, tile_w, _ = image_parts[0].full_image.shape
    canvas_h, canvas_w = grid_rows * tile_h, grid_cols * tile_w
    
    # --- Greedy Placement ---
    for row in range(grid_rows):
        for col in range(grid_cols):
            best_cost = float('inf')
            best_image_idx = -1
            
            # --- 1. Calculate cost for every available image ---
            for i in available_indices:
                current_image = image_parts[i]
                current_cost = 0
                
                # Check for image to the LEFT
                if col > 0:
                    left_idx = grid_indices[row, col - 1]
                    left_image = image_parts[left_idx]
                    
                    # Cost = Distance between LEFT image's RIGHT edge and CURRENT image's LEFT edge
                    # cdist requires 2D arrays, so we wrap the 1D feature vectors
                    cost_left = cdist([left_image.right], [current_image.left], metric='euclidean')[0][0]
                    current_cost += cost_left

                # Check for image ABOVE
                if row > 0:
                    top_idx = grid_indices[row - 1, col]
                    top_image = image_parts[top_idx]
                    
                    # Cost = Distance between TOP image's BOTTOM edge and CURRENT image's TOP edge
                    cost_top = cdist([top_image.bottom], [current_image.top], metric='euclidean')[0][0]
                    current_cost += cost_top

                # For the very first image (0, 0), the cost is 0, so the first available image is chosen.
                
                # --- 2. Select the image with the lowest cost ---
                if current_cost < best_cost:
                    best_cost = current_cost
                    best_image_idx = i

            # --- 3. Place the best image ---
            if best_image_idx != -1:
                grid_indices[row, col] = best_image_idx
                available_indices.remove(best_image_idx)
            
            # If we run out of images, break the loop
            if not available_indices:
                break
        if not available_indices:
            break

    # --- 4. Construct the Final Canvas ---
    canvas = np.zeros((canvas_h, canvas_w, 3), dtype=np.uint8)
    
    print("Building final image grid...")
    for row in range(grid_rows):
        for col in range(grid_cols):
            img_idx = grid_indices[row, col]
            
            if img_idx != -1:
                img_part = image_parts[img_idx]
                tile = img_part.full_image
                
                # Calculate paste position
                x_pos = col * tile_w
                y_pos = row * tile_h
                
                # Paste the tile
                canvas[y_pos : y_pos + tile_h, x_pos : x_pos + tile_w] = tile
            # Any unfilled slots remain black.

    print("Edge matching grid creation complete.")
    return canvas

# --- EXECUTION ---
REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_FOLDER = REPO_ROOT / 'data' / 'pokemoncards'
OUTPUT_DIR = REPO_ROOT / 'output'
STRIP_SIZE = 0.5


def main():
    output_file = OUTPUT_DIR / f'edge_matching_grid_strip{int(STRIP_SIZE * 100)}.png'
    output_file.parent.mkdir(parents=True, exist_ok=True)

    print("--- Starting Image Processing for Edge Matching ---")

    # 1. Load, resize, and calculate edge features
    all_image_parts, smallest_shape = load_and_process_images(str(DATA_FOLDER), STRIP_SIZE)

    if not all_image_parts:
        print(f"\nNo images found in '{DATA_FOLDER}'.")
        return

    # 2. Create the grid using the 'factor' method (guarantees a full grid)
    result = create_edge_matching_grid(all_image_parts, grid_method='factor')

    if result.size > 0:
        cv2.imwrite(str(output_file), result)
        print(f"\nSuccessfully saved edge-matched grid to: {output_file}")
        print("The resulting image is a seamless collage where adjacent tiles share similar boundary colors.")
    else:
        print("\nFailed to create grid.")


if __name__ == "__main__":
    main()