#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

audio_ml=false
no_build=false
for arg in "$@"; do
  case "$arg" in
    --audio-ml) audio_ml=true ;;
    --no-build) no_build=true ;;
    *) echo "Unknown option: $arg" >&2; exit 2 ;;
  esac
done

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created .env from .env.example"
fi
if [[ "$audio_ml" == true ]]; then
  export DSP_WORKER_TARGET=audio-ml
  export AUDIO_ML_ENABLED=true
fi
if [[ "$no_build" == false ]]; then
  docker compose build frontend upload-service dsp-worker
fi
docker compose up -d --force-recreate
docker compose ps
echo "SoundDebug P0: http://localhost:8080"
echo "Run ./scripts/smoke-test.sh after services become healthy."
