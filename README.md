# OBS Digital Signage Automation System

Automated digital signage for churches and venues. Upload slides and videos to your cloud folder (Storebox, Synology, or any WebDAV server). The system downloads them automatically and displays them on your TV or projector with smooth transitions -- no manual work needed.

[![Production Ready](https://img.shields.io/badge/status-production%20ready-brightgreen)]()
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Ubuntu-blue)]()
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)]()

---

## What Is This?

A system that runs on a small computer connected to your screen. It:

- **Shows your content automatically** -- images and videos rotate in a loop on your TV/projector
- **Syncs from the cloud** -- upload files to Storebox or your NAS and they appear on screen within 30 seconds
- **Switches content by schedule** -- show Sunday service slides during service, default announcements the rest of the week
- **Has a web admin panel** -- manage schedules from your phone or laptop at `http://<computer-ip>:8080`
- **Runs 24/7 unattended** -- starts automatically, recovers from errors, no babysitting needed
- **Plays background music** -- optional continuous audio loop during content display

Built for church IT volunteers, but works for any venue: retail, restaurants, offices, waiting rooms.

---

## ⚡ Quick Start

### 1. Install Prerequisites

**Ubuntu:**
```bash
sudo apt install python3 python3-pip obs-studio ffmpeg -y
```

**Windows:**
- Install [Python 3.10+](https://www.python.org/downloads/) (✅ Check "Add to PATH")
- Install [OBS Studio](https://obsproject.com/download)
- Install [FFmpeg](https://ffmpeg.org/download.html)

### 2. Run Installation

**Ubuntu:**
```bash
chmod +x install.sh
./install.sh
```

**Windows:**
```
Double-click INSTALL.bat
```

### 3. Configure

Edit your configuration file:
- **Ubuntu Production**: `config/ubuntu_prod.env`
- **Windows Development**: `config/windows_test.env`
- **Windows Production**: `config/windows_prod.env`

```ini
# Base directory (leave empty to auto-detect the project folder)
CONTENT_BASE_DIR=

# OBS password (set the same password in OBS: Tools > WebSocket Server Settings)
OBS_PASSWORD=your_obs_password

# Cloud sync (leave WEBDAV_HOST empty to run without cloud sync)
WEBDAV_HOST=https://your-nas.com
WEBDAV_USERNAME=your_username
WEBDAV_PASSWORD=your_password
WEBDAV_ROOT_PATH=/your_content_folder  # Folder on NAS containing your slides

# Scheduling (switches content automatically by day/time)
SCHEDULE_ENABLED=true
TIMEZONE=UTC  # Examples: UTC, America/New_York, Europe/London, Asia/Tokyo
```

**⚠️ SECURITY NOTE:** Config files are protected by `.gitignore` and won't be uploaded to GitHub.

### 4. Start System

**Ubuntu:**
```bash
./start.sh
```

**Windows (Development/Testing):**
```
Double-click start.bat
```

**Windows (Production):**
```
Double-click start_prod.bat
```

**Manual Content Testing:**
```
Double-click test_manual_folder.bat  (Windows only - tests sunday_service_slideshow)
```

---

## 📖 Complete Documentation

**For detailed step-by-step instructions, see:**

### [📘 COMPLETE_GUIDE.md](COMPLETE_GUIDE.md) - Full Installation & Configuration Guide

This comprehensive guide includes:
- ✅ Detailed Ubuntu installation (with desktop settings)
- ✅ Detailed Windows installation
- ✅ Complete OBS Studio configuration
- ✅ Ubuntu Desktop settings for 24/7 operation
- ✅ WebDAV cloud sync setup
- ✅ Auto-start configuration
- ✅ Troubleshooting guide
- ✅ Advanced configuration options

COMPLETE_GUIDE.md also covers security & credentials, transferring from Windows to Ubuntu, and a deployment verification checklist.

---

## 🎯 Features

### Content Management
- **Supported formats**: MP4, MOV, AVI, JPG, PNG, MP3, WAV
- **Cloud sync**: Automatic WebDAV synchronization every 30 seconds with recursive subfolder scanning
- **Offline mode**: Works without internet connection
- **Auto-detection**: FFprobe reads video durations automatically
- **Hot reload**: Add/remove content while running

### Time-Based Scheduling
- **Automatic content switching**: Different content for different times/days
- **Recurring + one-time schedules**: Weekly recurring and date-specific events
- **Smart transitions**: Different OBS transitions per schedule
- **Per-schedule audio volume**: Set background music level for each schedule
- **Priority system**: One-time events override recurring, recurring overrides default
- **Web-based management**: Create, edit, delete schedules from browser
- **Manual override**: `MANUAL_CONTENT_FOLDER` for testing without scheduling
- **No restart required**: Content and transitions switch automatically

### Web Admin Panel (New in v2.2.0)
- **Dashboard**: Live OBS status, current playing content, active schedule, media count, uptime
- **Schedule manager**: Create, edit, delete recurring and one-time schedules
- **Storebox browser**: Browse NAS folders for content selection
- **Manual sync**: Trigger a cloud sync from the browser
- **Conflict detection**: Warnings for overlapping schedules
- **Accessible on local network**: `http://<host>:8080` (no authentication required)

### Display & Transitions
- **Professional transitions**: Stinger transitions for smooth content changes
- **Dynamic transition control**: Automatically switch between Fade, Cut, Stinger based on schedule
- **Dual monitor support**: Control on one screen, display on another
- **Full HD**: Native 1920x1080 support
- **Customizable timing**: Configure image display time and transition offset

### Reliability
- **24/7 operation**: Health monitoring and automatic recovery
- **Auto-start**: Launches OBS automatically if not running
- **Error handling**: Graceful fallbacks and comprehensive logging
- **Portable**: Run from any folder, USB drive, or network share

---

## 🔧 Configuration Reference

### Key Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `IMAGE_DISPLAY_TIME` | 15 | Seconds each image displays |
| `TRANSITION_START_OFFSET` | 2.0 | Start transition N seconds before video ends |
| `WEBDAV_SYNC_INTERVAL` | 30 | Sync interval in seconds |
| `OBS_STARTUP_DELAY` | 15 | Wait time for OBS to start |

### Scheduling & Web UI Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `SCHEDULE_ENABLED` | true | Enable/disable automatic scheduling |
| `TIMEZONE` | UTC | Timezone for schedule calculations |
| `SCHEDULE_CHECK_INTERVAL` | 60 | How often to check for schedule changes (seconds) |
| `MANUAL_CONTENT_FOLDER` | (empty) | Override folder when scheduling disabled |
| `WEB_UI_ENABLED` | true | Enable web admin panel |
| `WEB_UI_PORT` | 8080 | Web UI port (accessible on local network) |
| `NOTIFICATION_ENABLED` | false | Enable webhook notifications |
| `NOTIFICATION_WEBHOOK_URL` | (empty) | HTTP POST endpoint for notifications |

Schedules are now managed through the web UI at `http://<host>:8080`. On first startup, existing `.env` schedule settings are automatically migrated to `config/schedules.json`.

**See [COMPLETE_GUIDE.md](COMPLETE_GUIDE.md#system-configuration) for all settings.**

---

## 📁 Adding Content

### Method 1: WebDAV/Cloud Sync with Scheduling (Recommended)

**Folder Structure:**
```
WEBDAV_ROOT_PATH/
├── sunday_service_slideshow/     # Content for Sunday 08:00-13:30
│   ├── 01_welcome.jpg
│   └── 02_service_info.mp4
└── default_slideshow/             # Content for all other times
    ├── 01_welcome.jpg
    └── 02_announcement.mp4
```

1. Upload files to your WebDAV server in the appropriate subfolder
2. Files automatically download within 30 seconds (with subfolder structure preserved)
3. System switches content automatically based on schedule

**Unicode Support:** ✓ Supports Danish characters (æ, ø, å) and spaces in filenames

### Method 2: WebDAV/Cloud Sync (Simple)

1. Upload files to your WebDAV root path
2. Files automatically download within 30 seconds
3. System creates scenes and starts rotation

### Method 3: Manual/Offline

1. Place files in the `content/` folder (or scheduled folder if using scheduling)
2. Restart system or wait for automatic scan
3. Content appears in rotation

**Best Practices:**
- **Images**: 1920x1080, JPG format
- **Videos**: 1920x1080, MP4 H.264 format, under 15 minutes
- **File naming**: Use numbers for order (e.g., `01_welcome.jpg`, `02_video.mp4`)
- **Scheduling**: Organize content in subfolders (sunday_service_slideshow, default_slideshow)

---

## Web Admin Panel

Open `http://<computer-ip>:8080` in any browser on the same network. No login needed.

**What you can do:**
- **View live status** -- see if OBS is connected, what's currently playing, how many media files are loaded, and system uptime
- **Create schedules** -- set up recurring weekly schedules (e.g., Sunday 08:00-13:30) or one-time events (e.g., Christmas Eve)
- **Browse NAS folders** -- pick content folders directly from your Storebox/NAS when creating schedules
- **Trigger a sync** -- click "Sync Now" to immediately download new content from the cloud
- **See schedule conflicts** -- get warnings if two schedules overlap

**Tips:**
- Works on phones and tablets -- the layout is responsive
- Changes take effect immediately, no restart needed
- To find the computer's IP address: run `hostname -I` (Ubuntu) or `ipconfig` (Windows)
- The default port is 8080. Change it with `WEB_UI_PORT` in your config file

---

## Troubleshooting

### Multiple Folders Created (Ubuntu)

**Problem**: You see both `obs-digital-signage-system/` and `digital-signage/` folders.

**Solution**:
1. Edit `config/ubuntu_prod.env` and leave `CONTENT_BASE_DIR` empty (auto-detects project directory):
   ```ini
   CONTENT_BASE_DIR=
   ```
2. Delete the separate folder:
   ```bash
   rm -rf ~/digital-signage
   ```
3. Restart the system - everything will be in `obs-digital-signage-system/`

**Why**: When `CONTENT_BASE_DIR` is empty, it defaults to the project directory, keeping everything together.

### OBS Won't Connect

**Check:**
1. OBS is running
2. WebSocket is enabled (Tools → WebSocket Server Settings)
3. Port is 4455
4. Password matches config (or is empty)

### Videos Not Playing

**Solution:**
```bash
# Convert to compatible format
ffmpeg -i input.mov -c:v libx264 -c:a aac output.mp4
```

### WebDAV Sync Failed

**Workaround:**
- Set `WEBDAV_HOST=` (empty) in config
- Manually add files to `content/` folder

**See [COMPLETE_GUIDE.md](COMPLETE_GUIDE.md#troubleshooting) for detailed solutions.**

---

## 📊 System Requirements

**Minimum:**
- CPU: Dual-core 2.0 GHz
- RAM: 4 GB
- Storage: 500 MB + content
- OS: Ubuntu 20.04+ or Windows 10+

**Recommended:**
- CPU: Quad-core 2.5 GHz
- RAM: 8 GB
- Storage: SSD with 10 GB free
- Display: Dual monitors (1920x1080 each)

---

## 🔒 Security

**Your credentials are protected:**
- Real config files (`.env`) are ignored by Git
- Only example templates (`.env.example`) are in version control
- Installation creates personal configs automatically

**See [Security & Credentials](COMPLETE_GUIDE.md#security--credentials) in COMPLETE_GUIDE.md for details.**

---

## 📂 Project Structure

### Required for deployment

These files must be present for the system to run. Everything else is optional.

```
obs-digital-signage-system/
├── src/                              # Application code (all files required)
│   ├── main.py                       #   Entry point
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
│   └── *.env.example                 #   Config templates (pick one for your OS)
├── requirements.txt                  #   Python dependencies
└── pyproject.toml                    #   Project metadata
```

**Plus one install + start script per platform:**

| Platform | Installer | Launcher |
|----------|-----------|----------|
| Windows  | `INSTALL.bat` | `START.bat` (dev) or `start_prod.bat` (prod) |
| Linux    | `install.sh` | `start.sh` |

**Created automatically at runtime** (don't need to exist beforehand):

```
├── config/*.env              # Your config (copied from .example by installer)
├── config/schedules.json     # Schedule data (created by web UI)
├── content/                  # Media files (populated by WebDAV or manually)
├── logs/                     # System logs
└── venv/                     # Python virtual environment (created by installer)
```

### Optional (included in repo but not needed to run)

```
├── deployment/
│   └── obs-signage.service   # Systemd service template (Linux auto-start)
├── TEST.bat / test.sh        # OBS connection test scripts
├── status.sh                 # Health check script (Linux)
├── README.md                 # This file
├── COMPLETE_GUIDE.md         # Full documentation
└── CHANGELOG.md              # Version history
```

### Not in repo (local only, excluded by .gitignore)

```
├── tests/                    # Unit tests (pytest)
├── claude.md                 # Development history
└── obs_ws_protocol.md        # OBS WebSocket protocol reference
```

---

## 🚀 Advanced Features

### Auto-Start on Boot

**Ubuntu (systemd service):**
```bash
sudo systemctl enable obs-signage.service
```

**Windows (Startup folder):**
Add `START.bat` to: `C:\Users\YourName\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup`

**See [COMPLETE_GUIDE.md](COMPLETE_GUIDE.md#ubuntu-desktop-settings-configuration) for setup instructions.**

### Remote Management

**Ubuntu (SSH):**
```bash
ssh user@signage-computer
tail -f ~/obs-digital-signage-system/logs/digital_signage.log
```

**Windows (Remote Desktop):**
- Use Windows Remote Desktop
- View logs in `logs/` folder

---

## 📝 Supported File Formats

**Videos**: `.mp4` `.mov` `.avi` `.mkv` `.wmv` `.webm` `.m4v`
**Images**: `.jpg` `.jpeg` `.png` `.bmp` `.gif` `.tiff` `.webp`
**Audio**: `.mp3` `.wav` `.ogg` `.flac` `.m4a`

---

## 🆘 Getting Help

1. **Pre-flight check**: `python src/main.py --check` (validates config, FFprobe, OBS, WebDAV)
2. **Check logs**: `logs/digital_signage.log`
3. **Full documentation**: [COMPLETE_GUIDE.md](COMPLETE_GUIDE.md) (troubleshooting, security, transfers)

---

## 📜 License

MIT License - Free for commercial and personal use.

---

## 🎓 Quick Links

- **Full Setup Guide**: [COMPLETE_GUIDE.md](COMPLETE_GUIDE.md)
- **Version History**: [CHANGELOG.md](CHANGELOG.md)

---

**Ready to get started? See [COMPLETE_GUIDE.md](COMPLETE_GUIDE.md) for step-by-step instructions!**
