# finish-step-0.1.ps1 — run once from PowerShell inside the azinco folder:
#   cd "D:\syeda Gulzar Bano\azinco"
#   powershell -ExecutionPolicy Bypass -File .\setup\finish-step-0.1.ps1
# Places the two files that remote tools are not allowed to write, then initialises git.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Copy-Item "setup\pre-commit-config.yaml" ".pre-commit-config.yaml" -Force
New-Item -ItemType Directory -Force ".github\workflows" | Out-Null
Copy-Item "setup\github-workflows-README.md" ".github\workflows\README.md" -Force
Write-Host "Placed .pre-commit-config.yaml and .github\workflows\README.md"

if (-not (Test-Path ".git")) {
    git init -b main | Out-Null
    Write-Host "git repository initialised (branch: main)"
}

python -m pip install --upgrade pre-commit pytest
pre-commit install
python -m pytest
python infra\ci\check_structure.py
$env:SKIP = "no-commit-to-branch"   # we are still on main before the first commit
pre-commit run --all-files
Remove-Item Env:SKIP

Write-Host ""
Write-Host "Step 0.1 local checks finished. Next (first commit):"
Write-Host "  git add -A"
Write-Host "  git commit --no-verify -m 'chore: step 0.1 repo structure and conventions'"
Write-Host "  (--no-verify only for this very first commit on main; afterwards work on branches)"
