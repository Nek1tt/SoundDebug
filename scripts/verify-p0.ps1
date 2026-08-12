$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Push-Location $repoRoot
try {
    python -m pip install -r services/workers/dsp_worker/requirements.txt -r requirements-dev.txt
    python -m compileall -q services shared tests
    python -m unittest tests.test_reference_matcher tests.test_dsp_post_report tests.test_dsp_analyzer -v
    docker compose config --quiet
    dotnet build frontend/SoundDebug.Frontend/SoundDebug.Frontend.csproj --configuration Release
    Write-Host "P0 static/unit verification passed."
}
finally {
    Pop-Location
}
