@echo off
title OBS Connection Test
echo ===================================================
echo Testing OBS WebSocket Connection
echo ===================================================
echo.

cd /d "%~dp0"

REM Check virtual environment
if not exist "venv\Scripts\activate.bat" (
    echo [ERROR] Virtual environment not found. Run INSTALL.bat first.
    echo.
    pause
    exit /b 1
)
call venv\Scripts\activate.bat

echo Testing connection to OBS Studio...
echo Host: localhost
echo Port: 4455
echo Password: (from config file)
echo.

python -c "import os; exec('for line in open(\"config/windows_test.env\"): exec(\"os.environ[line.split(\\\"=\\\")[0].strip()] = line.split(\\\"=\\\", 1)[1].strip()\\\" if \\\"=\\\" in line and not line.startswith(\\\"#\\\") else \\\"\\\")'); import obsws_python as obs; client = obs.ReqClient(host='localhost', port=4455, password=os.getenv('OBS_PASSWORD', ''), timeout=5); version = client.get_version(); print('SUCCESS: Connected to OBS Studio'); print(f'OBS Version: {version.obs_version}'); print(f'WebSocket Version: {version.obs_web_socket_version}'); print(''); print('OBS WebSocket is working correctly!')"

if %errorlevel% neq 0 (
    echo.
    echo ERROR: Could not connect to OBS
    echo.
    echo Troubleshooting:
    echo 1. Make sure OBS Studio 31.1.2+ is running
    echo 2. Enable WebSocket server in OBS:
    echo    - Tools ^> WebSocket Server Settings
    echo    - Enable WebSocket Server
    echo    - Port: 4455
    echo    - Password: (match your config file)
    echo 3. Click Apply and OK
    echo 4. Run this test again
)

echo.
pause
