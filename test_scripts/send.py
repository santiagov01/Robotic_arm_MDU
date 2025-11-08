#!/usr/bin/env python3
import os
import sys
import subprocess
import argparse
import re
import time

# -------------------- Root Privilege Check --------------------
def ensure_root():
    if os.geteuid() != 0:
        print("Re-executing with sudo...")
        os.execvp("sudo", ["sudo", sys.executable] + sys.argv)

# -------------------- Run Command Helper --------------------
def run(cmd, check=True):
    """Run a system command safely."""
    try:
        subprocess.run(cmd, shell=True, check=check)
    except subprocess.CalledProcessError as e:
        print(f"Command failed: {cmd}\n{e}")
        if check:
            sys.exit(1)


def send_frame(iface, frame, interval):
    try:
        while True:
            result = subprocess.run(f"cansend {iface} {frame}", shell=True)
            if result.returncode != 0:
                print(f"Warning: cansend failed, retrying in {interval}s...")
            time.sleep(interval)
    except KeyboardInterrupt:
        print(f"\nStopping sends on {iface}...")
        # Bring interface down (optional)
        run(f"ip link set {iface} down", check=False)
        sys.exit(0)

# -------------------- Main Logic --------------------
def main():
    ensure_root()

    parser = argparse.ArgumentParser(
        description="Setup and send CAN frames on Jetson Orin AGX"
    )
    parser.add_argument("-b", "--bitrate", type=int, default=500000,
                        help="CAN bitrate in bits/s (default: 500000)")
    parser.add_argument("-c", "--controller", type=int, choices=[0, 1], default=0,
                        help="CAN controller index (0 or 1)")
    parser.add_argument("-i", "--interval", type=float, default=1.0,
                        help="Seconds between sends (default: 1.0)")

    args = parser.parse_args()

    bitrate = args.bitrate
    dbitrate = 1000000
    controller = args.controller
    interval = args.interval
    frame = "123#abcdabcd"
    iface = f"can{controller}"

    # -------------------- Validate --------------------
    if bitrate <= 0:
        sys.exit("ERROR: --bitrate must be positive integer")
    if interval <= 0:
        sys.exit("ERROR: --interval must be positive number")

    # -------------------- Hardware / Pin Setup --------------------
    print(f"Configuring CAN{controller} pins...")
    if controller == 0:
        run("busybox devmem 0x0c303018 w 0xc458")  # Can0_din
        run("busybox devmem 0x0c303010 w 0xc400")  # Can0_dout
    else:
        run("busybox devmem 0x0c303008 w 0xc458")  # Can1_din
        run("busybox devmem 0x0c303000 w 0xc400")  # Can1_dout

    # -------------------- Load Kernel Modules --------------------
    print("Loading kernel modules...")
    for mod in ["can", "can_raw", "mttcan"]:
        run(f"modprobe {mod}", check=False)

    # -------------------- Bring Up Interface --------------------
    print(f"Bringing up {iface} with bitrate={bitrate}, dbitrate={dbitrate}...")
    run(f"ip link set {iface} up type can bitrate {bitrate} dbitrate {dbitrate} berr-reporting on fd on")

    print(f"Setup done. Sending CAN frame '{frame}' on {iface} every {interval}s.")
    print("Press Ctrl+C to stop.\n")

    # -------------------- Main Sending Loop --------------------
    try:
        while True:
            result = subprocess.run(f"cansend {iface} {frame}", shell=True)
            if result.returncode != 0:
                print(f"Warning: cansend failed, retrying in {interval}s...")
            time.sleep(interval)
    except KeyboardInterrupt:
        print(f"\nStopping sends on {iface}...")
        # Bring interface down (optional)
        run(f"ip link set {iface} down", check=False)
        sys.exit(0)

# -------------------- Entry Point --------------------
if __name__ == "__main__":
    main()
