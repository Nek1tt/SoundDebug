param(
    [Parameter(Mandatory = $true)][string]$Track,
    [ValidateSet("lo-fi", "modern-pop", "hip-hop", "techno", "electronic")][string]$Genre = "electronic",
    [string[]]$Reference = @(),
    [switch]$AudioML
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$trackPath = (Resolve-Path $Track).Path
$trackExt = [IO.Path]::GetExtension($trackPath)
$outputDir = Join-Path $repoRoot "analysis-output"
New-Item -ItemType Directory -Force -Path $outputDir | Out-Null

$volumes = @("-v", "${trackPath}:/input/target${trackExt}:ro", "-v", "${outputDir}:/output")
$cliArgs = @(
    "dsp-worker", "python", "-m", "services.workers.dsp_worker.cli",
    "/input/target${trackExt}", "--genre", $Genre, "--output", "/output/report.json"
)
for ($index = 0; $index -lt $Reference.Count; $index++) {
    $referencePath = (Resolve-Path $Reference[$index]).Path
    $referenceExt = [IO.Path]::GetExtension($referencePath)
    $volumes += @("-v", "${referencePath}:/input/reference-${index}${referenceExt}:ro")
    $cliArgs += @("--reference", "/input/reference-${index}${referenceExt}")
}

if ($AudioML) {
    $env:DSP_WORKER_TARGET = "audio-ml"
    $env:AUDIO_ML_ENABLED = "true"
}

Push-Location $repoRoot
try {
    if ($AudioML) { docker compose build dsp-worker }
    docker compose run --rm --no-deps @volumes @cliArgs
} finally { Pop-Location }
Write-Host "JSON report: $outputDir\report.json"
