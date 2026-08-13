#!/usr/bin/env sh
set -eu

command -v docker >/dev/null 2>&1 || {
  echo "Docker CLI not found. Local Python and .NET are not required." >&2
  exit 1
}
docker version >/dev/null

for image in \
  python:3.11-slim \
  nginx:1.27-alpine \
  mcr.microsoft.com/dotnet/sdk:8.0-alpine \
  postgres:16-alpine \
  redis:7-alpine \
  minio/minio:RELEASE.2025-04-22T22-12-26Z
do
  if [ "${SOUNDDEBUG_OFFLINE:-0}" = "1" ]; then
    docker image inspect "$image" >/dev/null 2>&1 || {
      echo "Offline mode needs cached image $image. Run online once first." >&2
      exit 1
    }
    echo "Cached image available: $image"
    continue
  fi
  echo "Checking registry access: $image"
  if ! docker pull "$image"; then
    echo "Docker cannot pull $image. Fix Docker Engine DNS/proxy, restart Docker, then retry." >&2
    exit 1
  fi
done
echo "Docker preflight passed."
