@echo off
rem Double-click to launch Hyperium's web interface.
cd /d "%~dp0"
set HYPERIUM_MODEL=qwen3:8b
echo Starting Hyperium. A browser will open at http://127.0.0.1:8765
echo Close this window to stop.
start "" http://127.0.0.1:8765
".venv\Scripts\python.exe" main.py serve
