import os
import cv2
import numpy as np
from typing import List, Optional, Tuple

def load_images_from_folders(
    root_dir: str, 
    valid_extensions: Optional[List[str]] = None
) -> Tuple[List[np.ndarray], Optional[Tuple[int, int]]]:
    """
    Recursively loads all images from a root directory and its subfolders,
    and finds the smallest image dimensions.

    Args:
        root_dir (str): The path to the main folder.
        valid_extensions (list, optional): A list of valid image file 
            extensions (e.g., ['.jpg', '.png']).

    Returns:
        tuple: (images_list, smallest_shape)
            - images_list: A list of images (NumPy arrays).
            - smallest_shape: (min_width, min_height) or None if no images.
    """
    
    if valid_extensions is None:
        valid_extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff']
    
    valid_extensions = [ext.lower() for ext in valid_extensions]
    
    images_list = []
    # Initialize with "infinite" size
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
                        # Get image dimensions (height, width)
                        h, w = img.shape[:2]
                        # Update minimums
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