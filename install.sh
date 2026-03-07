#!/bin/bash
# ============================================================================
# OBS Digital Signage Automation System - Ubuntu/Linux Installation Script
# ============================================================================

echo ""
echo "===================================================================="
echo " OBS Digital Signage Automation System - Installation"
echo "===================================================================="
echo ""

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}[ERROR]${NC} Python 3 is not installed"
    echo ""
    echo "Please install Python 3.10 or higher:"
    echo "  sudo apt update"
    echo "  sudo apt install python3 python3-pip python3-venv"
    echo ""
    exit 1
fi

echo -e "${GREEN}[1/7]${NC} Python detected"
python3 --version

# Check Python version (must be 3.10+)
python3 -c "import sys; exit(0 if sys.version_info >= (3, 10) else 1)" 2>/dev/null
if [ $? -ne 0 ]; then
    echo -e "${RED}[ERROR]${NC} Python 3.10 or higher is required"
    echo ""
    exit 1
fi

# Check if FFmpeg is installed
echo ""
echo -e "${GREEN}[2/7]${NC} Checking for FFmpeg..."
if ! command -v ffprobe &> /dev/null; then
    echo -e "${YELLOW}[WARNING]${NC} FFmpeg/FFprobe not found"
    echo ""
    echo "FFmpeg is required for video duration detection."
    echo "Install it with:"
    echo "  sudo apt install ffmpeg"
    echo ""
    read -p "Continue without FFmpeg? (y/n) " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
else
    echo "FFmpeg found: $(ffprobe -version | head -n 1)"
fi

# Create virtual environment
echo ""
echo -e "${GREEN}[3/7]${NC} Creating virtual environment..."
if [ -d "venv" ]; then
    # Check if venv is valid (has activate script)
    if [ ! -f "venv/bin/activate" ]; then
        echo -e "${YELLOW}[WARNING]${NC} Virtual environment is corrupted, recreating..."
        rm -rf venv
    else
        echo "Virtual environment already exists, skipping creation"
    fi
fi

if [ ! -d "venv" ]; then
    python3 -m venv venv 2>&1 | tee /tmp/venv_error.log
    if [ $? -ne 0 ]; then
        echo -e "${RED}[ERROR]${NC} Failed to create virtual environment"
        echo ""
        if grep -q "ensurepip is not available" /tmp/venv_error.log; then
            echo "The python3-venv package is missing."
            echo ""
            echo "Install it with:"
            echo -e "${YELLOW}  sudo apt install python3-venv -y${NC}"
            echo ""
            echo "Then run this installation script again:"
            echo "  ./install.sh"
        fi
        echo ""
        exit 1
    fi
fi

# Activate virtual environment
echo ""
echo -e "${GREEN}[4/7]${NC} Activating virtual environment..."
source venv/bin/activate
if [ $? -ne 0 ]; then
    echo -e "${RED}[ERROR]${NC} Failed to activate virtual environment"
    exit 1
fi

# Upgrade pip
echo ""
echo -e "${GREEN}[5/7]${NC} Upgrading pip..."
python -m pip install --upgrade pip --quiet

# Install SDL2 dev libraries (needed if pygame must build from source)
echo ""
echo -e "${GREEN}[6/8]${NC} Checking SDL2 libraries for pygame..."
if ! dpkg -s libsdl2-dev &> /dev/null; then
    echo "Installing SDL2 development libraries..."
    sudo apt install libsdl2-dev libsdl2-mixer-dev libsdl2-image-dev -y 2>/dev/null || \
        echo -e "${YELLOW}[WARNING]${NC} Could not install SDL2 libs (pygame may still work with prebuilt wheel)"
else
    echo "SDL2 libraries already installed"
fi

# Install dependencies
echo ""
echo -e "${GREEN}[7/8]${NC} Installing dependencies..."
pip install -r requirements.txt --quiet
if [ $? -ne 0 ]; then
    echo -e "${RED}[ERROR]${NC} Failed to install dependencies"
    exit 1
fi

# Setup configuration files
echo ""
echo -e "${GREEN}[8/8]${NC} Setting up configuration files..."
if [ ! -f "config/ubuntu_prod.env" ]; then
    echo "Creating config/ubuntu_prod.env from example..."
    cp "config/ubuntu_prod.env.example" "config/ubuntu_prod.env"

    # Automatically set CONTENT_BASE_DIR to current directory
    CURRENT_DIR=$(pwd)
    sed -i "s|CONTENT_BASE_DIR=.*|CONTENT_BASE_DIR=$CURRENT_DIR|" "config/ubuntu_prod.env"

    echo -e "${YELLOW}[IMPORTANT]${NC} Please edit config/ubuntu_prod.env with your credentials!"
else
    echo "config/ubuntu_prod.env already exists, skipping"
fi

echo ""
echo "===================================================================="
echo " Installation Complete!"
echo "===================================================================="
echo ""
echo -e "${YELLOW}IMPORTANT: Configure your settings before running!${NC}"
echo ""
echo "1. Edit your configuration file:"
echo -e "   ${GREEN}nano config/ubuntu_prod.env${NC}"
echo ""
echo "   Update these settings:"
echo "   - OBS_PASSWORD (OBS WebSocket password)"
echo "   - WEBDAV_HOST, WEBDAV_USERNAME, WEBDAV_PASSWORD"
echo "   - Or leave WebDAV settings empty for offline mode"
echo ""
echo "   Press Ctrl+X, then Y, then Enter to save"
echo ""
echo "2. Install OBS Studio if not already installed:"
echo -e "   ${GREEN}sudo apt install obs-studio -y${NC}"
echo ""
echo "3. View the README for more information:"
echo -e "   ${GREEN}cat README.md${NC}"
echo ""
echo "4. Start the system:"
echo -e "   ${GREEN}./start.sh${NC}"
echo ""
echo "5. Access the admin panel:"
echo -e "   ${GREEN}http://localhost:8080${NC}  (or http://<ip-address>:8080 from another device)"
echo ""
echo "For detailed documentation, see README.md"
echo ""
