#!/usr/bin/env sh
set -eu

repo_root="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$repo_root"
./scripts/setup.sh
./scripts/docker-preflight.sh
if [ "${SOUNDDEBUG_OFFLINE:-0}" = "1" ]; then
  docker compose build --pull=false "$@"
else
  docker compose build --pull "$@"
fi
docker compose up -d --force-recreate
./scripts/smoke-test.sh
docker compose ps
port="$(sed -n 's/^PUBLIC_PORT=//p' .env)"
echo "SoundDebug P1 is ready: http://localhost:${port:-8080}"
