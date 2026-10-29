#!/bin/bash
# Join the drone's Wi-Fi hotspot on the Mac (the AP line in the Pi's wifi.txt)
# and check the camera at http://10.42.0.1:8080.
#
#   tools/drone_wifi.sh join SSID PASSWORD
#   tools/drone_wifi.sh check
#   tools/drone_wifi.sh leave SSID   forget it, Wi-Fi off and on: macOS joins its usual network
#
# The hotspot gives no gateway, so the Mac keeps its internet (map tiles, cloud)
# on another service: iPhone USB or Ethernet. With only Wi-Fi, there is no internet
# while joined; ground control still works.
PI=10.42.0.1
DEV=$(networksetup -listallhardwareports | awk '/Hardware Port: Wi-Fi/{getline; print $2}')
[ -z "$DEV" ] && { echo "no Wi-Fi port"; exit 1; }

check() {
  ip=$(ipconfig getifaddr "$DEV")
  echo "Wi-Fi ($DEV): ${ip:-no address}"
  echo "internet via: $(route -n get default 2>/dev/null | awk '/interface:/{print $2}' || true)"
  if curl -fsS -m 2 -o /dev/null "http://$PI:8080/lid.json"; then
    echo "camera OK: http://$PI:8080  (ground control finds it by itself)"
  else
    echo "camera not reachable at http://$PI:8080"; return 1
  fi
}

case "$1" in
  join)
    [ $# -eq 3 ] || { echo "usage: $0 join SSID PASSWORD"; exit 2; }
    networksetup -setairportpower "$DEV" on
    out=$(networksetup -setairportnetwork "$DEV" "$2" "$3" 2>&1)
    [ -n "$out" ] && { echo "$out"; exit 1; }       # networksetup prints only errors
    for _ in $(seq 1 15); do [[ $(ipconfig getifaddr "$DEV") == 10.42.0.* ]] && break; sleep 1; done
    check ;;
  check) check ;;
  leave)
    [ $# -eq 2 ] || { echo "usage: $0 leave SSID"; exit 2; }
    # Forget it first, or macOS joins the drone again (the last joined comes first).
    networksetup -removepreferredwirelessnetwork "$DEV" "$2" >/dev/null
    networksetup -setairportpower "$DEV" off; sleep 1
    networksetup -setairportpower "$DEV" on ;;
  *) sed -n 2,11p "$0"; exit 2 ;;
esac
