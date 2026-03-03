"""
Cross-platform configuration management.
Handles Windows development and Ubuntu production environments.
"""

import logging
import os
import platform
from pathlib import Path
from typing import Optional, Set


def _safe_int(key: str, default: int) -> int:
    """Safely parse an integer from env var, with fallback and warning."""
    val = os.getenv(key)
    if val is None:
        return default
    try:
        return int(val)
    except (ValueError, TypeError):
        logging.getLogger(__name__).warning(
            f"Invalid integer for {key}='{val}', using default {default}"
        )
        return default


def _safe_float(key: str, default: float) -> float:
    """Safely parse a float from env var, with fallback and warning."""
    val = os.getenv(key)
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        logging.getLogger(__name__).warning(
            f"Invalid float for {key}='{val}', using default {default}"
        )
        return default


def get_env_file_path() -> Path:
    """Get the platform-appropriate .env config file path.

    Shared by Settings._get_env_file() and the setup wizard so the
    path logic lives in one place.
    """
    config_dir = Path(__file__).parent.parent.parent / "config"
    env = os.getenv("ENVIRONMENT", "development")
    plat = platform.system().lower()
    if env == "production":
        if plat == "windows":
            return config_dir / "windows_prod.env"
        else:
            return config_dir / "ubuntu_prod.env"
    else:
        if plat == "windows":
            return config_dir / "windows_test.env"
        else:
            return config_dir / "ubuntu_prod.env"


class Settings:
    """Cross-platform configuration management."""

    def __init__(self):
        self.platform = platform.system().lower()
        self._load_environment_config()
        self._setup_paths()
        self._setup_obs_settings()
        self._setup_webdav_settings()
        self._setup_media_settings()
        self._setup_system_settings()
        self._setup_schedule_settings()
        
    def _load_environment_config(self) -> None:
        """Load configuration from environment variables."""
        # Determine environment (development or production)
        self.ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
        
        # Load environment-specific variables
        env_file = self._get_env_file()
        if env_file.exists():
            self._load_env_file(env_file)
    
    def _get_env_file(self) -> Path:
        """Get environment configuration file."""
        return get_env_file_path()
    
    def _load_env_file(self, env_file: Path) -> None:
        """Load environment variables from file."""
        try:
            with open(env_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        # Remove inline comments
                        if '#' in value:
                            value = value.split('#')[0].strip()
                        os.environ[key.strip()] = value.strip()
        except Exception as e:
            logging.getLogger(__name__).warning(f"Could not load env file {env_file}: {e}")
    
    def _setup_paths(self) -> None:
        """Setup platform-specific paths."""
        # Base directories - default to project directory on all platforms
        default_path = str(Path(__file__).parent.parent.parent)
        base_dir = Path(os.getenv("CONTENT_BASE_DIR", "") or default_path)

        # Store CONTENT_BASE_DIR for use by other components (e.g., WebDAV)
        self.CONTENT_BASE_DIR = base_dir

        # Ensure base directory exists
        base_dir.mkdir(parents=True, exist_ok=True)

        # Ensure directories exist
        self.CONTENT_DIR = base_dir / "content"
        self.LOG_DIR = base_dir / "logs"
        self.CONFIG_DIR = base_dir / "config"

        # Create directories
        for directory in [self.CONTENT_DIR, self.LOG_DIR, self.CONFIG_DIR]:
            directory.mkdir(parents=True, exist_ok=True)
    
    def _setup_obs_settings(self) -> None:
        """Setup OBS WebSocket configuration."""
        self.OBS_HOST = os.getenv("OBS_HOST", "localhost")
        self.OBS_PORT = _safe_int("OBS_PORT", 4455)
        self.OBS_PASSWORD = os.getenv("OBS_PASSWORD", "")
        self.OBS_TIMEOUT = _safe_int("OBS_TIMEOUT", 10)
        self.OBS_STARTUP_DELAY = _safe_int("OBS_STARTUP_DELAY", 15)
    
    def _setup_webdav_settings(self) -> None:
        """Setup WebDAV/Synology NAS configuration."""
        self.WEBDAV_HOST = os.getenv("WEBDAV_HOST", "")
        self.WEBDAV_PORT = _safe_int("WEBDAV_PORT", 5006)
        self.WEBDAV_USERNAME = os.getenv("WEBDAV_USERNAME", "")
        self.WEBDAV_PASSWORD = os.getenv("WEBDAV_PASSWORD", "")
        self.WEBDAV_TIMEOUT = _safe_int("WEBDAV_TIMEOUT", 30)
        self.WEBDAV_SYNC_INTERVAL = _safe_int("WEBDAV_SYNC_INTERVAL", 30)
        # Corrected Synology NAS path - convert Windows path to WebDAV format
        self.WEBDAV_ROOT_PATH = os.getenv("WEBDAV_ROOT_PATH", "/")
    
    def _setup_media_settings(self) -> None:
        """Setup media file and display settings."""
        # Display settings
        self.VIDEO_WIDTH = _safe_int("VIDEO_WIDTH", 1920)
        self.VIDEO_HEIGHT = _safe_int("VIDEO_HEIGHT", 1080)
        self.VIDEO_FPS = _safe_float("VIDEO_FPS", 30.0)

        # Media timing
        self.IMAGE_DISPLAY_TIME = _safe_int("IMAGE_DISPLAY_TIME", 8)  # seconds
        self.MAX_VIDEO_DURATION = _safe_int("MAX_VIDEO_DURATION", 900)  # 15 minutes
        self.SLIDE_TRANSITION_SECONDS = _safe_int("SLIDE_TRANSITION_SECONDS", 8)  # configurable slide timing

        # Transition timing - manual control over when transition starts
        # Number of seconds before media ends to trigger the transition
        # Example: 2.0 = start transition 2 seconds before video/image ends
        self.TRANSITION_START_OFFSET = _safe_float("TRANSITION_START_OFFSET", 2.0)

        # Audio settings
        self.AUDIO_SAMPLE_RATE = _safe_int("AUDIO_SAMPLE_RATE", 44100)
        self.AUDIO_CHANNELS = _safe_int("AUDIO_CHANNELS", 2)
        self.AUDIO_BUFFER_SIZE = _safe_int("AUDIO_BUFFER_SIZE", 1024)
        
        # Supported file formats
        self.SUPPORTED_VIDEO_FORMATS: Set[str] = {'.mp4', '.mov', '.avi', '.mkv', '.wmv', '.webm', '.m4v'}
        self.SUPPORTED_IMAGE_FORMATS: Set[str] = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff', '.webp'}
        self.SUPPORTED_AUDIO_FORMATS: Set[str] = {'.mp3', '.wav', '.ogg', '.flac', '.m4a'}
    
    def _setup_system_settings(self) -> None:
        """Setup system and logging settings."""
        self.LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
        self.LOG_MAX_SIZE = _safe_int("LOG_MAX_SIZE", 10485760)  # 10MB
        self.LOG_BACKUP_COUNT = _safe_int("LOG_BACKUP_COUNT", 5)

        # System monitoring
        self.HEALTH_CHECK_INTERVAL = _safe_int("HEALTH_CHECK_INTERVAL", 60)  # seconds
        self.MAX_RESTART_ATTEMPTS = _safe_int("MAX_RESTART_ATTEMPTS", 3)

        # File monitoring
        self.FILE_MONITOR_DELAY = _safe_float("FILE_MONITOR_DELAY", 2.0)  # seconds

    def _setup_schedule_settings(self) -> None:
        """Setup time-based scheduling configuration."""
        # Enable/disable scheduling feature
        schedule_enabled_str = os.getenv("SCHEDULE_ENABLED", "false").lower()
        self.SCHEDULE_ENABLED = schedule_enabled_str in ("true", "1", "yes", "on")

        # Timezone for schedule calculations
        self.TIMEZONE = os.getenv("TIMEZONE", "UTC")

        # Schedule check interval (how often to check for schedule changes)
        self.SCHEDULE_CHECK_INTERVAL = _safe_int("SCHEDULE_CHECK_INTERVAL", 60)

        # Reuse base directory from _setup_paths
        base_dir = self.CONTENT_BASE_DIR

        # Sunday Service Schedule
        self.SUNDAY_SERVICE_FOLDER = base_dir / os.getenv(
            "SUNDAY_SERVICE_FOLDER",
            "content/sunday_service"
        )
        self.SUNDAY_SERVICE_START_TIME = os.getenv("SUNDAY_SERVICE_START_TIME", "08:00")
        self.SUNDAY_SERVICE_END_TIME = os.getenv("SUNDAY_SERVICE_END_TIME", "13:30")
        self.SUNDAY_SERVICE_TRANSITION = os.getenv("SUNDAY_SERVICE_TRANSITION", "Stinger Transition")
        self.SUNDAY_SERVICE_TRANSITION_OFFSET = _safe_float("SUNDAY_SERVICE_TRANSITION_OFFSET", 2.0)
        self.SUNDAY_SERVICE_DAY = _safe_int("SUNDAY_SERVICE_DAY", 6)  # 6 = Sunday

        # Default Schedule (fallback)
        self.DEFAULT_FOLDER = base_dir / os.getenv(
            "DEFAULT_FOLDER",
            "content/default"
        )
        self.DEFAULT_TRANSITION = os.getenv("DEFAULT_TRANSITION", "Fade")
        self.DEFAULT_TRANSITION_OFFSET = _safe_float("DEFAULT_TRANSITION_OFFSET", 0.5)

        # Manual content folder override (when scheduling is disabled)
        # Example: "vaeveriet_screens_slideshow/sunday_service_slideshow"
        manual_folder_env = os.getenv("MANUAL_CONTENT_FOLDER", "")
        if manual_folder_env and not self.SCHEDULE_ENABLED:
            self.MANUAL_CONTENT_FOLDER = base_dir / manual_folder_env
            # Override CONTENT_DIR to use the manual folder
            self.CONTENT_DIR = self.MANUAL_CONTENT_FOLDER
            # Note: logging happens later in main.py when logger is initialized
        else:
            self.MANUAL_CONTENT_FOLDER = None

        # Web UI settings
        self.WEB_UI_PORT = _safe_int("WEB_UI_PORT", 8080)
        self.WEB_UI_ENABLED = os.getenv("WEB_UI_ENABLED", "true").lower() in ("true", "1", "yes", "on")

        # Notification settings
        self.NOTIFICATION_ENABLED = os.getenv("NOTIFICATION_ENABLED", "false").lower() in ("true", "1", "yes", "on")
        self.NOTIFICATION_WEBHOOK_URL = os.getenv("NOTIFICATION_WEBHOOK_URL", "")

    def validate(self) -> list[str]:
        """Validate configuration and return list of errors."""
        errors = []
        logger = logging.getLogger(__name__)

        if not (1 <= self.OBS_PORT <= 65535):
            errors.append(f"OBS_PORT={self.OBS_PORT} is out of range (1-65535)")

        if self.WEBDAV_HOST and not (1 <= self.WEBDAV_PORT <= 65535):
            errors.append(f"WEBDAV_PORT={self.WEBDAV_PORT} is out of range (1-65535)")

        if self.WEB_UI_ENABLED and not (1 <= self.WEB_UI_PORT <= 65535):
            errors.append(f"WEB_UI_PORT={self.WEB_UI_PORT} is out of range (1-65535)")

        try:
            from zoneinfo import ZoneInfo
            ZoneInfo(self.TIMEZONE)
        except Exception:
            errors.append(f"TIMEZONE='{self.TIMEZONE}' is not a valid timezone")

        if self.IMAGE_DISPLAY_TIME < 1:
            errors.append(f"IMAGE_DISPLAY_TIME={self.IMAGE_DISPLAY_TIME} must be >= 1")

        if self.TRANSITION_START_OFFSET < 0:
            errors.append(f"TRANSITION_START_OFFSET={self.TRANSITION_START_OFFSET} must be >= 0")

        for error in errors:
            logger.error(f"Config validation: {error}")

        return errors