#!/bin/bash
# Live status on the HDMI screen (tty1) in place of the login prompt.
# Started at every boot by cloud-init bootcmd. Login stays possible over SSH.
systemctl mask --runtime --now getty@tty1.service >/dev/null 2>&1
exec </dev/null >/dev/tty1 2>&1
setterm --term linux --blank 0 --powerdown 0 --cursor off 2>/dev/null

while true; do
  wifi=$(nmcli -t -f ACTIVE,SSID,SIGNAL dev wifi 2>/dev/null | awk -F: '$1=="yes"{print $2", "$3" %"; exit}')
  state=$(nmcli -t -f DEVICE,STATE dev 2>/dev/null | awk -F: '$1=="wlan0"{print $2}')
  ip=$(ip -4 -br addr show wlan0 2>/dev/null | awk '{print $3}')
  if getent hosts pypi.org >/dev/null 2>&1; then inet="OK"; else inet="no"; fi
  if [ -e /var/lib/packet-setup-done ]; then
    setup="done"
  elif pgrep -x apt-get >/dev/null || pgrep -x dpkg >/dev/null; then
    setup="installing packages (apt)"
  elif pgrep -f "pip install" >/dev/null; then
    setup="installing pymavlink (pip)"
  else
    setup=$(tail -1 /var/log/packet-setup.log 2>/dev/null || echo "not started")
  fi
  ci=$(cloud-init status 2>/dev/null | awk '{print $2}')
  err=$(journalctl -b -u NetworkManager -p warning -n 1 -o cat --no-pager 2>/dev/null | cut -c1-70)
  up=$(awk '{printf "%d min %d s", $1/60, $1%60}' /proc/uptime)

  printf '\033[H\033[2J'
  printf '  PACKET CV COMPANION   %s\n' "$(hostname)"
  printf '  --------------------------------------------\n'
  printf '  Wi-Fi     : %s\n' "${wifi:-not connected} (${state:-?})"
  printf '  IP        : %s\n' "${ip:-none}"
  printf '  Internet  : %s\n' "$inet"
  printf '  Setup     : %s\n' "$setup"
  printf '  cloud-init: %s\n' "${ci:-?}"
  printf '  Uptime    : %s\n' "$up"
  printf '  --------------------------------------------\n'
  printf '  Last network warning:\n  %s\n' "${err:-none}"
  printf '\n  SSH: ssh packet@%s\n' "${ip%/*}"
  sleep 5
done
