# finish-step-0.11.ps1 — place the CI files where GitHub expects them, then open a PR.
#   cd "D:\syeda Gulzar Bano\azinco"
#   powershell -ExecutionPolicy Bypass -File .\setup\finish-step-0.11.ps1
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

New-Item -ItemType Directory -Force ".github\workflows" | Out-Null
Copy-Item "setup\ci\ci.yml" ".github\workflows\ci.yml" -Force
Copy-Item "setup\ci\dependabot.yml" ".github\dependabot.yml" -Force
Copy-Item "setup\github-workflows-README.md" ".github\workflows\README.md" -Force
Write-Host "Placed .github\workflows\ci.yml, .github\dependabot.yml and .github\workflows\README.md"

Write-Host ""
Write-Host "Next (CI runs on the pull request):"
Write-Host "  git checkout -b ci/step-0.11"
Write-Host "  git add ."
Write-Host "  git commit -m `"ci: step 0.11 GitHub Actions pipeline, gitleaks config, dependabot`""
Write-Host "  git push -u origin ci/step-0.11"
Write-Host "Then open the pull request on GitHub and watch the four checks (python, web, security, stack)."
