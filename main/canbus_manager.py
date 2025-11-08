import subprocess
import time
from utils import run

class CanBusManager:
    def __init__(self, controller=0, bitrate=500000, dbitrate=1000000):
        self.controller = controller
        self.bitrate = bitrate
        self.dbitrate = dbitrate
        self.iface = f"can{controller}"

    def setup_pins(self):
        """Configure Jetson pins for CAN RX/TX."""
        print(f"Configuring CAN{self.controller} pins...")
        if self.controller == 0:
            run("busybox devmem 0x0c303018 w 0xc458")  # Can0_din
            run("busybox devmem 0x0c303010 w 0xc400")  # Can0_dout
        else:
            run("busybox devmem 0x0c303008 w 0xc458")  # Can1_din
            run("busybox devmem 0x0c303000 w 0xc400")  # Can1_dout

    def load_kernel_modules(self):
        """Load CAN-related kernel modules."""
        print("Loading kernel modules...")
        for mod in ["can", "can_raw", "mttcan"]:
            run(f"modprobe {mod}", check=False)

    def bring_up_interface(self):
        """Activate CAN interface with configured bitrates."""
        print(f"Bringing up {self.iface} with bitrate={self.bitrate}, dbitrate={self.dbitrate}...")
        run(f"ip link set {self.iface} up type can bitrate {self.bitrate} "
            f"dbitrate {self.dbitrate} berr-reporting on fd on")

    def bring_down_interface(self):
        """Deactivate CAN interface (safe shutdown)."""
        print(f"Bringing down {self.iface}...")
        run(f"ip link set {self.iface} down", check=False)

    def send_frame(self, frame, interval=1.0, repeat=False):
        """
        Send a CAN frame.
        Example frame: '123#abcdabcd'
        """
        print(f"Sending CAN frame '{frame}' on {self.iface}")
        if not repeat:
            run(f"cansend {self.iface} {frame}", check=False)
            return

        print(f"Repeating every {interval}s. Press Ctrl+C to stop.")
        try:
            """
            TODO: Change infinite loop to a scheduled job.
            Loop can be incorporated into main or a thread
            """
            while True:
                result = subprocess.run(f"cansend {self.iface} {frame}", shell=True)
                if result.returncode != 0:
                    print(f"Warning: cansend failed, retrying in {interval}s...")
                time.sleep(interval)
        except KeyboardInterrupt:
            print("\nStopped by user.")
            self.bring_down_interface()


    def dump_frames(self):
        """
        Dump incoming CAN frames.
        """
        try:
            subprocess.run(f"candump {self.iface}", shell=True)
        except KeyboardInterrupt:
            print(f"\nStopping listen on {self.iface}...")
        finally:
            run(f"ip link set {self.iface} down", check=False)
            print("Interface brought down cleanly.")