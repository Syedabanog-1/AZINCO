# install-playwright-mcp.ps1
# Adds the official Playwright MCP server (@playwright/mcp) to Claude Desktop.
# Safe: backs up the existing config, keeps all other MCP servers, writes UTF-8 without BOM.
# Usage (PowerShell):
#   powershell -ExecutionPolicy Bypass -File "D:\syeda Gulzar Bano\azinco\tools\playwright-mcp\install-playwright-mcp.ps1"

$ErrorActionPreference = "Stop"

# 1. Check Node.js >= 20
try { $nodeVersion = (node -v) } catch { Write-Error "Node.js not found. Install Node.js 20+ from https://nodejs.org and re-run."; exit 1 }
$major = [int]($nodeVersion.TrimStart('v').Split('.')[0])
if ($major -lt 20) { Write-Error "Node.js $nodeVersion found; version 20+ is required."; exit 1 }
Write-Host "Node.js $nodeVersion OK"

# 2. Locate config
$configDir  = Join-Path $env:APPDATA "Claude"
$configPath = Join-Path $configDir "claude_desktop_config.json"
if (-not (Test-Path $configDir)) { New-Item -ItemType Directory -Path $configDir | Out-Null }

# 3. Load or create config
if (Test-Path $configPath) {
    $backup = "$configPath.bak-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
    Copy-Item $configPath $backup
    Write-Host "Backup written: $backup"
    $raw = Get-Content $configPath -Raw
    if ([string]::IsNullOrWhiteSpace($raw)) { $config = [pscustomobject]@{} } else { $config = $raw | ConvertFrom-Json }
} else {
    $config = [pscustomobject]@{}
}

# 4. Ensure mcpServers exists
if (-not ($config.PSObject.Properties.Name -contains "mcpServers")) {
    $config | Add-Member -NotePropertyName "mcpServers" -NotePropertyValue ([pscustomobject]@{})
}

# 5. Add / replace the playwright entry (cmd /c npx works reliably on Windows)
$playwright = [pscustomobject]@{
    command = "cmd"
    args    = @("/c", "npx", "-y", "@playwright/mcp@latest", "--isolated", "--viewport-size", "1366x768")
}
if ($config.mcpServers.PSObject.Properties.Name -contains "playwright") {
    $config.mcpServers.playwright = $playwright
    Write-Host "Existing 'playwright' entry updated."
} else {
    $config.mcpServers | Add-Member -NotePropertyName "playwright" -NotePropertyValue $playwright
    Write-Host "'playwright' entry added."
}

# 6. Write UTF-8 without BOM
$json = $config | ConvertTo-Json -Depth 20
[System.IO.File]::WriteAllText($configPath, $json, (New-Object System.Text.UTF8Encoding($false)))
Write-Host "Config saved: $configPath"

# 7. Pre-download the server and the Chromium browser
npx -y @playwright/mcp@latest --help | Out-Null
npx -y playwright install chromium

Write-Host ""
Write-Host "DONE. Now fully quit Claude Desktop (system tray -> Quit) and open it again."
Write-Host "Then tell Claude: 'playwright tools check karo'."
