@echo off
setlocal
cd /d "%~dp0"

rem ------------------------------------------------------------
rem  SteamPY price monitor - launcher
rem  Usage:
rem    start_monitor.bat          -> loop mode (poll every N sec)
rem    start_monitor.bat once     -> single check, then exit
rem  Exit codes:
rem    0 = alert sent / finished
rem    1 = config.json not filled
rem    2 = cookie expired or login failed
rem    3 = query/network failed
rem    4 = no matching buyer (once mode)
rem ------------------------------------------------------------

set "MODE="
if /i "%~1"=="once" set "MODE=--once"

set "PYTHON_EXE=C:\Users\cyh\.workbuddy\binaries\python\versions\3.13.12\python.exe"
if not exist "%PYTHON_EXE%" set "PYTHON_EXE=python"

"%PYTHON_EXE%" monitor.py %MODE%
set "CODE=%ERRORLEVEL%"

if "%CODE%"=="1" (
    echo [ERROR] config.json is not filled.
    echo         Edit it first: cookie / game_url / email settings.
)
if "%CODE%"=="2" (
    echo [ERROR] Cookie expired or login failed.
    echo         Log in at steampy.com and copy a fresh cookie.
)
if "%CODE%"=="3" (
    echo [ERROR] Query or network failed.
    echo         Check your connection, then run again.
)
if "%CODE%"=="4" (
    echo [INFO] No buyer below target price this round.
)

echo.
pause
exit /b %CODE%
