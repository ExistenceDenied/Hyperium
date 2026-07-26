@echo off
rem Double-click to launch Hyperium's web interface.
cd /d "%~dp0"
rem The local model to use. qwen3:latest is the 8B model and runs fully on an
rem 8 GB GPU. Change it to any model you have pulled (see: ollama list).
set HYPERIUM_MODEL=qwen3:latest
echo Starting Hyperium. A browser will open at http://127.0.0.1:8765
echo Close this window to stop.
start "" http://127.0.0.1:8765
".venv\Scripts\python.exe" main.py serve
