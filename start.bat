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
echo   Q^) Quit
echo.
set /p choice="  Choose: "

if /i "%choice%"=="1" goto ai
if /i "%choice%"=="2" goto finance
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

:end
endlocal
