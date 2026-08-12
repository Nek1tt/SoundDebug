$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$env:DSP_WORKER_TARGET = "audio-ml"
$env:AUDIO_ML_ENABLED = "true"
Push-Location $repoRoot
try {
    docker compose build dsp-worker
    docker compose up -d --force-recreate dsp-worker
    docker compose logs --tail 60 dsp-worker
} finally { Pop-Location }
