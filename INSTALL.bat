@echo off
REM ============================================================================
REM OBS Digital Signage Automation System - Windows Installation Script
REM ============================================================================

echo.
echo ====================================================================
echo  OBS Digital Signage Automation System - Installation
echo ====================================================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH
    echo.
    echo Please install Python 3.10 or higher from:
    echo https://www.python.org/downloads/
    echo.
    echo Make sure to check "Add Python to PATH" during installation!
    echo.
    pause
    exit /b 1
)

echo [1/7] Python detected
python --version

REM Check Python version (must be 3.10+)
python -c "import sys; exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python 3.10 or higher is required
    echo.
    pause
    exit /b 1
)

REM Check for FFmpeg/FFprobe
echo.
echo [2/7] Checking for FFmpeg...
where ffprobe >nul 2>&1
if errorlevel 1 (
    echo [WARNING] FFmpeg/FFprobe not found in PATH
    echo Video duration detection will use fallback values.
    echo.
    echo Install FFmpeg with one of these commands:
    echo   winget install FFmpeg
    echo   choco install ffmpeg
    echo.
    echo Or download from: https://ffmpeg.org/download.html
) else (
    echo FFmpeg found
)

REM Create virtual environment
echo.
echo [3/7] Creating virtual environment...
if exist venv (
    echo Virtual environment already exists, skipping creation
) else (
    python -m venv venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment
        pause
        exit /b 1
    )
)

REM Activate virtual environment
echo.
echo [4/7] Activating virtual environment...
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo [ERROR] Failed to activate virtual environment
    pause
    exit /b 1
)

REM Upgrade pip
echo.
echo [5/7] Upgrading pip...
python -m pip install --upgrade pip --quiet

REM Install dependencies
echo.
echo [6/7] Installing dependencies...
pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies
    pause
    exit /b 1
)

REM Setup configuration files
echo.
echo [7/7] Setting up configuration files...
if not exist "config\windows_test.env" (
    echo Creating config\windows_test.env from example...
    copy "config\windows_test.env.example" "config\windows_test.env" >nul
    echo [IMPORTANT] Please edit config\windows_test.env with your credentials!
) else (
    echo config\windows_test.env already exists, skipping
)

echo.
echo ====================================================================
echo  Installation Complete!
echo ====================================================================
echo.
echo IMPORTANT: Configure your settings before running!
echo.
echo 1. Edit your configuration file:
echo    notepad config\windows_test.env
echo.
echo    Update these settings:
echo    - OBS_PASSWORD (OBS WebSocket password)
echo    - WEBDAV_HOST, WEBDAV_USERNAME, WEBDAV_PASSWORD
echo    - Or leave WebDAV settings empty for offline mode
echo.
echo 2. Install OBS Studio if not already installed:
echo    Download from: https://obsproject.com/download
echo.
echo 3. View the README for more information:
echo    type README.md
echo.
echo 4. Start the system:
echo    START.bat
echo.
echo For detailed documentation, see README.md
echo.
pause
