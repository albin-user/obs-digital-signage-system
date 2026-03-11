# Changelog

All notable changes to the OBS Digital Signage Automation System.

---

## [2.3.0] - 2026-03-11

### Web UI UX Improvements & Live Settings Apply

Seven frontend improvements to close feedback loops and prevent errors, plus a backend change so schedule setting edits (volume, transition, image time) apply immediately to the live schedule without a full content switch.

**Connection Lost Banner**
- Orange banner appears after 2 consecutive status-fetch failures: "Connection to signage system lost -- retrying..."
- Auto-hides when connection is restored

**"Live Settings Applied" Toast**
- After saving a schedule that has the LIVE badge, a second toast appears ~10 s later confirming the running system picked up the change
- Only triggers for the active schedule

**Modal Fade Animation**
- Open: 0.2 s fade-in + scale from 95 %
- Close: 0.15 s fade-out + scale to 95 %
- Prevents jarring instant-appear/disappear

**Client-Side Time Validation**
- End time <= start time shows inline red error: "End time must be after start time"
- Blocks save until corrected; clears on input

**Active Schedule Accent Border**
- Schedule card with the LIVE badge gets a 4 px red left border
- Applies to both regular and default schedule cards

**Unsaved Changes Warning**
- Closing the modal after any edit triggers "Discard unsaved changes?" confirmation
- Uses the existing styled confirm dialog (ESC dismissable)
- Reset on open and after successful save

**Conflict Priority Explanation**
- When overlap warnings appear, a muted line is appended: "Priority: one-time events > recurring schedules > default"

**Backend: Settings-Only Apply (scheduler + main loop)**
- `Scheduler` now distinguishes folder changes (full content switch) from settings-only changes (volume, transition, offset, image time)
- New `check_settings_change()` flag consumed by the main loop
- Main loop applies volume, transition offset, image display time, and transition type in-place -- no content reload needed

### Files Changed

| File | Changes |
|------|---------|
| `src/web/templates/index.html` | +2 elements (connection-lost div, time-error hint) |
| `src/web/static/style.css` | +55 lines (banner, animations, error hint, accent border, priority text) |
| `src/web/static/app.js` | +75 lines (all 7 UX improvements) |
| `src/core/scheduler.py` | +40 lines (`_is_same_schedule_slot`, `_settings_differ`, `check_settings_change`) |
| `src/main.py` | +24 lines (settings-apply branch in schedule monitor loop) |

### Testing

- 126/126 tests pass

---

## [2.2.1] - 2026-02-17

### UX Polish: Simplified Schedule Admin Panel

Focused on making the web UI approachable for non-technical users (church volunteers).

**Collapsible Advanced Settings**
- Wrapped transition, offset, image display time, and volume fields in a `<details>` element
- New schedules show only 6 fields by default (name, type, day/time, folder, enabled)
- Advanced settings auto-expand when editing the default schedule
- Zero-JS, keyboard-accessible, screen-reader-friendly

**Auto-Focus on Modal Open**
- Name field receives focus when opening Add Schedule modal
- Folder field receives focus when editing Default Schedule

**Folder Loading Indicator**
- Dropdown shows "Loading folders..." during fetch
- Shows "No folders found" when empty, "Failed to load folders" on error

**Replaced Tooltips with Inline Help Text**
- Removed all 10 `?` tooltip spans (unusable on mobile/touch devices)
- Added 3 inline help hints under the fields that actually confuse users:
  folder, transition offset, and image display time

**Styled Delete Confirmation Dialog**
- Replaced browser `confirm()` with a themed dark-mode dialog
- Promise-based `showConfirm()` function reuses existing `.modal-overlay` styling
- ESC key dismisses both the confirm dialog and the schedule modal

**Folder Content Preview**
- When a folder is selected, shows a preview: "8 files (5 images, 3 videos)" + first 10 filenames
- New backend: `StoreboxBrowser.list_files()` method and `GET /api/folders/files/<path>` route
- Helps volunteers verify they picked the right content folder

**Mobile Layout Improvements**
- Status bar switches to 2-column grid on mobile (was single-column stack)
- Uptime card hidden on mobile (least actionable info)
- Schedule list stays higher on the page

### Files Changed

| File | Changes |
|------|---------|
| `src/web/templates/index.html` | Removed tooltip spans, added `<details>` wrapper, confirm dialog, folder preview div, inline hints |
| `src/web/static/style.css` | Added details/summary, form-hint, confirm-dialog, folder-preview, mobile grid styles |
| `src/web/static/app.js` | Auto-focus, folder loading states, showConfirm(), previewFolder(), ESC handler, advanced toggle |
| `src/web/app.py` | New `/api/folders/files/<path>` route |
| `src/web/storebox_browser.py` | New `list_files()` method with path sanitization |
| `tests/test_web_app.py` | New `test_folder_files_no_webdav` test |

### Testing

- 82/82 tests pass
- Zero `alert()` or `confirm()` calls in app.js
- Zero tooltip `?` spans in HTML

---

## [2.2.0] - 2026-02-16

### New Features

**Web-Based Admin Panel**
- Schedule management via browser at `http://<host>:80`
- Dashboard with live OBS status, current playing content, active schedule, sync time, and uptime
- Create, edit, and delete recurring and one-time schedules
- Storebox NAS folder browser for selecting content paths
- Conflict detection with warnings for overlapping schedules
- Per-schedule audio volume control (0-100%)
- Help tooltips on all form fields

**JSON-Based Schedule Storage**
- Schedules stored in `config/schedules.json` (managed by web UI)
- Automatic migration from `.env` settings on first run
- Support for one-time date-specific events (e.g., Christmas Eve)
- Priority system: one-time > recurring > default
- Hot-reload: schedule changes take effect within 60 seconds

**Webhook Notifications**
- HTTP POST notifications for system events (startup, shutdown, OBS crash, WebDAV failure)
- Configure via `NOTIFICATION_WEBHOOK_URL` in `.env`

**Health Check Script**
- `status.sh` - Quick system health check (OBS, Python process, log age, disk, web UI)
- `test.sh` - Connection test equivalent of TEST.bat for Linux

### Code Quality Improvements

- **Audio race condition fix**: Added `asyncio.Lock` around start/stop audio
- **Task restart backoff**: Exponential backoff (1s-300s) with max 10 restarts per task
- **DEBUG log misuse**: Changed `logger.info("DEBUG: ...")` to `logger.debug(...)`
- **Config validation**: New `Settings.validate()` checks ports, timezone, paths
- **FFprobe startup check**: Warns at startup if FFprobe is missing
- **OBS relaunch in recovery**: If reconnect fails and OBS is not running, relaunches OBS
- **File monitor cleanup**: Sets `self.observer = None` on startup failure
- **Silent config failure**: Replaced `except: pass` with `logger.warning()`
- **Temp file cleanup**: Deletes `*.tmp` files before scanning content
- **Unsupported format feedback**: Logs warning for unrecognized file extensions

### Security & Cleanup

- Deleted nested duplicate `obs-digital-signage-system/` directory (~47 MB)
- Deleted `project_backup/` (~833 MB)
- Removed `debug_obs_check.py` and `debug_transform.py` (contained hardcoded passwords)
- Cleaned `.tmp` files from content directories
- Updated `.gitignore` with cleanup patterns

### Testing

- New `tests/` directory with pytest infrastructure
- `tests/test_scheduler.py` - Schedule logic and priority tests
- `tests/test_settings.py` - Config validation tests
- `tests/test_schedule_store.py` - JSON CRUD and conflict detection tests
- `tests/test_content_manager.py` - MediaFile metadata tests
- `pyproject.toml` with pytest configuration

### Documentation

- Updated `.env.example` files with scheduling, web UI, and notification sections
- New `config/windows_prod.env.example` template
- Updated CHANGELOG with v2.2.0 entry

### Dependencies

- Added `flask>=3.0.0` for web UI

### Upgrade Notes

**From 2.1.x to 2.2.0:**
1. Pull latest code: `git pull origin main`
2. Install new dependency: `pip install flask>=3.0.0` (or run `./install.sh`)
3. On first startup, schedules will auto-migrate from `.env` to `config/schedules.json`
4. Web UI available at `http://<host>:80` (port 80 by default)
5. Future schedule changes should be made through the web UI
6. Add `WEB_UI_ENABLED=true` and `WEB_UI_PORT=80` to your `.env` if not present

---

## [2.1.1] - 2025-11-14

### 🐛 Critical Bug Fix - OBS Scene Source Deletion After Reboot

**Issue Fixed:**
After system reboot with only 1 scene containing 1 image, OBS would keep the scene but delete the image source inside it, resulting in "no file in scene" errors.

**Root Cause:**
The cleanup logic in `_cleanup_all_digital_signage_content()` removed sources (inputs) BEFORE attempting to remove scenes. Since OBS requires a minimum of 1 scene and won't delete the last scene, the scene remained but its sources were already deleted.

**Solution Implemented (3-part fix):**

1. **Scene Count Check** - Added logic to count scenes before cleanup
   - Calculates how many scenes will remain after cleanup
   - If only 1 scene will remain, skips source removal
   - Prevents leaving an empty scene that OBS won't delete

2. **Startup Delay** - Added 5-second wait on first scan
   - Handles cases where content folder is still mounting after reboot
   - Performs second scan if no content found initially
   - Ensures content is detected before cleanup runs

3. **Scene Verification** - New recovery mechanism
   - Checks all managed scenes for missing sources on startup
   - Detects empty scenes and finds their corresponding media files
   - Automatically recreates missing sources
   - Logs recovery actions for troubleshooting

### 📝 Code Changes

**Modified Files:**
- `src/core/content_manager.py` (+120 lines):
  - Lines 224-243: Scene count logic before cleanup
  - Lines 250-265: Conditional source removal
  - Lines 107-114: Startup delay for content folder mounting
  - Lines 301-363: New `_verify_scenes_have_sources()` method

- `src/core/obs_manager.py` (+14 lines):
  - Lines 436-448: New `get_scene_items()` method to query scene sources

- `src/main.py` (+3 lines):
  - Lines 148-150: Call scene verification after initial content scan

**Total Impact:** 137 insertions, 17 deletions across 3 files

### 🔧 How It Works

**On System Startup:**
1. Initial content scan runs
2. If no content found, waits 5 seconds and scans again
3. Cleanup logic checks how many scenes will remain
4. If only 1 scene remains, preserves its sources
5. Scene verification detects any empty scenes
6. Missing sources are automatically recreated

**Benefits:**
- ✅ No more empty scenes after reboot
- ✅ Automatic recovery from source deletion
- ✅ Works reliably in 24/7 operation
- ✅ Minimal impact on existing functionality
- ✅ Comprehensive logging for troubleshooting

### 🧪 Testing Scenario

**Before Fix:**
1. OBS running with `default_slideshow` folder containing 1 image
2. System reboots
3. OBS starts, scene exists but source is deleted
4. Error: "no file in scene"

**After Fix:**
1. OBS running with `default_slideshow` folder containing 1 image
2. System reboots
3. Startup delay ensures content is detected
4. Cleanup preserves sources in last scene
5. Verification detects any missing sources and recreates them
6. ✅ System works correctly

### 📋 Known Issues

**None** - Bug has been resolved and tested.

### 🔄 Upgrade Notes

**From 2.1.0 to 2.1.1:**

No configuration changes needed. Simply pull the latest code:

```bash
git pull origin main
```

The fix is automatic and requires no manual intervention.

---

## [2.1.0] - 2025-11-11

### 🎉 Time-Based Scheduling Feature

Major feature release adding automatic content switching based on time and day of week.

### ✅ New Features

**Time-Based Scheduling System**
- **Automatic content switching** - Different content folders for different schedules
- **Dynamic OBS transitions** - Switch transitions (Fade, Stinger, Cut) based on schedule
- **Timezone support** - Accurate time calculations with zoneinfo (Europe/Copenhagen)
- **Sunday Service mode** - Special schedule for Sundays 08:00-13:30 with Stinger transitions
- **Default mode** - Fallback schedule for all other times with Fade transitions
- **Schedule monitoring** - Checks every 60 seconds for schedule changes
- **No restart required** - Content and transitions switch automatically in real-time
- **New file**: `src/core/scheduler.py` - Complete scheduling implementation (280 lines)
- **New file**: `test_scheduler.py` - Test script for scheduler validation

**Manual Content Override**
- **`MANUAL_CONTENT_FOLDER`** setting for testing specific content without scheduling
- **Works when `SCHEDULE_ENABLED=false`** - Perfect for testing individual folders
- **Example**: Set to `vaeveriet_screens_slideshow/sunday_service_slideshow` to test Sunday content
- **New file**: `test_manual_folder.bat` - Quick test script for Windows

**Windows Production Configuration**
- **`config/windows_prod.env`** - Production config for Windows deployments
- **`start_prod.bat`** - Production start script (sets `ENVIRONMENT=production`)
- **Platform-aware config loading** - Automatically selects correct config file
- **Updated `start.bat`** - Clarified it's for development/testing

**WebDAV Improvements**
- **Recursive directory scanning** - Syncs files in all subfolders automatically
- **Subfolder structure preserved** - Maintains folder hierarchy during sync
- **Unicode support** - Fixed Danish characters (æ, ø, å) and spaces in filenames
- **Simplified URL handling** - Let webdav4 library handle encoding internally

### 🔧 Configuration Changes

**New Environment Variables** (all platforms):
```ini
# Scheduling
SCHEDULE_ENABLED=true
TIMEZONE=Europe/Copenhagen
SCHEDULE_CHECK_INTERVAL=60
MANUAL_CONTENT_FOLDER=

# Sunday Service Schedule (day 6 = Sunday per ISO 8601)
SUNDAY_SERVICE_FOLDER=vaeveriet_screens_slideshow/sunday_service_slideshow
SUNDAY_SERVICE_START_TIME=08:00
SUNDAY_SERVICE_END_TIME=13:30
SUNDAY_SERVICE_TRANSITION=Stinger Transition
SUNDAY_SERVICE_TRANSITION_OFFSET=2.0
SUNDAY_SERVICE_DAY=6

# Default Schedule
DEFAULT_FOLDER=vaeveriet_screens_slideshow/default_slideshow
DEFAULT_TRANSITION=Fade
DEFAULT_TRANSITION_OFFSET=0.5
```

**Updated Config Files**:
- `config/windows_test.env` - Added scheduling section with MANUAL_CONTENT_FOLDER
- `config/ubuntu_prod.env` - Added scheduling section, fixed WEBDAV_ROOT_PATH
- `config/windows_prod.env` - **NEW** - Windows production configuration

**Important Path Fix**:
- ⚠️ **Ubuntu**: Changed `CONTENT_BASE_DIR=/opt/digital-signage` → `/home/your_user/obs-digital-signage-system`
- Fixes permission errors for non-root users
- **Recommended**: Use project directory to keep everything in one place (avoid creating separate `digital-signage` folder)

### 🐛 Bug Fixes

**OBS Transition API**
- **Problem**: Wrong parameter name in `set_current_scene_transition()` call
- **Solution**: Use positional argument instead of `transition_name=` keyword
- **File**: `src/core/obs_manager.py` lines 541, 549, 556

**Settings Attribute Missing**
- **Problem**: `CONTENT_BASE_DIR` attribute not stored in Settings class
- **Solution**: Added `self.CONTENT_BASE_DIR = base_dir` for WebDAV client
- **File**: `src/config/settings.py` line 70

**WebDAV Directory Scanning**
- **Problem**: Only scanned top-level directory, missed files in subfolders
- **Solution**: Implemented recursive `_scan_remote_directory()` method
- **File**: `src/core/webdav_client.py` lines 151-195

**WebDAV File Downloads**
- **Problem**: URL encoding issues with Danish characters caused download failures
- **Solution**: Removed manual encoding, let webdav4 library handle it
- **File**: `src/core/webdav_client.py` lines 248-264

### 📝 Code Changes

**Modified Files**:
- `src/config/settings.py` - Added scheduling settings, MANUAL_CONTENT_FOLDER, platform-aware config loading
- `src/core/obs_manager.py` - Added `set_transition()` method (lines 522-567)
- `src/core/content_manager.py` - Added `switch_content_folder()` method (lines 615-660)
- `src/core/webdav_client.py` - Recursive scanning, URL encoding fixes
- `src/main.py` - Integrated scheduler, schedule monitoring loop (lines 72-98, 263-295)
- `requirements.txt` - Added `tzdata>=2024.1` for timezone support
- `start.bat` - Updated to clarify development mode

**New Files**:
- `src/core/scheduler.py` - Complete scheduling system
- `test_scheduler.py` - Scheduler test script
- `test_manual_folder.bat` - Manual content testing script
- `config/windows_prod.env` - Windows production config
- `start_prod.bat` - Windows production launcher
- `CHANGELOG.md` - This file (updated)

### 📊 Testing Results

**Schedule Logic**:
- ✅ Sunday detection working (day 6 = Sunday)
- ✅ Time range checking (08:00-13:30)
- ✅ Timezone calculations correct (Europe/Copenhagen)
- ✅ Schedule switching at correct times

**WebDAV Sync**:
- ✅ Recursive subfolder scanning working
- ✅ All 5 test files synced successfully
- ✅ Danish characters working: `Vælgermøde 2025 infoskærm.png`
- ✅ Spaces in filenames working: `Velkommen i aabenkirke.png`
- ✅ Subfolder structure preserved

**OBS Integration**:
- ✅ Transition switching working (Fade ↔ Stinger)
- ✅ Content folder switching without restart
- ✅ Scenes created correctly for scheduled content

**Cross-Platform**:
- ✅ Windows: Development (windows_test.env) and Production (windows_prod.env)
- ✅ Ubuntu: Production (ubuntu_prod.env)
- ✅ Config file selection working on both platforms

### 📁 Config File Matrix

```
┌──────────┬─────────────────────┬──────────────────────┐
│ Platform │ Development         │ Production           │
├──────────┼─────────────────────┼──────────────────────┤
│ Windows  │ windows_test.env    │ windows_prod.env ✓   │
│ Ubuntu   │ ubuntu_prod.env     │ ubuntu_prod.env      │
└──────────┴─────────────────────┴──────────────────────┘
```

### 🚀 Usage Examples

**Automatic Scheduling** (Sunday Service + Default):
```ini
SCHEDULE_ENABLED=true
```
System automatically switches at 08:00 Sunday and back at 13:30.

**Manual Testing** (Sunday Service content):
```ini
SCHEDULE_ENABLED=false
MANUAL_CONTENT_FOLDER=vaeveriet_screens_slideshow/sunday_service_slideshow
```
Or run `test_manual_folder.bat` on Windows.

**Disable Scheduling** (use default content folder):
```ini
SCHEDULE_ENABLED=false
MANUAL_CONTENT_FOLDER=
```

### 📋 Known Issues

**None** - All features tested and working.

### 🔄 Upgrade Notes

**From 2.0.0 to 2.1.0**:

1. **Pull latest code**: `git pull origin main`
2. **Update config files manually** (not tracked by git):
   - Add scheduling section to your config file
   - Fix `WEBDAV_ROOT_PATH=/vaeveriet_screens_slideshow` (if using WebDAV)
   - **Ubuntu**: Change `CONTENT_BASE_DIR=/home/your_user/obs-digital-signage-system` (use project directory, not separate folder)
3. **Clean up old folders** (Ubuntu only, if you had separate digital-signage folder):
   ```bash
   rm -rf ~/digital-signage  # Optional: remove old separate folder
   ```
4. **Install new dependency**: `pip install tzdata>=2024.1` (or run `./install.sh` again)
5. **Create folder structure** (if using scheduling):
   ```bash
   mkdir -p vaeveriet_screens_slideshow/sunday_service_slideshow
   mkdir -p vaeveriet_screens_slideshow/default_slideshow
   ```

---

## [2.0.0] - 2025-11-04

### 🎉 Production Release - Fully Tested on Ubuntu 24.04

This release includes extensive testing and bug fixes for Ubuntu deployment.

### ✅ Major Features

- **Cross-platform support** - Works on both Windows 10/11 and Ubuntu 20.04+
- **Automatic OBS management** - Launches, configures, and controls OBS Studio
- **WebDAV cloud sync** - Automatic content synchronization from NAS/cloud storage
- **Dynamic scene creation** - Automatically creates OBS scenes for all media files
- **Background audio** - Continuous music playback with pygame
- **FFprobe integration** - Accurate video duration detection
- **24/7 operation** - Health monitoring and automatic recovery
- **Auto-start on boot** - SystemD service or Startup Applications support
- **Visible terminal mode** - Real-time log monitoring with manual control

### 🐛 Critical Bug Fixes

#### Ubuntu Installation Issues

**Issue #1: Permission Denied - `/opt/digital-signage`**
- **Problem**: Default path required sudo permissions
- **Solution**: Changed default `CONTENT_BASE_DIR` to project directory
- **File**: `config/ubuntu_prod.env.example`, `src/config/settings.py`
- **Impact**: Users can now run without sudo

**Issue #2: Virtual Environment Creation Failed**
- **Problem**: Missing `python3-venv` package on Ubuntu
- **Solution**: Added clear error message and installation instructions
- **File**: `install.sh`
- **Impact**: Better user guidance during installation

**Issue #3: Corrupted Virtual Environment**
- **Problem**: Failed venv creation left broken folder
- **Solution**: Auto-detect and recreate corrupted venv
- **File**: `install.sh` lines 62-70
- **Impact**: Installation script now self-heals

**Issue #4: Config File Not Loading**
- **Problem**: `start.sh` set wrong environment variable
- **Fix**: Changed `DIGITAL_SIGNAGE_ENV` → `ENVIRONMENT`
- **File**: `start.sh` line 40
- **Impact**: CRITICAL - Config files now load correctly, OBS password works

**Issue #5: OBS Safe Mode Dialog**
- **Problem**: Dialog appears after improper shutdown (Ctrl+C)
- **Root Cause**: OBS 32.0+ removed `--disable-shutdown-check` flag
- **Solution**: Delete `~/.config/obs-studio/.sentinel` folder before launch
- **File**: `src/core/obs_manager.py` lines 156-165
- **Impact**: No more manual dialog dismissal needed
- **Source**: OBS GitHub issue #9877

#### Cross-Platform Fixes

**Issue #6: VIDEO_FPS Float Parsing**
- **Problem**: `int()` couldn't parse decimal framerates (59.94, 29.97)
- **Solution**: Changed to `float()` to support all framerates
- **File**: `src/config/settings.py` line 102
- **Supported**: 24, 25, 30, 60, 23.976, 29.97, 59.94, 120, etc.

### 🔧 Improvements

#### Installation Experience

**Better Error Messages**
- Clear instructions when `python3-venv` is missing
- Exact commands shown: `nano config/ubuntu_prod.env`
- Step-by-step post-installation guide
- Color-coded output (green for success, red for errors)

**Auto-Configuration**
- Installation script auto-sets `CONTENT_BASE_DIR` to current directory
- No manual path editing needed
- Works from any location (USB drive, home directory, etc.)

**Clearer Documentation**
- Added explicit `chmod +x` commands in installation steps
- Troubleshooting section for common errors
- Git installation instructions included
- OBS WebSocket password clarification

#### User Experience

**Visible Terminal Mode**
- Start command opens terminal window
- Real-time log monitoring
- Manual Ctrl+C control
- Perfect for troubleshooting

**Startup Applications Support**
- Command for auto-start with visible terminal:
  ```bash
  gnome-terminal -- bash -c "cd ~/obs-digital-signage-system && ./start.sh; exec bash"
  ```

### 📝 Documentation Updates

**New Files**
- `CHANGELOG.md` - This file
- Updated troubleshooting sections in all guides

**Updated Files**
- `README.md` - Clarified OBS WebSocket password
- `COMPLETE_GUIDE.md` - Added Git installation, troubleshooting
- `TRANSFER_GUIDE.md` - Removed credentials, added GitHub clone URL
- `install.sh` - Better error handling and user guidance
- `start.sh` - Fixed environment variable name
- `config/*.env.example` - Added helpful comments

### 🔐 Security

**Credential Protection**
- All credentials removed from documentation
- `.gitignore` protects config files
- Template files safe to share publicly
- GitHub repository verified credential-free

**Protected Files** (not in version control):
- `config/windows_test.env`
- `config/ubuntu_prod.env`
- `content/` folder
- `logs/` folder
- `venv/` folder

### ⚙️ Technical Changes

**Code Optimizations** (Session 11)
- Removed expensive MD5 file hashing (100x faster)
- Removed unused code (~214 lines)
- Simplified OBS path detection
- Centralized scene/source naming logic

**Bug Fixes** (Session 12)
- Fixed image transition timing (images now display full duration)
- Transition offset only applies to videos, not images
- `src/core/content_manager.py` lines 563-576

### 📊 Testing

**Platforms Tested**
- ✅ Windows 11 (development machine)
- ✅ Ubuntu 24.04 LTS (production deployment)

**Test Results**
- ✅ Installation script (both platforms)
- ✅ OBS automatic startup
- ✅ WebSocket connection
- ✅ WebDAV synchronization
- ✅ Content rotation
- ✅ Auto-start on boot
- ✅ Safe mode dialog bypass
- ✅ Virtual environment creation
- ✅ Config file loading
- ✅ FFprobe duration detection

### 🚀 Deployment

**GitHub Repository**
- Repository: `https://github.com/albin-user/obs-digital-signage-system`
- All code and documentation available
- Credentials protected
- Ready for public sharing

**Installation Methods**
1. Clone from GitHub (recommended)
2. Download ZIP
3. USB drive transfer

### 📋 Known Issues

**None** - All identified issues have been resolved.

### 🙏 Credits

**Developed with:**
- Claude Code (AI assistance)
- Testing by: project contributors
- Platform: Ubuntu 24.04, Windows 11

---

## [1.0.0] - 2025-10-28

### Initial Release

**Core Features**
- OBS Studio automation
- WebDAV synchronization
- Content rotation
- Background audio
- Health monitoring

**Platforms**
- Windows 10/11 support
- Initial Ubuntu support

**Known Issues**
- Safe mode dialog on Ubuntu
- Permission errors with /opt directory
- Virtual environment issues
- Config loading problems

---

## Version History

- **2.3.0** (2026-03-11) - UX improvements: connection banner, fade animations, time validation, unsaved changes warning, live settings apply
- **2.2.1** (2026-02-17) - UX polish: collapsible advanced settings, styled dialogs, folder preview, mobile grid
- **2.2.0** (2026-02-16) - Web admin panel, JSON schedules, one-time events, code quality fixes
- **2.1.1** (2025-11-14) - Critical bug fix: OBS scene source deletion after reboot
- **2.1.0** (2025-11-11) - Time-based scheduling, WebDAV improvements, Windows production config
- **2.0.0** (2025-11-04) - Production release with Ubuntu fixes
- **1.0.0** (2025-10-28) - Initial release

---

**For detailed documentation, see [COMPLETE_GUIDE.md](COMPLETE_GUIDE.md)**
