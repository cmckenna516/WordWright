@echo off
setlocal
title Start Wordwright
set "START_SCRIPT=%~dp0scripts\run.ps1"
set "SETUP_MARKER=%~dp0.setup-complete"

if not exist "%START_SCRIPT%" goto not_extracted
if not exist "%SETUP_MARKER%" goto not_ready

echo Starting Wordwright. Please wait...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%START_SCRIPT%"
if errorlevel 1 (
    echo.
    echo Wordwright could not start. Review the message above.
    pause
    exit /b 1
)
exit /b 0

:not_extracted
echo.
echo Wordwright cannot run from inside the downloaded ZIP file.
echo Right-click WordWright-main.zip, choose Extract All, and use the files
echo in the new extracted WordWright-main folder.
echo.
echo Missing required file: scripts\run.ps1
pause
exit /b 1

:not_ready
echo.
echo Wordwright setup has not completed successfully in this folder.
echo Double-click Setup Wordwright.cmd and wait for every functional check.
pause
exit /b 1

