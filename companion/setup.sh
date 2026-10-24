#!/bin/bash
# First-boot setup for the Packet CV companion (Pi Zero 2 W).
# cloud-init runs this one time. Run it again by hand if it fails:
#   sudo bash /boot/firmware/packet/setup.sh
set -euo pipefail
exec > >(tee -a /var/log/packet-setup.log) 2>&1
echo "=== packet setup $(date)"

SRC=/boot/firmware/packet
DST=/home/packet/companion

for i in $(seq 1 60); do
  getent hosts pypi.org >/dev/null && break
  echo "waiting for network ($i)"; sleep 5
done

install -d -o packet -g packet "$DST"
install -o packet -g packet -m 0755 "$SRC"/*.py "$SRC"/setup.sh "$DST"/
install -o packet -g packet -m 0644 "$SRC"/*.json "$DST"/ 2>/dev/null || true
cp "$SRC"/README.md "$DST"/ 2>/dev/null || true
chown packet:packet "$DST"/*

# Debian OpenCV is used from the venv (no slow pip build on the Zero 2 W).
sudo -u packet python3 -m venv --system-site-packages "$DST/.venv"
sudo -u packet "$DST/.venv/bin/pip" install --no-cache-dir pymavlink

sudo -u packet "$DST/.venv/bin/python" -c "import cv2, pymavlink; print('cv2', cv2.__version__, 'aruco ok' if hasattr(cv2, 'aruco') else 'NO ARUCO')"
touch /var/lib/packet-setup-done
echo "=== packet setup done"
