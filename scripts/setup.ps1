$ErrorActionPreference = "Stop"

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    function New-Secret {
    	$bytes = New-Object byte[] 32
    	$rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    	try {
                $rng.GetBytes($bytes)
    	}
    	finally {
        	$rng.Dispose()
    	}
    		return -join ($bytes | ForEach-Object { $_.ToString("x2") })
	}
    $content = Get-Content ".env" -Raw
    $content = $content.Replace("change-me-postgres", (New-Secret))
    $content = $content.Replace("change-me-minio", (New-Secret))
    $content = $content.Replace("change-me-use-at-least-32-random-characters", (New-Secret))
    $content = $content.Replace("change-me-use-another-random-secret", (New-Secret))
    $utf8 = New-Object System.Text.UTF8Encoding($false)
    [IO.File]::WriteAllText((Join-Path (Get-Location) ".env"), $content, $utf8)
    Write-Host "Created .env with random local secrets."
} else {
    Write-Host ".env already exists; left unchanged."
}

docker compose config --quiet
Write-Host "Configuration is valid."
