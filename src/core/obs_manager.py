"""
OBS Studio management with obsws-python integration.
Handles connection, scene management, and projector control.
"""

import asyncio
import logging
import subprocess
import threading
import time
import platform
import os
from pathlib import Path
from typing import Optional, Dict, Any, List
import psutil

# obsws-python imports
import obsws_python as obs

from config.settings import Settings


class OBSManager:
    """Manages OBS Studio lifecycle and WebSocket communication using obsws-python."""

    # Crash loop detection: max crashes within window before giving up
    CRASH_LOOP_MAX = 3
    CRASH_LOOP_WINDOW = 300  # 5 minutes

    def __init__(self, settings: Settings):
        self.settings = settings
        self.logger = logging.getLogger(__name__)
        self.client: Optional[obs.ReqClient] = None
        self.event_client: Optional[obs.EventClient] = None
        self.connected = False
        self.obs_process: Optional[subprocess.Popen] = None
        self.startup_time: Optional[float] = None
        self._lock = threading.RLock()
        self._crash_times: List[float] = []
        self.transition_warning: Optional[str] = None

    async def initialize(self) -> bool:
        """Initialize OBS Studio with full automation."""
        try:
            # 1. Check if OBS is running, launch if needed
            if not self._is_obs_running():
                self.logger.info("OBS not running - starting OBS Studio...")
                if not await self._launch_obs():
                    return False
            else:
                self.logger.info("OBS already running")

            # 2. Connect to WebSocket using obsws-python
            if not await self._connect_websocket():
                return False

            # 3. Setup fullscreen projector
            await self._setup_fullscreen_projector()

            self.logger.info("OBS Manager initialized successfully")
            return True

        except Exception as e:
            self.logger.error(f"OBS initialization failed: {e}")
            return False

    def _is_obs_running(self) -> bool:
        """Check if OBS Studio is currently running."""
        if platform.system() == "Windows":
            obs_processes = ["obs64.exe", "obs.exe", "obs-studio.exe"]
        elif platform.system() == "Darwin":  # macOS
            obs_processes = ["obs", "OBS"]
        else:  # Linux and other Unix-like systems
            obs_processes = ["obs", "obs-studio", "obs64"]

        try:
            for process in psutil.process_iter(['name', 'exe']):
                try:
                    process_info = process.info
                    process_name = process_info.get('name', '') or ''
                    process_exe = process_info.get('exe', '') or ''

                    # Check process name
                    for obs_name in obs_processes:
                        if obs_name.lower() in process_name.lower():
                            self.logger.debug(f"Found OBS process: {process_name}")
                            return True

                    # Check executable path for more accurate detection
                    # Check executable path for more accurate detection
                    if process_exe:
                        exe_name = Path(process_exe).name.lower()
                        if any(name in exe_name for name in ['obs', 'obs64', 'obs-studio']):
                             # Double check it's not just a substring (like 'jobs')
                             if exe_name in ['obs', 'obs64', 'obs64.exe', 'obs.exe', 'obs-studio', 'obs-studio.exe']:
                                self.logger.debug(f"Found OBS executable: {process_exe}")
                                return True

                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue

        except Exception as e:
            self.logger.warning(f"Error checking for OBS processes: {e}")

        return False

    async def _launch_obs(self) -> bool:
        """Launch OBS Studio with optimized arguments."""
        try:
            # Guard: don't launch if we already have a running process
            if self.obs_process is not None and self.obs_process.poll() is None:
                self.logger.info(f"OBS process already running (PID: {self.obs_process.pid}), skipping launch")
                return True
            # Also check via process list in case OBS was started externally
            if self._is_obs_running():
                self.logger.info("OBS already running (detected via process list), skipping launch")
                return True

            obs_path = self._find_obs_executable()
            if not obs_path:
                self.logger.error("OBS Studio executable not found")
                return False

            # OBS command line arguments for digital signage
            cmd_args = [
                str(obs_path),
                # Note: --disable-shutdown-check removed in OBS 32.0+
                # Delete .sentinel folder instead (see Linux section)
            ]

            self.logger.info(f"Launching OBS with command: {' '.join(cmd_args)}")

            # Set working directory to OBS installation directory
            # This fixes the "Failed to find locale/en-US.ini" error
            obs_working_dir = obs_path.parent
            self.logger.info(f"Setting working directory to: {obs_working_dir}")

            # Verify the working directory exists and contains necessary files
            if not obs_working_dir.exists():
                self.logger.error(f"OBS working directory does not exist: {obs_working_dir}")
                return False

            # Check for locale directory (critical for avoiding the init error)
            locale_dir = obs_working_dir / "data" / "locale"
            if not locale_dir.exists():
                # Try alternative path structure
                locale_dir = obs_working_dir.parent.parent / "data" / "locale"
                if locale_dir.exists():
                    obs_working_dir = obs_working_dir.parent.parent
                    self.logger.info(f"Using alternative working directory: {obs_working_dir}")
                else:
                    self.logger.warning(f"Locale directory not found at: {locale_dir}")
                    self.logger.warning("OBS may fail to start, but attempting anyway...")

            # Verify en-US.ini exists
            en_us_ini = locale_dir / "en-US.ini" if locale_dir.exists() else None
            if en_us_ini and en_us_ini.exists():
                self.logger.debug(f"Found locale file: {en_us_ini}")
            else:
                self.logger.warning("en-US.ini not found - OBS may show locale errors")

            # Platform-specific launch
            if platform.system() == "Windows":
                self.obs_process = subprocess.Popen(
                    cmd_args,
                    cwd=str(obs_working_dir),  # Critical: Set working directory
                    # Removed CREATE_NO_WINDOW to show OBS interface
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            else:
                # Linux environment setup
                env = os.environ.copy()
                env.setdefault('DISPLAY', ':0')

                # Remove OBS .sentinel folder to prevent safe mode dialog
                # OBS 32.0+ removed --disable-shutdown-check, so delete .sentinel folder
                sentinel_folder = Path.home() / ".config/obs-studio/.sentinel"
                if sentinel_folder.exists():
                    try:
                        import shutil
                        shutil.rmtree(sentinel_folder)
                        self.logger.info("Deleted .sentinel folder to prevent safe mode dialog")
                    except Exception as e:
                        self.logger.warning(f"Could not remove .sentinel folder: {e}")

                # Ensure scene collection has at least one scene to prevent OBS crash
                # OBS 30.2+ crashes with "basic_string: construction from null" when
                # current_scene is empty and no scenes exist
                self._ensure_valid_scene_collection()

                self.obs_process = subprocess.Popen(
                    cmd_args,
                    cwd=str(obs_working_dir),  # Critical: Set working directory
                    env=env,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    preexec_fn=os.setsid,
                )

            self.startup_time = time.time()
            self.logger.info(f"OBS Studio launched (PID: {self.obs_process.pid})")
            self.logger.info("Using currently active scene collection")

            # Wait for OBS to fully initialize
            self.logger.info(f"Waiting {self.settings.OBS_STARTUP_DELAY} seconds for OBS to initialize...")
            await asyncio.sleep(self.settings.OBS_STARTUP_DELAY)

            # Verify OBS started successfully
            if self._is_obs_running():
                self.logger.info("OBS Studio started successfully")
                return True
            else:
                self.logger.error("OBS Studio failed to start properly")
                # Check if process is still running but maybe showing error dialogs
                if self.obs_process and self.obs_process.poll() is None:
                    self.logger.warning("OBS process is running but may be showing error dialogs")
                    self.logger.warning("Check for any OBS error windows that need to be closed")
                return False

        except Exception as e:
            self.logger.error(f"Failed to launch OBS: {e}")
            return False

    def _ensure_valid_scene_collection(self) -> None:
        """Ensure OBS scene collection has at least one scene.

        OBS 30.2+ crashes with 'basic_string: construction from null is not valid'
        when the scene collection has current_scene="" and no scenes. This can happen
        when our signage script removes all scenes during shutdown or after a crash.
        """
        try:
            import json, uuid as _uuid
            scenes_dir = Path.home() / ".config/obs-studio/basic/scenes"
            if not scenes_dir.exists():
                return

            for scene_file in scenes_dir.glob("*.json"):
                if scene_file.name.endswith(".bak"):
                    continue
                try:
                    with open(scene_file) as f:
                        data = json.load(f)
                except (json.JSONDecodeError, OSError):
                    continue

                sources = data.get("sources", [])
                has_scene = any(s.get("id") == "scene" for s in sources)

                if not has_scene:
                    self.logger.warning(f"Scene collection '{scene_file.name}' has no scenes — adding fallback")
                    scene_uuid = str(_uuid.uuid4())
                    sources.append({
                        "prev_ver": 503447555, "name": "Scene", "uuid": scene_uuid,
                        "id": "scene", "versioned_id": "scene", "settings": {},
                        "mixers": 0, "sync": 0, "flags": 0, "volume": 1.0,
                        "balance": 0.5, "enabled": True, "muted": False,
                        "push-to-mute": False, "push-to-mute-delay": 0,
                        "push-to-talk": False, "push-to-talk-delay": 0,
                        "hotkeys": {}, "deinterlace_mode": 0,
                        "deinterlace_field_order": 0, "monitoring_type": 0,
                        "private_settings": {}
                    })
                    data["sources"] = sources
                    data["current_scene"] = "Scene"
                    data["current_program_scene"] = "Scene"
                    data["scene_order"] = [{"name": "Scene"}]

                    with open(scene_file, "w") as f:
                        json.dump(data, f, indent=2, ensure_ascii=False)
                    self.logger.info("Fallback scene added to prevent OBS crash")
        except Exception as e:
            self.logger.warning(f"Could not validate scene collection: {e}")

    def _find_obs_executable(self) -> Optional[Path]:
        """Find OBS executable across platforms."""
        import shutil

        if platform.system() == "Windows":
            # Try PATH first (fastest)
            obs_path = shutil.which("obs64") or shutil.which("obs")
            if obs_path:
                self.logger.info(f"Found OBS in PATH: {obs_path}")
                return Path(obs_path)

            # Check most common installation paths
            common_paths = [
                Path(os.getenv("ProgramFiles", "C:/Program Files")) / "obs-studio/bin/64bit/obs64.exe",
                Path("C:/Program Files/obs-studio/bin/64bit/obs64.exe"),
                Path("C:/Program Files (x86)/obs-studio/bin/64bit/obs64.exe"),
            ]

            for path in common_paths:
                if path.exists():
                    self.logger.info(f"Found OBS at: {path}")
                    return path

        else:
            # Linux/Unix/macOS - try PATH first
            obs_names = ["obs", "obs-studio"]
            for name in obs_names:
                obs_path = shutil.which(name)
                if obs_path:
                    self.logger.info(f"Found OBS in PATH: {obs_path}")
                    return Path(obs_path)

            # Check common Linux/macOS paths
            common_paths = [
                Path("/usr/bin/obs"),
                Path("/snap/obs-studio/current/usr/bin/obs"),
                Path("/Applications/OBS.app/Contents/MacOS/OBS"),
            ]

            for path in common_paths:
                if path.exists():
                    self.logger.info(f"Found OBS at: {path}")
                    return path

        self.logger.error("OBS Studio not found. Please ensure OBS Studio is installed.")
        return None

    async def _connect_websocket(self) -> bool:
        """Connect to OBS WebSocket using obsws-python."""
        max_retries = 5
        retry_delay = 2

        for attempt in range(max_retries):
            try:
                # Create obsws-python client (not yet assigned to self)
                new_client = obs.ReqClient(
                    host=self.settings.OBS_HOST,
                    port=self.settings.OBS_PORT,
                    password=self.settings.OBS_PASSWORD,
                    timeout=10
                )

                # Test connection with GetVersion
                version_info = new_client.get_version()

                # Atomically assign under lock
                with self._lock:
                    self.client = new_client
                    self.connected = True

                self.logger.info(f"Connected to OBS via obsws-python (OBS: {version_info.obs_version})")

                # Setup event client for monitoring
                self.event_client = obs.EventClient(
                    host=self.settings.OBS_HOST,
                    port=self.settings.OBS_PORT,
                    password=self.settings.OBS_PASSWORD
                )

                # Register event callbacks
                self.event_client.callback.register(self._on_scene_created)
                self.event_client.callback.register(self._on_input_created)

                return True

            except Exception as e:
                self.logger.warning(f"WebSocket connection attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay * (attempt + 1))
                else:
                    self.logger.error("Failed to connect to OBS WebSocket after all retries")
                    return False

        return False

    def _on_scene_created(self, data):
        """Handle scene created events."""
        self.logger.debug(f"Scene created: {data.scene_name}")

    def _on_input_created(self, data):
        """Handle input created events."""
        self.logger.debug(f"Input created: {data.input_name}")

    async def _setup_fullscreen_projector(self) -> None:
        """Setup fullscreen projector on available displays."""
        try:
            await asyncio.sleep(3)  # Wait for OBS to fully initialize

            # Get available monitors
            monitors = await self._get_available_monitors()

            if len(monitors) >= 2:
                # Dual monitor setup
                monitor_index = 1  # Secondary display
                self.logger.info("Setting up fullscreen projector on secondary display")
            else:
                # Single monitor setup
                monitor_index = 0  # Primary display
                self.logger.info("Single monitor detected - using primary display")

            # Open fullscreen projector using obsws-python
            with self._lock:
                if not self.client:
                    self.logger.warning("OBS not connected — cannot setup projector")
                    return
                try:
                    self.client.open_video_mix_projector(
                        video_mix_type="OBS_WEBSOCKET_VIDEO_MIX_TYPE_PROGRAM",
                        monitor_index=monitor_index
                    )
                    self.logger.info(f"Fullscreen projector activated on monitor {monitor_index}")
                except Exception as e:
                    self.logger.error(f"Failed to open projector: {e}")

        except Exception as e:
            self.logger.error(f"Failed to setup fullscreen projector: {e}")

    async def _get_available_monitors(self) -> List[int]:
        """Get list of available monitors."""
        try:
            if platform.system() == "Windows":
                # Windows monitor detection - basic approach
                return [0, 1]  # Assume up to 2 monitors
            else:
                # Linux monitor detection — preserve full env so xrandr finds PATH etc.
                xrandr_env = os.environ.copy()
                xrandr_env.setdefault('DISPLAY', ':0')
                result = subprocess.run(
                    ["xrandr", "--listmonitors"],
                    capture_output=True,
                    text=True,
                    env=xrandr_env,
                )
                if result.returncode == 0:
                    lines = result.stdout.strip().split('\n')[1:]  # Skip header
                    return list(range(len(lines)))

        except Exception as e:
            self.logger.warning(f"Could not detect monitors: {e}")

        return [0]  # Default to primary monitor

    async def health_check(self) -> bool:
        """Perform health check on OBS connection."""
        try:
            with self._lock:
                if not self.connected or not self.client:
                    return False
                # Test connection with simple request
                self.client.get_version()
            return True

        except Exception as e:
            self.logger.warning(f"OBS health check failed: {e}")
            self.connected = False
            return False

    def _handle_client_error(self, error: Exception, operation: str) -> None:
        """Log error and update connection state if it's a connection failure."""
        self.logger.error(f"Failed to {operation}: {error}")
        error_str = str(error).lower()
        if any(kw in error_str for kw in (
            'connection', 'closed', 'refused', 'timeout',
            'broken pipe', 'not connected', 'eof',
        )):
            self.connected = False
            self.logger.warning("Connection error detected — marking OBS as disconnected")

    def _cleanup_zombie_obs(self) -> None:
        """Reap zombie OBS processes (Linux) and kill stuck processes."""
        # Reap our own child if it's defunct
        if self.obs_process is not None:
            ret = self.obs_process.poll()
            if ret is not None:
                self.logger.info(f"Reaped OBS child process (exit code {ret})")
                # Kill entire process group on Linux
                if platform.system() != "Windows":
                    try:
                        os.killpg(self.obs_process.pid, 9)
                    except (ProcessLookupError, PermissionError):
                        pass
                self.obs_process = None

        # Also look for zombie OBS processes via psutil
        if platform.system() != "Windows":
            for proc in psutil.process_iter(['name', 'status']):
                try:
                    if proc.info['status'] == psutil.STATUS_ZOMBIE:
                        pname = (proc.info.get('name') or '').lower()
                        if 'obs' in pname:
                            self.logger.warning(f"Killing zombie OBS process (PID {proc.pid})")
                            os.waitpid(proc.pid, os.WNOHANG)
                except (psutil.NoSuchProcess, psutil.AccessDenied, ChildProcessError):
                    pass

    def _is_crash_looping(self) -> bool:
        """Check if OBS is crash-looping (too many crashes in short window)."""
        now = time.time()
        self._crash_times = [t for t in self._crash_times if now - t < self.CRASH_LOOP_WINDOW]
        self._crash_times.append(now)
        if len(self._crash_times) >= self.CRASH_LOOP_MAX:
            self.logger.critical(
                f"OBS crash loop detected: {len(self._crash_times)} crashes in "
                f"{self.CRASH_LOOP_WINDOW}s — stopping relaunch attempts"
            )
            return True
        return False

    async def recover(self) -> bool:
        """Attempt to recover OBS connection, relaunching OBS if needed."""
        try:
            self.logger.info("Attempting OBS recovery...")

            # Clean up zombie processes first
            self._cleanup_zombie_obs()

            # Reset connection state
            with self._lock:
                self.connected = False
                self.client = None
            self.obs_process = None

            # Reset stale event client
            if self.event_client:
                try:
                    self.event_client.unsubscribe()
                except Exception:
                    pass
                self.event_client = None

            # Try to reconnect
            if await self._connect_websocket():
                self.logger.info("OBS recovery successful (reconnected)")
                return True

            # Reconnect failed - check if OBS is still running
            if not self._is_obs_running():
                # Crash loop guard
                if self._is_crash_looping():
                    return False

                self.logger.warning("OBS is not running - attempting relaunch")
                if await self._launch_obs():
                    if await self._connect_websocket():
                        self.logger.info("OBS recovery successful (relaunched)")
                        return True

            self.logger.error("OBS recovery failed")
            return False

        except Exception as e:
            self.logger.error(f"OBS recovery error: {e}")
            return False

    # Scene Management Methods

    async def create_scene(self, scene_name: str) -> bool:
        """Create a new scene."""
        with self._lock:
            if not self.client:
                self.logger.warning(f"OBS not connected — cannot create scene '{scene_name}'")
                return False
            try:
                self.client.create_scene(name=scene_name)
                self.logger.debug(f"Created scene: {scene_name}")
                return True
            except Exception as e:
                self._handle_client_error(e, f"create scene '{scene_name}'")
                return False

    async def remove_scene(self, scene_name: str) -> bool:
        """Remove a scene."""
        with self._lock:
            if not self.client:
                self.logger.warning(f"OBS not connected — cannot remove scene '{scene_name}'")
                return False
            try:
                self.client.remove_scene(name=scene_name)
                self.logger.debug(f"Removed scene: {scene_name}")
                return True
            except Exception as e:
                self._handle_client_error(e, f"remove scene '{scene_name}'")
                return False

    async def set_current_scene(self, scene_name: str) -> bool:
        """Set the current program scene."""
        with self._lock:
            if not self.client:
                self.logger.warning(f"OBS not connected — cannot set current scene '{scene_name}'")
                return False
            try:
                self.client.set_current_program_scene(name=scene_name)
                self.logger.debug(f"Set current scene: {scene_name}")
                return True
            except Exception as e:
                self._handle_client_error(e, f"set current scene '{scene_name}'")
                return False

    async def get_scene_list(self) -> List[str]:
        """Get list of all scenes."""
        with self._lock:
            if not self.client:
                self.logger.warning("OBS not connected — cannot get scene list")
                return []
            try:
                response = self.client.get_scene_list()
                return [scene['sceneName'] for scene in response.scenes]
            except Exception as e:
                self._handle_client_error(e, "get scene list")
                return []

    async def get_input_list(self) -> List[str]:
        """Get list of all inputs."""
        with self._lock:
            if not self.client:
                self.logger.warning("OBS not connected — cannot get input list")
                return []
            try:
                response = self.client.get_input_list()
                return [input_item['inputName'] for input_item in response.inputs]
            except Exception as e:
                self._handle_client_error(e, "get input list")
                return []

    async def get_scene_items(self, scene_name: str) -> Optional[List]:
        """
        Get list of items (sources) in a scene.

        Returns:
            List of scene items, or empty list if scene has no items.
            Returns None if the request failed (e.g. scene doesn't exist).
        """
        with self._lock:
            if not self.client:
                self.logger.warning(f"OBS not connected — cannot get scene items for '{scene_name}'")
                return None
            try:
                response = self.client.get_scene_item_list(sceneName=scene_name)
                return response.scene_items if hasattr(response, 'scene_items') else []
            except Exception as e:
                self.logger.debug(f"Failed to get scene items for '{scene_name}': {e}")
                return None

    # Input Management Methods

    async def create_input(self, scene_name: str, input_name: str, input_kind: str, input_settings: Dict[str, Any]) -> bool:
        """Create an input and add it to a scene."""
        with self._lock:
            if not self.client:
                self.logger.warning(f"OBS not connected — cannot create input '{input_name}'")
                return False
            try:
                self.client.create_input(
                    sceneName=scene_name,
                    inputName=input_name,
                    inputKind=input_kind,
                    inputSettings=input_settings,
                    sceneItemEnabled=True
                )
                self.logger.debug(f"Created input: {input_name} of type {input_kind}")
                return True
            except Exception as e:
                self._handle_client_error(e, f"create input '{input_name}'")
                return False

    async def remove_input(self, input_name: str) -> bool:
        """Remove an input."""
        with self._lock:
            if not self.client:
                self.logger.warning(f"OBS not connected — cannot remove input '{input_name}'")
                return False
            try:
                # obsws-python uses 'name' parameter
                self.client.remove_input(name=input_name)
                self.logger.debug(f"Removed input: {input_name}")
                return True
            except Exception as e:
                self._handle_client_error(e, f"remove input '{input_name}'")
                return False

    async def set_input_mute(self, input_name: str, muted: bool) -> bool:
        """Set input mute state."""
        with self._lock:
            if not self.client:
                self.logger.warning(f"OBS not connected — cannot set input mute '{input_name}'")
                return False
            try:
                # obsws-python uses 'name' and 'muted' parameters
                self.client.set_input_mute(name=input_name, muted=muted)
                self.logger.debug(f"Set input {input_name} mute: {muted}")
                return True
            except Exception as e:
                self._handle_client_error(e, f"set input mute '{input_name}'")
                return False

    async def add_source_to_scene(self, scene_name: str, source_name: str) -> Optional[int]:
        """
        Add an existing input/source to a scene.

        This is used when a source exists globally in OBS but needs to be added to a scene.
        Returns the scene item ID if successful, None otherwise.
        """
        with self._lock:
            if not self.client:
                self.logger.warning(f"OBS not connected — cannot add source '{source_name}' to scene '{scene_name}'")
                return None
            try:
                response = self.client.create_scene_item(
                    scene_name=scene_name,
                    source_name=source_name,
                    enabled=True
                )
                scene_item_id = response.scene_item_id if hasattr(response, 'scene_item_id') else None
                self.logger.debug(f"Added existing source '{source_name}' to scene '{scene_name}' (item ID: {scene_item_id})")
                return scene_item_id
            except Exception as e:
                self._handle_client_error(e, f"add source '{source_name}' to scene '{scene_name}'")
                return None


    # Scene Item Management

    async def get_scene_item_id(self, scene_name: str, source_name: str) -> Optional[int]:
        """Get scene item ID for a source in a scene."""
        with self._lock:
            if not self.client:
                self.logger.warning(f"OBS not connected — cannot get scene item ID for '{source_name}'")
                return None
            try:
                response = self.client.get_scene_item_id(
                    scene_name=scene_name,
                    source_name=source_name
                )
                return response.scene_item_id
            except Exception as e:
                self._handle_client_error(e, f"get scene item ID for '{source_name}'")
                return None

    async def set_scene_item_transform(self, scene_name: str, scene_item_id: int, transform: Dict[str, Any]) -> bool:
        """Set scene item transform."""
        with self._lock:
            if not self.client:
                self.logger.warning("OBS not connected — cannot set scene item transform")
                return False
            try:
                self.client.set_scene_item_transform(
                    scene_name=scene_name,
                    item_id=scene_item_id,
                    transform=transform
                )
                self.logger.debug(f"Set transform for scene item {scene_item_id}")
                return True
            except Exception as e:
                self._handle_client_error(e, "set scene item transform")
                return False

    # Media Input Management

    async def get_media_input_status(self, input_name: str) -> Optional[Dict[str, Any]]:
        """Get media input status including duration."""
        with self._lock:
            if not self.client:
                self.logger.warning(f"OBS not connected — cannot get media status for '{input_name}'")
                return None
            try:
                # obsws-python uses 'name' parameter, not 'input_name'
                response = self.client.get_media_input_status(name=input_name)
                return {
                    'media_duration': response.media_duration,
                    'media_cursor': response.media_cursor,
                    'media_state': response.media_state
                }
            except Exception as e:
                self._handle_client_error(e, f"get media status for '{input_name}'")
                return None

    async def set_transition(self, transition_name: str) -> bool:
        """
        Set the current scene transition.

        Args:
            transition_name: Name of the transition to activate (e.g., "Fade", "Stinger Transition")

        Returns:
            True if successful, False otherwise
        """
        with self._lock:
            if not self.client:
                self.logger.warning(f"OBS not connected — cannot set transition '{transition_name}'")
                return False
            try:
                # Get list of available transitions
                transitions_response = self.client.get_scene_transition_list()
                available_transitions = [t['transitionName'] for t in transitions_response.transitions]

                self.logger.debug(f"Available transitions: {available_transitions}")

                # Try exact match first
                if transition_name in available_transitions:
                    self.client.set_current_scene_transition(transition_name)
                    self.logger.info(f"Set scene transition to: {transition_name}")
                    self.transition_warning = None
                    return True

                # Try case-insensitive partial match
                transition_name_lower = transition_name.lower()
                for available in available_transitions:
                    if transition_name_lower in available.lower():
                        self.client.set_current_scene_transition(available)
                        self.logger.info(f"Set scene transition to: {available} (matched '{transition_name}')")
                        self.transition_warning = None
                        return True

                # No match found — fall back to Fade (preferred), then any available
                fallback = "Fade" if "Fade" in available_transitions else (available_transitions[0] if available_transitions else None)
                if fallback:
                    self.client.set_current_scene_transition(fallback)
                    self.transition_warning = (
                        f"Transition '{transition_name}' is not set up in OBS. "
                        f"Using '{fallback}' instead. To fix: add a '{transition_name}' "
                        f"transition in OBS (Scene Transitions → +)."
                    )
                    self.logger.warning(self.transition_warning)
                    return True
                else:
                    self.logger.error("No transitions available in OBS")
                    return False

            except Exception as e:
                self._handle_client_error(e, f"set transition '{transition_name}'")
                return False

    async def shutdown(self) -> None:
        """Shutdown OBS manager."""
        try:
            self.logger.info("Shutting down OBS Manager...")

            # Disconnect event client and close its WebSocket
            if self.event_client:
                try:
                    self.event_client.unsubscribe()
                except Exception:
                    pass
                try:
                    if hasattr(self.event_client, 'base_client') and hasattr(self.event_client.base_client, 'ws'):
                        self.event_client.base_client.ws.close()
                except Exception:
                    pass
                self.event_client = None

            # Close ReqClient WebSocket
            with self._lock:
                if self.client:
                    try:
                        if hasattr(self.client, 'base_client') and hasattr(self.client.base_client, 'ws'):
                            self.client.base_client.ws.close()
                    except Exception:
                        pass
                self.connected = False
                self.client = None

            self.logger.info("OBS Manager shutdown completed")

        except Exception as e:
            self.logger.error(f"Error during OBS shutdown: {e}")
