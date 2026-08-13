param([switch]$NoCache, [switch]$Offline)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

function Invoke-DockerChecked {
    param([Parameter(Mandatory = $true)][string[]]$Arguments)
    & docker @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Docker command failed: docker $($Arguments -join ' ')"
    }
}

Push-Location $repoRoot
try {
    & (Join-Path $PSScriptRoot "docker-preflight.ps1") -Offline:$Offline
    & (Join-Path $PSScriptRoot "setup.ps1")

    $buildArgs = @("compose", "build")
    if ($Offline) { $buildArgs += "--pull=false" } else { $buildArgs += "--pull" }
    if ($NoCache) { $buildArgs += "--no-cache" }
    Invoke-DockerChecked $buildArgs
    Invoke-DockerChecked @("compose", "up", "-d", "--force-recreate")

    & (Join-Path $PSScriptRoot "smoke-test.ps1")

    $migrationId = ([string](& docker compose ps -a -q db-migrate)).Trim()
    if (-not $migrationId) { throw "db-migrate container was not created." }
    $migrationExit = (& docker inspect --format '{{.State.ExitCode}}' $migrationId).Trim()
    if ($LASTEXITCODE -ne 0 -or $migrationExit -ne "0") {
        docker compose logs --tail 200 db-migrate
        throw "Database migration failed with exit code $migrationExit. Preserve the .env that belongs to an existing postgres_data volume."
    }

    $testsPath = (Resolve-Path "tests").Path
    $dataPath = (Resolve-Path "data").Path

    Invoke-DockerChecked @(
    	"compose", "run", "--rm", "--no-deps",
    	"-v", "${testsPath}:/verification/tests:ro",
    	"-v", "${dataPath}:/verification/data:ro",
        "dsp-worker", "python", "-m", "unittest", "discover",
        "-s", "/verification/tests", "-p", "test_*.py", "-v"
    )

    $experimentsPath = (Resolve-Path "experiments").Path
    Invoke-DockerChecked @(
        "compose", "run", "--rm", "--no-deps",
        "-e", "PYTHONPATH=/app",
        "-v", "${experimentsPath}:/verification/experiments:ro",
        "dsp-worker", "python", "/verification/experiments/run_p1_temporal_synthetic.py"
    )

    Invoke-DockerChecked @(
        "compose", "run", "--rm", "--no-deps",
        "-e", "SOUNDDEBUG_API_URL=http://gateway:8000",
        "-v", "${testsPath}:/verification/tests:ro",
        "dsp-worker", "python", "/verification/tests/test_api.py"
    )

    Write-Host "P1 Docker build, services, migration, unit tests, synthetic checks and public API E2E passed."
}
catch {
    docker compose ps -a
    docker compose logs --tail 120 gateway auth-service upload-service report-service dsp-worker db-migrate
    throw
}
finally {
    Pop-Location
}
