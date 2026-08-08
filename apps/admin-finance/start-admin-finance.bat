@echo off
REM ============================================================
REM  Hyperium BV - Admin & Finance
REM  One-click launcher: starts the local API + web app and
REM  opens the browser. Data stays local under admin-finance\data.
REM ============================================================
setlocal
cd /d "%~dp0"

if not exist "node_modules" (
  echo Installing dependencies ^(first run^)...
  call npm install
  if errorlevel 1 (
    echo.
    echo npm install failed. Make sure Node.js is installed.
    pause
    exit /b 1
  )
)

echo.
echo Starting Admin ^& Finance ^(API on 8930, web on 5173^)...
echo Close this window to stop both servers.
echo.

REM Open the browser shortly after the dev servers boot.
start "" /b cmd /c "timeout /t 4 >nul & start "" http://localhost:5173"

call npm run dev

endlocal
