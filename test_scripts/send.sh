#!/usr/bin/env bash
set -euo pipefail

# If not running as root, re-exec this script with sudo
if [ "$(id -u)" -ne 0 ]; then
	exec sudo bash "$0" "$@"
fi

# --- defaults ---
BITRATE=500000
DBITRATE=1000000
CONTROLLER=0
INTERVAL=1
FRAME="123#abcdabcd"

usage() {
	cat <<EOF
Usage: $0 [OPTIONS]

Options:
  -b, --bitrate N       CAN bitrate in bits/s (default: ${BITRATE})
  -c, --controller N    CAN controller index (0 or 1) (default: ${CONTROLLER})
  -i, --interval N      seconds between sends (default: ${INTERVAL})
  -h, --help            show this help
EOF
	exit 1
}

# --- parse args ---
while [ "$#" -gt 0 ]; do
	case "$1" in
		-b|--bitrate)
			BITRATE="$2"; shift 2 || usage
			;;
		-c|--controller)
			CONTROLLER="$2"; shift 2 || usage
			;;
		-i|--interval)
			INTERVAL="$2"; shift 2 || usage
			;;
		-h|--help)
			usage
			;;
		--)
			shift; break
			;;
		*)
			echo "Unknown option: $1" >&2; usage
			;;
	esac
done

# validate inputs
if ! [[ "${CONTROLLER}" =~ ^[01]$ ]]; then
	echo "ERROR: --controller must be 0 or 1" >&2; exit 1
fi
if ! [[ "${BITRATE}" =~ ^[0-9]+$ ]]; then
	echo "ERROR: --bitrate must be a positive integer" >&2; exit 1
fi
if ! [[ "${INTERVAL}" =~ ^[0-9]+([.][0-9]+)?$ ]]; then
	echo "ERROR: --interval must be numeric" >&2; exit 1
fi

IFACE="can${CONTROLLER}"

# --- hardware / kernel setup (keeps original commands) ---
if [ "${CONTROLLER}" -eq 0 ]; then
    busybox devmem 0x0c303018 w 0xc458 # Can0_din
    busybox devmem 0x0c303010 w 0xc400 # Can0_dout
elif [ "${CONTROLLER}" -eq 1 ]; then
    busybox devmem 0x0c303008 w 0xc458 # Can1_din
    busybox devmem 0x0c303000 w 0xc400 # Can1_dout
fi

modprobe can || true
modprobe can_raw || true
modprobe mttcan || true

# Bring up the selected interface with the requested bitrate (keep dbitrate as before)
ip link set "${IFACE}" up type can bitrate ${BITRATE} dbitrate ${DBITRATE} berr-reporting on fd on

echo "Setup done. Sending CAN frame '${FRAME}' on ${IFACE} every ${INTERVAL}s. Press Ctrl-C to stop."

# trap to cleanly exit message
trap 'echo "Stopping sends on ${IFACE}"; exit 0' INT TERM

# Loop sending the CAN frame at requested interval. Keep going even if a single send fails.
while true; do

	if ! cansend "${IFACE}" "${FRAME}"; then
		echo "Warning: cansend failed, retrying in ${INTERVAL}s..." >&2
	fi
	# sleep supports fractional intervals; use sleep builtin
	sleep "${INTERVAL}"
done