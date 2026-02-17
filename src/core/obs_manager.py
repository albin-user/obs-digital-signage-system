"""
OBS Studio management with obsws-python integration.
Handles connection, scene management, and projector control.
"""

import asyncio
import logging
import subprocess
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
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.logger = logging.getLogger(__name__)
        self.client: Optional[obs.ReqClient] = None
        self.event_client: Optional[obs.EventClient] = None
        self.connected = False
        self.obs_process: Optional[subprocess.Popen] = None
        self.startup_time: Optional[float] = None
        
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
                env['DISPLAY'] = ':0'

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

                self.obs_process = subprocess.Popen(
                    cmd_args,
                    cwd=str(obs_working_dir),  # Critical: Set working directory
                    env=env,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
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
                # Create obsws-python client
                self.client = obs.ReqClient(
                    host=self.settings.OBS_HOST,
                    port=self.settings.OBS_PORT,
                    password=self.settings.OBS_PASSWORD,
                    timeout=10
                )
                
                # Test connection with GetVersion
                version_info = self.client.get_version()
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
                # Linux monitor detection
                result = subprocess.run(
                    ["xrandr", "--listmonitors"], 
                    capture_output=True, 
                    text=True,
                    env={'DISPLAY': ':0'}
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
            if not self.connected or not self.client:
                return False
            
            # Test connection with simple request
            self.client.get_version()
            return True
            
        except Exception as e:
            self.logger.warning(f"OBS health check failed: {e}")
            return False
    
    async def recover(self) -> bool:
        """Attempt to recover OBS connection, relaunching OBS if needed."""
        try:
            self.logger.info("Attempting OBS recovery...")

            # Reset connection state
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
        try:
            self.client.create_scene(name=scene_name)
            self.logger.debug(f"Created scene: {scene_name}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to create scene {scene_name}: {e}")
            return False
    
    async def remove_scene(self, scene_name: str) -> bool:
        """Remove a scene."""
        try:
            self.client.remove_scene(name=scene_name)
            self.logger.debug(f"Removed scene: {scene_name}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to remove scene {scene_name}: {e}")
            return False
    
    async def set_current_scene(self, scene_name: str) -> bool:
        """Set the current program scene."""
        try:
            self.client.set_current_program_scene(name=scene_name)
            self.logger.debug(f"Set current scene: {scene_name}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to set current scene {scene_name}: {e}")
            return False
    
    async def get_scene_list(self) -> List[str]:
        """Get list of all scenes."""
        try:
            response = self.client.get_scene_list()
            return [scene['sceneName'] for scene in response.scenes]
        except Exception as e:
            self.logger.error(f"Failed to get scene list: {e}")
            return []

    async def get_input_list(self) -> List[str]:
        """Get list of all inputs."""
        try:
            response = self.client.get_input_list()
            return [input_item['inputName'] for input_item in response.inputs]
        except Exception as e:
            self.logger.error(f"Failed to get input list: {e}")
            return []

    async def get_scene_items(self, scene_name: str) -> Optional[List]:
        """
        Get list of items (sources) in a scene.

        Returns:
            List of scene items, or empty list if scene has no items.
            Returns None if the request failed (e.g. scene doesn't exist).
        """
        try:
            response = self.client.get_scene_item_list(sceneName=scene_name)
            return response.scene_items if hasattr(response, 'scene_items') else []
        except Exception as e:
            self.logger.debug(f"Failed to get scene items for '{scene_name}': {e}")
            return None

    # Input Management Methods
    
    async def create_input(self, scene_name: str, input_name: str, input_kind: str, input_settings: Dict[str, Any]) -> bool:
        """Create an input and add it to a scene."""
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
            self.logger.error(f"Failed to create input {input_name}: {e}")
            return False
    
    async def remove_input(self, input_name: str) -> bool:
        """Remove an input."""
        try:
            # obsws-python uses 'name' parameter
            self.client.remove_input(name=input_name)
            self.logger.debug(f"Removed input: {input_name}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to remove input {input_name}: {e}")
            return False
    
    async def set_input_mute(self, input_name: str, muted: bool) -> bool:
        """Set input mute state."""
        try:
            # obsws-python uses 'name' and 'muted' parameters
            self.client.set_input_mute(name=input_name, muted=muted)
            self.logger.debug(f"Set input {input_name} mute: {muted}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to set input mute {input_name}: {e}")
            return False
    
    async def add_source_to_scene(self, scene_name: str, source_name: str) -> Optional[int]:
        """
        Add an existing input/source to a scene.
        
        This is used when a source exists globally in OBS but needs to be added to a scene.
        Returns the scene item ID if successful, None otherwise.
        """
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
            self.logger.error(f"Failed to add source {source_name} to scene {scene_name}: {e}")
            return None
    
    
    # Scene Item Management
    
    async def get_scene_item_id(self, scene_name: str, source_name: str) -> Optional[int]:
        """Get scene item ID for a source in a scene."""
        try:
            response = self.client.get_scene_item_id(
                scene_name=scene_name,
                source_name=source_name
            )
            return response.scene_item_id
        except Exception as e:
            self.logger.error(f"Failed to get scene item ID for {source_name}: {e}")
            return None
    
    async def set_scene_item_transform(self, scene_name: str, scene_item_id: int, transform: Dict[str, Any]) -> bool:
        """Set scene item transform."""
        try:
            self.client.set_scene_item_transform(
                scene_name=scene_name,
                item_id=scene_item_id,
                transform=transform
            )
            self.logger.debug(f"Set transform for scene item {scene_item_id}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to set scene item transform: {e}")
            return False
    
    # Media Input Management

    async def get_media_input_status(self, input_name: str) -> Optional[Dict[str, Any]]:
        """Get media input status including duration."""
        try:
            # obsws-python uses 'name' parameter, not 'input_name'
            response = self.client.get_media_input_status(name=input_name)
            return {
                'media_duration': response.media_duration,
                'media_cursor': response.media_cursor,
                'media_state': response.media_state
            }
        except Exception as e:
            self.logger.error(f"Failed to get media status for {input_name}: {e}")
            return None

    async def set_transition(self, transition_name: str) -> bool:
        """
        Set the current scene transition.

        Args:
            transition_name: Name of the transition to activate (e.g., "Fade", "Stinger Transition")

        Returns:
            True if successful, False otherwise
        """
        try:
            # Get list of available transitions
            transitions_response = self.client.get_scene_transition_list()
            available_transitions = [t['transitionName'] for t in transitions_response.transitions]

            self.logger.debug(f"Available transitions: {available_transitions}")

            # Try exact match first
            if transition_name in available_transitions:
                self.client.set_current_scene_transition(transition_name)
                self.logger.info(f"Set scene transition to: {transition_name}")
                return True

            # Try case-insensitive partial match
            transition_name_lower = transition_name.lower()
            for available in available_transitions:
                if transition_name_lower in available.lower():
                    self.client.set_current_scene_transition(available)
                    self.logger.info(f"Set scene transition to: {available} (matched '{transition_name}')")
                    return True

            # No match found - use first available transition as fallback
            if available_transitions:
                fallback = available_transitions[0]
                self.client.set_current_scene_transition(fallback)
                self.logger.warning(
                    f"Transition '{transition_name}' not found, using fallback: {fallback}"
                )
                return True
            else:
                self.logger.error("No transitions available in OBS")
                return False

        except Exception as e:
            self.logger.error(f"Failed to set transition '{transition_name}': {e}")
            return False

    async def shutdown(self) -> None:
        """Shutdown OBS manager."""
        try:
            self.logger.info("Shutting down OBS Manager...")
            
            # Disconnect event client
            if self.event_client:
                self.event_client.unsubscribe()
            
            # No explicit disconnect needed for obsws-python ReqClient
            self.connected = False
            self.client = None
            
            self.logger.info("OBS Manager shutdown completed")
            
        except Exception as e:
            self.logger.error(f"Error during OBS shutdown: {e}")
