#!/bin/bash
# Adds the Wi-Fi networks in /boot/firmware/packet/wifi.txt to NetworkManager
# at every boot. cloud-init applies its network file on the first boot only,
# so this is how to add or change a network later: edit wifi.txt on a Mac.
#
# wifi.txt format, one network per line:  SSID|PASSWORD|PRIORITY
# A higher priority is tried first. Lines that start with # are ignored.
LIST=/boot/firmware/packet/wifi.txt
LOG=/boot/firmware/packet-wifi.txt

for i in $(seq 1 60); do nmcli -t general status >/dev/null 2>&1 && break; sleep 2; done

{
  echo "=== wifi_join, uptime $(cut -d' ' -f1 /proc/uptime)s"
  # ponytail: the Wi-Fi driver as loaded at boot does not join the Mac's Internet
  # Sharing network (WPA2/WPA3: "Authentication timed out"); after one reload it
  # joins with WPA2 (seen 2026-10-29, cause unknown). Ceiling: a workaround, and
  # the Mac network also restarts every few minutes. Upgrade: the Pi makes the
  # network itself (WPA2 only), the reverted hotspot commits on PR #2 (1081934).
  for m in brcmfmac_wcc brcmfmac_cyw brcmfmac_bca; do rmmod $m 2>/dev/null; done
  modprobe -r brcmfmac && modprobe brcmfmac
  for i in $(seq 1 30); do nmcli -t -f DEVICE dev 2>/dev/null | grep -qx wlan0 && break; sleep 1; done
  grep -v '^\s*#' "$LIST" 2>/dev/null | while IFS='|' read -r ssid psk prio; do
    [ -z "$ssid" ] && continue
    name="packet-$ssid"
    nmcli con delete "$name" >/dev/null 2>&1
    # The MAC must stay fixed: UW MPSK keys are tied to the registered MAC.
    # Power save off: with it on, the Zero 2 W dropped off Wi-Fi and got a new IP.
    # Retries 0 = forever: by default NetworkManager stops for 5 min after 4
    # failures, and the Mac network is gone for a moment when it restarts.
    nmcli con add type wifi ifname wlan0 con-name "$name" ssid "$ssid" \
      wifi-sec.key-mgmt wpa-psk wifi-sec.psk "$psk" \
      802-11-wireless.cloned-mac-address permanent \
      802-11-wireless.powersave 2 \
      connection.autoconnect yes connection.autoconnect-priority "${prio:-0}" \
      connection.autoconnect-retries 0 \
      && echo "added $ssid (priority ${prio:-0})"
  done
  nmcli dev wifi rescan >/dev/null 2>&1; sleep 8
  best=$(grep -v '^\s*#' "$LIST" | sort -t'|' -k3 -nr | cut -d'|' -f1 | while read -r s; do
    nmcli -t -f SSID dev wifi list 2>/dev/null | grep -qxF "$s" && { echo "$s"; break; }; done)
  if [ -n "$best" ]; then
    echo "connecting to $best"
    nmcli con up "packet-$best" 2>&1 | tail -2
  else
    echo "no listed network in range"
  fi
  nmcli -f DEVICE,STATE,CONNECTION dev status 2>&1 | grep wlan0
  ip -4 -br addr show wlan0
} >> "$LOG" 2>&1
sync
