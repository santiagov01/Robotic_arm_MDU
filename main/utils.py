import os
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
