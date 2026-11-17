# run-step-0.3.ps1 — build and verify the AZINCO API (FastAPI skeleton).
#   cd "D:\syeda Gulzar Bano\azinco"
#   powershell -ExecutionPolicy Bypass -File .\setup\run-step-0.3.ps1
# Output is logged to .data\step-0.3-log.txt (git-ignored). Secrets are never printed.

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
New-Item -ItemType Directory -Force ".data" | Out-Null
$log = Join-Path $root ".data\step-0.3-log.txt"
Start-Transcript -Path $log -Force | Out-Null
function Section($t) { Write-Host ""; Write-Host "==== $t ====" }
$compose = @("compose", "--env-file", ".env", "-f", "infra/docker/compose.yml")

try {
    if (-not (Select-String -Path ".env" -Pattern "^API_PORT=" -Quiet)) {
        Add-Content ".env" "`nAPI_PORT=8000"
        Write-Host "Added API_PORT=8000 to .env"
    }

    Section "Build API images (runtime + dev)"
    & docker @compose --profile test build api api-test 2>&1 | Select-Object -Last 25

    Section "Start stack (incl. api)"
    & docker @compose up -d 2>&1

    Section "Wait for api healthy (max 2 min)"
    $deadline = (Get-Date).AddMinutes(2)
    do {
        $state = (& docker @compose ps --format "{{.Service}}={{.Health}}" 2>$null) -join " "
        Write-Host "$(Get-Date -Format HH:mm:ss)  $state"
        if ($state -match "api=healthy") { break }
        Start-Sleep -Seconds 5
    } while ((Get-Date) -lt $deadline)

    Section "GET /health and /ready"
    foreach ($p in "/health", "/ready") {
        try {
            $r = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:8000$p"
            Write-Host "$p -> $($r.StatusCode) $($r.Content)"
            Write-Host "   X-Request-ID: $($r.Headers['X-Request-ID'])  nosniff: $($r.Headers['X-Content-Type-Options'])"
        } catch { Write-Host "$p -> ERROR $($_.Exception.Message)" }
    }

    Section "API tests in container (unit + integration + mypy + ruff)"
    & docker @compose --profile test run --rm api-test 2>&1
    Write-Host "api-test exit code: $LASTEXITCODE"

    Section "api logs (last 10)"
    & docker @compose logs --no-color --tail 10 api 2>&1

    Section "verify_stack.py"
    python infra/docker/verify_stack.py
    Write-Host "verify exit code: $LASTEXITCODE"
}
catch { Write-Host "SCRIPT ERROR: $_" }
finally {
    Stop-Transcript | Out-Null
    Write-Host ""
    Write-Host "Log saved to $log - tell Claude: 'log parh lo'"
}
