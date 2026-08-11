$ErrorActionPreference = "Stop"
if (-not (Test-Path ".env")) { throw "Run ./scripts/setup.ps1 first." }
docker compose up --build -d
docker compose ps
Write-Host "SoundDebug: http://localhost:$((Get-Content .env | Select-String '^PUBLIC_PORT=').Line.Split('=')[1])"
Write-Host "Follow analysis logs: docker compose logs -f dsp-worker"
