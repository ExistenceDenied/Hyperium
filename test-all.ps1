# Run both apps' test suites from the umbrella root. Mirrors CI locally.
# Reuses an app's installed deps (node_modules / .venv) if present.
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$failed = @()

Write-Host "`n=== admin-finance (TypeScript) ===" -ForegroundColor Cyan
Push-Location (Join-Path $root 'apps/admin-finance')
try {
  if (-not (Test-Path 'node_modules')) { npm install --no-fund --no-audit }
  npm run typecheck
  npm test
  if ($LASTEXITCODE -ne 0) { $failed += 'admin-finance' }
} catch { $failed += 'admin-finance' } finally { Pop-Location }

Write-Host "`n=== hyperium-ai (Python) ===" -ForegroundColor Cyan
Push-Location (Join-Path $root 'apps/hyperium-ai')
try {
  if (-not (Test-Path '.venv')) {
    python -m venv .venv
    ./.venv/Scripts/python.exe -m pip install -q -e ".[dev,office]"
  }
  ./.venv/Scripts/python.exe -m pytest -q
  if ($LASTEXITCODE -ne 0) { $failed += 'hyperium-ai' }
} catch { $failed += 'hyperium-ai' } finally { Pop-Location }

Write-Host ""
if ($failed.Count -eq 0) {
  Write-Host "ALL GREEN" -ForegroundColor Green
  exit 0
} else {
  Write-Host ("FAILED: " + ($failed -join ', ')) -ForegroundColor Red
  exit 1
}
