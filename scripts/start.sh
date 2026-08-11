#!/usr/bin/env sh
set -eu
[ -f .env ] || { echo "Run ./scripts/setup.sh first."; exit 1; }
docker compose up --build -d
docker compose ps
port="$(sed -n 's/^PUBLIC_PORT=//p' .env)"
echo "SoundDebug: http://localhost:${port:-8080}"
echo "Follow analysis logs: docker compose logs -f dsp-worker"
