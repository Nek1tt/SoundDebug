$ErrorActionPreference = "Stop"
$portLine = (Get-Content .env | Select-String '^PUBLIC_PORT=').Line
$port = if ($portLine) { $portLine.Split('=')[1] } else { "8080" }
$base = "http://localhost:$port"

# The HTTP stack can be healthy while Celery is down, leaving jobs pending.
$workerId = docker compose ps -q dsp-worker
if (-not $workerId) {
    docker compose logs --tail 100 dsp-worker
    throw "DSP worker container does not exist. Rebuild with: docker compose up -d --build dsp-worker"
}
$workerState = docker inspect --format '{{.State.Status}}' $workerId
if ($workerState -ne "running") {
    docker compose logs --tail 100 dsp-worker
    throw "DSP worker is not running (state: $workerState)."
}
docker compose exec -T dsp-worker `
    celery -A services.workers.dsp_worker.worker.celery_app inspect ping `
    --destination celery@dsp-worker --timeout 10 | Out-Null
if ($LASTEXITCODE -ne 0) {
    docker compose logs --tail 100 dsp-worker
    throw "DSP worker did not answer Celery ping."
}

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
