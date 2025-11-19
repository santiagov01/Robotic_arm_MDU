import can
import threading
import queue
import time
import random

# -----------------------
# CONFIGURATION
# -----------------------
CAN_INTERFACE = "can0"
BITRATE = 500000

ID_A = 0x100  # First CAN ID to process
ID_B = 0x200  # Second CAN ID to process

# -----------------------
# SHARED RESOURCES
# -----------------------
incoming_queue = queue.Queue()      # Messages read from the bus
outgoing_queue = queue.Queue()      # Messages we want to send out
queue_id_A = queue.Queue()          # Filtered messages for ID_A
queue_id_B = queue.Queue()          # Filtered messages for ID_B

stop_event = threading.Event()


# -----------------------
# TASK 1: Read CAN bus and store data
# -----------------------
def task_read_bus(bus):
    """
    Continuously reads CAN messages from the bus and stores them
    in the incoming_queue for processing by other threads.
    """
    print("[Task 1] Started CAN bus reader.")

    while not stop_event.is_set():
        message = bus.recv(timeout=0.1)
        if message is None:
            continue

        incoming_queue.put(message)
        print(f"[Task 1] Read: ID=0x{message.arbitration_id:X}, Data={message.data}")


# -----------------------
# TASK 2: Send data to CAN bus from outgoing_queue
# -----------------------
def task_send_bus(bus):
    """
    Sends messages from the outgoing_queue to the CAN bus.
    """
    print("[Task 2] Started CAN bus sender.")

    while not stop_event.is_set():
        try:
            msg = outgoing_queue.get(timeout=0.1)
        except queue.Empty:
            continue

        try:
            bus.send(msg)
            print(f"[Task 2] Sent: ID=0x{msg.arbitration_id:X}, Data={msg.data}")
        except can.CanError:
            print("[Task 2] ERROR sending message.")

        outgoing_queue.task_done()


# -----------------------
# TASK 3: Process ID_A messages and generate responses
# -----------------------
def task_process_id_A():
    print("[Task 3] Processing CAN ID_A messages.")

    while not stop_event.is_set():
        try:
            msg = queue_id_A.get(timeout=0.1)
        except queue.Empty:
            continue

        print(f"[Task 3] Received ID_A Msg: {msg.data}")

        # Example processing: invert each byte
        new_data = bytes([b ^ 0xFF for b in msg.data])

        response = can.Message(arbitration_id=ID_A, data=new_data, is_extended_id=False)
        outgoing_queue.put(response)

        print(f"[Task 3] Sent Processed Response for ID_A: {new_data}")
        queue_id_A.task_done()


# -----------------------
# TASK 4: Process ID_B messages and generate responses
# -----------------------
def task_process_id_B():
    print("[Task 4] Processing CAN ID_B messages.")

    while not stop_event.is_set():
        try:
            msg = queue_id_B.get(timeout=0.1)
        except queue.Empty:
            continue

        print(f"[Task 4] Received ID_B Msg: {msg.data}")

        # Example processing: add +1 to each byte (mod 256)
        new_data = bytes([(b + 1) % 256 for b in msg.data])

        response = can.Message(arbitration_id=ID_B, data=new_data, is_extended_id=False)
        outgoing_queue.put(response)

        print(f"[Task 4] Sent Processed Response for ID_B: {new_data}")
        queue_id_B.task_done()


# -----------------------
# DISPATCHER: Route messages to task 3 & 4
# -----------------------
def task_dispatcher():
    """
    Routes messages from incoming_queue to ID_A or ID_B queues.
    """
    print("[Dispatcher] Started.")

    while not stop_event.is_set():
        try:
            msg = incoming_queue.get(timeout=0.1)
        except queue.Empty:
            continue

        if msg.arbitration_id == ID_A:
            queue_id_A.put(msg)
        elif msg.arbitration_id == ID_B:
            queue_id_B.put(msg)

        incoming_queue.task_done()


# -----------------------
# MAIN SETUP
# -----------------------
if __name__ == "__main__":
    print("[System] Initializing CAN interface...")

    bus = can.interface.Bus(channel=CAN_INTERFACE,
                            interface="socketcan",
                            bitrate=BITRATE)

    # Launch threads
    threads = [
        threading.Thread(target=task_read_bus, args=(bus,)),
        threading.Thread(target=task_send_bus, args=(bus,)),
        threading.Thread(target=task_dispatcher),
        threading.Thread(target=task_process_id_A),
        threading.Thread(target=task_process_id_B),
    ]

    for t in threads:
        t.start()

    print("[System] All tasks running. Press Ctrl+C to stop.")

    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n[System] Stopping all tasks...")
        stop_event.set()

    for t in threads:
        t.join()

    print("[System] Shutdown complete.")
