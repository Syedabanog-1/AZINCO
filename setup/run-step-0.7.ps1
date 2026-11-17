# run-step-0.7.ps1 — build and verify Steps 0.6 (RLS) + 0.7 (auth, MFA, sign-in).
#   cd "D:\syeda Gulzar Bano\azinco"
#   powershell -ExecutionPolicy Bypass -File .\setup\run-step-0.7.ps1
# Output is logged to .data\step-0.7-log.txt (git-ignored). Secrets are never printed.
# TIP: do not click inside this PowerShell window while it runs (QuickEdit mode pauses it).

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
New-Item -ItemType Directory -Force ".data" | Out-Null
$log = Join-Path $root ".data\step-0.7-log.txt"
Start-Transcript -Path $log -Force | Out-Null
function Section($t) { Write-Host ""; Write-Host "==== $t ====" }
$compose = @("compose", "--env-file", ".env", "-f", "infra/docker/compose.yml")

try {
    Section ".env additions"
    foreach ($kv in @("API_PORT=8000", "WEB_PORT=3000", "AZINCO_REPORTING_CURRENCIES=PKR,USD")) {
        $k = $kv.Split("=")[0]
        if (-not (Select-String -Path ".env" -Pattern "^$k=" -Quiet)) { Add-Content ".env" "`n$kv"; Write-Host "Added $k" }
    }
    if (-not (Select-String -Path ".env" -Pattern "^AZINCO_MFA_ENCRYPTION_KEY=.{44}" -Quiet)) {
        $key = python -c "import base64,os;print(base64.urlsafe_b64encode(os.urandom(32)).decode())"
        Add-Content ".env" "`nAZINCO_MFA_ENCRYPTION_KEY=$key"
        Write-Host "Added AZINCO_MFA_ENCRYPTION_KEY (value not shown)"
    }

    Section "Build images (retry once on network errors)"
    $built = $false
    foreach ($attempt in 1, 2) {
        & docker @compose --profile test build migrate api api-test web 2>&1 | Select-Object -Last 25
        if ($LASTEXITCODE -eq 0) { $built = $true; break }
        Write-Host "Build attempt $attempt failed (exit $LASTEXITCODE). Retrying in 20 s..."
        Start-Sleep -Seconds 20
    }
    if (-not $built) { throw "Docker build failed twice - check your internet connection and run this script again." }

    Section "Start everything"
    & docker @compose up -d 2>&1

    Section "Wait for web healthy (max 3 min)"
    $deadline = (Get-Date).AddMinutes(3)
    do {
        $state = (& docker @compose ps --format "{{.Service}}={{.Health}}" 2>$null) -join " "
        Write-Host "$(Get-Date -Format HH:mm:ss)  $state"
        if ($state -match "web=healthy") { break }
        Start-Sleep -Seconds 5
    } while ((Get-Date) -lt $deadline)

    Section "Migrations (migrate container)"
    & docker @compose logs --no-color migrate 2>&1 | Select-Object -Last 10

    Section "API tests in container (alembic check + unit + DB + RLS isolation + auth flows + Money)"
    & docker @compose --profile test run --rm api-test 2>&1 | Select-Object -Last 25
    Write-Host "api-test exit code: $LASTEXITCODE"

    Section "verify_stack.py"
    python infra/docker/verify_stack.py
    Write-Host "verify exit code: $LASTEXITCODE"

    Section "Open the app"
    Start-Process "http://localhost:3000/register"
    Write-Host "Register: http://localhost:3000/register   Test inbox (Mailpit): http://localhost:8025   Sign in: http://localhost:3000/login"
}
catch { Write-Host "SCRIPT ERROR: $_" }
finally {
    Stop-Transcript | Out-Null
    Write-Host ""
    Write-Host "Log saved to $log - tell Claude: 'log parh lo'"
}
