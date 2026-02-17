"""
Local file monitoring system.
Watches for changes in the content directory.
"""

import logging
from pathlib import Path
from typing import Callable, Optional
import threading
import time

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent


class ContentFileHandler(FileSystemEventHandler):
    """Handles file system events for content directory."""
    
    def __init__(self, callback: Callable[[Path], None], supported_extensions: set):
        self.callback = callback
        self.supported_extensions = supported_extensions
        self.logger = logging.getLogger(__name__)
        
    def on_any_event(self, event: FileSystemEvent):
        """Handle any file system event."""
        if event.is_directory:
            return
            
        file_path = Path(event.src_path)
        
        # Only process supported file types
        if file_path.suffix.lower() in self.supported_extensions:
            self.logger.debug(f"File event: {event.event_type} - {file_path.name}")
            
            # Call the callback function safely
            try:
                # Since callback might be async, we'll schedule it
                import asyncio
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        loop.call_soon_threadsafe(lambda: asyncio.create_task(self.callback(file_path)))
                    else:
                        asyncio.run(self.callback(file_path))
                except RuntimeError:
                    # No event loop or event loop not running - call synchronously  
                    if asyncio.iscoroutinefunction(self.callback):
                        self.logger.warning("Async callback called without event loop - skipping")
                    else:
                        self.callback(file_path)
            except Exception as e:
                self.logger.error(f"Error in file change callback: {e}")


class FileMonitor:
    """Monitors local file changes in content directory."""
    
    def __init__(self, content_dir: Path, callback: Callable[[Path], None]):
        self.content_dir = content_dir
        self.callback = callback
        self.logger = logging.getLogger(__name__)
        
        # Supported file extensions
        self.supported_extensions = {
            '.mp4', '.mov', '.avi', '.mkv', '.wmv', '.webm', '.m4v',  # Video
            '.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff', '.webp',  # Image
            '.mp3', '.wav', '.ogg', '.flac', '.m4a'  # Audio
        }
        
        # File system watcher components
        self.observer: Optional[Observer] = None
        self.handler: Optional[ContentFileHandler] = None
        self.running = False
        
    def start(self) -> None:
        """Start file monitoring."""
        try:
            if self.running:
                self.logger.warning("File monitor already running")
                return

            self.logger.info(f"Starting file monitor for: {self.content_dir}")

            # Ensure directory exists
            self.content_dir.mkdir(parents=True, exist_ok=True)

            # Create event handler
            self.handler = ContentFileHandler(self.callback, self.supported_extensions)

            # Create and start observer
            self.observer = Observer()
            self.observer.schedule(
                self.handler,
                str(self.content_dir),
                recursive=False
            )

            self.observer.start()
            self.running = True

            self.logger.info("File monitor started successfully")

        except TypeError as e:
            # Python 3.13 compatibility issue with watchdog threading
            if "'handle' must be a _ThreadHandle" in str(e):
                self.logger.warning(f"File monitor not available (Python 3.13 compatibility issue): {e}")
                self.logger.info("System will work without file monitoring - content will be reloaded on restart")
            else:
                self.logger.error(f"Failed to start file monitor: {e}")
            self.observer = None
        except Exception as e:
            self.logger.error(f"Failed to start file monitor: {e}")
            self.observer = None
    
    def stop(self) -> None:
        """Stop file monitoring."""
        try:
            if not self.running:
                return
                
            self.logger.info("Stopping file monitor...")
            
            if self.observer:
                self.observer.stop()
                self.observer.join(timeout=5.0)
                
            self.running = False
            self.observer = None
            self.handler = None
            
            self.logger.info("File monitor stopped")
            
        except Exception as e:
            self.logger.error(f"Error stopping file monitor: {e}")
    
    def is_running(self) -> bool:
        """Check if file monitor is running."""
        return self.running and self.observer and self.observer.is_alive()