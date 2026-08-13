param(
    [switch]$NoCache,
    [switch]$AudioML,
    [switch]$Offline
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Push-Location $repoRoot
try {
    & (Join-Path $PSScriptRoot "docker-preflight.ps1") -Offline:$Offline
    & (Join-Path $PSScriptRoot "setup.ps1")

    if ($AudioML) {
        $env:DSP_WORKER_TARGET = "audio-ml"
        $env:AUDIO_ML_ENABLED = "true"
    }

    $buildArgs = @("compose", "build")
    if ($Offline) { $buildArgs += "--pull=false" } else { $buildArgs += "--pull" }
    if ($NoCache) { $buildArgs += "--no-cache" }
    & docker @buildArgs
    if ($LASTEXITCODE -ne 0) { throw "Docker Compose build failed." }

    docker compose up -d --force-recreate
    if ($LASTEXITCODE -ne 0) { throw "Docker Compose startup failed." }

    & (Join-Path $PSScriptRoot "smoke-test.ps1")
    docker compose ps

    $portLine = (Get-Content .env | Select-String '^PUBLIC_PORT=').Line
    $port = if ($portLine) { $portLine.Split('=')[1] } else { "8080" }
    Write-Host "SoundDebug P1 is ready: http://localhost:$port"
}
finally {
    Pop-Location
}
