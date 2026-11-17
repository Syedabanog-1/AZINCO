# run-step-0.2.ps1 — start the AZINCO local stack and verify it.
# Run from PowerShell:
#   cd "D:\syeda Gulzar Bano\azinco"
#   powershell -ExecutionPolicy Bypass -File .\setup\run-step-0.2.ps1
# Everything is logged to .data\step-0.2-log.txt (git-ignored) so Claude can read the result.
# Secrets are never printed.

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
New-Item -ItemType Directory -Force ".data" | Out-Null
$log = Join-Path $root ".data\step-0.2-log.txt"
Start-Transcript -Path $log -Force | Out-Null

function Section($t) { Write-Host ""; Write-Host "==== $t ====" }
$compose = @("compose", "--env-file", ".env", "-f", "infra/docker/compose.yml")

try {
    Section "Versions"
    docker --version
    docker compose version
    python --version

    Section ".env"
    if (Test-Path ".env") { Write-Host ".env exists (kept)" }
    else { python infra/docker/generate_env.py }

    Section "Pull images"
    & docker @compose pull 2>&1 | Select-Object -Last 15

    Section "Start stack"
    & docker @compose up -d 2>&1

    Section "Wait for clamav (first start downloads signatures, max 10 min)"
    $deadline = (Get-Date).AddMinutes(10)
    do {
        $state = (& docker @compose ps --format "{{.Service}}={{.Health}}" 2>$null) -join " "
        Write-Host "$(Get-Date -Format HH:mm:ss)  $state"
        if ($state -match "clamav=healthy") { break }
        Start-Sleep -Seconds 20
    } while ((Get-Date) -lt $deadline)

    Section "docker compose ps"
    & docker @compose ps --all 2>&1

    Section "storage-init logs"
    & docker @compose logs --no-color storage-init 2>&1 | Select-Object -Last 20

    Section "verify_stack.py"
    python infra/docker/verify_stack.py
    Write-Host "verify exit code: $LASTEXITCODE"
}
catch {
    Write-Host "SCRIPT ERROR: $_"
}
finally {
    Stop-Transcript | Out-Null
    Write-Host ""
    Write-Host "Log saved to $log - tell Claude: 'log parh lo'"
}
