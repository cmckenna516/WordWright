@echo off
setlocal

if /i "%~1"=="--keep-open" goto begin_setup
start "Wordwright Setup" "%ComSpec%" /k call "%~f0" --keep-open
exit /b 0

:begin_setup
title Wordwright Setup
set "SETUP_SCRIPT=%~dp0scripts\setup.ps1"
set "SETUP_MARKER=%~dp0.setup-complete"

if not exist "%SETUP_SCRIPT%" goto not_extracted
if exist "%SETUP_MARKER%" del /q "%SETUP_MARKER%" >nul 2>&1

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SETUP_SCRIPT%"
if errorlevel 1 goto setup_failed
if not exist "%SETUP_MARKER%" goto setup_failed

echo.
echo Wordwright setup and functional checks are complete.
pause
exit /b 0

:not_extracted
echo.
echo Wordwright cannot run from inside the downloaded ZIP file.
echo.
echo 1. Close this window.
echo 2. Right-click WordWright-main.zip and choose Extract All.
echo 3. Open the new extracted WordWright-main folder.
echo 4. Double-click Setup Wordwright.cmd in that extracted folder.
echo.
echo Missing required file: scripts\setup.ps1
pause
exit /b 1

:setup_failed
echo.
echo Setup did not finish successfully. Review the message above.
echo Wordwright has not been marked ready to start.
pause
exit /b 1

