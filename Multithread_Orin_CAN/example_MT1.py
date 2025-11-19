import threading
import time

def print_numbers(thread_name):
    """
    Simple worker function that prints numbers from 1 to 5.
    
    Args:
        thread_name (str): Name to identify the thread in prints.
    """
    for i in range(1, 6):
        print(f"{thread_name}: {i}")
        time.sleep(0.2)  # Simulate a small delay


if __name__ == "__main__":
    # Create thread objects
    t1 = threading.Thread(target=print_numbers, args=("Thread-1",))
    t2 = threading.Thread(target=print_numbers, args=("Thread-2",))

    # Start the threads
    t1.start()
    t2.start()

    # Ensure both threads finish
    t1.join()
    t2.join()

    print("All threads finished.")
