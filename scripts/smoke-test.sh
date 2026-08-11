#!/usr/bin/env sh
set -eu
port="$(sed -n 's/^PUBLIC_PORT=//p' .env)"
base="http://localhost:${port:-8080}"
i=0
while [ "$i" -lt 30 ]; do
  if curl -fsS "$base/healthz" >/dev/null && curl -fsS "$base/api/health" | grep -q '"status"'; then
    echo "Smoke test passed: $base"
    exit 0
  fi
  i=$((i + 1))
  sleep 2
done
docker compose ps
docker compose logs --tail 100 gateway
echo "Smoke test failed after 60 seconds." >&2
exit 1
