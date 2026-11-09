#!/usr/bin/env bash
# End-to-end demo: order -> dispatch -> mock drone -> delivery.
# Needs wrangler dev (local-test.sh doubles as the boot) and mock-drone.mjs
# running in two other terminals. Run from anywhere:
#   bash backend/cloud/telemetry-api/demo.sh
set -euo pipefail
API="${API:-http://127.0.0.1:8787}"
RD="Bearer ${READ_TOKEN:-dev-read-token}"
D="${DRONE_ID:-mock-v0}"

jget() { curl -sf -H "Authorization: $RD" "$API$1"; }
jpost() { curl -sf -X POST -H "Authorization: $RD" -H "Content-Type: application/json" -d "$2" "$API$1"; }
jpatch() { curl -sf -X PATCH -H "Authorization: $RD" -H "Content-Type: application/json" -d "$2" "$API$1"; }

echo "== worker health =="
jget /v1/health | head -c 120; echo
echo "== drone online? =="
jget "/v1/drones/$D/position"

echo "== place order =="
ORDER=$(jpost /v1/orders '{"items":[{"name":"U Village Bowl","qty":2}],"pickup":"qfc","dropoff":"uplace"}')
OID=$(node -e "console.log(JSON.parse(process.argv[1]).id)" "$ORDER")
echo "order $OID"
echo "== accept (dispatch files the plan) =="
jpatch "/v1/orders/$OID" "{\"status\":\"accepted\",\"drone_id\":\"$D\"}" | head -c 400; echo
echo "== operator loads, releases (dispatch sends goto) =="
jpatch "/v1/orders/$OID" '{"status":"picked_up"}' > /dev/null
jpatch "/v1/orders/$OID" '{"status":"loaded"}' | head -c 400; echo
echo "== waiting for delivery =="
for _ in $(seq 1 90); do
  ST=$(jget "/v1/orders/$OID" | node -e "let s='';process.stdin.on('data',d=>s+=d).on('end',()=>console.log(JSON.parse(s).status))")
  echo "  $ST"
  if [ "$ST" = "delivered" ]; then echo "DELIVERED"; exit 0; fi
  if [ "$ST" = "failed" ] || [ "$ST" = "cancelled" ]; then echo "ENDED AS $ST"; exit 1; fi
  sleep 2
done
echo "TIMED OUT waiting for delivered"; exit 1
