@echo off
title Backup Important TRELAPP Files

set "PROJECT=%~dp0"
set "BACKUP=%PROJECT%IMPORTANT_FILES_BACKUP"

echo.
echo ================================================
echo       BACKING UP IMPORTANT TRELAPP FILES
echo ================================================
echo.

if not exist "%BACKUP%" mkdir "%BACKUP%"

if exist "%PROJECT%backend\routes\files.py" (
    mkdir "%BACKUP%\backend\routes" 2>nul
    copy /Y "%PROJECT%backend\routes\files.py" "%BACKUP%\backend\routes\files.py" >nul
    echo Backed up: backend\routes\files.py
)

if exist "%PROJECT%backend\server.py" (
    mkdir "%BACKUP%\backend" 2>nul
    copy /Y "%PROJECT%backend\server.py" "%BACKUP%\backend\server.py" >nul
    echo Backed up: backend\server.py
)

if exist "%PROJECT%backend\Dockerfile" (
    mkdir "%BACKUP%\backend" 2>nul
    copy /Y "%PROJECT%backend\Dockerfile" "%BACKUP%\backend\Dockerfile" >nul
    echo Backed up: backend\Dockerfile
)

if exist "%PROJECT%backend\requirements.txt" (
    mkdir "%BACKUP%\backend" 2>nul
    copy /Y "%PROJECT%backend\requirements.txt" "%BACKUP%\backend\requirements.txt" >nul
    echo Backed up: backend\requirements.txt
)

if exist "%PROJECT%fly.toml" (
    copy /Y "%PROJECT%fly.toml" "%BACKUP%\fly.toml" >nul
    echo Backed up: fly.toml
)

if exist "%PROJECT%Dockerfile" (
    copy /Y "%PROJECT%Dockerfile" "%BACKUP%\Dockerfile" >nul
    echo Backed up: Dockerfile
)

echo.
echo ================================================
echo Backup completed successfully.
echo.
echo Backup folder:
echo %BACKUP%
echo ================================================
echo.

pause
