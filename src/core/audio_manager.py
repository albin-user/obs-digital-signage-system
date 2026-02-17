"""
Background audio management system.
Handles continuous background music playback.
"""

import asyncio
import logging
from pathlib import Path
from typing import Optional
import threading
import time

import pygame

from config.settings import Settings


class AudioManager:
    """Manages background audio playback."""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.logger = logging.getLogger(__name__)
        
        # Audio state
        self.current_audio_file: Optional[Path] = None
        self.audio_thread: Optional[threading.Thread] = None
        self.audio_running = False
        self.pygame_initialized = False
        self._intentional_stop = False  # True when audio was stopped deliberately (e.g. schedule switch)
        self._audio_lock = asyncio.Lock()
        self._volume_lock = threading.Lock()
        
    async def initialize(self) -> None:
        """Initialize audio system."""
        try:
            self.logger.info("Initializing audio system...")
            
            # Initialize pygame mixer
            await self._initialize_pygame()
            
            self.logger.info("Audio system initialized")
            
        except Exception as e:
            self.logger.error(f"Audio system initialization failed: {e}")
            raise
    
    async def _initialize_pygame(self) -> None:
        """Initialize pygame mixer for audio playback."""
        try:
            # Pygame init is fast (<100ms), no need for async executor
            pygame.mixer.pre_init(
                frequency=self.settings.AUDIO_SAMPLE_RATE,
                size=-16,
                channels=self.settings.AUDIO_CHANNELS,
                buffer=self.settings.AUDIO_BUFFER_SIZE
            )
            pygame.mixer.init()
            self.pygame_initialized = True
            self.logger.debug("Pygame mixer initialized")

        except Exception as e:
            self.logger.error(f"Pygame initialization error: {e}")
            raise
    
    async def scan_and_start_audio(self) -> None:
        """Scan for audio files and start background music."""
        try:
            # Find audio file in content directory
            audio_file = await self._find_audio_file()
            
            if audio_file:
                if audio_file != self.current_audio_file:
                    # Audio file changed, restart playback
                    await self._stop_audio()
                    self.current_audio_file = audio_file
                    await self._start_audio()
                elif not self.audio_running:
                    # Audio file is the same but not playing
                    await self._start_audio()
            else:
                # No audio file found, stop playback
                await self._stop_audio()
                self.current_audio_file = None
                
        except Exception as e:
            self.logger.error(f"Audio scan and start error: {e}")
    
    async def _find_audio_file(self) -> Optional[Path]:
        """Find the first audio file in content directory."""
        try:
            for file_path in self.settings.CONTENT_DIR.iterdir():
                if file_path.is_file():
                    file_ext = file_path.suffix.lower()
                    if file_ext in self.settings.SUPPORTED_AUDIO_FORMATS:
                        self.logger.debug(f"Found audio file: {file_path.name}")
                        return file_path
            
            self.logger.debug("No audio files found in content directory")
            return None
            
        except Exception as e:
            self.logger.error(f"Error finding audio file: {e}")
            return None
    
    async def _start_audio(self) -> None:
        """Start background audio playback."""
        async with self._audio_lock:
            await self._start_audio_inner()

    async def _start_audio_inner(self) -> None:
        """Start background audio playback (inner, lock already held)."""
        try:
            if not self.pygame_initialized or not self.current_audio_file:
                return

            self._intentional_stop = False

            if self.audio_running:
                await self._stop_audio_inner()
            
            def audio_playback():
                try:
                    self.logger.info(f"Starting background audio: {self.current_audio_file.name}")
                    
                    # Load and play audio file
                    pygame.mixer.music.load(str(self.current_audio_file))
                    pygame.mixer.music.play(-1)  # Loop indefinitely
                    
                    self.audio_running = True
                    
                    # Keep thread alive while music is playing
                    while self.audio_running and pygame.mixer.music.get_busy():
                        time.sleep(0.1)
                        
                except Exception as e:
                    self.logger.error(f"Audio playback error: {e}")
                finally:
                    self.audio_running = False
            
            # Start audio in background thread
            self.audio_thread = threading.Thread(target=audio_playback, daemon=True)
            self.audio_thread.start()
            
            # Wait a moment for playback to start
            await asyncio.sleep(0.5)
            
        except Exception as e:
            self.logger.error(f"Failed to start audio: {e}")
    
    async def _stop_audio(self) -> None:
        """Stop background audio playback."""
        async with self._audio_lock:
            await self._stop_audio_inner()

    async def _stop_audio_inner(self) -> None:
        """Stop background audio playback (inner, lock already held)."""
        try:
            if self.audio_running:
                self._intentional_stop = True
                self.audio_running = False
                
                def stop_pygame():
                    pygame.mixer.music.stop()
                
                await asyncio.get_event_loop().run_in_executor(None, stop_pygame)
                
                # Wait for thread to finish
                if self.audio_thread and self.audio_thread.is_alive():
                    self.audio_thread.join(timeout=2.0)
                
                self.logger.debug("Background audio stopped")
                
        except Exception as e:
            self.logger.error(f"Error stopping audio: {e}")
    
    def set_volume(self, volume_percent: int) -> None:
        """Set background music volume.

        Args:
            volume_percent: Volume level 0-100
        """
        try:
            if not self.pygame_initialized:
                return
            clamped = max(0, min(100, volume_percent))
            with self._volume_lock:
                pygame.mixer.music.set_volume(clamped / 100.0)
            self.logger.debug(f"Audio volume set to {clamped}%")
        except Exception as e:
            self.logger.error(f"Failed to set volume: {e}")

    def is_healthy(self) -> bool:
        """Check if audio system is healthy."""
        try:
            if not self.pygame_initialized:
                return False

            # If audio was intentionally stopped (e.g. schedule switch), that's healthy
            if self._intentional_stop:
                return True

            # If we have an audio file, check if it's playing
            if self.current_audio_file and not self.audio_running:
                return False

            return True

        except Exception:
            return False
    
    async def recover(self) -> bool:
        """Attempt to recover audio system."""
        try:
            self.logger.info("Attempting audio system recovery...")

            # Stop current playback
            await self._stop_audio()

            # Reinitialize pygame
            await self._initialize_pygame()

            # Check if current audio file still exists; if not, rescan
            if self.current_audio_file and not self.current_audio_file.exists():
                self.logger.warning(f"Audio file no longer exists: {self.current_audio_file.name}, rescanning")
                self.current_audio_file = None
                await self.scan_and_start_audio()
            elif self.current_audio_file:
                await self._start_audio()

            self.logger.info("Audio system recovery completed")
            return True

        except Exception as e:
            self.logger.error(f"Audio system recovery failed: {e}")
            return False
    
    async def shutdown(self) -> None:
        """Shutdown audio system."""
        try:
            self.logger.info("Shutting down audio system...")
            
            # Stop audio playback
            await self._stop_audio()
            
            # Quit pygame mixer
            if self.pygame_initialized:
                def quit_pygame():
                    pygame.mixer.quit()
                
                await asyncio.get_event_loop().run_in_executor(None, quit_pygame)
                self.pygame_initialized = False
            
            self.logger.info("Audio system shutdown completed")
            
        except Exception as e:
            self.logger.error(f"Error during audio shutdown: {e}")