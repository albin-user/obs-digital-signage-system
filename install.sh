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

# Install OBS Studio if missing
echo ""
echo -e "${GREEN}[8/10]${NC} Checking for OBS Studio..."
if command -v obs &> /dev/null || command -v obs-studio &> /dev/null; then
    echo "OBS Studio is already installed"
else
    echo -e "${YELLOW}[INFO]${NC} OBS Studio not found"
    read -p "Install OBS Studio now? (y/n) " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        sudo apt install obs-studio -y || \
            echo -e "${YELLOW}[WARNING]${NC} OBS install failed — install it manually with 'sudo apt install obs-studio'"
    else
        echo "Skipped — install OBS later with 'sudo apt install obs-studio'"
    fi
fi

# Configuration is created by the first-run web wizard, NOT here.
# (Pre-creating it would skip the wizard and leave placeholder credentials.)
echo ""
echo -e "${GREEN}[9/10]${NC} Configuration..."
if [ -f "config/ubuntu_prod.env" ]; then
    echo "config/ubuntu_prod.env already exists — the setup wizard will be skipped."
else
    echo "No config yet — the first-run setup wizard will collect it in your browser."
fi

# Optional: auto-start on boot + serve the panel on port 80
echo ""
echo -e "${GREEN}[10/10]${NC} Optional system integration..."
INSTALL_DIR="$(pwd)"

read -p "Set up auto-start on boot (recommended for a dedicated signage PC)? (y/n) " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    AUTOSTART_DIR="$HOME/.config/autostart"
    mkdir -p "$AUTOSTART_DIR"
    cat > "$AUTOSTART_DIR/obs-signage.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=OBS Digital Signage
Comment=Starts the digital signage system on login
Exec=$INSTALL_DIR/start.sh
Path=$INSTALL_DIR
X-GNOME-Autostart-enabled=true
Terminal=false
EOF
    echo -e "${GREEN}[OK]${NC} Auto-start enabled ($AUTOSTART_DIR/obs-signage.desktop)"
fi

read -p "Serve the web panel on port 80 (clean http://<ip> URL, no :8080)? (y/n) " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    # Option A: redirect port 80 to the app on 8080 (app stays non-root).
    # PREROUTING handles traffic from OTHER devices on the LAN.
    # OUTPUT (loopback) handles traffic from THIS PC's own browser
    # (http://localhost) — local traffic never traverses PREROUTING.
    # Note: on Ubuntu 24.04 the iptables command is the nft-backed shim;
    # these rules and netfilter-persistent work as expected.
    add_redirect() {
        local chain="$1"; shift
        if sudo iptables -t nat -C "$chain" "$@" -p tcp --dport 80 -j REDIRECT --to-ports 8080 2>/dev/null; then
            echo "  $chain redirect already present"
        else
            sudo iptables -t nat -A "$chain" "$@" -p tcp --dport 80 -j REDIRECT --to-ports 8080
            echo -e "  ${GREEN}[OK]${NC} $chain port 80 -> 8080 redirect added"
        fi
    }
    add_redirect PREROUTING
    add_redirect OUTPUT -o lo
    echo "Making the redirect persistent..."
    sudo apt install iptables-persistent -y 2>/dev/null && sudo netfilter-persistent save 2>/dev/null || \
        echo -e "${YELLOW}[WARNING]${NC} Could not persist the rule — it will reset on reboot. Re-run this step or install iptables-persistent manually."
fi

echo ""
echo "===================================================================="
echo " Installation Complete!"
echo "===================================================================="
echo ""
echo "Next steps:"
echo ""
echo -e "1. Start the system:  ${GREEN}./start.sh${NC}"
echo "   (or just reboot, if you enabled auto-start)"
echo ""
echo "2. Open the setup wizard in any browser on the same network:"
echo -e "   ${GREEN}http://<this-computer-ip>${NC}   (or http://localhost on this PC)"
echo "   The wizard generates an OBS password, configures OBS automatically,"
echo "   and tests your NAS connection — no manual config editing needed."
echo ""
echo -e "3. Check system health any time with:  ${GREEN}./doctor.sh${NC}"
echo ""
echo "For detailed documentation, see README.md and COMPLETE_GUIDE.md"
echo ""
