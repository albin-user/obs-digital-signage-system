"""
JSON file-based schedule storage with CRUD operations and conflict detection.
"""

import json
import logging
import os
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

DEFAULT_SCHEDULES = {
    "default_schedule": {
        "folder": "content/default",
        "transition": "Fade",
        "transition_offset": 0.5,
        "image_display_time": 15,
        "audio_volume": 100,
    },
    "schedules": [],
}


VALID_TRANSITIONS = {"Fade", "Stinger", "Stinger Transition", "Cut"}
VALID_SCHEDULE_TYPES = {"recurring", "one-time"}


def _validate_schedule_data(data: dict) -> Optional[str]:
    """Validate schedule data, returning error message or None if valid."""
    # Required fields
    name = data.get("name", "")
    if not name or not isinstance(name, str) or not name.strip():
        return "name is required and must be a non-empty string"

    stype = data.get("type", "")
    if stype not in VALID_SCHEDULE_TYPES:
        return f"type must be one of: {', '.join(VALID_SCHEDULE_TYPES)}"

    folder = data.get("folder", "")
    if not folder or not isinstance(folder, str) or not folder.strip():
        return "folder is required and must be a non-empty string"
    # Reject path traversal
    if ".." in folder:
        return "folder must not contain '..'"

    # Validate times (HH:MM format)
    for field in ("start_time", "end_time"):
        val = data.get(field, "")
        if val:
            try:
                parts = val.split(":")
                if len(parts) != 2:
                    raise ValueError
                h, m = int(parts[0]), int(parts[1])
                if not (0 <= h <= 23 and 0 <= m <= 59):
                    raise ValueError
            except (ValueError, AttributeError):
                return f"{field} must be in HH:MM format (00:00-23:59)"

    # Validate day_of_week for recurring
    if stype == "recurring":
        dow = data.get("day_of_week")
        if dow is not None:
            try:
                dow_int = int(dow)
                if not (0 <= dow_int <= 6):
                    raise ValueError
            except (ValueError, TypeError):
                return "day_of_week must be an integer 0-6 (Monday-Sunday)"

    # Validate date for one-time
    if stype == "one-time":
        date_str = data.get("date", "")
        if not date_str:
            return "date is required for one-time schedules"
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            return "date must be in YYYY-MM-DD format"

    # Validate optional numeric fields
    for field, lo, hi in [
        ("transition_offset", 0, 30),
        ("image_display_time", 1, 300),
        ("audio_volume", 0, 100),
    ]:
        if field in data:
            try:
                val = float(data[field])
                if not (lo <= val <= hi):
                    return f"{field} must be between {lo} and {hi}"
            except (ValueError, TypeError):
                return f"{field} must be a number"

    # Validate transition type
    transition = data.get("transition", "")
    if transition and transition not in VALID_TRANSITIONS:
        return f"transition must be one of: {', '.join(VALID_TRANSITIONS)}"

    return None


def _validate_default_data(data: dict) -> Optional[str]:
    """Validate default schedule update data, returning error message or None if valid."""
    folder = data.get("folder")
    if folder is not None:
        if not isinstance(folder, str) or not folder.strip():
            return "folder must be a non-empty string"
        if ".." in folder:
            return "folder must not contain '..'"

    transition = data.get("transition")
    if transition is not None and transition not in VALID_TRANSITIONS:
        return f"transition must be one of: {', '.join(VALID_TRANSITIONS)}"

    for field, lo, hi in [
        ("transition_offset", 0, 30),
        ("image_display_time", 1, 300),
        ("audio_volume", 0, 100),
    ]:
        if field in data:
            try:
                val = float(data[field])
                if not (lo <= val <= hi):
                    return f"{field} must be between {lo} and {hi}"
            except (ValueError, TypeError):
                return f"{field} must be a number"

    return None


class ScheduleStore:
    """Manages schedules in a JSON file."""

    def __init__(self, config_path: Path):
        self.file_path = config_path / "schedules.json"
        self._lock = threading.RLock()
        self._ensure_file()

    def _ensure_file(self) -> None:
        """Create schedules.json with defaults if it doesn't exist."""
        if not self.file_path.exists():
            self._write(DEFAULT_SCHEDULES)
            logger.info("Created default schedules.json")

    def _read(self) -> dict:
        with self._lock:
            try:
                with open(self.file_path, "r") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to read schedules.json: {e}")
                return DEFAULT_SCHEDULES.copy()

    def _write(self, data: dict) -> None:
        with self._lock:
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = self.file_path.with_suffix(".json.tmp")
            bak_path = self.file_path.with_suffix(".json.bak")
            try:
                with open(tmp_path, "w") as f:
                    json.dump(data, f, indent=2)
                    f.flush()
                    os.fsync(f.fileno())

                # Validate: re-read and parse the temp file to catch truncation
                with open(tmp_path, "r") as f:
                    json.load(f)

                # Keep a backup of the current good copy before replacing
                if self.file_path.exists():
                    try:
                        # Copy (not rename) so file_path stays valid during replace
                        import shutil
                        shutil.copy2(self.file_path, bak_path)
                    except Exception:
                        pass  # Best-effort backup

                os.replace(tmp_path, self.file_path)
            except Exception:
                # Clean up failed temp file
                try:
                    tmp_path.unlink(missing_ok=True)
                except Exception:
                    pass
                raise

    # -- CRUD --

    def get_all(self) -> dict:
        """Return the full schedules data."""
        return self._read()

    def get_default(self) -> dict:
        return self._read().get("default_schedule", DEFAULT_SCHEDULES["default_schedule"])

    def update_default(self, data: dict) -> dict:
        with self._lock:
            store = self._read()
            store["default_schedule"].update(data)
            self._write(store)
            return store["default_schedule"]

    def get_schedules(self) -> list[dict]:
        return self._read().get("schedules", [])

    def get_schedule(self, schedule_id: str) -> Optional[dict]:
        for s in self.get_schedules():
            if s["id"] == schedule_id:
                return s
        return None

    def create_schedule(self, data: dict) -> dict:
        with self._lock:
            store = self._read()
            schedule = {
                "id": str(uuid.uuid4()),
                "name": data["name"],
                "type": data["type"],
                "folder": data["folder"],
                "transition": data.get("transition", "Fade"),
                "transition_offset": float(data.get("transition_offset", 2.0)),
                "image_display_time": int(data.get("image_display_time", 15)),
                "audio_volume": int(data.get("audio_volume", 100)),
                "enabled": data.get("enabled", True),
                "created_at": datetime.now().isoformat(),
            }

            if data["type"] == "recurring":
                schedule["day_of_week"] = int(data["day_of_week"])
            elif data["type"] == "one-time":
                schedule["date"] = data["date"]

            schedule["start_time"] = data["start_time"]
            schedule["end_time"] = data["end_time"]

            store["schedules"].append(schedule)
            self._write(store)
            logger.info(f"Created schedule: {schedule['name']} ({schedule['id']})")
            return schedule

    def update_schedule(self, schedule_id: str, data: dict) -> Optional[dict]:
        with self._lock:
            store = self._read()
            for i, s in enumerate(store["schedules"]):
                if s["id"] == schedule_id:
                    # Update allowed fields
                    for key in [
                        "name", "type", "folder", "transition", "transition_offset",
                        "image_display_time", "audio_volume", "day_of_week", "date",
                        "start_time", "end_time", "enabled",
                    ]:
                        if key in data:
                            val = data[key]
                            if key == "transition_offset":
                                val = float(val)
                            elif key in ("image_display_time", "audio_volume", "day_of_week"):
                                val = int(val)
                            elif key == "enabled":
                                val = bool(val)
                            store["schedules"][i][key] = val
                    self._write(store)
                    logger.info(f"Updated schedule: {schedule_id}")
                    return store["schedules"][i]
            return None

    def delete_schedule(self, schedule_id: str) -> bool:
        with self._lock:
            store = self._read()
            before = len(store["schedules"])
            store["schedules"] = [s for s in store["schedules"] if s["id"] != schedule_id]
            if len(store["schedules"]) < before:
                self._write(store)
                logger.info(f"Deleted schedule: {schedule_id}")
                return True
            return False

    # -- Conflict detection --

    def check_conflicts(self) -> list[dict]:
        """Return list of conflict pairs among enabled schedules."""
        schedules = [s for s in self.get_schedules() if s.get("enabled", True)]
        conflicts = []

        for i in range(len(schedules)):
            for j in range(i + 1, len(schedules)):
                conflict = self._check_pair(schedules[i], schedules[j])
                if conflict:
                    conflicts.append(conflict)

        return conflicts

    def _check_pair(self, a: dict, b: dict) -> Optional[dict]:
        """Check if two schedules conflict."""
        # Check time overlap
        if not self._times_overlap(a["start_time"], a["end_time"], b["start_time"], b["end_time"]):
            return None

        # Check day overlap
        a_type, b_type = a["type"], b["type"]

        if a_type == "recurring" and b_type == "recurring":
            if a.get("day_of_week") == b.get("day_of_week"):
                return {
                    "type": "error",
                    "message": f"'{a['name']}' and '{b['name']}' overlap on the same weekday and time",
                    "schedule_a": a["id"],
                    "schedule_b": b["id"],
                }
        elif a_type == "one-time" and b_type == "one-time":
            if a.get("date") == b.get("date"):
                return {
                    "type": "error",
                    "message": f"'{a['name']}' and '{b['name']}' overlap on {a['date']}",
                    "schedule_a": a["id"],
                    "schedule_b": b["id"],
                }
        else:
            # one-time vs recurring
            onetime = a if a_type == "one-time" else b
            recurring = b if a_type == "one-time" else a
            try:
                event_date = datetime.strptime(onetime["date"], "%Y-%m-%d")
                if event_date.weekday() == recurring.get("day_of_week"):
                    return {
                        "type": "warning",
                        "message": (
                            f"One-time '{onetime['name']}' on {onetime['date']} "
                            f"will override recurring '{recurring['name']}'"
                        ),
                        "schedule_a": a["id"],
                        "schedule_b": b["id"],
                    }
            except (ValueError, KeyError):
                pass

        return None

    @staticmethod
    def _times_overlap(start_a: str, end_a: str, start_b: str, end_b: str) -> bool:
        """Check if two HH:MM time ranges overlap (handles midnight-crossing)."""
        try:
            sa = int(start_a.replace(":", ""))
            ea = int(end_a.replace(":", ""))
            sb = int(start_b.replace(":", ""))
            eb = int(end_b.replace(":", ""))

            # Normalize midnight-crossing ranges by checking both against
            # a virtual 48-hour timeline.  A range like 23:00-02:00 becomes
            # [2300,2600) — we add 2400 to the end when it wraps.
            def _ranges(s, e):
                if s < e:
                    return [(s, e)]
                # Crosses midnight: split into [s,2400) and [0,e)
                return [(s, 2400), (0, e)]

            for (a0, a1) in _ranges(sa, ea):
                for (b0, b1) in _ranges(sb, eb):
                    if a0 < b1 and b0 < a1:
                        return True
            return False
        except (ValueError, AttributeError):
            return False
