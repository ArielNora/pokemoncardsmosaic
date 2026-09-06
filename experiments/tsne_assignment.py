"""EXPÉRIENCE : regroupement par t-SNE, approche distincte du chemin principal.

Au lieu de raccorder les bords, on projette chaque carte en 2D par similarité
visuelle globale (t-SNE sur les pixels bruts), puis on affecte optimalement une
carte par case avec l'algorithme hongrois. Le rendu regroupe les cartes qui se
ressemblent, plutôt que de lisser les coutures.

Jamais branché sur un point d'entrée : `create_tsne_image_grid` n'est appelée
nulle part. Conservé pour référence. Non maintenu.
"""

import os
from typing import List, Optional, Tuple

import cv2
import numpy as np
from scipy.optimize import linear_sum_assignment  # For 1-to-1 assignment
from scipy.spatial.distance import cdist  # For the distance matrix
from sklearn.manifold import TSNE

def load_images_from_folders(
    root_dir: str, 
    valid_extensions: Optional[List[str]] = None
) -> Tuple[List[np.ndarray], Optional[Tuple[int, int]]]:
    
    if valid_extensions is None:
        valid_extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff']
    valid_extensions = [ext.lower() for ext in valid_extensions]
    images_list = []
    min_h, min_w = float('inf'), float('inf')
    print(f"Starting to load images from: {root_dir}")
    for dirpath, dirnames, filenames in os.walk(root_dir):
        for filename in filenames:
            file_ext = os.path.splitext(filename)[1].lower()
            if file_ext in valid_extensions:
                image_path = os.path.join(dirpath, filename)
                try:
                    img = cv2.imread(image_path, cv2.IMREAD_COLOR)
                    if img is not None:
                        images_list.append(img)
                        h, w = img.shape[:2]
                        if h < min_h: min_h = h
                        if w < min_w: min_w = w
                    else:
                        print(f"Warning: Could not read image at {image_path}")
                except Exception as e:
                    print(f"Error loading image {image_path}: {e}")
    smallest_shape = None
    if images_list:
        smallest_shape = (int(min_w), int(min_h))
        print(f"Finished loading. Found {len(images_list)} images.")
        print(f"Smallest image dimensions found: {smallest_shape}")
    else:
        print("No images found.")
    return images_list, smallest_shape

# --- UPDATED FUNCTION ---

def create_tsne_image_grid(
    images_list: List[np.ndarray],
    tsne_input_size: Tuple[int, int] = (64, 64),
    tile_size: Tuple[int, int] = (100, 138),
    grid_dims: Tuple[int, int] = (16, 16),
    perplexity: int = 30,
    random_state: int = 42
) -> np.ndarray:
    """
    Runs t-SNE and creates a single large, dense image grid (collage)
    by finding the OPTIMAL 1-to-1 assignment of images to grid cells.
    
    Each image is used at most once.
    """
    
    if not images_list:
        print("The image list is empty.")
        return np.array([])

    print(f"Processing {len(images_list)} images for t-SNE...")

    # 1. Run t-SNE (Same as before)
    flat_data = []
    valid_images = []
    
    for img in images_list:
        try:
            img_tsne = cv2.resize(img, tsne_input_size, interpolation=cv2.INTER_AREA)
            flat_data.append(img_tsne.flatten())
            valid_images.append(img)
        except Exception as e:
            print(f"Warning: Could not process an image, skipping. Error: {e}")
            continue

    if not valid_images:
        print("No images were successfully processed.")
        return np.array([])
        
    num_images = len(valid_images)
    print(f"Successfully processed {num_images} images.")

    data = np.array(flat_data)
    print(f"Data shape for t-SNE: {data.shape}")

    print("Running t-SNE...")
    tsne = TSNE(
        n_components=2,
        perplexity=min(perplexity, num_images - 1),
        init='pca',
        random_state=random_state,
        max_iter=1000
    )
    embedding = tsne.fit_transform(data)
    print("t-SNE complete.")

    # 2. Normalize t-SNE coordinates (Same as before)
    x_min, x_max = embedding[:, 0].min(), embedding[:, 0].max()
    y_min, y_max = embedding[:, 1].min(), embedding[:, 1].max()
    tsne_coords = np.zeros_like(embedding)
    tsne_coords[:, 0] = (embedding[:, 0] - x_min) / (x_max - x_min)
    tsne_coords[:, 1] = (embedding[:, 1] - y_min) / (y_max - y_min)

    # 3. Create the target grid
    grid_w, grid_h = grid_dims
    num_cells = grid_w * grid_h
    tile_w, tile_h = tile_size
    
    canvas = np.zeros((grid_h * tile_h, grid_w * tile_w, 3), dtype=np.uint8)
    
    grid_x = (np.arange(grid_w) + 0.5) / grid_w
    grid_y = (np.arange(grid_h) + 0.5) / grid_h
    target_coords = np.array(np.meshgrid(grid_x, grid_y)).T.reshape(-1, 2)
    
    # 4. **NEW:** Solve the 1-to-1 assignment problem
    print("Calculating distance matrix...")
    # cost_matrix[i, j] = distance from grid cell i to image j
    cost_matrix = cdist(target_coords, tsne_coords)
    
    print("Solving optimal assignment (Hungarian algorithm)...")
    # This finds the best 1-to-1 assignment
    # row_ind = grid cell indices (0 to num_cells-1)
    # col_ind = image indices (0 to num_images-1)
    row_ind, col_ind = linear_sum_assignment(cost_matrix)
    print("Assignment complete.")

    # 5. Paste images onto the canvas based on the assignment
    print(f"Building {grid_w}x{grid_h} image grid...")
    
    # 'row_ind' has the index of the grid cell
    # 'col_ind' has the index of the image to place there
    for grid_idx, image_idx in zip(row_ind, col_ind):
        # This check is in case num_images < num_cells
        if image_idx >= num_images:
            continue
            
        # Get the row and column for this grid cell
        row = grid_idx // grid_w
        col = grid_idx % grid_w
        
        # Get the assigned image
        img = valid_images[image_idx]
        
        # Resize it
        try:
            tile = cv2.resize(img, tile_size, interpolation=cv2.INTER_AREA)
        except Exception as e:
            print(f"Warning: Could not resize image {image_idx}, skipping. {e}")
            continue
            
        # Calculate paste position
        x_pos = col * tile_w
        y_pos = row * tile_h
        
        # Paste the tile
        canvas[y_pos : y_pos + tile_h, x_pos : x_pos + tile_w] = tile

    # Any grid cells that didn't get an image (if num_cells > num_images)
    # will remain black, which is the correct behavior.

    print("Image grid creation complete.")
    return canvas