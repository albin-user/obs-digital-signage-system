"""
Flask web application for schedule management and system dashboard.
"""

import asyncio
import logging
import os
import re
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo, available_timezones

from flask import Flask, jsonify, render_template, request

from web.schedule_store import ScheduleStore, _validate_schedule_data, _validate_default_data
from web.storebox_browser import StoreboxBrowser

logger = logging.getLogger(__name__)


def create_app(
    config_path: Path,
    system_refs: dict | None = None,
) -> Flask:
    """Create and configure the Flask application.

    Args:
        config_path: Path to the config directory (contains schedules.json)
        system_refs: Dict with references to running system components:
            - obs_manager, content_manager, scheduler, audio_manager
            - webdav_client, settings, startup_time
    """
    app = Flask(
        __name__,
        template_folder=str(Path(__file__).parent / "templates"),
        static_folder=str(Path(__file__).parent / "static"),
    )
    app.config["JSON_SORT_KEYS"] = False

    @app.after_request
    def set_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "font-src 'self'"
        )
        return response

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "Not found"}), 404

    @app.errorhandler(500)
    def internal_error(e):
        return jsonify({"error": "Internal server error"}), 500

    store = ScheduleStore(config_path)
    refs = system_refs or {}

    # -- Dashboard page --

    # Cache-bust token: changes on each restart so browsers fetch fresh static files
    _cache_bust = str(int(time.time()))

    @app.route("/")
    def index():
        return render_template("index.html", cache_bust=_cache_bust)

    # -- Status API --

    @app.route("/api/status")
    def api_status():
        obs = refs.get("obs_manager")
        cm = refs.get("content_manager")
        scheduler = refs.get("scheduler")
        startup = refs.get("startup_time", 0)

        current_file = ""
        if cm:
            try:
                files = cm.media_files
                idx = cm.current_index
                if files and 0 <= idx < len(files):
                    current_file = files[idx].filename
            except (IndexError, AttributeError):
                pass

        active_schedule = ""
        if scheduler and scheduler.current_schedule:
            active_schedule = scheduler.current_schedule.name

        webdav = refs.get("webdav_client")
        last_sync = ""
        if webdav and webdav.last_sync_time:
            ago = int(time.time() - webdav.last_sync_time)
            last_sync = f"{ago}s ago"

        settings = refs.get("settings")
        try:
            tz_name = str(settings.TIMEZONE) if settings else "UTC"
            tz = ZoneInfo(tz_name)
            system_time = datetime.now(tz).strftime("%H:%M:%S")
        except Exception:
            tz_name = "UTC"
            system_time = ""

        return jsonify({
            "obs_connected": bool(obs and obs.connected),
            "current_playing": current_file,
            "active_schedule": active_schedule,
            "last_sync": last_sync,
            "uptime": _format_uptime(time.time() - startup) if startup else "",
            "media_count": len(cm.media_files) if cm else 0,
            "timezone": tz_name,
            "system_time": system_time,
        })

    # -- Schedule CRUD --

    @app.route("/api/schedules", methods=["GET"])
    def get_schedules():
        return jsonify(store.get_all())

    @app.route("/api/schedules", methods=["POST"])
    def create_schedule():
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400
        validation_error = _validate_schedule_data(data)
        if validation_error:
            return jsonify({"error": validation_error}), 400
        schedule = store.create_schedule(data)
        _notify_scheduler_reload()
        return jsonify(schedule), 201

    @app.route("/api/schedules/<schedule_id>", methods=["PUT"])
    def update_schedule(schedule_id):
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400
        # Validate updated fields (merge with existing for full validation)
        existing = store.get_schedule(schedule_id)
        if existing is None:
            return jsonify({"error": "Schedule not found"}), 404
        merged = {**existing, **data}
        validation_error = _validate_schedule_data(merged)
        if validation_error:
            return jsonify({"error": validation_error}), 400
        result = store.update_schedule(schedule_id, data)
        _notify_scheduler_reload()
        return jsonify(result)

    @app.route("/api/schedules/<schedule_id>/toggle", methods=["PATCH"])
    def toggle_schedule(schedule_id):
        existing = store.get_schedule(schedule_id)
        if existing is None:
            return jsonify({"error": "Schedule not found"}), 404
        new_enabled = not existing.get("enabled", True)
        result = store.update_schedule(schedule_id, {"enabled": new_enabled})
        _notify_scheduler_reload()
        return jsonify(result)

    @app.route("/api/schedules/<schedule_id>", methods=["DELETE"])
    def delete_schedule(schedule_id):
        if store.delete_schedule(schedule_id):
            _notify_scheduler_reload()
            return jsonify({"ok": True})
        return jsonify({"error": "Schedule not found"}), 404

    @app.route("/api/schedules/default", methods=["PUT"])
    def update_default():
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400
        validation_error = _validate_default_data(data)
        if validation_error:
            return jsonify({"error": validation_error}), 400
        result = store.update_default(data)
        _notify_scheduler_reload()
        return jsonify(result)

    @app.route("/api/schedules/conflicts")
    def check_conflicts():
        return jsonify(store.check_conflicts())

    # -- Sync trigger --

    @app.route("/api/sync/trigger", methods=["POST"])
    def trigger_sync():
        webdav = refs.get("webdav_client")
        cm = refs.get("content_manager")
        loop = refs.get("_event_loop")

        if not webdav:
            return jsonify({"error": "WebDAV client not available"}), 503
        if not loop:
            return jsonify({"error": "Event loop not available"}), 503

        try:
            async def _do_sync():
                changes = await webdav.sync_content()
                if changes:
                    await cm.scan_and_update_content()
                return changes

            future = asyncio.run_coroutine_threadsafe(_do_sync(), loop)
            changes = future.result(timeout=60)
            return jsonify({"ok": True, "changes": bool(changes)})
        except Exception as e:
            logger.error(f"Sync trigger failed: {e}")
            return jsonify({"error": str(e)}), 500

    # -- Timezone settings --

    @app.route("/api/settings/timezone", methods=["GET"])
    def get_timezone():
        settings = refs.get("settings")
        tz_name = settings.TIMEZONE if settings else "UTC"
        try:
            tz = ZoneInfo(tz_name)
            now = datetime.now(tz)
            system_time = now.strftime("%H:%M:%S")
        except Exception:
            system_time = ""
        return jsonify({"timezone": tz_name, "system_time": system_time})

    @app.route("/api/settings/timezone", methods=["PUT"])
    def set_timezone():
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400
        new_tz = (data.get("timezone") or "").strip()
        if not new_tz:
            return jsonify({"error": "timezone is required"}), 400
        if new_tz not in available_timezones():
            return jsonify({"error": f"'{new_tz}' is not a valid timezone"}), 400

        # Update running settings
        settings = refs.get("settings")
        if settings:
            settings.TIMEZONE = new_tz

        # Update scheduler timezone
        scheduler = refs.get("scheduler")
        if scheduler:
            try:
                scheduler.timezone = ZoneInfo(new_tz)
                logger.info(f"Scheduler timezone updated to {new_tz}")
            except Exception as e:
                logger.error(f"Failed to update scheduler timezone: {e}")

        # Persist to .env file
        _update_env_value("TIMEZONE", new_tz)

        logger.info(f"Timezone changed to {new_tz}")
        return jsonify({"timezone": new_tz, "ok": True})

    @app.route("/api/settings/timezones", methods=["GET"])
    def list_timezones():
        """Return list of common timezones for the dropdown."""
        common = [
            "Europe/Copenhagen", "Europe/London", "Europe/Berlin",
            "Europe/Paris", "Europe/Stockholm", "Europe/Oslo",
            "Europe/Helsinki", "Europe/Amsterdam", "Europe/Rome",
            "Europe/Madrid", "Europe/Zurich", "Europe/Vienna",
            "Europe/Warsaw", "Europe/Prague", "Europe/Athens",
            "Europe/Moscow",
            "US/Eastern", "US/Central", "US/Mountain", "US/Pacific",
            "America/New_York", "America/Chicago", "America/Denver",
            "America/Los_Angeles", "America/Toronto", "America/Sao_Paulo",
            "Asia/Tokyo", "Asia/Shanghai", "Asia/Kolkata", "Asia/Dubai",
            "Asia/Singapore", "Asia/Seoul",
            "Australia/Sydney", "Australia/Melbourne",
            "Pacific/Auckland",
            "Africa/Johannesburg", "Africa/Cairo",
            "UTC",
        ]
        all_tzs = sorted(available_timezones())
        return jsonify({"common": common, "all": all_tzs})

    def _update_env_value(key: str, value: str) -> None:
        """Update a key=value in the .env config file."""
        try:
            from config.settings import get_env_file_path
            env_file = get_env_file_path()
            if not env_file.exists():
                return

            lines = env_file.read_text().splitlines()
            updated = False
            for i, line in enumerate(lines):
                stripped = line.strip()
                if stripped.startswith(f"{key}=") or stripped.startswith(f"{key} ="):
                    lines[i] = f"{key}={value}"
                    updated = True
                    break

            if not updated:
                lines.append(f"{key}={value}")

            env_file.write_text("\n".join(lines) + "\n")
            logger.info(f"Updated {key} in {env_file}")
        except Exception as e:
            logger.error(f"Failed to update .env file: {e}")

    # -- Content listing --

    @app.route("/api/content")
    def list_content():
        cm = refs.get("content_manager")
        if not cm:
            return jsonify([])
        try:
            files = cm.media_files
            return jsonify([
                {
                    "name": f.filename,
                    "type": "video" if f.is_video else "image",
                    "duration": f.duration,
                }
                for f in files
            ])
        except Exception as e:
            logger.error(f"Content listing failed: {e}")
            return jsonify([])

    # -- Folder browser --

    @app.route("/api/folders", methods=["GET"])
    def list_root_folders():
        return jsonify(_browse_folders("/"))

    @app.route("/api/folders", methods=["POST"])
    def create_folder():
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400
        parent = data.get("path", "/")
        name = (data.get("name") or "").strip()
        if not name:
            return jsonify({"error": "Folder name is required"}), 400
        # Validate name: no slashes, no traversal, no control chars
        if "/" in name or "\\" in name or ".." in name:
            return jsonify({"error": "Folder name must not contain slashes or '..'"}), 400
        if "\x00" in name or any(ord(c) < 32 for c in name):
            return jsonify({"error": "Folder name contains invalid characters"}), 400

        webdav = refs.get("webdav_client")
        if not webdav:
            return jsonify({"error": "WebDAV client not available"}), 503
        browser = StoreboxBrowser(webdav)
        try:
            browser.create_folder(parent, name)
            return jsonify({"ok": True}), 201
        except Exception as e:
            logger.error(f"Failed to create folder: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route("/api/folders/<path:subpath>")
    def list_sub_folders(subpath):
        # Strip WebDAV root prefix — _browse_folders will re-add it
        settings = refs.get("settings")
        root_prefix = settings.WEBDAV_ROOT_PATH.strip("/") if settings else ""
        if root_prefix and subpath.startswith(root_prefix + "/"):
            subpath = subpath[len(root_prefix) + 1:]
        return jsonify(_browse_folders("/" + subpath))

    @app.route("/api/folders/files/<path:subpath>")
    def list_folder_files(subpath):
        webdav = refs.get("webdav_client")
        if not webdav:
            return jsonify({"files": []})
        # Strip WebDAV root prefix — StoreboxBrowser expects NAS-relative paths
        settings = refs.get("settings")
        root_prefix = settings.WEBDAV_ROOT_PATH.strip("/") if settings else ""
        if root_prefix and subpath.startswith(root_prefix + "/"):
            subpath = subpath[len(root_prefix) + 1:]
        browser = StoreboxBrowser(webdav)
        files = browser.list_files("/" + subpath)
        return jsonify({"files": files})

    def _browse_folders(path: str) -> list:
        webdav = refs.get("webdav_client")
        if not webdav:
            return []
        browser = StoreboxBrowser(webdav)
        folders = browser.list_folders(path)
        # Prefix paths so they match local download structure
        # (schedules.json needs CONTENT_BASE_DIR-relative paths)
        settings = refs.get("settings")
        root_prefix = settings.WEBDAV_ROOT_PATH.strip("/") if settings else ""
        if root_prefix:
            for f in folders:
                f["path"] = f"{root_prefix}/{f['path']}"
        return folders

    def _notify_scheduler_reload():
        scheduler = refs.get("scheduler")
        if scheduler and hasattr(scheduler, "reload_schedules"):
            try:
                scheduler.reload_schedules()
                logger.info("Scheduler reloaded after web UI change")
            except Exception as e:
                logger.error(f"Failed to reload scheduler: {e}")

    return app


def _format_uptime(seconds: float) -> str:
    s = int(seconds)
    days = s // 86400
    hours = (s % 86400) // 3600
    minutes = (s % 3600) // 60
    if days > 0:
        return f"{days}d {hours}h {minutes}m"
    elif hours > 0:
        return f"{hours}h {minutes}m"
    else:
        return f"{minutes}m"
