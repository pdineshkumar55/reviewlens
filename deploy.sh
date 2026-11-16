#!/usr/bin/env bash
# Redeploy on the server: pull the latest code, rebuild, and wait for the health check.
set -euo pipefail
cd "$(dirname "$0")"

git pull --ff-only
docker compose -f docker-compose.prod.yml up -d --build

for i in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:8611/_stcore/health >/dev/null; then
    echo "ReviewLens is up on 127.0.0.1:8611"
    exit 0
  fi
  sleep 2
done
echo "Health check failed. Recent logs:" >&2
docker compose -f docker-compose.prod.yml logs --tail 50 >&2
exit 1
