@echo off
title Restore Important TRELAPP Files

set "PROJECT=%~dp0"
set "BACKUP=%PROJECT%IMPORTANT_FILES_BACKUP"

echo.
echo ================================================
echo       RESTORE IMPORTANT TRELAPP FILES
echo ================================================
echo.
echo WARNING:
echo This will replace the current important files
echo with the saved backup copies.
echo.

if not exist "%BACKUP%" (
    echo ERROR: The backup folder does not exist.
    echo.
    echo Expected location:
    echo %BACKUP%
    echo.
    pause
    exit /b 1
)

choice /C YN /M "Do you want to continue"

if errorlevel 2 (
    echo.
    echo Restore cancelled.
    pause
    exit /b 0
)

echo.

if exist "%BACKUP%\backend\routes\files.py" (
    if not exist "%PROJECT%backend\routes" mkdir "%PROJECT%backend\routes"
    copy /Y "%BACKUP%\backend\routes\files.py" "%PROJECT%backend\routes\files.py" >nul
    echo Restored: backend\routes\files.py
)

if exist "%BACKUP%\backend\server.py" (
    if not exist "%PROJECT%backend" mkdir "%PROJECT%backend"
    copy /Y "%BACKUP%\backend\server.py" "%PROJECT%backend\server.py" >nul
    echo Restored: backend\server.py
)

if exist "%BACKUP%\backend\Dockerfile" (
    if not exist "%PROJECT%backend" mkdir "%PROJECT%backend"
    copy /Y "%BACKUP%\backend\Dockerfile" "%PROJECT%backend\Dockerfile" >nul
    echo Restored: backend\Dockerfile
)

if exist "%BACKUP%\backend\requirements.txt" (
    if not exist "%PROJECT%backend" mkdir "%PROJECT%backend"
    copy /Y "%BACKUP%\backend\requirements.txt" "%PROJECT%backend\requirements.txt" >nul
    echo Restored: backend\requirements.txt
)

if exist "%BACKUP%\fly.toml" (
    copy /Y "%BACKUP%\fly.toml" "%PROJECT%fly.toml" >nul
    echo Restored: fly.toml
)

if exist "%BACKUP%\Dockerfile" (
    copy /Y "%BACKUP%\Dockerfile" "%PROJECT%Dockerfile" >nul
    echo Restored: Dockerfile
)

echo.
echo ================================================
echo Restore completed successfully.
echo ================================================
echo.
echo Review the restored files before committing them
echo to GitHub.
echo.

pause
