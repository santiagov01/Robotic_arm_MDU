#!/usr/bin/env python3
import os
import sys
import subprocess
import argparse
import sys
import subprocess

def ensure_root():
    """Re-run script with sudo if not root."""
    if os.geteuid() != 0:
        print("Re-executing with sudo...")
        os.execvp("sudo", ["sudo", sys.executable] + sys.argv)

def run(cmd, check=True):
    """Run system command safely."""
    try:
        subprocess.run(cmd, shell=True, check=check)
    except subprocess.CalledProcessError as e:
        print(f"Command failed: {cmd}\n{e}")
        if check:
            sys.exit(1)

def main():
    ensure_root()

    parser = argparse.ArgumentParser(
        description="Setup and listen to CAN frames on Jetson Orin AGX"
    )
    parser.add_argument("-b", "--bitrate", type=int, default=500000,
                        help="CAN bitrate in bits/s (default: 500000)")
    parser.add_argument("-c", "--controller", type=int, choices=[0, 1], default=1,
                        help="CAN controller index (0 or 1) (default: 1)")
    args = parser.parse_args()

    bitrate = args.bitrate
    dbitrate = 1000000
    controller = args.controller
    iface = f"can{controller}"

    # --- Validate ---
    if bitrate <= 0:
        sys.exit("ERROR: --bitrate must be positive integer")

    # --- Hardware setup ---
    print(f"Configuring CAN{controller} pins...")
    if controller == 0:
        run("busybox devmem 0x0c303018 w 0xc458")  # Can0_din
        run("busybox devmem 0x0c303010 w 0xc400")  # Can0_dout
    else:
        run("busybox devmem 0x0c303008 w 0xc458")  # Can1_din
        run("busybox devmem 0x0c303000 w 0xc400")  # Can1_dout

    # --- Load kernel modules ---
    print("Loading kernel modules...")
    for mod in ["can", "can_raw", "mttcan"]:
        run(f"modprobe {mod}", check=False)

    # --- Bring up interface ---
    print(f"Bringing up {iface} with bitrate={bitrate}, dbitrate={dbitrate}...")
    run(f"ip link set {iface} up type can bitrate {bitrate} "
        f"dbitrate {dbitrate} berr-reporting on fd on")

    print(f"Setup done. Listening for CAN frames on {iface}. Press Ctrl-C to stop.\n")

    # --- Listen using candump ---
    try:
        subprocess.run(f"candump {iface}", shell=True)
    except KeyboardInterrupt:
        print(f"\nStopping listen on {iface}...")
    finally:
        run(f"ip link set {iface} down", check=False)
        print("Interface brought down cleanly.")

if __name__ == "__main__":
    main()
