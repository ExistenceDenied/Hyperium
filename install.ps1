# Hyperium one-click setup for Windows.
#
# Right-click this file and "Run with PowerShell", or run:  .\install.ps1
# It is safe to run more than once. It installs Hyperium, sets up its local
# model, and creates a launcher you double-click to open the web interface.

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

function Step($msg) { Write-Host "==> $msg" -ForegroundColor Cyan }

Step "Checking Python"
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    Write-Host "Python 3.11+ is required. Install it from" -ForegroundColor Yellow
    Write-Host "  https://www.python.org/downloads/  (tick 'Add to PATH'), then re-run." -ForegroundColor Yellow
    exit 1
}

Step "Creating the virtual environment"
if (-not (Test-Path ".venv")) { python -m venv .venv }
$venvPython = Join-Path $root ".venv\Scripts\python.exe"

Step "Installing Hyperium and its dependencies"
& $venvPython -m pip install --upgrade pip | Out-Null
& $venvPython -m pip install -e ".[dev,office]"

Step "Checking Ollama (the local AI engine)"
if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
    Write-Host "Ollama not found. Trying to install it with winget..."
    try {
        winget install --id Ollama.Ollama -e --accept-source-agreements --accept-package-agreements
    } catch {
        Write-Host "Could not install Ollama automatically." -ForegroundColor Yellow
        Write-Host "  Install it from https://ollama.com/download and run this script again." -ForegroundColor Yellow
        exit 1
    }
}

$model = if ($env:HYPERIUM_MODEL) { $env:HYPERIUM_MODEL } else { "qwen3:8b" }
Step "Downloading the local model ($model) - one-time, a few GB"
try { ollama pull $model } catch {
    Write-Host "Could not pull $model now. Once Ollama is running, run: ollama pull $model" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Hyperium is ready." -ForegroundColor Green
Write-Host "Double-click  start.bat  to open the web interface (http://127.0.0.1:8765)."
