#!/usr/bin/env bash
# One-shot local verification for the packet telemetry API.
# Installs deps, type-checks, boots wrangler dev, and runs the e2e suite.
# Run from anywhere:  bash backend/cloud/telemetry-api/local-test.sh
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

if ! node -e "process.exit(Number(process.versions.node.split('.')[0]) >= 18 ? 0 : 1)"; then
  echo "Node 18+ required (wrangler 4). You have: $(node -v)"
  exit 1
fi

if [ ! -f .dev.vars ]; then
  printf 'INGEST_TOKEN=dev-ingest-token\nREAD_TOKEN=dev-read-token\nCOMMAND_TOKEN=dev-command-token\n' > .dev.vars
  echo "Created .dev.vars with dev tokens (local only, gitignored)."
fi

npm ci
npm run check

npx wrangler dev --port 8787 & DEV=$!
trap "kill $DEV" EXIT
for _ in $(seq 1 60); do
  if curl -sf http://127.0.0.1:8787/v1/health >/dev/null; then break; fi
  sleep 1
done
curl -sf http://127.0.0.1:8787/v1/health >/dev/null || { echo "wrangler dev did not start"; exit 1; }
npm test
