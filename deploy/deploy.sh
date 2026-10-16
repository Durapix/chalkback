#!/usr/bin/env bash
# Pull the latest main and (re)start the stack. Safe to run repeatedly.
set -euo pipefail
cd "$(dirname "$0")/.."

git fetch --tags origin
git checkout --quiet main
git pull --ff-only origin main

cd deploy
docker compose up -d --build --remove-orphans
docker image prune -f >/dev/null

# Wait for the API to report healthy through Caddy's network.
for _ in $(seq 1 30); do
  if docker compose exec -T api python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')" 2>/dev/null; then
    echo "Deployed $(git rev-parse --short HEAD)"
    exit 0
  fi
  sleep 2
done
echo "API did not become healthy" >&2
docker compose logs --tail=80 api >&2
exit 1
