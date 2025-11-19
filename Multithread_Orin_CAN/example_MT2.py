from concurrent.futures import ThreadPoolExecutor
import time

def square(n):
    """
    Computes the square of a number.
    
    Args:
        n (int): Input number.
        
    Returns:
        int: Square of n.
    """
    time.sleep(0.1)  # Simulate work
    return n * n


if __name__ == "__main__":
    numbers = [1, 2, 3, 4, 5]

    # ThreadPoolExecutor simplifies thread management
    with ThreadPoolExecutor(max_workers=3) as executor:
        results = list(executor.map(square, numbers))

    print("Squares:", results)
