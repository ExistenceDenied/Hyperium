@echo off
rem Double-click to launch Hyperium's web interface.
cd /d "%~dp0"
rem The local model to use. qwen3:30b-a3b is a mixture-of-experts model — 30B
rem total but only ~3B active per token — so it is both larger and faster than
rem the dense 14b on an 8 GB GPU. Change it to any model you have pulled (see:
rem ollama list); qwen3:latest (8B) is the fastest if you want snappier triage.
set HYPERIUM_MODEL=qwen3:30b-a3b

rem Stop any previous Hyperium server still holding the port, so this instance
rem can bind. A lingering process on 8765 is what causes "connection refused".
echo Freeing port 8765 if a previous session is still running...
powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }" >nul 2>&1

echo Starting Hyperium. A browser will open at http://127.0.0.1:8765
echo Close this window to stop.
rem Open the browser a few seconds later, once the server has had time to bind,
rem so the first page load succeeds instead of showing "connection refused".
start "" /min powershell -NoProfile -WindowStyle Hidden -Command "Start-Sleep 4; Start-Process 'http://127.0.0.1:8765'"
".venv\Scripts\python.exe" main.py serve
