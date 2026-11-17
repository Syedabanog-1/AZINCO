# run-step-0.4.ps1 — build and start the full AZINCO app (stack + API + web UI) and verify it.
#   cd "D:\syeda Gulzar Bano\azinco"
#   powershell -ExecutionPolicy Bypass -File .\setup\run-step-0.4.ps1
# Output is logged to .data\step-0.4-log.txt (git-ignored). Secrets are never printed.
# TIP: do not click inside this PowerShell window while it runs (QuickEdit mode pauses it).

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
New-Item -ItemType Directory -Force ".data" | Out-Null
$log = Join-Path $root ".data\step-0.4-log.txt"
Start-Transcript -Path $log -Force | Out-Null
function Section($t) { Write-Host ""; Write-Host "==== $t ====" }
$compose = @("compose", "--env-file", ".env", "-f", "infra/docker/compose.yml")

try {
    foreach ($kv in @("API_PORT=8000", "WEB_PORT=3000")) {
        $k = $kv.Split("=")[0]
        if (-not (Select-String -Path ".env" -Pattern "^$k=" -Quiet)) { Add-Content ".env" "`n$kv"; Write-Host "Added $kv to .env" }
    }

    Section "Build images (api, api-test, web)"
    & docker @compose --profile test build api api-test web 2>&1 | Select-Object -Last 30

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

    Section "API tests in container"
    & docker @compose --profile test run --rm api-test 2>&1 | Select-Object -Last 15
    Write-Host "api-test exit code: $LASTEXITCODE"

    Section "web logs (last 10)"
    & docker @compose logs --no-color --tail 10 web 2>&1

    Section "verify_stack.py"
    python infra/docker/verify_stack.py
    Write-Host "verify exit code: $LASTEXITCODE"

    Section "Open the app"
    Start-Process "http://localhost:3000"
    Write-Host "AZINCO web: http://localhost:3000   status: http://localhost:3000/status   API docs: http://localhost:8000/docs"
}
catch { Write-Host "SCRIPT ERROR: $_" }
finally {
    Stop-Transcript | Out-Null
    Write-Host ""
    Write-Host "Log saved to $log - tell Claude: 'log parh lo'"
}
