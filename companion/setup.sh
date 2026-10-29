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

# cloud-init installs these on the first boot only; install them here too,
# so a first boot without network can still finish later.
export DEBIAN_FRONTEND=noninteractive
apt-get update
# dnsmasq-base: DHCP for the Wi-Fi hotspot (wifi_join.sh, NetworkManager shared mode)
apt-get install -y avahi-daemon dnsmasq-base python3-opencv python3-numpy python3-serial \
  python3-venv python3-pip v4l-utils git tmux

install -d -o packet -g packet "$DST"
install -o packet -g packet -m 0755 "$SRC"/*.py "$SRC"/setup.sh "$DST"/
install -o packet -g packet -m 0644 "$SRC"/*.json "$DST"/ 2>/dev/null || true
cp "$SRC"/README.md "$DST"/ 2>/dev/null || true
rm -f "$DST"/wifi.txt
chown packet:packet "$DST"/*

# The venv sees Debian's numpy. OpenCV comes from the prebuilt aarch64 wheel (no
# build on the Zero 2 W): lid_tags.py needs >= 4.12 (one-pass multi-dictionary
# detection); Debian has 4.10.
sudo -u packet python3 -m venv --system-site-packages "$DST/.venv"
sudo -u packet "$DST/.venv/bin/pip" install --no-cache-dir pymavlink "opencv-python-headless==4.12.0.88"

sudo -u packet "$DST/.venv/bin/python" -c "import cv2, pymavlink; print('cv2', cv2.__version__, 'aruco ok' if hasattr(cv2, 'aruco') else 'NO ARUCO')"
# Raw YUYV camera: drop incomplete frames (nodrop=1 passes them on, and the missing
# part keeps old data: torn, smeared pictures; seen 2026-10-25 with the C270).
echo "options uvcvideo nodrop=0" > /etc/modprobe.d/uvcvideo-nodrop.conf

touch /var/lib/packet-setup-done
echo "=== packet setup done"
