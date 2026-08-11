$ErrorActionPreference = "Stop"
$portLine = (Get-Content .env | Select-String '^PUBLIC_PORT=').Line
$port = if ($portLine) { $portLine.Split('=')[1] } else { "8080" }
$base = "http://localhost:$port"

for ($attempt = 1; $attempt -le 30; $attempt++) {
    try {
        $web = Invoke-WebRequest "$base/healthz" -UseBasicParsing -TimeoutSec 3
        $api = Invoke-RestMethod "$base/api/health" -TimeoutSec 5
        if ($web.StatusCode -eq 200 -and $api.status -in @("ok", "degraded")) {
            Write-Host "Smoke test passed: web=$($web.StatusCode), api=$($api.status)"
            exit 0
        }
    } catch { Start-Sleep -Seconds 2 }
}
docker compose ps
docker compose logs --tail 100 gateway
throw "Smoke test failed after 60 seconds."
