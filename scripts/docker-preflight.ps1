param([switch]$Offline)

$ErrorActionPreference = "Stop"

function Invoke-DockerChecked {
    param([Parameter(Mandatory = $true)][string[]]$Arguments)
    & docker @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Docker command failed: docker $($Arguments -join ' ')"
    }
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker CLI not found. Install and start Docker Desktop. No local Python or .NET SDK is required."
}

Invoke-DockerChecked @("version")

$images = @(
    "python:3.11-slim",
    "nginx:1.27-alpine",
    "mcr.microsoft.com/dotnet/sdk:8.0-alpine",
    "postgres:16-alpine",
    "redis:7-alpine",
    "minio/minio:RELEASE.2025-04-22T22-12-26Z"
)

foreach ($image in $images) {
    if ($Offline) {
        & docker image inspect $image *> $null
        if ($LASTEXITCODE -ne 0) {
            throw "Offline mode needs cached image '$image'. Restore Docker network access and run without -Offline once."
        }
        Write-Host "Cached image available: $image"
        continue
    }
    Write-Host "Checking registry access: $image"
    & docker pull $image
    if ($LASTEXITCODE -ne 0) {
        throw @"
Docker Desktop cannot pull '$image'. This is a Docker network/DNS/proxy problem,
not a SoundDebug build error. Open Docker Desktop -> Settings -> Resources ->
Proxies and configure the proxy used by Windows, or set Docker Engine DNS to a
working resolver, restart Docker Desktop, and rerun this script.
"@
    }
}

Write-Host $(if ($Offline) { "Docker offline cache preflight passed." } else { "Docker registry preflight passed." })
