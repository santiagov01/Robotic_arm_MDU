from utils import ensure_root
from canbus_manager import CanBusManager

def main():
    ensure_root()

    # --- Create CAN Manager ---
    can = CanBusManager(controller=0, bitrate=500000)

    # --- Initialize hardware ---
    can.setup_pins()
    can.load_kernel_modules()
    can.bring_up_interface()

    # --- Send data ---
    # Format: ID#DATA (hexadecimal data)
    # Example: "123#deadbeef"
    # ID = "123"
    # data = "abcdabcd"
    # frame = f"{ID}#{data}"
    # can.send_frame(frame, interval=1.0, repeat=True)

    # Dump CAN frames (for testing)
    can.dump_frames()


if __name__ == "__main__":
    main()
