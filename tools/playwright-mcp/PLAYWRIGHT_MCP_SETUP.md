# Playwright MCP — setup for AZINCO (Windows)

Official package: `@playwright/mcp` (Microsoft). Requires Node.js 20+.
Purpose in AZINCO: let Claude drive a real browser against the **local** AZINCO web app
(http://localhost:3000) to explore UI flows, reproduce bugs, and draft Playwright E2E tests.
Use synthetic test data only. Never point it at production or log in with real client accounts.

## Option 1 — Claude Desktop app
1. Claude Desktop → Settings → Developer → Edit Config
   (file: `%APPDATA%\Claude\claude_desktop_config.json`).
2. Merge the `playwright` entry from `claude_desktop_config.playwright.json` into the existing
   `"mcpServers"` object (do not delete other servers).
3. If `npx` is not found on Windows, use:
   `"command": "cmd", "args": ["/c", "npx", "-y", "@playwright/mcp@latest", "--isolated"]`
4. Fully quit and restart Claude Desktop. The `playwright` tools appear under the tools menu.

## Option 2 — Claude Code CLI (inside the azinco repo)
```powershell
cd "D:\syeda Gulzar Bano\azinco"
claude mcp add playwright -- npx -y @playwright/mcp@latest --isolated
claude mcp list
```

## First run
```powershell
node -v                      # must be >= 20
npx -y @playwright/mcp@latest --help
npx playwright install chromium
```

## Flags used
- `--isolated` : fresh browser profile each session (no leftover logins/cookies).
- `--viewport-size 1366x768` : stable screenshots.
- Add `--headless` for unattended runs.

## Safety rules (AZINCO)
- Only `localhost` / dev / staging URLs with synthetic data.
- No real payment-provider pages; payment flows use the [MOCK] provider.
- Do not store screenshots that contain real personal or financial data.
