#!/usr/bin/env python3
"""
OBS Digital Signage Automation System
Production-ready implementation with obsws-python integration
"""

import asyncio
import signal
import sys
import time
import logging
import os
import threading
from pathlib import Path
from typing import Optional
import platform

# Local imports
from config.settings import Settings
from core.obs_manager import OBSManager
from core.content_manager import ContentManager
from core.audio_manager import AudioManager
from core.webdav_client import WebDAVClient
from core.file_monitor import FileMonitor
from core.scheduler import Scheduler
from utils.logging_config import setup_logging
from utils.system_utils import SystemUtils
from utils.notifications import NotificationManager


class DigitalSignageSystem:
    """Main automation system with obsws-python integration."""
    
    def __init__(self):
        self.settings = Settings()
        self.running = False
        self.startup_time = time.time()
        
        # Initialize logging first
        setup_logging(self.settings.LOG_LEVEL, self.settings.LOG_DIR)
        self.logger = logging.getLogger(__name__)
        
        # System components
        self.obs_manager: Optional[OBSManager] = None
        self.content_manager: Optional[ContentManager] = None
        self.audio_manager: Optional[AudioManager] = None
        self.webdav_client: Optional[WebDAVClient] = None
        self.file_monitor: Optional[FileMonitor] = None
        self.scheduler: Optional[Scheduler] = None
        self._web_thread: Optional[threading.Thread] = None
        self.notifier = NotificationManager(
            webhook_url=self.settings.NOTIFICATION_WEBHOOK_URL,
            enabled=self.settings.NOTIFICATION_ENABLED,
        )
        
        # Setup signal handlers for graceful shutdown
        if platform.system() != "Windows":
            signal.signal(signal.SIGINT, self._signal_handler)
            signal.signal(signal.SIGTERM, self._signal_handler)
        
        # Validate configuration
        config_errors = self.settings.validate()
        if config_errors:
            for err in config_errors:
                self.logger.error(f"Config error: {err}")

        self.logger.info(f"Digital Signage System initialized on {platform.system()}")
    
    def _signal_handler(self, signum: int, frame) -> None:
        """Handle shutdown signals gracefully."""
        self.logger.info(f"Received signal {signum}, initiating shutdown...")
        self.running = False
    
    async def initialize_components(self) -> bool:
        """Initialize all system components with error handling."""
        try:
            self.logger.info("Starting component initialization...")
            
            # 1. Initialize OBS Manager with obsws-python
            self.logger.info("Initializing OBS Studio connection...")
            self.obs_manager = OBSManager(self.settings)
            if not await self.obs_manager.initialize():
                raise Exception("Failed to initialize OBS Studio connection")

            # 2. Initialize Scheduler (if enabled)
            if self.settings.SCHEDULE_ENABLED:
                self.logger.info("Initializing scheduler...")
                self.scheduler = Scheduler(self.settings)

                # Get initial schedule
                initial_folder = self.scheduler.get_current_content_folder()
                initial_offset = self.scheduler.get_current_transition_offset()
                initial_transition = self.scheduler.get_current_transition_type()

                # Override content folder with scheduled folder
                self.settings.CONTENT_DIR = initial_folder

                # Set initial transition in OBS
                await self.obs_manager.set_transition(initial_transition)

                self.logger.info(f"Initial schedule active: {self.scheduler.current_schedule.name}")
                self.logger.info(f"  Content folder: {initial_folder}")
                self.logger.info(f"  Transition: {initial_transition}")
            else:
                # Scheduling is disabled
                if self.settings.MANUAL_CONTENT_FOLDER:
                    self.logger.info("Scheduling disabled - using manual content folder override")
                    self.logger.info(f"  Content folder: {self.settings.MANUAL_CONTENT_FOLDER}")
                else:
                    self.logger.info("Scheduling disabled - using default content folder")
                    self.logger.info(f"  Content folder: {self.settings.CONTENT_DIR}")

            # 3. Initialize Content Manager (before WebDAV so we can pass callback)
            self.logger.info("Initializing content management...")
            self.content_manager = ContentManager(self.settings, self.obs_manager)
            await self.content_manager.initialize()

            # 3. Initialize WebDAV Client for Synology NAS (with deletion callback)
            self.logger.info("Initializing WebDAV synchronization...")
            self.webdav_client = WebDAVClient(
                self.settings,
                deletion_callback=self.content_manager.on_file_deleted
            )
            if not await self.webdav_client.test_connection():
                self.logger.warning("WebDAV connection failed - running in offline mode")
            
            # 4. Initialize Audio Manager
            self.logger.info("Initializing background audio system...")
            self.audio_manager = AudioManager(self.settings)
            await self.audio_manager.initialize()
            
            # 5. Initialize File Monitor
            self.logger.info("Initializing file monitoring...")
            self.file_monitor = FileMonitor(
                self.settings.CONTENT_DIR,
                self.content_manager.on_content_change
            )
            
            # 6. Perform initial content sync and scan
            await self._initial_content_setup()

            # 7. Apply initial audio volume from schedule
            if self.scheduler and self.audio_manager:
                vol = self.scheduler.get_current_audio_volume()
                self.audio_manager.set_volume(vol)

            # 8. Start Web UI in background thread
            if self.settings.WEB_UI_ENABLED:
                self._start_web_ui()

            self.notifier.notify_startup()
            self.logger.info("All components initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Component initialization failed: {e}")
            return False
    
    def _start_web_ui(self) -> None:
        """Start Flask web UI in a background thread."""
        try:
            from web.app import create_app

            system_refs = {
                "obs_manager": self.obs_manager,
                "content_manager": self.content_manager,
                "scheduler": self.scheduler,
                "audio_manager": self.audio_manager,
                "webdav_client": self.webdav_client,
                "settings": self.settings,
                "startup_time": self.startup_time,
                "_event_loop": asyncio.get_event_loop(),
            }

            self._web_app = create_app(self.settings.CONFIG_DIR, system_refs)
            self._web_port = self.settings.WEB_UI_PORT

            def run_flask():
                try:
                    # Suppress Flask/Werkzeug default logging
                    log = logging.getLogger("werkzeug")
                    log.setLevel(logging.WARNING)
                    self._web_app.run(host="0.0.0.0", port=self._web_port, debug=False, use_reloader=False)
                except Exception as e:
                    self.logger.error(f"Flask thread crashed: {e}")

            self._web_thread = threading.Thread(target=run_flask, daemon=True, name="web-ui")
            self._web_thread.start()
            self.logger.info(f"Web UI started on http://0.0.0.0:{self._web_port}")
        except Exception as e:
            self.logger.error(f"Failed to start Web UI: {e}")

    async def _initial_content_setup(self) -> None:
        """Perform initial content synchronization and setup."""
        try:
            # Sync from WebDAV if available
            if self.webdav_client and await self.webdav_client.test_connection():
                self.logger.info("Performing initial WebDAV synchronization...")
                await self.webdav_client.sync_content()
            
            # Scan local content and setup OBS scenes
            self.logger.info("Scanning local content...")
            await self.content_manager.scan_and_update_content()



            # Initialize background audio
            self.logger.info("Setting up background audio...")
            await self.audio_manager.scan_and_start_audio()
            
            # Start file monitoring
            self.file_monitor.start()
            
        except Exception as e:
            self.logger.error(f"Initial content setup failed: {e}")
    
    async def run_main_loop(self) -> None:
        """Main automation loop with async task management."""
        self.running = True

        # Task registry: name -> (factory, task, restart_count, next_backoff)
        task_factories = {
            "webdav_sync": self._webdav_sync_loop,
            "content_rotation": self._content_rotation_loop,
            "health_monitoring": self._health_monitoring_loop,
            "audio_monitoring": self._audio_monitoring_loop,
        }
        if self.settings.SCHEDULE_ENABLED and self.scheduler:
            task_factories["schedule_monitoring"] = self._schedule_monitoring_loop

        MAX_RESTARTS = 10
        INITIAL_BACKOFF = 1.0
        MAX_BACKOFF = 300.0

        task_state = {}
        tasks = {}
        for name, factory in task_factories.items():
            tasks[name] = asyncio.create_task(factory())
            task_state[name] = {"restarts": 0, "backoff": INITIAL_BACKOFF}

        try:
            while self.running:
                await asyncio.sleep(1)

                for name, task in list(tasks.items()):
                    if not task.done():
                        continue
                    try:
                        task.result()
                        continue  # Task completed normally
                    except asyncio.CancelledError:
                        continue  # Task was cancelled, not a failure
                    except Exception:
                        self.logger.error(f"Task '{name}' failed:", exc_info=True)
                        state = task_state[name]

                        if state["restarts"] >= MAX_RESTARTS:
                            self.logger.error(f"Task '{name}' exceeded {MAX_RESTARTS} restarts, not restarting")
                            continue

                        state["restarts"] += 1
                        backoff = state["backoff"]
                        self.logger.info(f"Restarting '{name}' in {backoff:.0f}s (attempt {state['restarts']}/{MAX_RESTARTS})")
                        await asyncio.sleep(backoff)
                        state["backoff"] = min(backoff * 2, MAX_BACKOFF)
                        tasks[name] = asyncio.create_task(task_factories[name]())

        except KeyboardInterrupt:
            self.logger.info("Keyboard interrupt received")
            self.running = False

        finally:
            for task in tasks.values():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
    
    async def _webdav_sync_loop(self) -> None:
        """WebDAV synchronization loop."""
        while self.running:
            try:
                if self.webdav_client and await self.webdav_client.test_connection():
                    changes_detected = await self.webdav_client.sync_content()
                    if changes_detected:
                        self.logger.info("Content changes detected, updating scenes...")
                        await self.content_manager.scan_and_update_content()
                        await self.audio_manager.scan_and_start_audio()
                
                await asyncio.sleep(30)  # 30-second sync interval
                
            except Exception as e:
                self.logger.error(f"WebDAV sync error: {e}")
                await asyncio.sleep(60)  # Longer delay on error
    
    async def _content_rotation_loop(self) -> None:
        """Content rotation management loop."""
        while self.running:
            try:
                if self.content_manager:
                    await self.content_manager.process_content_rotation()
                await asyncio.sleep(0.5)  # High-frequency loop for precise timing
                
            except Exception as e:
                self.logger.error(f"Content rotation error: {e}")
                await asyncio.sleep(5)
    
    async def _health_monitoring_loop(self) -> None:
        """System health monitoring."""
        while self.running:
            try:
                # Check OBS health
                if self.obs_manager and not await self.obs_manager.health_check():
                    self.logger.warning("OBS health check failed - attempting recovery")
                    await self.obs_manager.recover()

                # Check web UI thread health
                if (self.settings.WEB_UI_ENABLED
                        and self._web_thread is not None
                        and not self._web_thread.is_alive()):
                    self.logger.warning("Web UI thread died - restarting")
                    self._start_web_ui()

                await asyncio.sleep(60)  # Health check every minute

            except Exception as e:
                self.logger.error(f"Health monitoring error: {e}")
                await asyncio.sleep(120)
    
    async def _audio_monitoring_loop(self) -> None:
        """Audio system monitoring."""
        while self.running:
            try:
                if self.audio_manager and not self.audio_manager.is_healthy():
                    self.logger.warning("Audio system unhealthy - attempting recovery")
                    await self.audio_manager.recover()

                await asyncio.sleep(30)  # Audio check every 30 seconds

            except Exception as e:
                self.logger.error(f"Audio monitoring error: {e}")
                await asyncio.sleep(60)

    async def _schedule_monitoring_loop(self) -> None:
        """Schedule monitoring and automatic content switching."""
        while self.running:
            try:
                if self.scheduler and self.scheduler.check_schedule_change():
                    # Schedule changed - switch content folder and transition
                    new_folder = self.scheduler.get_current_content_folder()
                    new_offset = self.scheduler.get_current_transition_offset()
                    new_transition = self.scheduler.get_current_transition_type()

                    self.logger.info(f"Schedule change detected:")
                    self.logger.info(f"  New schedule: {self.scheduler.current_schedule.name}")
                    self.logger.info(f"  Content folder: {new_folder}")
                    self.logger.info(f"  Transition: {new_transition}")
                    self.logger.info(f"  Transition offset: {new_offset}s")

                    # Set new transition in OBS
                    await self.obs_manager.set_transition(new_transition)

                    # Switch content folder
                    await self.content_manager.switch_content_folder(new_folder, new_offset)

                    # Apply audio volume for new schedule
                    new_volume = self.scheduler.get_current_audio_volume()
                    self.audio_manager.set_volume(new_volume)
                    self.logger.info(f"  Audio volume: {new_volume}%")

                    # Resync background audio
                    await self.audio_manager.scan_and_start_audio()

                    self.logger.info("Schedule switch completed successfully")

                # Check every SCHEDULE_CHECK_INTERVAL seconds
                await asyncio.sleep(self.settings.SCHEDULE_CHECK_INTERVAL)

            except Exception as e:
                self.logger.error(f"Schedule monitoring error: {e}")
                await asyncio.sleep(60)  # Longer delay on error

    async def shutdown(self) -> None:
        """Graceful system shutdown."""
        self.logger.info("Starting graceful shutdown...")
        self.notifier.notify_shutdown()

        try:
            # Stop file monitoring
            if self.file_monitor:
                self.file_monitor.stop()
            
            # Stop audio system
            if self.audio_manager:
                await self.audio_manager.shutdown()
            
            # Disconnect from OBS
            if self.obs_manager:
                await self.obs_manager.shutdown()
            
            self.logger.info("Shutdown completed successfully")
            
        except Exception as e:
            self.logger.error(f"Error during shutdown: {e}")
    
    async def run(self) -> int:
        """Run the complete system."""
        try:
            self.logger.info("Starting OBS Digital Signage Automation System")
            
            # Initialize all components
            if not await self.initialize_components():
                self.logger.critical("System initialization failed")
                return 1
            
            # Run main automation loop
            await self.run_main_loop()
            
            return 0
            
        except Exception as e:
            self.logger.critical(f"Critical system error: {e}")
            return 1
            
        finally:
            await self.shutdown()


def run_preflight_check() -> int:
    """Run pre-flight validation checks and print pass/fail summary."""
    from config.settings import Settings
    import shutil

    results = []

    # 1. Config loads
    print("Running pre-flight checks...\n")
    try:
        settings = Settings()
        results.append(("Config loads", True, ""))
    except Exception as e:
        results.append(("Config loads", False, str(e)))
        print(_format_results(results))
        return 1

    # 2. Config validates
    errors = settings.validate()
    if errors:
        results.append(("Config validates", False, "; ".join(errors)))
    else:
        results.append(("Config validates", True, ""))

    # 3. FFprobe available
    ffprobe = shutil.which("ffprobe")
    if ffprobe:
        results.append(("FFprobe found", True, ffprobe))
    else:
        results.append(("FFprobe found", False, "Install FFmpeg for video duration detection"))

    # 4. Content directory exists
    if settings.CONTENT_DIR.exists():
        results.append(("Content directory", True, str(settings.CONTENT_DIR)))
    else:
        results.append(("Content directory", False, f"{settings.CONTENT_DIR} does not exist"))

    # 5. OBS WebSocket connection
    try:
        import obsws_python as obs
        client = obs.ReqClient(
            host=settings.OBS_HOST,
            port=settings.OBS_PORT,
            password=settings.OBS_PASSWORD,
            timeout=5,
        )
        version = client.get_version()
        client.base_client.ws.close()
        results.append(("OBS WebSocket", True, f"OBS {version.obs_version}"))
    except Exception as e:
        results.append(("OBS WebSocket", False, str(e)))

    # 6. WebDAV connection (optional)
    if settings.WEBDAV_HOST:
        try:
            from core.webdav_client import WebDAVClient
            wdav = WebDAVClient(settings)
            # test_connection is async, run it synchronously
            connected = asyncio.get_event_loop().run_until_complete(wdav.test_connection())
            if connected:
                results.append(("WebDAV connection", True, settings.WEBDAV_HOST))
            else:
                results.append(("WebDAV connection", False, "Connection test returned false"))
        except Exception as e:
            results.append(("WebDAV connection", False, str(e)))
    else:
        results.append(("WebDAV connection", None, "Not configured (offline mode)"))

    print(_format_results(results))

    # Exit 0 if all critical checks pass (skip optional ones marked None)
    critical_passed = all(ok for _, ok, _ in results if ok is not None)
    return 0 if critical_passed else 1


def _format_results(results: list) -> str:
    """Format check results as a readable summary."""
    lines = []
    for name, ok, detail in results:
        if ok is True:
            status = "PASS"
        elif ok is False:
            status = "FAIL"
        else:
            status = "SKIP"
        suffix = f"  ({detail})" if detail else ""
        lines.append(f"  [{status}] {name}{suffix}")

    passed = sum(1 for _, ok, _ in results if ok is True)
    failed = sum(1 for _, ok, _ in results if ok is False)
    skipped = sum(1 for _, ok, _ in results if ok is None)

    lines.append("")
    lines.append(f"  {passed} passed, {failed} failed, {skipped} skipped")
    if failed == 0:
        lines.append("  All critical checks passed!")
    else:
        lines.append("  Fix the failures above before starting the system.")
    return "\n".join(lines)


async def main() -> None:
    """Application entry point."""
    system = DigitalSignageSystem()

    try:
        exit_code = await system.run()
        sys.exit(exit_code)

    except KeyboardInterrupt:
        print("\nShutdown requested by user")
        await system.shutdown()
        sys.exit(0)

    except Exception as e:
        print(f"Critical error: {e}")
        sys.exit(1)


def needs_setup() -> bool:
    """Check if first-run setup is needed (no .env config file exists)."""
    from config.settings import get_env_file_path
    return not get_env_file_path().exists()


if __name__ == "__main__":
    # Handle --check flag before starting the full system
    if "--check" in sys.argv:
        sys.exit(run_preflight_check())

    # First-run setup wizard
    if needs_setup():
        try:
            from web.setup_app import run_setup_wizard
        except ImportError as e:
            print(f"\n  Cannot start setup wizard: {e}")
            print("  Run 'pip install -r requirements.txt' first, then try again.")
            sys.exit(1)
        print("\n  No configuration file found. Starting first-run setup wizard...")
        run_setup_wizard()
        print("  Setup complete! Starting system...\n")

    # Set event loop policy for Windows
    if platform.system() == "Windows":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    asyncio.run(main())