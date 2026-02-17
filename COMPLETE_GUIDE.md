# OBS Digital Signage Automation System - Complete Guide

**Version**: 2.2.1
**Last Updated**: February 2026
**Production Ready**: Yes ✅

---

## Table of Contents

1. [System Overview](#system-overview)
2. [What You Need to Deploy](#what-you-need-to-deploy)
3. [Prerequisites](#prerequisites)
4. [Installation Guide - Ubuntu Desktop](#installation-guide---ubuntu-desktop)
5. [Installation Guide - Windows](#installation-guide---windows)
6. [OBS Studio Configuration](#obs-studio-configuration)
7. [Ubuntu Desktop Settings Configuration](#ubuntu-desktop-settings-configuration)
8. [System Configuration](#system-configuration)
9. [Adding Content](#adding-content)
10. [Running the System](#running-the-system)
11. [Troubleshooting](#troubleshooting)
12. [Advanced Configuration](#advanced-configuration)
13. [Security & Credentials](#security--credentials)
14. [Transferring from Windows to Ubuntu](#transferring-from-windows-to-ubuntu)
15. [Deployment Verification Checklist](#deployment-verification-checklist)

---

## System Overview

### What Does This System Do?

The OBS Digital Signage Automation System is a professional digital signage solution that:

1. **Automatically manages OBS Studio** - Starts OBS, creates scenes, manages transitions
2. **Displays your content** - Images and videos in a continuous loop
3. **Syncs from cloud storage** - Automatically downloads content from WebDAV/Synology NAS
4. **Plays background music** - Continuous audio loop (optional)
5. **Runs 24/7** - Self-healing with automatic recovery
6. **Works on dual monitors** - Fullscreen output on second display

### Perfect For:

- Church services and announcements
- Retail store displays
- Restaurant menu boards
- Office lobby displays
- Trade show booths
- Waiting room displays

### Technical Features:

- ✅ Automatic OBS scene creation
- ✅ Professional stinger transitions
- ✅ WebDAV cloud synchronization
- ✅ FFprobe video duration detection
- ✅ Health monitoring and auto-recovery
- ✅ Cross-platform (Windows & Ubuntu)
- ✅ Portable - runs from any folder
- ✅ Time-based scheduling (recurring + one-time events)
- ✅ Web admin panel for schedule management
- ✅ Per-schedule audio volume control
- ✅ Webhook notifications

---

## What You Need to Deploy

The repository contains documentation, tests, and development files that aren't needed on the target machine. Here's the short version:

**Required (about 25 files):**
- The entire `src/` directory (application code)
- `requirements.txt` and `pyproject.toml` (dependencies)
- One config template from `config/` for your OS (e.g., `ubuntu_prod.env.example`)
- One installer script (`install.sh` or `INSTALL.bat`)
- One start script (`start.sh` or `START.bat`)

**Not required:**
- Documentation files (`README.md`, `COMPLETE_GUIDE.md`, `CHANGELOG.md`) -- helpful but the system runs without them
- `tests/`, `claude.md`, `obs_ws_protocol.md` -- excluded from the repo (local dev files only)

**Created automatically:**
- `venv/` -- the installer creates this
- `config/*.env` -- the installer copies from `.example`
- `content/`, `logs/`, `config/schedules.json` -- created at runtime

See [File Structure Reference](#file-structure-reference) in the appendix for the complete list.

**Pre-flight check:** After installing, run `python src/main.py --check` to verify config, FFprobe, OBS connection, and WebDAV before starting the full system.

---

## Prerequisites

### Hardware Requirements

**Minimum:**
- CPU: Dual-core 2.0 GHz
- RAM: 4 GB
- Storage: 500 MB + content space
- Display: 1920x1080 (Full HD)
- Network: Internet connection (for WebDAV sync)

**Recommended:**
- CPU: Quad-core 2.5 GHz or better
- RAM: 8 GB or more
- Storage: SSD with 10 GB+ free space
- Display: Dual monitors (one for control, one for output)
- Network: Stable broadband connection

### Software Requirements

**Both Platforms:**
- Python 3.10 or higher
- OBS Studio 28+ with WebSocket v5
- FFmpeg (for video duration detection)
- Git (for downloading from GitHub)

**Ubuntu Specific:**
- Ubuntu Desktop 20.04 LTS or newer
- GNOME Desktop Environment

**Windows Specific:**
- Windows 10 or Windows 11
- 64-bit operating system

---

## Installation Guide - Ubuntu Desktop

### Step 1: Update System

Open Terminal and update your system:

```bash
sudo apt update
sudo apt upgrade -y
```

### Step 2: Install Required Software

Install Python 3, Git, and other dependencies:

```bash
# Install Python 3 and pip
sudo apt install python3 python3-pip python3-venv -y

# Install Git (for downloading from GitHub)
sudo apt install git -y

# Verify installations
python3 --version
git --version
```

Should show Python 3.10 or higher. If not, install:

```bash
sudo apt install python3 python3-pip python3-venv -y
```

### Step 3: Install FFmpeg

FFmpeg is required for video duration detection:

```bash
sudo apt install ffmpeg -y
```

Verify installation:

```bash
ffprobe -version
```

### Step 4: Install OBS Studio

#### Method 1: Ubuntu Repository (Easier)

```bash
sudo apt install obs-studio -y
```

#### Method 2: Official PPA (Latest Version - Recommended)

```bash
# Add OBS Studio PPA
sudo add-apt-repository ppa:obsproject/obs-studio
sudo apt update

# Install OBS Studio
sudo apt install obs-studio -y
```

Verify installation:

```bash
obs --version
```

### Step 5: Get the System Files

**If you already have the system on a Windows PC**, see [Transferring from Windows to Ubuntu](#transferring-from-windows-to-ubuntu) for detailed instructions on transferring files using USB drive, SCP/SSH, Git, or cloud storage.

**If downloading fresh**, choose a location for the system:

```bash
cd ~
```

**Option A: Clone from GitHub (Recommended)**

```bash
git clone https://github.com/albin-user/obs-digital-signage-system.git
cd obs-digital-signage-system

# Make scripts executable (REQUIRED on Linux)
chmod +x install.sh start.sh
```

**Option B: If you have a zip file**

```bash
unzip obs-digital-signage-system.zip
cd obs-digital-signage-system

# Make scripts executable (REQUIRED on Linux)
chmod +x install.sh start.sh
```

### Step 6: Run Installation Script

```bash
./install.sh
```

The script will:
1. Check Python version
2. Check for FFmpeg
3. Create virtual environment
4. Install Python dependencies
5. Create configuration file from template

**Important**: When prompted about FFmpeg, if not found, install it before continuing.

### Step 8: Configure the System

Edit the configuration file:

```bash
nano config/ubuntu_prod.env
```

**Minimum required settings:**

```ini
# OBS WebSocket Settings (leave password empty if OBS has no password)
OBS_PASSWORD=

# WebDAV Settings (leave empty for offline mode)
WEBDAV_HOST=https://your-nas-server.com
WEBDAV_USERNAME=your_username
WEBDAV_PASSWORD=your_password
WEBDAV_ROOT_PATH=/path/to/content

# Media Settings
IMAGE_DISPLAY_TIME=15
TRANSITION_START_OFFSET=2.0
```

Press `Ctrl+X`, then `Y`, then `Enter` to save.

**For offline mode** (no WebDAV), leave WebDAV settings empty:

```ini
WEBDAV_HOST=
WEBDAV_USERNAME=
WEBDAV_PASSWORD=
```

You're done with basic installation! Continue to [OBS Studio Configuration](#obs-studio-configuration).

---

## Installation Guide - Windows

### Step 1: Install Python

1. Download Python from https://www.python.org/downloads/
2. Run the installer
3. ⚠️ **IMPORTANT**: Check ✅ "Add Python to PATH"
4. Click "Install Now"
5. Wait for installation to complete

Verify installation:

1. Open Command Prompt (Win+R, type `cmd`, press Enter)
2. Type: `python --version`
3. Should show Python 3.10 or higher

### Step 2: Install FFmpeg

#### Method 1: Using Chocolatey (Easiest)

If you have Chocolatey installed:

```cmd
choco install ffmpeg -y
```

#### Method 2: Using winget (Windows 10/11)

```cmd
winget install FFmpeg
```

#### Method 3: Manual Installation

1. Download FFmpeg from https://ffmpeg.org/download.html
2. Extract to `C:\ffmpeg`
3. Add to PATH:
   - Open Start Menu, search "Environment Variables"
   - Click "Environment Variables" button
   - Under "System variables", find "Path", click "Edit"
   - Click "New", add: `C:\ffmpeg\bin`
   - Click "OK" on all dialogs
4. Restart Command Prompt

Verify installation:

```cmd
ffprobe -version
```

### Step 3: Install OBS Studio

1. Download OBS Studio from https://obsproject.com/download
2. Run the installer
3. Follow the installation wizard
4. Complete installation

Verify installation:

```cmd
"C:\Program Files\obs-studio\bin\64bit\obs64.exe" --version
```

### Step 4: Download the System

1. Download the system folder
2. Extract to a location of your choice, for example:
   - `C:\DigitalSignage\` or
   - `D:\OBS-Signage\` or
   - Your Desktop

**Important**: The system can be placed anywhere! It will work from any location.

### Step 5: Run Installation Script

1. Open the system folder
2. Double-click `INSTALL.bat`
3. Wait for installation to complete

The script will:
1. Check Python version (3.10+ required)
2. Check for FFmpeg/FFprobe (warns if missing)
3. Create virtual environment
4. Install Python dependencies
5. Create configuration file from template

### Step 6: Configure the System

1. Open the `config` folder
2. Right-click `windows_test.env`
3. Choose "Edit with Notepad" (or your preferred text editor)

**Minimum required settings:**

```ini
# OBS WebSocket Settings
OBS_PASSWORD=

# WebDAV Settings (leave empty for offline mode)
WEBDAV_HOST=https://your-nas-server.com
WEBDAV_USERNAME=your_username
WEBDAV_PASSWORD=your_password
WEBDAV_ROOT_PATH=/path/to/content

# Media Settings
IMAGE_DISPLAY_TIME=15
TRANSITION_START_OFFSET=2.0
```

Save and close.

**For offline mode**, leave WebDAV settings empty and manually add files to the `content` folder.

You're done with basic installation! Continue to [OBS Studio Configuration](#obs-studio-configuration).

---

## OBS Studio Configuration

### First-Time OBS Setup

#### Step 1: Launch OBS Studio

**Ubuntu:**
```bash
obs
```

**Windows:**
- Double-click the OBS Studio icon on your desktop, or
- Start Menu → OBS Studio

#### Step 2: Skip the Auto-Configuration Wizard

When OBS first launches, it will show an "Auto-Configuration Wizard":

1. Click "Cancel" - we'll configure manually for digital signage use

#### Step 3: Configure OBS Settings

Click **File → Settings** (or **Tools → Settings** on some versions)

##### **General Tab:**
- ✅ Enable "Automatically record when streaming"
- ❌ Disable "Show confirmation dialog when starting streams"
- ❌ Disable "Show confirmation dialog when stopping streams"

##### **Output Tab:**
1. Output Mode: "Simple"
2. Video Bitrate: 2500 Kbps (for recording if needed)
3. Recording Format: MP4 (if you want to record the output)
4. Recording Quality: "High Quality, Medium File Size"

##### **Video Tab:**
1. Base (Canvas) Resolution: **1920x1080**
2. Output (Scaled) Resolution: **1920x1080**
3. Downscale Filter: Lanczos (Sharpened scaling, 36 samples)
4. Common FPS Values: **30** or **60** (30 is fine for digital signage)

Click **OK** to save settings.

### Step 4: Enable WebSocket Server

This is crucial for the automation system to control OBS!

1. Click **Tools → WebSocket Server Settings**
2. ✅ Check "Enable WebSocket server"
3. Server Port: **4455** (default, leave as is)
4. **Enable Authentication**:
   - ❌ **Uncheck this** for easier setup (recommended), or
   - ✅ Check it and set a password (must match `OBS_PASSWORD` in config)
5. Click **OK**

**Important Notes:**
- If you don't set a password, leave `OBS_PASSWORD=` empty in your config
- If you set a password (e.g., "mypassword"), set `OBS_PASSWORD=mypassword` in config

### Step 5: Configure Stinger Transition (Optional but Recommended)

Stinger transitions make your content changes look professional.

1. In the main OBS window, find "Scene Transitions" section (usually bottom-right)
2. Click the **+** button next to the dropdown
3. Select **"Stinger"**
4. Name it: "Stinger Transition"
5. Click **OK**

Configure the stinger:

1. Click the **⚙️ (gear icon)** next to the transition dropdown
2. **Video file**: Browse and select your stinger video file
   - This is a short video (usually 1-2 seconds) that plays during transitions
   - Common formats: MP4, MOV
   - Example: A "whoosh" animation or logo reveal
3. **Transition Point Type**: "Time (milliseconds)"
4. **Transition Point**: Set to when your stinger should cut to the next scene
   - For a 2-second stinger, set to 2000ms
5. Click **OK**

Set as default transition:

1. In the Scene Transitions dropdown, select "Stinger Transition"
2. This is now your default transition

**Don't have a stinger video?**
- You can use the default "Fade" transition
- Or download free stinger transitions from sites like:
  - https://mixkit.co/free-stock-video/transitions/
  - https://www.videvo.net/

### Step 6: Remove Default Scenes (Optional)

OBS creates default scenes. You can remove them:

1. In the "Scenes" panel, right-click "Scene"
2. Select "Remove"
3. Confirm deletion

Don't worry - the automation system will create all necessary scenes automatically!

### Step 7: Configure Fullscreen Projector (Important!)

This is how you'll display the content on your second monitor or TV.

#### For Dual Monitor Setup:

1. Connect your second monitor/TV
2. In OBS, right-click in the preview area
3. Select **Fullscreen Projector (Program) → [Your Second Monitor]**
4. The second display should now show the OBS program output in fullscreen

**Example:**
- Monitor 1 (main): Shows OBS interface for control
- Monitor 2 (TV/display): Shows fullscreen output to audience

#### For Single Monitor Setup:

You can still use projector mode, but it will cover your entire screen:

1. Right-click preview area
2. Select **Fullscreen Projector (Program) → [Your Monitor]**
3. Press **Esc** to exit fullscreen when needed

**Note**: The automation system can set up the projector automatically, but it's good to know how to do it manually.

### Step 8: Test OBS WebSocket Connection

Before running the full system, test the connection:

**Ubuntu:**
```bash
cd obs-digital-signage-system
./start.sh
```

**Windows:**
Double-click `TEST.bat`

You should see:
```
Testing OBS WebSocket connection...
✓ OBS Studio is running
✓ Connected to OBS WebSocket
✓ OBS Version: [version info]
```

If you see errors, verify:
- OBS is running
- WebSocket server is enabled
- Port is 4455
- Password matches config (or is empty)

---

## Ubuntu Desktop Settings Configuration

For a professional 24/7 digital signage display, you need to configure Ubuntu to:
1. Auto-login
2. Prevent screen from sleeping
3. Hide desktop icons/taskbar (optional)
4. Auto-start the system on boot

### Step 1: Enable Auto-Login

This ensures the system starts automatically when the computer boots.

#### Using GUI:

1. Open **Settings** (click top-right corner → Settings)
2. Go to **Users**
3. Click **Unlock** (enter your password)
4. Toggle **Automatic Login** to ON
5. Close Settings

#### Using Command Line:

Edit the GDM configuration:

```bash
sudo nano /etc/gdm3/custom.conf
```

Find the `[daemon]` section and add/uncomment:

```ini
[daemon]
AutomaticLoginEnable=true
AutomaticLogin=your_username
```

Replace `your_username` with your actual username.

Save (Ctrl+X, Y, Enter) and reboot to test.

### Step 2: Disable Screen Blanking and Sleep

Prevent the display from turning off or going to sleep.

#### Using GUI:

1. Open **Settings**
2. Go to **Power**
3. Set **Blank screen**: **Never**
4. Set **Automatic Suspend**: **Off**
5. Set **Screen Brightness**: **100%** (or desired level)
6. Toggle **Dim screen when inactive**: **Off**

#### Using Command Line:

```bash
# Disable screen blanking
gsettings set org.gnome.desktop.session idle-delay 0

# Disable screen saver
gsettings set org.gnome.desktop.screensaver idle-activation-enabled false

# Prevent automatic suspend
gsettings set org.gnome.settings-daemon.plugins.power sleep-inactive-ac-type 'nothing'
gsettings set org.gnome.settings-daemon.plugins.power sleep-inactive-battery-type 'nothing'
```

### Step 3: Disable Notifications (Optional)

Prevents notification popups from appearing on the display.

```bash
gsettings set org.gnome.desktop.notifications show-banners false
```

Or via GUI:
1. **Settings** → **Notifications**
2. Toggle **Notification Banners**: **Off**

### Step 4: Hide Desktop Icons and Dock (Optional)

For a clean, professional look:

```bash
# Hide desktop icons
gsettings set org.gnome.desktop.background show-desktop-icons false

# Auto-hide the dock
gsettings set org.gnome.shell.extensions.dash-to-dock autohide true
gsettings set org.gnome.shell.extensions.dash-to-dock dock-fixed false

# Or hide the dock completely
gsettings set org.gnome.shell.extensions.dash-to-dock autohide true
gsettings set org.gnome.shell.extensions.dash-to-dock dock-position 'BOTTOM'
gsettings set org.gnome.shell.extensions.dash-to-dock autohide-in-fullscreen true
```

### Step 5: Configure Auto-Start on Boot

Create a startup application to launch the system automatically.

#### Method 1: Using Startup Applications GUI

1. Press **Super** (Windows key) and search for **Startup Applications**
2. Click **Add**
3. Fill in:
   - **Name**: `OBS Digital Signage`
   - **Command**: `/home/your_username/obs-digital-signage-system/start.sh`
   - **Comment**: `Starts OBS digital signage system`
4. Click **Add**

Replace `/home/your_username/obs-digital-signage-system/` with your actual path.

#### Method 2: Using systemd (Advanced)

A template service file is included at `deployment/obs-signage.service`. Copy and customise it:

```bash
sudo cp deployment/obs-signage.service /etc/systemd/system/obs-signage.service
sudo nano /etc/systemd/system/obs-signage.service
```

Replace `your_username` and paths as needed. The template includes `AmbientCapabilities=CAP_NET_BIND_SERVICE` so the service can bind to port 80 without running as root.

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable obs-signage.service
sudo systemctl start obs-signage.service
```

Check status:

```bash
sudo systemctl status obs-signage.service
```

### Step 6: Configure Display Settings

For optimal display:

1. **Settings** → **Displays**
2. Select your display
3. Set **Resolution**: **1920x1080** (or native resolution)
4. Set **Refresh Rate**: **60 Hz** (or highest available)
5. **Scale**: **100%**
6. **Primary Display**: Select the display for OBS output
7. Click **Apply**

### Step 7: Disable Automatic Updates (Optional)

Prevents unexpected reboots during operation:

```bash
# Disable automatic updates
sudo systemctl disable apt-daily.timer
sudo systemctl disable apt-daily-upgrade.timer
```

**Note**: You should still manually update the system during maintenance windows.

### Step 8: Test Auto-Start

Reboot the system:

```bash
sudo reboot
```

After reboot:
1. System should auto-login
2. OBS should start automatically (if using systemd service)
3. Digital signage system should begin running
4. Content should appear on the second display

---

## System Configuration

### Configuration File: `config/ubuntu_prod.env` (Linux) or `config/windows_test.env` (Windows)

#### Essential Settings

```ini
# ============================================================================
# OBS WebSocket Settings
# ============================================================================
OBS_HOST=localhost
OBS_PORT=4455
OBS_PASSWORD=
OBS_TIMEOUT=10
OBS_STARTUP_DELAY=15
```

**Explanation:**
- `OBS_HOST`: Always `localhost` (OBS runs on same machine)
- `OBS_PORT`: WebSocket port (default 4455)
- `OBS_PASSWORD`: Leave empty if OBS has no password, or set your password
- `OBS_STARTUP_DELAY`: Seconds to wait for OBS to start (15 is safe)

#### WebDAV/Cloud Storage Settings

```ini
# ============================================================================
# WebDAV/Synology Settings
# ============================================================================
WEBDAV_HOST=https://storebox.example.com
WEBDAV_PORT=5006
WEBDAV_USERNAME=signage_user
WEBDAV_PASSWORD=your_secure_password
WEBDAV_TIMEOUT=30
WEBDAV_SYNC_INTERVAL=30
WEBDAV_ROOT_PATH=/digital_signage/content
```

**Explanation:**
- `WEBDAV_HOST`: Your WebDAV server URL (e.g., Synology NAS)
- `WEBDAV_USERNAME/PASSWORD`: Your WebDAV credentials
- `WEBDAV_SYNC_INTERVAL`: How often to sync (30 = every 30 seconds)
- `WEBDAV_ROOT_PATH`: Path to your content folder on the server

**For Offline Mode** (no WebDAV):
```ini
WEBDAV_HOST=
WEBDAV_USERNAME=
WEBDAV_PASSWORD=
```

#### Media Settings

```ini
# ============================================================================
# Media Settings
# ============================================================================
VIDEO_WIDTH=1920
VIDEO_HEIGHT=1080
VIDEO_FPS=30
IMAGE_DISPLAY_TIME=15
MAX_VIDEO_DURATION=900
SLIDE_TRANSITION_SECONDS=15
```

**Explanation:**
- `IMAGE_DISPLAY_TIME`: How long each image shows (in seconds)
- `MAX_VIDEO_DURATION`: Maximum video length (900 = 15 minutes)
- `SLIDE_TRANSITION_SECONDS`: Same as `IMAGE_DISPLAY_TIME`

#### Transition Settings

```ini
# ============================================================================
# Transition Settings
# ============================================================================
TRANSITION_START_OFFSET=2.0
```

**Explanation:**
- `TRANSITION_START_OFFSET`: Start transition N seconds before VIDEO ends
- For a 2-second stinger, set to `2.0`
- Images always display full duration (this only affects videos)

**Example:**
- 30-second video with offset=2.0
- Video plays for 28 seconds
- At 28 seconds, stinger transition starts
- Video continues playing under the stinger for final 2 seconds
- Seamless transition to next content

#### Audio Settings

```ini
# ============================================================================
# Audio Settings
# ============================================================================
AUDIO_SAMPLE_RATE=48000
AUDIO_CHANNELS=2
AUDIO_BUFFER_SIZE=1024
```

**Explanation:**
- Default settings work for most cases
- Only change if you have audio issues

#### Scheduling Settings

```ini
# ============================================================================
# Scheduling Settings
# ============================================================================
SCHEDULE_ENABLED=true
TIMEZONE=UTC
SCHEDULE_CHECK_INTERVAL=60
MANUAL_CONTENT_FOLDER=
```

**Explanation:**
- `SCHEDULE_ENABLED`: Enable/disable automatic scheduling (true/false)
- `TIMEZONE`: Your local timezone for schedule calculations (e.g., `UTC`, `America/New_York`, `Europe/London`)
- `SCHEDULE_CHECK_INTERVAL`: How often to check for schedule changes (seconds)
- `MANUAL_CONTENT_FOLDER`: Override folder for testing (only when SCHEDULE_ENABLED=false)

#### Web Admin Panel Settings

```ini
# ============================================================================
# Web Admin Panel
# ============================================================================
WEB_UI_ENABLED=true
WEB_UI_PORT=80
```

**Explanation:**
- `WEB_UI_ENABLED`: Enable/disable the web admin panel (true/false)
- `WEB_UI_PORT`: Port for the web UI (default: 80)

#### Notification Settings

```ini
# ============================================================================
# Notifications (Optional)
# ============================================================================
NOTIFICATION_ENABLED=false
NOTIFICATION_WEBHOOK_URL=
```

**Explanation:**
- `NOTIFICATION_ENABLED`: Enable HTTP webhook notifications on events
- `NOTIFICATION_WEBHOOK_URL`: URL to POST notifications to (e.g., Slack webhook)

Events that trigger notifications: system startup, shutdown, OBS crash, WebDAV sync failure.

#### Logging

```ini
# ============================================================================
# Logging
# ============================================================================
LOG_LEVEL=INFO
```

**Options:**
- `DEBUG`: Detailed information (useful for troubleshooting)
- `INFO`: Normal operation information (recommended)
- `WARNING`: Only warnings and errors
- `ERROR`: Only errors

---

## Adding Content

### Supported File Formats

**Videos:**
- .mp4 (recommended)
- .mov
- .avi
- .mkv
- .wmv
- .webm
- .m4v

**Images:**
- .jpg, .jpeg (recommended)
- .png
- .bmp
- .gif
- .tiff
- .webp

**Audio** (background music):
- .mp3 (recommended)
- .wav
- .ogg
- .flac
- .m4a

### Method 1: WebDAV/Cloud Sync (Recommended)

1. Upload files to your WebDAV server (e.g., Synology NAS)
2. Place files in the folder specified in `WEBDAV_ROOT_PATH`
3. Files will automatically download within 30 seconds
4. New scenes will be created automatically
5. Content will appear in rotation

**Example:** Synology NAS
1. Open Synology File Station
2. Navigate to `/digital_signage/content/`
3. Upload your images/videos
4. Done! System syncs automatically

### Method 2: Manual/Offline (No WebDAV)

1. Open the system folder
2. Navigate to the `content` folder
3. Copy your images and videos into this folder
4. Restart the system or wait for next scan

**File naming tips:**
- Use descriptive names: `announcement_2024.jpg`
- Files are displayed alphabetically
- Prefix with numbers for order: `01_welcome.mp4`, `02_menu.jpg`

### Background Music

1. Place ONE audio file in the `content` folder
2. The system will automatically detect and play it
3. Audio loops continuously
4. Video audio is muted (only background music plays)

**Note:** Only one audio file is supported. If multiple audio files exist, the first one found will be used.

### Content Best Practices

**Image Specifications:**
- Resolution: 1920x1080 (Full HD)
- Aspect Ratio: 16:9
- Format: JPG (for photos) or PNG (for graphics/transparency)
- File Size: Under 5 MB each

**Video Specifications:**
- Resolution: 1920x1080 (Full HD)
- Frame Rate: 30 fps or 60 fps
- Format: MP4 with H.264 codec
- Audio: AAC (will be muted, only background music plays)
- Length: Under 15 minutes (MAX_VIDEO_DURATION setting)
- File Size: Under 100 MB each (for smooth playback)

**Example Content Structure:**
```
content/
├── 01_welcome_slide.jpg
├── 02_announcements.mp4
├── 03_menu_board.jpg
├── 04_promotion_video.mp4
├── 05_thank_you.jpg
└── background_music.mp3
```

---

## Running the System

### Starting the System

**Ubuntu:**
```bash
cd ~/obs-digital-signage-system
./start.sh
```

**Windows:**
1. Navigate to the system folder
2. Double-click `START.bat`

### What Happens When You Start:

1. ✅ Virtual environment activates
2. ✅ System checks for OBS (launches if not running)
3. ✅ Connects to OBS WebSocket
4. ✅ Syncs content from WebDAV (if configured)
5. ✅ Scans content folder for media files
6. ✅ Detects video durations using FFprobe
7. ✅ Creates OBS scenes for each file
8. ✅ Sets up fullscreen projector (if configured)
9. ✅ Starts content rotation
10. ✅ Begins background audio (if present)
11. ✅ Enters monitoring mode

### System Console Output

```
====================================================================
 OBS Digital Signage Automation System
====================================================================

[1/2] Activating virtual environment...
[2/2] Starting Digital Signage System...

INFO: Digital Signage System initialized on Linux
INFO: Initializing OBS Studio connection...
INFO: OBS Studio started successfully
INFO: Connected to OBS via obsws-python (OBS: 30.0.0)
INFO: Initializing content management...
INFO: Initializing WebDAV synchronization...
INFO: Performing initial WebDAV synchronization...
INFO: Scanning local content...
INFO: Detecting media durations using FFprobe...
INFO: Video 001.mp4: 45.23s
INFO: Video 002.mp4: 30.50s
INFO: Created scene and source for: 001.mp4
INFO: Created scene and source for: 002.mp4
INFO: Created scene and source for: slide01.jpg
INFO: Content updated: 3 media files
INFO: Switching from 001.mp4 to 002.mp4
```

### Stopping the System

**Method 1: Graceful Shutdown**
- Press `Ctrl+C` in the terminal/console

**Method 2: Close Window**
- Close the terminal/console window
- System will shut down gracefully

### Checking System Status

**View logs:**

**Ubuntu:**
```bash
tail -f ~/obs-digital-signage-system/logs/digital_signage.log
```

**Windows:**
1. Open the `logs` folder
2. Open `digital_signage.log` with Notepad

**Common log messages:**

```
INFO: Switching from slide01.jpg to video01.mp4    # Normal operation
INFO: Content changes detected, updating scenes...  # New content added
WARNING: WebDAV connection failed - running in...   # WebDAV offline
ERROR: Failed to create scene for corrupted.mp4     # File issue
```

---

## Troubleshooting

### Permission Denied When Running Scripts (Ubuntu)

**Symptom:** `bash: ./install.sh: Permission denied`

**Solution:**
```bash
# Make scripts executable
chmod +x install.sh start.sh

# Then run
./install.sh
```

**Why This Happens:**
Files cloned from Git don't have execute permissions by default on Linux. The `chmod +x` command makes them executable.

### Virtual Environment Creation Failed (Ubuntu)

**Symptom:** `ensurepip is not available` or `Failed to create virtual environment`

**Solution:**
```bash
# Install python3-venv package
sudo apt install python3-venv -y

# Then run installation again
./install.sh
```

**Why This Happens:**
Ubuntu doesn't include the `venv` module by default. The `python3-venv` package is required to create virtual environments.

### OBS Won't Start Automatically

**Symptom:** System reports "OBS Studio executable not found"

**Ubuntu Solution:**
```bash
# Verify OBS is installed
which obs

# If not found, install:
sudo apt install obs-studio -y
```

**Windows Solution:**
1. Verify OBS is installed: `C:\Program Files\obs-studio\bin\64bit\obs64.exe`
2. If not found, reinstall OBS Studio
3. Or add OBS to PATH

### WebSocket Connection Failed

**Symptom:** "Failed to connect to OBS WebSocket"

**Solutions:**

1. **Check OBS is running:**
   ```bash
   # Ubuntu
   ps aux | grep obs

   # Windows (Command Prompt)
   tasklist | find "obs64.exe"
   ```

2. **Check WebSocket is enabled:**
   - Open OBS → Tools → WebSocket Server Settings
   - Ensure "Enable WebSocket server" is checked
   - Port should be 4455

3. **Check password matches:**
   - If OBS has password, config must match
   - If OBS has no password, config should be empty

4. **Restart OBS:**
   - Close OBS completely
   - Let the system start it automatically

### FFprobe Not Found

**Symptom:** "FFprobe not found" or videos show 10s fallback duration

**Ubuntu Solution:**
```bash
sudo apt install ffmpeg -y
ffprobe -version  # Verify
```

**Windows Solution:**
```cmd
# Install via Chocolatey
choco install ffmpeg -y

# Or via winget
winget install FFmpeg

# Verify
ffprobe -version
```

### Videos Not Playing / Showing Black Screen

**Possible Causes:**

1. **Corrupted video file:**
   - Test video in VLC or another player
   - Re-encode video if necessary

2. **Unsupported codec:**
   - Convert to MP4 with H.264 codec
   - Use HandBrake or FFmpeg to convert

3. **File locked:**
   - Close any programs using the file
   - Check logs for "Permission denied" errors

**Solution:**
```bash
# Ubuntu: Convert video to compatible format
ffmpeg -i input.mov -c:v libx264 -c:a aac -preset fast output.mp4

# Windows: Use HandBrake (free software)
# Download from: https://handbrake.fr/
```

### Content Not Syncing from WebDAV

**Symptom:** "WebDAV connection failed"

**Check:**

1. **URL is correct:**
   ```bash
   # Test WebDAV connection
   curl -u username:password https://your-server.com/path/
   ```

2. **Credentials are correct:**
   - Verify username and password
   - Check for special characters (use quotes in config)

3. **Network connection:**
   ```bash
   # Ubuntu
   ping your-server.com

   # Windows
   ping your-server.com
   ```

4. **Firewall/SSL:**
   - Check if HTTPS certificate is valid
   - Verify firewall allows connection

**Offline Mode Workaround:**
- Set `WEBDAV_HOST=` (empty)
- Manually copy files to `content` folder

### Screen Goes to Sleep

**Ubuntu:**
```bash
# Disable screen blanking
gsettings set org.gnome.desktop.session idle-delay 0

# Verify
gsettings get org.gnome.desktop.session idle-delay
# Should show: uint32 0
```

**Windows:**
1. Settings → System → Power & sleep
2. Set Screen to: Never
3. Set Sleep to: Never

### System Crashes or Freezes

**Check logs:**
```bash
# Ubuntu
tail -100 ~/obs-digital-signage-system/logs/digital_signage.log

# Look for ERROR messages
grep ERROR ~/obs-digital-signage-system/logs/digital_signage.log
```

**Common causes:**
- Out of memory (check with `htop` or Task Manager)
- Corrupted media files
- OBS crash (check OBS logs in `~/.config/obs-studio/logs/`)

**Solutions:**
- Reduce number of media files
- Lower video quality/resolution
- Add more RAM
- Check for system updates

### Transitions Not Working

**Check:**

1. **Stinger file exists:**
   - OBS → Scene Transitions → Configure
   - Verify video file path is valid

2. **Transition offset:**
   - Check `TRANSITION_START_OFFSET` in config
   - Should match stinger duration

3. **OBS transition settings:**
   - Ensure transition is set to "Stinger" (not Fade or Cut)

---

## Web Admin Panel (v2.2.0)

The web admin panel provides a browser-based interface for managing schedules and monitoring system status.

### Accessing the Admin Panel

The panel starts automatically with the system and is accessible at:

```
http://<host-ip>:80
```

For example: `http://localhost:80` or `http://192.168.1.100:80` from another device on the network.

**Note:** Port 80 requires root/sudo on Linux. The system runs on port 80 by default. To change the port, set `WEB_UI_PORT` in your config file.

### Dashboard

The dashboard shows real-time system status:
- **OBS Connection**: Whether OBS Studio is connected
- **Currently Playing**: The media file currently on screen
- **Active Schedule**: Which schedule is currently active
- **Last Sync**: Time since last WebDAV synchronization
- **Uptime**: How long the system has been running

Status auto-refreshes every 5 seconds.

### Managing Schedules

**Creating a Schedule:**
1. Click "Add Schedule" — the name field auto-focuses for quick entry
2. Fill in the basic details:
   - **Name**: Descriptive name (e.g., "Sunday Service")
   - **Type**: Recurring (weekly) or One-time (specific date)
   - **Day/Date**: Which day (recurring) or date (one-time)
   - **Start/End Time**: When the schedule is active
   - **Folder**: Content folder on Storebox NAS (browse from dropdown)
   - **Enabled**: Turn the schedule on or off
3. Expand **"Advanced settings"** if needed (transition, offset, image time, volume)
4. Click "Save"

**Folder Preview:** When you select a folder, a preview box shows the file count (e.g., "8 files (5 images, 3 videos)") and file names, so you can verify you picked the right content.

**Editing a Schedule:**
- Click "Edit" on any schedule card to modify its settings

**Deleting a Schedule:**
- Click "Delete" on any schedule card — a styled confirmation dialog appears (press ESC or Cancel to dismiss)

**Default Schedule:**
- The default schedule always exists and cannot be deleted
- Click "Edit" to change its folder, transition, or volume settings
- Advanced settings auto-expand when editing the default (since those are the main fields)
- It activates whenever no other schedule matches the current time

### Conflict Detection

The system warns about overlapping schedules:
- **Error (red)**: Two recurring schedules on the same day and time, or two one-time events on the same date and time. These are blocked from saving.
- **Warning (yellow)**: A one-time event overrides a recurring schedule. You can confirm to allow this.

### Storebox Folder Browser

When creating/editing a schedule, the folder dropdown shows available folders from your Storebox NAS (WebDAV). The dropdown displays loading/error states and paths are restricted to the NAS for security.

---

## Advanced Configuration

### Customizing Display Time Per File

Currently, all images display for the same time (`IMAGE_DISPLAY_TIME`). To customize per file, you would need to modify the source code in `src/core/content_manager.py`.

### Adding Multiple Audio Tracks

The system currently supports one background audio file. For multiple tracks or playlists, you would need custom development.

### Remote Management

**Access logs remotely:**

**Ubuntu (SSH):**
```bash
ssh user@signage-computer
tail -f ~/obs-digital-signage-system/logs/digital_signage.log
```

**Windows (Remote Desktop):**
- Use Windows Remote Desktop
- View logs in the `logs` folder

**Restart system remotely:**

**Ubuntu:**
```bash
ssh user@signage-computer
sudo systemctl restart obs-signage.service
```

**Windows:**
- Use Remote Desktop
- Close and restart the system

### Multiple Displays/Locations

To run multiple signage displays:

1. Install the system on each computer
2. Use the same WebDAV server
3. Use different `WEBDAV_ROOT_PATH` for different content:
   - Location 1: `/signage/lobby`
   - Location 2: `/signage/cafeteria`
   - Location 3: `/signage/chapel`

Or use the same path for identical content across all displays.

### Time-Based Scheduling (v2.2.0+)

The system supports automatic time-based content scheduling through the web admin panel.

**Schedule Types:**
- **Recurring**: Repeats every week on a specific day (e.g., every Sunday 08:00-13:30)
- **One-time**: Plays only on a specific date (e.g., Christmas Eve 2026-12-24)
- **Default**: Fallback content when no other schedule is active

**Priority Order:**
1. One-time events (highest priority)
2. Recurring schedules
3. Default schedule (always last fallback)

**Per-Schedule Settings:**
Each schedule can have its own transition type, transition offset, image display time, and audio volume.

**Management:**
All schedules are managed through the web admin panel at `http://<host>:80`. See [Web Admin Panel](#web-admin-panel-v220) below.

### Monitoring and Alerts

**Setup email alerts on crash:**

Create a monitoring script (advanced):

```bash
#!/bin/bash
# monitor.sh

while true; do
    if ! pgrep -f "obs-digital-signage" > /dev/null; then
        echo "System down!" | mail -s "Signage Alert" admin@church.com
        ./start.sh &
    fi
    sleep 60
done
```

**Or use systemd:**
The systemd service automatically restarts on crash (if configured).

---

## Security & Credentials

### Configuration Files

**Example files (safe to share)** — contain NO credentials, safe to commit to Git:
- `config/windows_test.env.example`
- `config/ubuntu_prod.env.example`
- `config/windows_prod.env.example`

**Your personal config files (NEVER share)** — contain YOUR passwords:
- `config/windows_test.env`
- `config/ubuntu_prod.env`
- `config/windows_prod.env`

The `.gitignore` file prevents accidental commits of credential files. Even `git add .` will skip them.

### How Installation Creates Your Config

1. Installer checks if your config file exists
2. If not, copies the `.example` template
3. You edit the copy with your actual credentials

### Credential Types

**OBS WebSocket Password** (`OBS_PASSWORD`):
- Connects to OBS Studio via WebSocket
- Only accessible on localhost by default
- Leave empty if OBS has no password set

**WebDAV Credentials** (`WEBDAV_USERNAME`, `WEBDAV_PASSWORD`):
- Login for your Synology NAS or WebDAV server
- Network accessible — use strong, unique passwords
- Consider a dedicated user account with limited folder permissions

**WebDAV Server URL** (`WEBDAV_HOST`):
- Use HTTPS (not HTTP) for encrypted transit
- Consider VPN for remote access instead of exposing NAS directly

### Offline Mode (No Credentials Needed)

Leave WebDAV settings empty and manually place files in `content/`:
```ini
WEBDAV_HOST=
WEBDAV_USERNAME=
WEBDAV_PASSWORD=
```

### If Credentials Are Accidentally Committed

1. **Change passwords immediately** on your WebDAV server and OBS
2. Remove from Git:
   ```bash
   git rm --cached config/windows_test.env
   git commit -m "Remove credentials file"
   ```
3. If pushed to GitHub, consider the repository compromised
4. For full history removal:
   ```bash
   git filter-branch --force --index-filter \
     "git rm --cached --ignore-unmatch config/windows_test.env" \
     --prune-empty --tag-name-filter cat -- --all
   ```

### Security Checklist

- [ ] `.gitignore` includes `config/*.env` (not `.example`)
- [ ] `.env.example` files have NO real passwords
- [ ] `git status` does NOT show `config/*.env` files
- [ ] WebDAV uses HTTPS (not HTTP)

---

## Transferring from Windows to Ubuntu

If you already have the system running on Windows and want to deploy it on Ubuntu, here are the transfer methods.

### Method 1: USB Drive (Easiest)

**On Windows:**
1. Insert USB drive (any format: FAT32, exFAT, NTFS)
2. Copy the `obs-digital-signage-system` folder to the USB drive
3. Safely eject the USB

**On Ubuntu:**
1. Insert USB — Ubuntu auto-mounts it at `/media/username/USB_NAME`
2. Copy to home directory:
   ```bash
   cp -r /media/$USER/*/obs-digital-signage-system ~/
   ```
3. Make scripts executable and install:
   ```bash
   cd ~/obs-digital-signage-system
   chmod +x install.sh start.sh
   ./install.sh
   ```

### Method 2: SCP/SSH (Same Network)

**On Ubuntu** — install and enable SSH:
```bash
sudo apt install openssh-server -y
sudo systemctl enable ssh
ip addr show  # Note the IP address
```

**On Windows** — transfer via SCP (built into Windows 10/11):
```cmd
scp -r obs-digital-signage-system ubuntu_user@192.168.1.50:/home/ubuntu_user/
```

Or use [WinSCP](https://winscp.net/) for a graphical interface.

### Method 3: Git/GitHub (Best for Ongoing Updates)

**On Windows:**
```cmd
cd obs-digital-signage-system
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/you/obs-digital-signage-system.git
git push -u origin main
```

**On Ubuntu:**
```bash
git clone https://github.com/you/obs-digital-signage-system.git
cd obs-digital-signage-system
chmod +x install.sh start.sh
./install.sh
```

The `.gitignore` protects credential files automatically.

### Method 4: Cloud Storage

Upload the folder (or a zip of it) to Dropbox, Google Drive, or OneDrive on Windows, then download it on Ubuntu via the browser.

### After Any Transfer

Regardless of method:

```bash
cd ~/obs-digital-signage-system
chmod +x install.sh start.sh   # Make scripts executable
./install.sh                    # Create venv and install deps
nano config/ubuntu_prod.env     # Edit config for Ubuntu
./start.sh                      # Start the system
```

**Important**: Do NOT reuse the Windows config file. The installer creates a fresh `ubuntu_prod.env` from the template. You only need to copy over your WebDAV credentials and OBS password.

Files you do NOT need to transfer: `venv/`, `logs/`, `content/` (will be synced from WebDAV), `config/*.env` (platform-specific).

---

## Deployment Verification Checklist

After installation, use this checklist to verify everything works.

### Pre-Flight Check

Run the automated check (fastest way to verify):
```bash
python src/main.py --check
```

This validates config, FFprobe, OBS connection, and WebDAV in one command.

### Manual Verification

**Content Management:**
- [ ] Add an image to `content/` — appears in rotation within 30 seconds
- [ ] Add a video — plays with correct duration (not 10s fallback)
- [ ] Remove a file — its scene is removed from OBS

**WebDAV Sync (if configured):**
- [ ] Upload file to WebDAV server — downloads within 30 seconds
- [ ] Delete file from WebDAV — removed from content and OBS

**Transitions:**
- [ ] Content transitions smoothly between files
- [ ] If using stinger: transition starts before video ends (check `TRANSITION_START_OFFSET`)

**Performance:**
- [ ] Initial content scan completes in < 2 seconds
- [ ] System responsive during rotation
- [ ] Memory usage < 500 MB (check with `htop` or Task Manager)

**Portability:**
- [ ] Stop system, move folder to different location, start again — works

---

## Getting Help

### Documentation

1. **README.md** - Quick start guide
2. **This guide** - Full documentation (security, transfers, troubleshooting)

### Log Files

Always check logs first:
- `logs/digital_signage.log` - Main system log
- `logs/errors.log` - Error-specific log (if present)

### Common Questions

**Q: Can I use this for commercial purposes?**
A: Yes, the system is free to use commercially.

**Q: How many files can I have?**
A: Recommended maximum 50-100 files for smooth operation.

**Q: Can I update content while running?**
A: Yes! With WebDAV, just upload new files. Manually, restart the system.

**Q: Does it work with triple monitors?**
A: Yes, you can select which monitor for the projector output.

**Q: Can I run multiple systems on one computer?**
A: Not recommended. One instance per computer is best.

---

## Appendix

### File Structure Reference

#### Required for deployment

These are the only files needed to install and run the system. The total is about 25 files.

```
obs-digital-signage-system/
├── src/                              # Application code (all files required)
│   ├── main.py                       #   Entry point (also supports --check flag)
│   ├── __init__.py
│   ├── config/
│   │   ├── __init__.py
│   │   └── settings.py               #   Configuration loader
│   ├── core/
│   │   ├── __init__.py
│   │   ├── obs_manager.py            #   OBS Studio control
│   │   ├── content_manager.py        #   Scene rotation
│   │   ├── audio_manager.py          #   Background audio
│   │   ├── scheduler.py              #   Time-based scheduling
│   │   ├── webdav_client.py          #   Cloud sync
│   │   └── file_monitor.py           #   File watching
│   ├── web/
│   │   ├── __init__.py
│   │   ├── app.py                    #   Flask admin panel
│   │   ├── schedule_store.py         #   Schedule persistence
│   │   ├── storebox_browser.py       #   NAS folder browser
│   │   ├── templates/index.html      #   Admin panel page
│   │   └── static/
│   │       ├── app.js                #   Admin panel JS
│   │       └── style.css             #   Admin panel styles
│   └── utils/
│       ├── __init__.py
│       ├── logging_config.py         #   Log setup
│       ├── notifications.py          #   Webhook alerts
│       └── system_utils.py           #   System helpers
├── config/
│   ├── ubuntu_prod.env.example       #   Linux config template
│   ├── windows_test.env.example      #   Windows dev config template
│   └── windows_prod.env.example      #   Windows prod config template
├── requirements.txt                  #   Python dependencies
├── pyproject.toml                    #   Project metadata
│
│   --- Pick one per platform ---
├── install.sh  OR  INSTALL.bat       #   Installer
└── start.sh    OR  START.bat         #   Launcher
```

**Created automatically at runtime** (don't ship these, the installer/system creates them):

```
├── config/*.env              # Your personal config (copied from .example)
├── config/schedules.json     # Schedule data (created by web UI on first use)
├── content/                  # Media files (populated by WebDAV sync or manually)
├── logs/                     # System logs
└── venv/                     # Python virtual environment
```

#### Optional / development only

These are not needed to run the system. Include them if you want docs or testing.

```
├── tests/                    # Unit tests (pytest, 82 tests)
├── deployment/
│   └── obs-signage.service   # Systemd service template (Linux auto-start)
├── start_prod.bat            # Windows production launcher (alternative to START.bat)
├── TEST.bat / test.sh        # OBS connection test scripts
├── status.sh                 # Health check script (Linux)
├── README.md                 # Quick start guide
├── COMPLETE_GUIDE.md         # This file -- full documentation
└── CHANGELOG.md              # Version history
```

### Python Dependencies

From `requirements.txt`:

```
obsws-python==1.8.0      # OBS WebSocket v5 client
webdav4==0.10.0          # WebDAV client for cloud sync
pygame==2.6.1            # Audio playback
psutil==6.1.0            # Process management
watchdog==6.0.0          # File monitoring (Python 3.13 limited)
python-dotenv==1.0.1     # Environment file parsing
```

### Quick Command Reference

**Ubuntu:**
```bash
# Installation
./install.sh

# Start system
./start.sh

# View logs
tail -f logs/digital_signage.log

# Test OBS connection
python src/main.py --test

# Update system
git pull
./install.sh
```

**Windows:**
```cmd
REM Installation
INSTALL.bat

REM Start system
START.bat

REM Test OBS connection
TEST.bat

REM View logs
notepad logs\digital_signage.log
```

---

**End of Complete Guide**

For additional help, check the other documentation files or review the system logs for detailed error messages.
