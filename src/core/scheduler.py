"""
Time-based content scheduling system.
Manages switching between different content folders and transitions based on time/day.
Supports recurring weekly schedules and one-time date-specific events.
Loads schedules from config/schedules.json (managed by web UI) with .env fallback.
"""

import json
import logging
import threading
from datetime import datetime, time, date as date_type
from pathlib import Path
from typing import List, Optional
from zoneinfo import ZoneInfo


class Schedule:
    """Represents a content schedule with time/day restrictions."""

    def __init__(
        self,
        name: str,
        folder: Path,
        transition_type: str,
        transition_offset: float,
        image_display_time: int = 15,
        audio_volume: int = 80,
        schedule_type: str = "recurring",
        day_of_week: Optional[int] = None,
        start_time: Optional[time] = None,
        end_time: Optional[time] = None,
        event_date: Optional[date_type] = None,
        enabled: bool = True,
        schedule_id: str = "",
    ):
        self.name = name
        self.folder = folder
        self.transition_type = transition_type
        self.transition_offset = transition_offset
        self.image_display_time = image_display_time
        self.audio_volume = audio_volume
        self.schedule_type = schedule_type
        self.day_of_week = day_of_week
        self.start_time = start_time
        self.end_time = end_time
        self.event_date = event_date
        self.enabled = enabled
        self.schedule_id = schedule_id

        self.logger = logging.getLogger(__name__)

    def is_active(self, current_time: datetime) -> bool:
        """Check if this schedule is currently active."""
        if not self.enabled:
            return False

        # One-time events must match the specific date
        if self.schedule_type == "one-time" and self.event_date is not None:
            if current_time.date() != self.event_date:
                return False

        # Recurring schedules must match the day of week
        if self.schedule_type == "recurring" and self.day_of_week is not None:
            if current_time.weekday() != self.day_of_week:
                return False

        # If no time restrictions, schedule is active (based on day only)
        if self.start_time is None and self.end_time is None:
            return True

        # Check time range
        if self.start_time is not None and self.end_time is not None:
            current_time_only = current_time.time()
            if self.start_time <= self.end_time:
                return self.start_time <= current_time_only < self.end_time
            else:
                return current_time_only >= self.start_time or current_time_only < self.end_time

        return True

    def __repr__(self) -> str:
        return (f"Schedule({self.name}, type={self.schedule_type}, folder={self.folder.name}, "
                f"transition={self.transition_type}, day={self.day_of_week}, "
                f"time={self.start_time}-{self.end_time})")


class Scheduler:
    """Manages multiple schedules and determines which is currently active."""

    def __init__(self, settings):
        self.settings = settings
        self.logger = logging.getLogger(__name__)

        try:
            self.timezone = ZoneInfo(settings.TIMEZONE)
        except Exception as e:
            self.logger.warning(f"Invalid timezone '{settings.TIMEZONE}': {e}, falling back to UTC")
            self.timezone = ZoneInfo("UTC")

        self._lock = threading.Lock()
        self.schedules: List[Schedule] = []
        self.default_schedule: Optional[Schedule] = None
        self.current_schedule: Optional[Schedule] = None
        self._switch_needed = False
        self._settings_changed = False

        self._json_path = Path(settings.CONFIG_DIR) / "schedules.json"
        self._load_schedules()

    def _load_schedules(self) -> None:
        """Load schedules from JSON file, falling back to .env settings."""
        try:
            self.logger.info("Loading schedules...")

            if self._json_path.exists():
                schedules, default = self._load_from_json_into()
            else:
                self.logger.info("No schedules.json found, loading from .env settings")
                schedules, default = self._load_from_env_into()
                self.schedules = schedules
                self.default_schedule = default
                self._migrate_to_json()
                # _migrate_to_json reads from self, so assign before calling it
                # but we still set via the tuple below for consistency
                schedules = self.schedules
                default = self.default_schedule

            self.schedules = schedules
            self.default_schedule = default

            if not self.default_schedule:
                raise Exception("No default schedule configured")

            self.current_schedule = self.get_active_schedule()
            self.logger.info(f"Initial active schedule: {self.current_schedule.name}")

        except Exception as e:
            self.logger.error(f"Failed to load schedules: {e}")
            raise

    def _load_from_json_into(self) -> tuple:
        """Load schedules from config/schedules.json.

        Returns:
            Tuple of (schedules_list, default_schedule).
        """
        try:
            with open(self._json_path, "r") as f:
                data = json.load(f)
        except Exception as e:
            self.logger.error(f"Failed to read schedules.json: {e}")
            return self._load_from_env_into()

        base_dir = self.settings.CONTENT_BASE_DIR

        # Load default schedule
        default_data = data.get("default_schedule", {})
        default_schedule = Schedule(
            name="Default",
            folder=base_dir / default_data.get("folder", "content/default"),
            transition_type=default_data.get("transition", "Fade"),
            transition_offset=float(default_data.get("transition_offset", 0.5)),
            image_display_time=int(default_data.get("image_display_time", 15)),
            audio_volume=int(default_data.get("audio_volume", 80)),
            schedule_type="default",
        )
        self.logger.info(f"Loaded default schedule: {default_schedule}")

        # Load custom schedules
        schedules = []
        for sdata in data.get("schedules", []):
            schedule = self._parse_schedule_json(sdata, base_dir)
            if schedule:
                schedules.append(schedule)
                self.logger.info(f"Loaded schedule: {schedule}")

        return schedules, default_schedule

    def _parse_schedule_json(self, sdata: dict, base_dir: Path) -> Optional[Schedule]:
        """Parse a single schedule from JSON data."""
        try:
            start_time = self._parse_time(sdata.get("start_time", ""))
            end_time = self._parse_time(sdata.get("end_time", ""))

            event_date = None
            if sdata.get("type") == "one-time" and sdata.get("date"):
                try:
                    event_date = datetime.strptime(sdata["date"], "%Y-%m-%d").date()
                except ValueError:
                    self.logger.warning(f"Invalid date in schedule '{sdata.get('name')}': {sdata['date']}")

            return Schedule(
                name=sdata.get("name", "Unnamed"),
                folder=base_dir / sdata.get("folder", ""),
                transition_type=sdata.get("transition", "Fade"),
                transition_offset=float(sdata.get("transition_offset", 2.0)),
                image_display_time=int(sdata.get("image_display_time", 15)),
                audio_volume=int(sdata.get("audio_volume", 80)),
                schedule_type=sdata.get("type", "recurring"),
                day_of_week=sdata.get("day_of_week"),
                start_time=start_time,
                end_time=end_time,
                event_date=event_date,
                enabled=sdata.get("enabled", True),
                schedule_id=sdata.get("id", ""),
            )
        except Exception as e:
            self.logger.error(f"Failed to parse schedule: {e}")
            return None

    def _load_from_env_into(self) -> tuple:
        """Fallback: load schedules from .env settings.

        Returns:
            Tuple of (schedules_list, default_schedule).
        """
        schedules = []

        # Sunday Service schedule
        if hasattr(self.settings, 'SUNDAY_SERVICE_FOLDER'):
            start = self._parse_time(self.settings.SUNDAY_SERVICE_START_TIME)
            end = self._parse_time(self.settings.SUNDAY_SERVICE_END_TIME)
            if start and end:
                sunday = Schedule(
                    name="Sunday Service",
                    folder=self.settings.SUNDAY_SERVICE_FOLDER,
                    transition_type=self.settings.SUNDAY_SERVICE_TRANSITION,
                    transition_offset=self.settings.SUNDAY_SERVICE_TRANSITION_OFFSET,
                    day_of_week=self.settings.SUNDAY_SERVICE_DAY,
                    start_time=start,
                    end_time=end,
                )
                schedules.append(sunday)
                self.logger.info(f"Loaded env schedule: {sunday}")

        # Default schedule
        default_schedule = Schedule(
            name="Default",
            folder=self.settings.DEFAULT_FOLDER,
            transition_type=self.settings.DEFAULT_TRANSITION,
            transition_offset=self.settings.DEFAULT_TRANSITION_OFFSET,
            schedule_type="default",
        )
        self.logger.info(f"Loaded default schedule: {default_schedule}")

        return schedules, default_schedule

    def _migrate_to_json(self) -> None:
        """Migrate .env schedules to schedules.json."""
        import uuid
        data = {
            "default_schedule": {
                "folder": str(self.default_schedule.folder.relative_to(self.settings.CONTENT_BASE_DIR))
                    if self.default_schedule else "content/default",
                "transition": self.default_schedule.transition_type if self.default_schedule else "Fade",
                "transition_offset": self.default_schedule.transition_offset if self.default_schedule else 0.5,
                "image_display_time": 15,
                "audio_volume": 80,
            },
            "schedules": [],
        }

        for s in self.schedules:
            entry = {
                "id": str(uuid.uuid4()),
                "name": s.name,
                "type": s.schedule_type,
                "folder": str(s.folder.relative_to(self.settings.CONTENT_BASE_DIR)) if s.folder else "",
                "transition": s.transition_type,
                "transition_offset": s.transition_offset,
                "image_display_time": s.image_display_time,
                "audio_volume": s.audio_volume,
                "start_time": s.start_time.strftime("%H:%M") if s.start_time else "",
                "end_time": s.end_time.strftime("%H:%M") if s.end_time else "",
                "enabled": True,
                "created_at": datetime.now().isoformat(),
            }
            if s.day_of_week is not None:
                entry["day_of_week"] = s.day_of_week
            data["schedules"].append(entry)

        try:
            self._json_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._json_path, "w") as f:
                json.dump(data, f, indent=2)
            self.logger.info("Migrated schedules from .env to schedules.json")
        except Exception as e:
            self.logger.error(f"Failed to migrate schedules: {e}")

    @staticmethod
    def _is_same_schedule_slot(a, b):
        """Check if two Schedules represent the same logical slot."""
        if a is None or b is None:
            return a is b
        if a.schedule_type == "default" and b.schedule_type == "default":
            return True
        return a.schedule_id == b.schedule_id and a.schedule_id != ""

    @staticmethod
    def _settings_differ(a, b):
        """Check if runtime settings differ (excluding folder)."""
        return (a.audio_volume != b.audio_volume
                or a.transition_offset != b.transition_offset
                or a.image_display_time != b.image_display_time
                or a.transition_type != b.transition_type)

    def reload_schedules(self) -> None:
        """Reload schedules from JSON file (called by web UI after changes)."""
        self.logger.info("Reloading schedules from JSON...")

        try:
            # Load into local variables — never touches self.schedules during loading
            if self._json_path.exists():
                new_schedules, new_default = self._load_from_json_into()
            else:
                new_schedules, new_default = self._load_from_env_into()

            if not new_default:
                self.logger.error("No default schedule after reload!")
                new_default = Schedule(
                    name="Default",
                    folder=self.settings.DEFAULT_FOLDER,
                    transition_type="Fade",
                    transition_offset=0.5,
                    schedule_type="default",
                )
        except Exception:
            self.logger.error("Reload failed, keeping previous schedules")
            raise

        # Swap atomically under lock so get_active_schedule() never sees partial state
        with self._lock:
            self.schedules = new_schedules
            self.default_schedule = new_default

        new_active = self.get_active_schedule()
        with self._lock:
            old = self.current_schedule
            if self._is_same_schedule_slot(old, new_active):
                # Same schedule slot — check for folder vs settings-only change
                if old.folder != new_active.folder:
                    self._switch_needed = True  # Folder change = full content switch
                elif self._settings_differ(old, new_active):
                    self._settings_changed = True  # Lightweight update
                self.current_schedule = new_active
            else:
                # Different schedule became active
                self.logger.info(f"Active schedule changed after reload: {new_active.name}")
                self.current_schedule = new_active
                self._switch_needed = True

    def _parse_time(self, time_str: str) -> Optional[time]:
        """Parse time string in HH:MM format."""
        try:
            parts = time_str.split(':')
            if len(parts) != 2:
                return None
            hour, minute = int(parts[0]), int(parts[1])
            if 0 <= hour <= 23 and 0 <= minute <= 59:
                return time(hour, minute)
            return None
        except Exception:
            return None

    def get_current_time(self) -> datetime:
        """Get current time in configured timezone."""
        return datetime.now(self.timezone)

    def get_active_schedule(self) -> Schedule:
        """Get the currently active schedule. Priority: one-time > recurring > default."""
        current_time = self.get_current_time()

        # Copy references under lock to iterate safely
        with self._lock:
            schedules = list(self.schedules)
            default = self.default_schedule

        # Check one-time schedules first (highest priority)
        for schedule in schedules:
            if schedule.schedule_type == "one-time" and schedule.is_active(current_time):
                return schedule

        # Then check recurring schedules
        for schedule in schedules:
            if schedule.schedule_type == "recurring" and schedule.is_active(current_time):
                return schedule

        return default

    def check_schedule_change(self) -> bool:
        """Check if the active schedule has changed since last check."""
        new_schedule = self.get_active_schedule()
        with self._lock:
            if self._switch_needed or new_schedule != self.current_schedule:
                self._switch_needed = False
                old_name = self.current_schedule.name if self.current_schedule else "None"
                self.logger.info(f"Schedule changed: {old_name} -> {new_schedule.name}")
                self.current_schedule = new_schedule
                return True
        return False

    def check_settings_change(self) -> bool:
        """Check if settings were updated on the current schedule (without schedule switch)."""
        with self._lock:
            if self._settings_changed:
                self._settings_changed = False
                return True
        return False

    def get_current_content_folder(self) -> Path:
        return self.get_active_schedule().folder

    def get_current_transition_type(self) -> str:
        return self.get_active_schedule().transition_type

    def get_current_transition_offset(self) -> float:
        return self.get_active_schedule().transition_offset

    def get_current_audio_volume(self) -> int:
        return self.get_active_schedule().audio_volume

    def get_current_image_display_time(self) -> int:
        return self.get_active_schedule().image_display_time
