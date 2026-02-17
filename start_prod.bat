@echo off
title OBS Digital Signage System (Production)
echo ===================================================
echo OBS Digital Signage Automation System - PRODUCTION
echo ===================================================
echo.

cd /d "%~dp0"

REM Set production environment
set ENVIRONMENT=production

echo Using production configuration (windows_prod.env)
echo.

REM Check configuration file exists
if not exist "config\windows_prod.env" (
    echo [ERROR] Configuration file not found: config\windows_prod.env
    echo Copy config\windows_prod.env.example to config\windows_prod.env
    echo and edit it with your credentials.
    echo.
    pause
    exit /b 1
)

REM Check virtual environment
if not exist "venv\Scripts\activate.bat" (
    echo [ERROR] Virtual environment not found. Run INSTALL.bat first.
    echo.
    pause
    exit /b 1
)
call venv\Scripts\activate.bat

echo Checking OBS connection...
echo.

REM Check if OBS is running
tasklist /FI "IMAGENAME eq obs64.exe" 2>NUL | find /I /N "obs64.exe">NUL
if "%ERRORLEVEL%"=="1" (
    echo WARNING: OBS Studio is not running
    echo The system will attempt to start OBS automatically
    echo.
)

echo Starting Digital Signage System...
echo.
echo Press Ctrl+C to stop the system
echo.
echo Log files location: %~dp0logs\
echo.

python src\main.py

if %errorlevel% neq 0 (
    echo.
    echo ===================================================
    echo System exited with error
    echo ===================================================
    echo.
    echo Check the logs for details:
    echo - %~dp0logs\digital_signage.log
    echo - %~dp0logs\errors.log
    echo.
)

pause
