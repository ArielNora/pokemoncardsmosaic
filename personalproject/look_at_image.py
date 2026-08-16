import os
from PIL import Image

Image.MAX_IMAGE_PIXELS = None

def print_image_properties(image_path):
    """
    Opens an image and prints its format, size, and mode.
    """
    try:
        with Image.open(image_path) as img:
            print(f"--- Properties for: {os.path.basename(image_path)} ---")
            print(f"Format: {img.format}")
            print(f"Size: {img.size} (Width: {img.width}, Height: {img.height})")
            print(f"Mode: {img.mode}")
            print("-" * 30)
    except FileNotFoundError:
        print(f"Error: The file at {image_path} was not found.")
    except Exception as e:
        print(f"Error processing image: {e}")

def resize_and_save(input_path, output_path, new_width: int, new_height: int, percent: int = 100):
    """
    Resizes an image to the specified dimensions and saves it to a new path.
    """
    try:
        with Image.open(input_path) as img:
            # Resize the image using the LANCZOS filter (high quality downsampling)
            if percent != 100:
                new_width = int(img.width * percent / 100)
                new_height = int(img.height * percent / 100)
            resized_img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            # Save the resized image
            resized_img.save(output_path)
            print(f"Success! Image saved to {output_path}")
            print(f"New size: {resized_img.size}")
            
    except FileNotFoundError:
        print(f"Error: The input file {input_path} was not found.")
    except Exception as e:
        print(f"Error resizing image: {e}")

if __name__ == "__main__":
    # Example Usage
    # Replace 'example.jpg' with a real path to an image on your computer
    current_image = "hard_constraints_grid.png" 
    
    # 1. Check if file exists purely for this demonstration
    if not os.path.exists(current_image):
        print(f"Please create or place an image named '{current_image}' in this directory to run the test.")
    else:
        # 2. Print properties
        print_image_properties(current_image)

        # 3. Resize and save
        # # Example: Resizing to 800x600
        output_filename = "resized_grid_15%.png"
        resize_and_save(current_image, output_filename, 800, 600, percent = 15)