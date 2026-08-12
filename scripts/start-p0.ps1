param(
    [switch]$AudioML,
    [switch]$NoBuild
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Push-Location $repoRoot
try {
    if (-not (Test-Path ".env")) {
        Copy-Item ".env.example" ".env"
        Write-Host "Created .env from .env.example"
    }
    if ($AudioML) {
        $env:DSP_WORKER_TARGET = "audio-ml"
        $env:AUDIO_ML_ENABLED = "true"
    }
    if (-not $NoBuild) {
        docker compose build frontend upload-service dsp-worker
    }
    docker compose up -d --force-recreate
    docker compose ps
    Write-Host "SoundDebug P0: http://localhost:8080"
    Write-Host "Run ./scripts/smoke-test.ps1 after services become healthy."
}
finally {
    Pop-Location
}
