@echo off
REM ============================================================
REM  Hyperium master launcher
REM  Picks one of the apps in this monorepo and starts it in
REM  its own folder (each app is self-contained).
REM ============================================================
setlocal
cd /d "%~dp0"

:menu
echo.
echo   HYPERIUM
echo   ========
echo   1^) AI consultancy OS   (hyperium-ai)   -^> http://127.0.0.1:8765
echo   2^) Admin ^& Finance     (admin-finance) -^> http://127.0.0.1:5173
echo   3^) Both                (for agent-driven finance, phase C)
echo   Q^) Quit
echo.
set /p choice="  Choose: "

if /i "%choice%"=="1" goto ai
if /i "%choice%"=="2" goto finance
if /i "%choice%"=="3" goto both
if /i "%choice%"=="q" goto end
echo   Unknown choice: %choice%
goto menu

:ai
echo.
echo   Starting hyperium-ai...
pushd "apps\hyperium-ai"
call start.bat
popd
goto end

:finance
echo.
echo   Starting admin-finance...
pushd "apps\admin-finance"
call start-admin-finance.bat
popd
goto end

:both
REM Phase C needs both running at once (the agent's finance tools call the
REM admin-finance API). Launch each in its own window so both stay up.
echo.
echo   Starting both apps, each in its own window...
start "Admin & Finance" cmd /k "cd /d %~dp0apps\admin-finance && start-admin-finance.bat"
start "Hyperium AI" cmd /k "cd /d %~dp0apps\hyperium-ai && start.bat"
echo   Launched. The finance API (:8930) must be up before an agent uses the
echo   finance tools; give it a few seconds on first run.
goto end

:end
endlocal
