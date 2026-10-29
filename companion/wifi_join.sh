#!/bin/bash
# Adds the Wi-Fi networks in /boot/firmware/packet/wifi.txt to NetworkManager
# at every boot. cloud-init applies its network file on the first boot only,
# so this is how to add or change a network later: edit wifi.txt on a Mac.
#
# wifi.txt format, one network per line:  SSID|PASSWORD|PRIORITY
# A higher priority is tried first. Lines that start with # are ignored.
#
# Hotspot: a line  AP|SSID|PASSWORD|PRIORITY  makes the Pi its own Wi-Fi network
# (WPA2, Pi at 10.42.0.1, DHCP for the laptop). It is always "in range", so it is
# used when no network with a higher priority is in range. Give it the highest
# priority to always run the hotspot. The password needs 8 or more characters.
LIST=${LIST:-/boot/firmware/packet/wifi.txt}
LOG=${LOG:-/boot/firmware/packet-wifi.txt}
SHARED_D=${SHARED_D:-/etc/NetworkManager/dnsmasq-shared.d}

for i in $(seq 1 60); do nmcli -t general status >/dev/null 2>&1 && break; sleep 2; done

{
  echo "=== wifi_join, uptime $(cut -d' ' -f1 /proc/uptime)s"
  # wifi.txt is the full list: remove the networks that are no longer in it.
  nmcli -t -f NAME con show 2>/dev/null | grep '^packet-' | while read -r name; do
    nmcli con delete "$name" >/dev/null 2>&1
  done
  grep -v '^\s*#' "$LIST" 2>/dev/null | while IFS='|' read -r ssid psk prio; do
    [ -z "$ssid" ] && continue
    if [ "$ssid" = AP ]; then
      IFS='|' read -r ssid psk prio <<< "$psk|$prio"
      [ ${#psk} -lt 8 ] && { echo "hotspot $ssid: the password needs 8 or more characters"; continue; }
      # No gateway and no DNS in the DHCP reply: the Pi has no internet, and the
      # laptop must keep its own (iPhone USB, Ethernet) for the map and the cloud.
      mkdir -p "$SHARED_D"
      printf 'dhcp-option=3\ndhcp-option=6\n' > "$SHARED_D/packet-ap.conf"
      # autoconnect no: at boot NetworkManager could start it before the scan finds
      # a known network. This script decides. WPA2-CCMP only and PMF off: macOS
      # does not join the Pi (brcmfmac) hotspot with the WPA1/TKIP or PMF defaults.
      nmcli con add type wifi ifname wlan0 con-name packet-ap ssid "$ssid" \
        802-11-wireless.mode ap 802-11-wireless.band bg \
        ipv4.method shared ipv4.addresses 10.42.0.1/24 ipv6.method disabled \
        wifi-sec.key-mgmt wpa-psk wifi-sec.psk "$psk" wifi-sec.proto rsn \
        wifi-sec.pairwise ccmp wifi-sec.group ccmp wifi-sec.pmf 1 \
        802-11-wireless.powersave 2 connection.autoconnect no \
        && echo "added hotspot $ssid (priority ${prio:-0})"
      continue
    fi
    # The MAC must stay fixed: UW MPSK keys are tied to the registered MAC.
    # Power save off: with it on, the Zero 2 W dropped off Wi-Fi and got a new IP.
    nmcli con add type wifi ifname wlan0 con-name "packet-$ssid" ssid "$ssid" \
      wifi-sec.key-mgmt wpa-psk wifi-sec.psk "$psk" \
      802-11-wireless.cloned-mac-address permanent \
      802-11-wireless.powersave 2 \
      connection.autoconnect yes connection.autoconnect-priority "${prio:-0}" \
      && echo "added $ssid (priority ${prio:-0})"
  done
  nmcli dev wifi rescan >/dev/null 2>&1; sleep 8
  # Highest priority first; the hotspot counts as in range.
  best=$(grep -v '^\s*#' "$LIST" | awk -F'|' '$1=="AP"{print $4"|packet-ap"; next} NF{print $3"|"$1}' \
    | sort -t'|' -k1 -nr | cut -d'|' -f2- | while read -r s; do
    [ "$s" = packet-ap ] && { echo "$s"; break; }
    nmcli -t -f SSID dev wifi list 2>/dev/null | grep -qxF "$s" && { echo "packet-$s"; break; }; done)
  if [ -n "$best" ]; then
    echo "connecting to $best"
    nmcli con up "$best" 2>&1 | tail -2
  else
    echo "no listed network in range"
  fi
  nmcli -f DEVICE,STATE,CONNECTION dev status 2>&1 | grep wlan0
  ip -4 -br addr show wlan0
} >> "$LOG" 2>&1
sync
