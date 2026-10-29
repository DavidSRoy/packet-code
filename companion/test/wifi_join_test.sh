#!/bin/bash
# wifi_join.sh with a fake nmcli: which network it picks, and the hotspot setup.
#   bash companion/test/wifi_join_test.sh
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
mkdir "$T/bin"
cat > "$T/bin/nmcli" <<'EOF'
#!/bin/bash
echo "$*" >> "$CALLS"
case "$*" in
  "-t -f NAME con show") echo packet-old ;;
  "-t -f SSID dev wifi list") printf '%s\n' $VISIBLE ;;
esac
exit 0
EOF
printf '#!/bin/sh\n' > "$T/bin/sleep"; cp "$T/bin/sleep" "$T/bin/ip"
chmod +x "$T/bin/"*
fail=0

run() {   # name, wifi.txt, visible SSIDs, expected connection
  printf '%s\n' "$2" > "$T/wifi.txt"; : > "$T/calls"; rm -rf "$T/shared"
  PATH="$T/bin:$PATH" CALLS="$T/calls" VISIBLE="$3" LIST="$T/wifi.txt" LOG="$T/log" \
    SHARED_D="$T/shared" bash "$HERE/../wifi_join.sh"
  got=$(sed -n 's/^con up //p' "$T/calls")
  if [ "$got" = "$4" ]; then echo "ok   $1"; else echo "FAIL $1: up '$got', want '$4'"; fail=1; fi
}
expect() { if eval "$2"; then echo "ok   $1"; else echo "FAIL $1"; fail=1; fi; }

LAB='Lab|labpass1|20'
run "known network in range beats the fallback hotspot" "$LAB
AP|PacketDrone|droneP4ss|0" "Lab Other" "packet-Lab"
expect "old packet-* connections removed" 'grep -qx "con delete packet-old" "$T/calls"'
expect "hotspot: WPA2 AP, shared, no autoconnect" \
  'grep "con-name packet-ap" "$T/calls" | grep -q "mode ap.*ipv4.method shared.*proto rsn.*pmf 1.*autoconnect no"'
expect "hotspot DHCP: no gateway, no DNS" '[ "$(cat "$T/shared/packet-ap.conf")" = "$(printf "dhcp-option=3\ndhcp-option=6")" ]'

run "nothing in range: hotspot" "$LAB
AP|PacketDrone|droneP4ss|0" "Other" "packet-ap"
run "hotspot with the highest priority: always" "$LAB
AP|PacketDrone|droneP4ss|30" "Lab" "packet-ap"
run "short hotspot password: not added" "AP|PacketDrone|short|30" "" "packet-ap"
expect "short password logged, no con add" \
  '! grep -q "con-name packet-ap" "$T/calls" && grep -q "8 or more" "$T/log"'
run "no hotspot line, nothing in range: no change" "$LAB" "Other" ""

exit $fail
