#!/bin/bash
# ============================================================================
# OBS Digital Signage System - Connection Test Script
# ============================================================================

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo ""
echo "===================================================================="
echo " OBS Digital Signage System - Connection Test"
echo "===================================================================="
echo ""

# Check Python
echo -e "${GREEN}[1/5]${NC} Checking Python..."
if command -v python3 &> /dev/null; then
    echo "       Python: $(python3 --version)"
else
    echo -e "       ${RED}Python 3 not found!${NC}"
    exit 1
fi

# Check virtual environment
echo -e "${GREEN}[2/5]${NC} Checking virtual environment..."
if [ -d "$SCRIPT_DIR/venv" ]; then
    source "$SCRIPT_DIR/venv/bin/activate"
    echo "       Virtual environment activated"
else
    echo -e "       ${YELLOW}No venv found - using system Python${NC}"
fi

# Check FFprobe
echo -e "${GREEN}[3/5]${NC} Checking FFprobe..."
if command -v ffprobe &> /dev/null; then
    echo "       FFprobe: $(ffprobe -version 2>&1 | head -1)"
else
    echo -e "       ${YELLOW}FFprobe not found (install: sudo apt install ffmpeg)${NC}"
fi

# Check OBS WebSocket
echo -e "${GREEN}[4/5]${NC} Testing OBS WebSocket connection..."
python3 -c "
import sys
sys.path.insert(0, '$SCRIPT_DIR/src')
try:
    from config.settings import Settings
    s = Settings()
    import obsws_python as obs
    client = obs.ReqClient(host=s.OBS_HOST, port=s.OBS_PORT, password=s.OBS_PASSWORD, timeout=5)
    v = client.get_version()
    print(f'       OBS Version: {v.obs_version}')
    print(f'       WebSocket:   {v.obs_web_socket_version}')
    print(f'       Platform:    {v.platform_description}')
except Exception as e:
    print(f'       Connection failed: {e}')
" 2>/dev/null

# Check dependencies
echo -e "${GREEN}[5/5]${NC} Checking dependencies..."
python3 -c "
import importlib
deps = ['obsws_python', 'webdav4', 'pygame', 'psutil', 'watchdog']
for dep in deps:
    try:
        m = importlib.import_module(dep)
        v = getattr(m, '__version__', 'installed')
        print(f'       {dep}: {v}')
    except ImportError:
        print(f'       {dep}: MISSING')
" 2>/dev/null

echo ""
echo "===================================================================="
echo ""

# Deactivate venv if activated
deactivate 2>/dev/null
