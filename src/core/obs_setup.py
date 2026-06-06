"""
OBS Studio pre-configuration helpers.

Lets the setup wizard enable the OBS WebSocket server with a known password
*before* OBS is first launched, so the operator never has to open OBS'
"Tools -> WebSocket Server Settings" dialog or copy the password by hand.

OBS reads this config only at launch, so writing it has effect on the next
OBS start (the signage app launches OBS itself, so this lines up naturally).

Config format and key names verified against obs-websocket source
(src/Config.cpp): the file is plugin_config/obs-websocket/config.json with
keys server_enabled, server_port, server_password, auth_required,
alerts_enabled, first_load.
"""

import json
import logging
import os
import platform
import shutil
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def get_obs_config_dir() -> Path:
    """Return the OBS Studio per-user config directory for this platform.

    Honors the OBS_CONFIG_DIR environment variable when set (used by tests
    and unusual installs to avoid touching the real OBS profile).
    """
    override = os.environ.get("OBS_CONFIG_DIR")
    if override:
        return Path(override)

    system = platform.system()
    if system == "Windows":
        base = os.environ.get("APPDATA")
        if base:
            return Path(base) / "obs-studio"
        return Path.home() / "AppData" / "Roaming" / "obs-studio"
    if system == "Darwin":
        return Path.home() / "Library" / "Application Support" / "obs-studio"

    # Linux: native (apt/deb) uses ~/.config/obs-studio, but Flatpak and Snap
    # sandbox OBS' config elsewhere. Prefer the native path, but if it does not
    # exist and a Flatpak/Snap profile does, target that so the WebSocket
    # pre-seed actually lands where this machine's OBS will read it.
    native = Path.home() / ".config" / "obs-studio"
    if native.exists():
        return native
    flatpak = Path.home() / ".var" / "app" / "com.obsproject.Studio" / "config" / "obs-studio"
    if flatpak.exists():
        return flatpak
    snap = Path.home() / "snap" / "obs-studio" / "current" / ".config" / "obs-studio"
    if snap.exists():
        return snap
    # Nothing exists yet (OBS never launched) — default to native.
    return native


def get_websocket_config_path() -> Path:
    """Return the path to the obs-websocket config.json."""
    return get_obs_config_dir() / "plugin_config" / "obs-websocket" / "config.json"


def write_websocket_config(
    password: str,
    port: int = 4455,
    enable: bool = True,
) -> Optional[Path]:
    """Enable the OBS WebSocket server with the given password.

    Merges into any existing config.json (preserving unknown keys), backs up
    the previous file, and writes atomically. Returns the config path on
    success, or None on failure (failures are logged, never raised, so a
    setup flow is not aborted by this best-effort step).
    """
    try:
        config_path = get_websocket_config_path()

        # Load existing config if present so we don't clobber unrelated keys.
        existing = {}
        if config_path.exists():
            try:
                existing = json.loads(config_path.read_text())
                if not isinstance(existing, dict):
                    existing = {}
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"Existing obs-websocket config unreadable, recreating: {e}")
                existing = {}

        existing.update({
            "server_enabled": bool(enable),
            "server_port": int(port),
            "server_password": password,
            "auth_required": bool(password),
            # Suppress the obs-websocket first-run dialog on next OBS launch.
            "first_load": False,
        })
        # Preserve alerts_enabled if it was set, otherwise default it off.
        existing.setdefault("alerts_enabled", False)

        config_path.parent.mkdir(parents=True, exist_ok=True)

        # Back up an existing file once per write so a bad edit is recoverable.
        if config_path.exists():
            backup = config_path.with_suffix(f".json.bak.{int(time.time())}")
            try:
                shutil.copy2(config_path, backup)
            except OSError as e:
                logger.warning(f"Could not back up obs-websocket config: {e}")

        tmp_path = config_path.with_suffix(".json.tmp")
        tmp_path.write_text(json.dumps(existing, indent=4))
        os.replace(str(tmp_path), str(config_path))

        logger.info(
            f"OBS WebSocket pre-configured (enabled={enable}, port={port}) "
            f"at {config_path}"
        )
        return config_path

    except Exception as e:
        logger.warning(f"Could not pre-configure OBS WebSocket: {e}")
        return None


def is_obs_running() -> bool:
    """Best-effort check whether OBS is currently running.

    Used by the wizard to warn that a pre-seeded WebSocket config will only
    take effect after OBS restarts. Returns False if psutil is unavailable.
    """
    try:
        import psutil
    except ImportError:
        return False

    names = ("obs", "obs64", "obs-studio")
    for proc in psutil.process_iter(["name"]):
        try:
            pname = (proc.info.get("name") or "").lower()
            if pname in (f"{n}.exe" for n in names) or pname in names:
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return False
