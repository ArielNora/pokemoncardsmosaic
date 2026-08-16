import numpy as np
import cv2
import random
from typing import List, Optional, Tuple, Dict, Set
from dataclasses import dataclass
import math
import os
from scipy.spatial.distance import cdist

# --- 1. Data Structure ---
@dataclass
class ImagePart:
    full_image: np.ndarray
    original_index: int
    path: str = ""

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

# --- 2. Group & Score Logic ---

def get_group_footprint(start_r: int, start_c: int, group_ids: List[int], grid_indices: np.ndarray) -> List[Tuple[int, int]]:
    """
    Returns the coordinates of a group assuming it is placed horizontally 
    starting at start_r, start_c.
    """
    coords = []
    rows, cols = grid_indices.shape
    for i in range(len(group_ids)):
        if start_c + i >= cols: return [] # Out of bounds
        coords.append((start_r, start_c + i))
    return coords

def calculate_grid_mismatch_score(grid_indices: np.ndarray, image_parts: List[ImagePart]) -> float:
    total_score = 0.0
    rows, cols = grid_indices.shape
    
    # Horizontal Seams
    for r in range(rows):
        for c in range(cols - 1):
            idx_L, idx_R = grid_indices[r, c], grid_indices[r, c+1]
            if idx_L == -1 or idx_R == -1: continue
            total_score += cdist([image_parts[idx_L].right], [image_parts[idx_R].left], 'euclidean')[0][0]

    # Vertical Seams
    for c in range(cols):
        for r in range(rows - 1):
            idx_T, idx_B = grid_indices[r, c], grid_indices[r+1, c]
            if idx_T == -1 or idx_B == -1: continue
            total_score += cdist([image_parts[idx_T].bottom], [image_parts[idx_B].top], 'euclidean')[0][0]
            
    return total_score

def get_local_score_for_cells(cells: List[Tuple[int, int]], grid_indices: np.ndarray, image_parts: List[ImagePart]) -> float:
    """
    Calculates score contribution for a specific list of cells (a group or set of tiles).
    """
    rows, cols = grid_indices.shape
    score = 0.0
    processed_edges = set()

    for r, c in cells:
        idx = grid_indices[r, c]
        if idx == -1: continue
        curr = image_parts[idx]

        # Check neighbors. If neighbor is IN the list of cells, we count the internal edge.
        # If neighbor is OUTSIDE, we count the external edge.
        
        # Right
        if c < cols - 1:
            n_idx = grid_indices[r, c+1]
            if n_idx != -1:
                edge_sig = tuple(sorted(((r,c), (r, c+1))))
                if edge_sig not in processed_edges:
                    score += cdist([curr.right], [image_parts[n_idx].left], 'euclidean')[0][0]
                    processed_edges.add(edge_sig)
        
        # Left
        if c > 0:
            n_idx = grid_indices[r, c-1]
            if n_idx != -1:
                edge_sig = tuple(sorted(((r,c), (r, c-1))))
                if edge_sig not in processed_edges:
                    score += cdist([image_parts[n_idx].right], [curr.left], 'euclidean')[0][0]
                    processed_edges.add(edge_sig)

        # Bottom
        if r < rows - 1:
            n_idx = grid_indices[r+1, c]
            if n_idx != -1:
                edge_sig = tuple(sorted(((r,c), (r+1, c))))
                if edge_sig not in processed_edges:
                    score += cdist([curr.bottom], [image_parts[n_idx].top], 'euclidean')[0][0]
                    processed_edges.add(edge_sig)

        # Top
        if r > 0:
            n_idx = grid_indices[r-1, c]
            if n_idx != -1:
                edge_sig = tuple(sorted(((r,c), (r-1, c))))
                if edge_sig not in processed_edges:
                    score += cdist([image_parts[n_idx].bottom], [curr.top], 'euclidean')[0][0]
                    processed_edges.add(edge_sig)
                    
    return score

# --- 3. Optimization with Group Swapping ---

def optimize_groups(
    grid_indices: np.ndarray, 
    image_parts: List[ImagePart], 
    img_to_group: Dict[int, List[int]], # Maps img_idx -> full group list
    iterations: int = 50000
):
    rows, cols = grid_indices.shape
    print(f"Starting Group-Aware Optimization ({iterations} iterations)...")
    changes = 0

    for i in range(iterations):
        # 1. Pick Source Coordinate
        r1, c1 = random.randint(0, rows-1), random.randint(0, cols-1)
        idx1 = grid_indices[r1, c1]
        if idx1 == -1: continue

        # Identify Source Group (Object A)
        if idx1 in img_to_group:
            group_A = img_to_group[idx1]
            
            # Use direct offset calculation instead of scanning loop
            # This assumes groups are always maintained contiguously and in order
            offset = group_A.index(idx1)
            head_c = c1 - offset
            
            # Verify valid group integrity (just in case)
            if head_c < 0 or head_c + len(group_A) > cols: continue
            
            # coords_A = list of (r, c) tuples
            coords_A = [(r1, head_c + k) for k in range(len(group_A))]
            
            # Verify the grid actually holds the group here (integrity check)
            match = True
            for k, (rr, cc) in enumerate(coords_A):
                if grid_indices[rr, cc] != group_A[k]: match = False
            if not match: continue

        else:
            # Single tile group
            group_A = [idx1]
            coords_A = [(r1, c1)]

        # 2. Pick Target Coordinate
        r2, c2 = random.randint(0, rows-1), random.randint(0, cols-1)
        
        # Safety: Don't pick a target inside Object A
        if (r2, c2) in coords_A: continue

        # Identify Target Area (Object B)
        # We need an area of size len(group_A) starting at r2, c2? 
        # Or we try to swap Group A with Group B found at r2, c2?
        
        # Strategy: We define a "Target Zone" matching A's shape at r2, c2
        # We check if the Target Zone is composed ONLY of Single Tiles (size 1 groups).
        # If yes, we can swap Group A with the bunch of Singles.
        
        width_A = len(group_A)
        if c2 + width_A > cols: continue # Out of bounds
        
        coords_B = [(r2, c2 + k) for k in range(width_A)]
        
        # Check if Target Zone overlaps Source Zone
        overlap = False
        for c in coords_B:
            if c in coords_A: overlap = True
        if overlap: continue

        # Check validity of Target Zone
        # It must contain only indices that are NOT part of multi-image groups
        # (We only swap Hard Groups with Singles to avoid complex Tetris logic)
        valid_target = True
        indices_B = []
        for rr, cc in coords_B:
            t_idx = grid_indices[rr, cc]
            if t_idx == -1: 
                valid_target = False; break
            if t_idx in img_to_group:
                valid_target = False; break # Can't break up another group
            indices_B.append(t_idx)
        
        if not valid_target: continue

        # 3. Calculate Scores Before Swap
        # We only need the local score changes for the cells involved
        score_before = get_local_score_for_cells(coords_A, grid_indices, image_parts) + \
                       get_local_score_for_cells(coords_B, grid_indices, image_parts)

        # 4. Perform Swap
        # Place Group A into Coords B
        for k, (rr, cc) in enumerate(coords_B):
            grid_indices[rr, cc] = group_A[k]
        
        # Place Singles B into Coords A
        for k, (rr, cc) in enumerate(coords_A):
            grid_indices[rr, cc] = indices_B[k]

        # 5. Calculate Score After Swap
        score_after = get_local_score_for_cells(coords_A, grid_indices, image_parts) + \
                      get_local_score_for_cells(coords_B, grid_indices, image_parts)

        # 6. Revert if worse
        if score_after >= score_before:
            # Revert
            for k, (rr, cc) in enumerate(coords_A):
                grid_indices[rr, cc] = group_A[k]
            for k, (rr, cc) in enumerate(coords_B):
                grid_indices[rr, cc] = indices_B[k]
        else:
            changes += 1

        if i % 10000 == 0 and i > 0:
            print(f"  Iteration {i}: {changes} swaps...")

    print(f"Optimization finished. {changes} swaps.")
    return grid_indices

# --- 4. Initialization Logic ---

def generate_hard_constrained_grid(image_parts: List[ImagePart], hard_groups: List[List[int]], iterations: int = 500000) -> np.ndarray:
    if not image_parts: return np.array([])
    print("start generating grid with hard constraints for",len(image_parts),"images and",len(hard_groups),"hard groups.")
    num_images = len(image_parts)
    grid_cols, grid_rows = calculate_grid_dims(num_images)  # Fixed to 216 for this example
    print(f"\n--- Grid Setup: {grid_cols}x{grid_rows} ---")

    # Map for easy lookup: img_idx -> group_list
    img_to_group = {}
    for grp in hard_groups:
        for idx in grp:
            img_to_group[idx] = grp
            
    # Track used indices
    used_indices = set()
    grid_indices = np.full((grid_rows, grid_cols), -1, dtype=int)

    # 1. Place Hard Groups First (linearly)
    print("Placing hard groups...")
    current_r, current_c = 0, 0
    
    for grp in hard_groups:
        grp_len = len(grp)
        # Find next available slot that fits grp_len horizontally
        placed = False
        while not placed and current_r < grid_rows:
            # Check if fits in current row
            if current_c + grp_len <= grid_cols:
                # Place it
                for k, img_idx in enumerate(grp):
                    grid_indices[current_r, current_c + k] = img_idx
                    used_indices.add(img_idx)
                current_c += grp_len
                placed = True
            else:
                # Move to next row
                current_r += 1
                current_c = 0
                
    # 2. Fill remaining spots with Singles
    print("Filling singles...")
    available_singles = [p.original_index for p in image_parts if p.original_index not in used_indices]
    random.shuffle(available_singles) # Random start for singles
    
    # Reset cursors to fill holes
    for r in range(grid_rows):
        for c in range(grid_cols):
            if grid_indices[r, c] == -1 and available_singles:
                grid_indices[r, c] = available_singles.pop()

    initial_score = calculate_grid_mismatch_score(grid_indices, image_parts)
    print(f"Initial Score: {initial_score:.2f}")

    # 3. Optimize
    grid_indices = optimize_groups(grid_indices, image_parts, img_to_group, iterations=iterations)

    final_score = calculate_grid_mismatch_score(grid_indices, image_parts)
    print(f"Final Score: {final_score:.2f}")
    
    return grid_indices

# --- 5. Helpers (Load/Save) ---

def load_and_process_images(root_dir: str, remove_list: List[str]=[]) -> Tuple[List[ImagePart], Optional[Tuple[int, int]]]:
    valid_extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff']
    images_data = []
    min_h, min_w = float('inf'), float('inf')
    print(f"Loading images from: {root_dir}")
    for idx, (dirpath, _, filenames) in enumerate(os.walk(root_dir)):
        for filename in filenames:
            full_path = os.path.join(dirpath, filename)
            if any(rem in full_path for rem in remove_list):
                print(f"Removing {full_path}")
                continue
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
    print(f"Total images found: {len(images_data)}")
    if not images_data: return [], None
    smallest = (int(min_w), int(min_h))
    parts = []
    for i, (img, path) in enumerate(images_data):
        try:
            resized = cv2.resize(img, smallest, interpolation=cv2.INTER_AREA)
            p = ImagePart(full_image=resized, original_index=i, path=path)
            p.calculate_features(strip_size=0.1)
            parts.append(p)
        except Exception as e:
            print(f"Error processing {path}: {e}")
    return parts, smallest

def calculate_grid_dims(n: int) -> Tuple[int, int]:
    if n <= 0: return (0,0)
    s = int(math.isqrt(n))
    for i in range(s, 0, -1):
        if n % i == 0: return (n//i, i)
    return (n, 1)

def save_grid_image(grid: np.ndarray, parts: List[ImagePart], path: str):
    if not parts: return
    rows, cols = grid.shape
    th, tw, _ = parts[0].full_image.shape
    canvas = np.zeros((rows*th, cols*tw, 3), dtype=np.uint8)
    for r in range(rows):
        for c in range(cols):
            idx = grid[r,c]
            if idx != -1:
                canvas[r*th:(r+1)*th, c*tw:(c+1)*tw] = parts[idx].full_image
    cv2.imwrite(path, canvas)
    print(f"Saved to {path}")
