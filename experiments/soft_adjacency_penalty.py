"""EXPÉRIENCE : contrainte d'adjacence molle, remplacée par src/pokemon_mosaic/.

Ici, forcer deux cartes à être voisines passe par une pénalité de score
(`distance × 5000`) qui les attire l'une vers l'autre. Cela oblige à recalculer
le score *global* à chaque itération, donc c'est très lent. L'approche retenue
traite au contraire les groupes comme des blocs indivisibles : la contrainte est
satisfaite par construction, et le scoring local rapide reste utilisable.

Conservé pour référence. Non maintenu.
"""

import math
import os
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np
from scipy.spatial.distance import cdist



# --- 1. Data Structure ---
@dataclass
class ImagePart:
    """
    Represents an image and its feature vectors.
    """
    full_image: np.ndarray
    original_index: int
    path: str = ""
    
    # Feature vectors (B, G, R averages)
    top: np.ndarray = None
    bottom: np.ndarray = None
    left: np.ndarray = None
    right: np.ndarray = None

    def calculate_features(self, strip_size: float=0.2):
        h, w, _ = self.full_image.shape
        strip_h = max(1, int(h * strip_size))
        strip_w = max(1, int(w * strip_size))

        self.top = np.mean(self.full_image[0:strip_h, :], axis=(0, 1))
        self.bottom = np.mean(self.full_image[h - strip_h:h, :], axis=(0, 1))
        self.left = np.mean(self.full_image[:, 0:strip_w], axis=(0, 1))
        self.right = np.mean(self.full_image[:, w - strip_w:w], axis=(0, 1))

# --- 2. Score Calculation with Constraints ---

def calculate_adjacency_penalty(grid_indices: np.ndarray, adjacency_pairs: List[Tuple[int, int]]) -> float:
    """
    Calculates a penalty score based on the distance between paired images.
    Acts like a spring/gravity pulling them together.
    """
    if not adjacency_pairs: return 0.0
    
    penalty = 0.0
    rows, cols = grid_indices.shape
    
    # Create a quick lookup for positions: {img_idx: (r, c)}
    # This is O(N) but necessary since we need coordinates
    positions = {}
    for r in range(rows):
        for c in range(cols):
            idx = grid_indices[r, c]
            if idx != -1:
                positions[idx] = (r, c)
    
    for idx_a, idx_b in adjacency_pairs:
        if idx_a in positions and idx_b in positions:
            r1, c1 = positions[idx_a]
            r2, c2 = positions[idx_b]
            # Manhattan distance (grid steps)
            dist = abs(r1 - r2) + abs(c1 - c2)
            
            # If they are neighbors (dist=1), penalty is 0.
            # Otherwise, penalty grows huge to force them closer.
            if dist > 1:
                penalty += (dist * 5000.0) # Strong gravity
                
    return penalty

def calculate_grid_mismatch_score(grid_indices: np.ndarray, image_parts: List[ImagePart]) -> float:
    """
    Standard edge mismatch score (visual seamlessness).
    """
    total_score = 0.0
    rows, cols = grid_indices.shape
    
    # Horizontal
    for r in range(rows):
        for c in range(cols - 1):
            idx_L, idx_R = grid_indices[r, c], grid_indices[r, c+1]
            if idx_L == -1 or idx_R == -1: continue
            total_score += cdist([image_parts[idx_L].right], [image_parts[idx_R].left], 'euclidean')[0][0]

    # Vertical
    for c in range(cols):
        for r in range(rows - 1):
            idx_T, idx_B = grid_indices[r, c], grid_indices[r+1, c]
            if idx_T == -1 or idx_B == -1: continue
            total_score += cdist([image_parts[idx_T].bottom], [image_parts[idx_B].top], 'euclidean')[0][0]
            
    return total_score

def get_local_score(r: int, c: int, grid_indices: np.ndarray, image_parts: List[ImagePart]) -> float:
    """
    Visual score contribution of a single tile.
    """
    rows, cols = grid_indices.shape
    idx_center = grid_indices[r, c]
    if idx_center == -1: return 0.0
    
    center_img = image_parts[idx_center]
    score = 0.0
    
    if r > 0: # Top
        idx_top = grid_indices[r - 1, c]
        if idx_top != -1: score += cdist([image_parts[idx_top].bottom], [center_img.top], 'euclidean')[0][0]
    if r < rows - 1: # Bottom
        idx_bottom = grid_indices[r + 1, c]
        if idx_bottom != -1: score += cdist([center_img.bottom], [image_parts[idx_bottom].top], 'euclidean')[0][0]
    if c > 0: # Left
        idx_left = grid_indices[r, c - 1]
        if idx_left != -1: score += cdist([image_parts[idx_left].right], [center_img.left], 'euclidean')[0][0]
    if c < cols - 1: # Right
        idx_right = grid_indices[r, c + 1]
        if idx_right != -1: score += cdist([center_img.right], [image_parts[idx_right].left], 'euclidean')[0][0]
            
    return score

# --- 3. Optimization Algorithm ---

def optimize_grid_hill_climbing(
    grid_indices: np.ndarray, 
    image_parts: List[ImagePart], 
    adjacency_pairs: List[Tuple[int, int]] = [],
    locked_mask: Optional[np.ndarray] = None,
    iterations: int = 20000
):
    rows, cols = grid_indices.shape
    if locked_mask is None:
        locked_mask = np.zeros((rows, cols), dtype=bool)

    print(f"Starting optimization loop ({iterations} iterations)...")
    changes = 0
    
    # Calculate initial full score (Visual + Constraint Gravity)
    current_global_score = calculate_grid_mismatch_score(grid_indices, image_parts)
    if adjacency_pairs:
        current_global_score += calculate_adjacency_penalty(grid_indices, adjacency_pairs)

    for i in range(iterations):
        # 1. Pick two random coordinates
        r1, c1 = random.randint(0, rows-1), random.randint(0, cols-1)
        r2, c2 = random.randint(0, rows-1), random.randint(0, cols-1)
        
        # Validation checks
        if (r1 == r2 and c1 == c2): continue
        if grid_indices[r1, c1] == -1 and grid_indices[r2, c2] == -1: continue
        
        # --- LOCK CHECK ---
        # If either tile is locked (fixed position), do not swap.
        if locked_mask[r1, c1] or locked_mask[r2, c2]: continue

        # 2. Optimization Strategy
        # If we have adjacency constraints, we must use the Global Score 
        # because swapping two tiles changes the distance penalty for the whole grid.
        # If NO adjacency constraints, we can use the fast Local Score.
        
        if adjacency_pairs:
            # -- Slow but accurate mode for Constraints --
            
            # Tentative Swap
            temp = grid_indices[r1, c1]
            grid_indices[r1, c1] = grid_indices[r2, c2]
            grid_indices[r2, c2] = temp
            
            new_global_score = calculate_grid_mismatch_score(grid_indices, image_parts)
            new_global_score += calculate_adjacency_penalty(grid_indices, adjacency_pairs)
            
            if new_global_score < current_global_score:
                current_global_score = new_global_score
                changes += 1
            else:
                # Revert
                temp = grid_indices[r1, c1]
                grid_indices[r1, c1] = grid_indices[r2, c2]
                grid_indices[r2, c2] = temp
        
        else:
            # -- Fast mode for Visuals only --
            curr_local = get_local_score(r1, c1, grid_indices, image_parts) + \
                         get_local_score(r2, c2, grid_indices, image_parts)
            
            # Tentative Swap
            temp = grid_indices[r1, c1]
            grid_indices[r1, c1] = grid_indices[r2, c2]
            grid_indices[r2, c2] = temp
            
            new_local = get_local_score(r1, c1, grid_indices, image_parts) + \
                        get_local_score(r2, c2, grid_indices, image_parts)
            
            if new_local < curr_local:
                changes += 1
            else:
                # Revert
                temp = grid_indices[r1, c1]
                grid_indices[r1, c1] = grid_indices[r2, c2]
                grid_indices[r2, c2] = temp

        if i % 5000 == 0 and i > 0:
            print(f"  Iteration {i}: {changes} improvements...")

    return grid_indices

# --- 4. Helpers & Main Logic ---

def load_and_process_images(root_dir: str) -> Tuple[List[ImagePart], Optional[Tuple[int, int]]]:
    # (Same as before)
    valid_extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff']
    images_data = []
    min_h, min_w = float('inf'), float('inf')
    for idx, (dirpath, _, filenames) in enumerate(os.walk(root_dir)):
        for filename in filenames:
            if os.path.splitext(filename)[1].lower() in valid_extensions:
                path = os.path.join(dirpath, filename)
                try:
                    img = cv2.imread(path)
                    if img is not None:
                        images_data.append((img, path))
                        h, w = img.shape[:2]
                        if h < min_h: min_h = h
                        if w < min_w: min_w = w
                except: pass

    if not images_data: return [], None
    smallest = (int(min_w), int(min_h))
    parts = []
    for i, (img, path) in enumerate(images_data):
        try:
            resized = cv2.resize(img, smallest, interpolation=cv2.INTER_AREA)
            p = ImagePart(full_image=resized, original_index=i, path=path)
            p.calculate_features(strip_size=0.1)
            parts.append(p)
        except: pass
    return parts, smallest

def calculate_grid_dims(num_images: int) -> Tuple[int, int]:
    if num_images <= 0: return (0, 0)
    start = int(math.isqrt(num_images))
    for i in range(start, 0, -1):
        if num_images % i == 0: return (num_images // i, i)
    return (num_images, 1)

def save_grid_image(grid_indices: np.ndarray, image_parts: List[ImagePart], output_path: str):
    if not image_parts: return
    rows, cols = grid_indices.shape
    tile_h, tile_w, _ = image_parts[0].full_image.shape
    canvas_h, canvas_w = rows * tile_h, cols * tile_w
    canvas = np.zeros((canvas_h, canvas_w, 3), dtype=np.uint8)
    for row in range(rows):
        for col in range(cols):
            img_idx = grid_indices[row, col]
            if img_idx != -1:
                tile = image_parts[img_idx].full_image
                x_pos = col * tile_w
                y_pos = row * tile_h
                canvas[y_pos : y_pos + tile_h, x_pos : x_pos + tile_w] = tile
    cv2.imwrite(output_path, canvas)
    print(f"Saved: {output_path}")

# --- MAIN GENERATOR with CONSTRAINTS ---

def generate_constrained_grid(
    image_parts: List[ImagePart],
    fixed_positions: Dict[int, Tuple[int, int]] = {}, # {img_idx: (row, col)}
    adjacency_pairs: List[Tuple[int, int]] = []       # [(img_idx_A, img_idx_B)]
) -> np.ndarray:
    
    if not image_parts: return np.array([])
    
    num_images = len(image_parts)
    grid_cols, grid_rows = calculate_grid_dims(num_images)
    print(f"\n--- Grid Setup: {grid_cols}x{grid_rows} ---")

    # Setup Arrays
    available_indices = set(range(num_images))
    grid_indices = np.full((grid_rows, grid_cols), -1, dtype=int)
    locked_mask = np.zeros((grid_rows, grid_cols), dtype=bool)

    # 1. APPLY FIXED POSITIONS (Hard Constraints)
    print(f"Applying {len(fixed_positions)} fixed position constraints...")
    for img_idx, (r, c) in fixed_positions.items():
        if 0 <= r < grid_rows and 0 <= c < grid_cols:
            if img_idx in available_indices:
                grid_indices[r, c] = img_idx
                locked_mask[r, c] = True # Lock this spot
                available_indices.remove(img_idx)
            else:
                print(f"Warning: Image {img_idx} used twice in constraints.")
        else:
            print(f"Warning: Position ({r},{c}) out of bounds.")

    # 2. GREEDY FILL (Fill remaining -1 spots)
    # We skip locked spots logic-wise
    print("Running greedy fill for remaining spots...")
    for row in range(grid_rows):
        for col in range(grid_cols):
            # Skip if already filled by Fixed Constraint
            if grid_indices[row, col] != -1:
                continue
                
            best_cost = float('inf')
            best_idx = -1
            
            # Simple greedy selection for remaining spots
            for i in list(available_indices):
                curr = image_parts[i]
                cost = 0.0
                if col > 0 and grid_indices[row, col-1] != -1: # Left
                    left = image_parts[grid_indices[row, col-1]]
                    cost += cdist([left.right], [curr.left], 'euclidean')[0][0]
                if row > 0 and grid_indices[row-1, col] != -1: # Top
                    top = image_parts[grid_indices[row-1, col]]
                    cost += cdist([top.bottom], [curr.top], 'euclidean')[0][0]
                
                if cost < best_cost:
                    best_cost = cost
                    best_idx = i
            
            if best_idx != -1:
                grid_indices[row, col] = best_idx
                available_indices.remove(best_idx)

    # 3. OPTIMIZATION (Respects Locks & Adjacency Gravity)
    print("Optimizing with constraints...")
    grid_indices = optimize_grid_hill_climbing(
        grid_indices, 
        image_parts, 
        adjacency_pairs=adjacency_pairs,
        locked_mask=locked_mask, # Pass the locks!
        iterations=50000
    )
    
    return grid_indices

# --- Execution Example ---
REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_FOLDER = REPO_ROOT / 'data' / 'pokemoncards'
OUTPUT_IMAGE = REPO_ROOT / 'output' / 'soft_adjacency_grid.png'


def main():
    parts, _ = load_and_process_images(str(DATA_FOLDER))

    if not parts:
        print("No images found.")
        return

    # Example Constraints:
    # 1. Fix the first loaded image to (0,0) (Top-Left corner)
    # 2. Force Lunala and Solgaleo to be neighbors (Soft Constraint)
    lunala = "pokemoncards/serie_A/6_gardiens_astraux/lunala.png"
    solgaleo = "pokemoncards/serie_A/6_gardiens_astraux/solgaleo.png"
    lunala_idx = next((p.original_index for p in parts if lunala in p.path), None)
    solgaleo_idx = next((p.original_index for p in parts if solgaleo in p.path), None)
    print(f"Lunala Index: {lunala_idx}, Solgaleo Index: {solgaleo_idx}")

    my_adj = [(lunala_idx, solgaleo_idx)] if lunala_idx is not None and solgaleo_idx is not None else []

    final_grid = generate_constrained_grid(parts, adjacency_pairs=my_adj)

    OUTPUT_IMAGE.parent.mkdir(parents=True, exist_ok=True)
    save_grid_image(final_grid, parts, str(OUTPUT_IMAGE))


if __name__ == "__main__":
    main()