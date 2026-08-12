#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"
DSP_WORKER_TARGET=audio-ml AUDIO_ML_ENABLED=true docker compose build dsp-worker
DSP_WORKER_TARGET=audio-ml AUDIO_ML_ENABLED=true docker compose up -d --force-recreate dsp-worker
docker compose logs --tail 60 dsp-worker
