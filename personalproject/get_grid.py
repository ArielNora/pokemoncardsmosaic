import math

def calculate_grid_dims(num_images: int, method: str = 'tight') -> tuple[int, int]:
    """
    Calculates the optimal (cols, rows) for a grid of images.
    
    Args:
        num_images: The total number of images.
        method: 'tight' for a perfect square (might drop a few images),
                'complete' to ensure ALL images fit (might have empty slots),
                'factor' to find the best rectangular fit using exact factors (no empty slots).
    
    Returns:
        (cols, rows)
    """
    if num_images <= 0:
        return (0, 0)

    if method == 'tight':
        # Takes the floor of the square root
        # e.g., 259 -> 16x16 (256 slots). 3 images dropped.
        side = int(math.isqrt(num_images))
        return (side, side)

    elif method == 'complete':
        # Takes the ceiling to ensure space for everyone
        # e.g., 259 -> 17 cols x 16 rows (272 slots). 13 empty spots.
        cols = int(math.ceil(math.sqrt(num_images)))
        rows = int(math.ceil(num_images / cols))
        return (cols, rows)

    elif method == 'factor':
        # Finds the factor pair closest to a square (Prime factorization logic)
        # e.g. 152 -> sqrt is ~12.3 
        # Checks 12, 11, 10, 9, 8...
        # 152 % 8 == 0 -> returns (8, 19)
        # This guarantees 0 empty slots and 0 dropped images.
        start = int(math.isqrt(num_images))
        for i in range(start, 0, -1):
            if num_images % i == 0:
                # Return (width, height). 
                # i is the smaller dimension, result is a taller/thinner strip.
                # Flip these variables if you want a wide strip.
                return (i, num_images // i)
        return (1, num_images) # Fallback (prime numbers result in 1 x N strip)
    
    return (1, num_images) # Fallback