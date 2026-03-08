"""
Content and scene management system.
Handles dynamic scene creation, media file processing, and content rotation.
"""

import asyncio
import logging
import re
import time
from pathlib import Path
from typing import List, Dict, Optional, Set

from config.settings import Settings
from core.obs_manager import OBSManager

# Pattern for characters unsafe in OBS scene/source names
_UNSAFE_NAME_RE = re.compile(r'[^a-zA-Z0-9_ .\-()]')


class MediaFile:
    """Represents a media file with metadata."""

    def __init__(self, file_path: Path, settings: Settings):
        self.file_path = file_path
        self.filename = file_path.name
        self.file_ext = file_path.suffix.lower()
        self.is_video = self._is_video_file(settings)
        self.is_image = self._is_image_file(settings)
        self.duration = 0.0  # Will be set later

        # Lightweight file metadata for change detection (instead of expensive MD5)
        try:
            stat = file_path.stat()
            self.file_size = stat.st_size
            self.file_mtime = stat.st_mtime
        except Exception:
            self.file_size = 0
            self.file_mtime = 0

    def _is_video_file(self, settings: Settings) -> bool:
        return self.file_ext in settings.SUPPORTED_VIDEO_FORMATS

    def _is_image_file(self, settings: Settings) -> bool:
        return self.file_ext in settings.SUPPORTED_IMAGE_FORMATS

    @staticmethod
    def _sanitize_obs_name(name: str) -> str:
        """Replace characters that may cause OBS API errors."""
        return _UNSAFE_NAME_RE.sub('_', name)

    def get_scene_name(self) -> str:
        """Get OBS scene name for this media file."""
        return self._sanitize_obs_name(f"{self.filename}_scene")

    def get_source_name(self) -> str:
        """Get OBS source/input name for this media file."""
        return self._sanitize_obs_name(f"{self.filename}_source")
    
    def __str__(self) -> str:
        return f"MediaFile({self.filename}, video={self.is_video}, image={self.is_image})"


class ContentManager:
    """Manages content scanning, scene creation, and rotation."""
    
    def __init__(self, settings: Settings, obs_manager: OBSManager):
        self.settings = settings
        self.obs_manager = obs_manager
        self.logger = logging.getLogger(__name__)

        # Content state (protected by _rotation_lock)
        self.media_files: List[MediaFile] = []
        self.current_index = 0
        self.playback_start_time = 0.0
        self.current_scene: Optional[str] = None
        self.rotation_active = False
        self._rotation_lock = asyncio.Lock()

        # Tracking for cleanup
        self.managed_scenes: Set[str] = set()
        self.managed_inputs: Set[str] = set()

        # Content change detection
        self.content_hash = ""

        # Dynamic content folder and transition offset (for scheduling)
        self.content_folder = settings.CONTENT_DIR
        self.transition_offset = settings.TRANSITION_START_OFFSET
        
    async def initialize(self) -> None:
        """Initialize content manager."""
        try:
            self.logger.info("Initializing Content Manager...")

            # Verify FFprobe is available (required for video duration detection)
            self._check_ffprobe()

            # Clean up leftover .tmp files from interrupted downloads
            self._cleanup_tmp_files()

            # Ensure content directory exists
            self.settings.CONTENT_DIR.mkdir(parents=True, exist_ok=True)

            # Create waiting scene if no content
            await self._create_waiting_scene()

            self.logger.info("Content Manager initialized")
            
        except Exception as e:
            self.logger.error(f"Content Manager initialization failed: {e}")
            raise
    
    async def scan_and_update_content(self) -> None:
        """Scan content directory and update OBS scenes."""
        try:
            self.logger.info("Scanning content directory...")

            # Get current content
            new_media_files = await self._scan_content_directory()

            # On first scan, if no content found, wait and try again
            is_first_scan = not self.managed_scenes and not self.managed_inputs
            if is_first_scan and not new_media_files:
                self.logger.info("First scan found no content - waiting 5 seconds for content folder to mount...")
                await asyncio.sleep(5)
                self.logger.info("Rescanning content directory...")
                new_media_files = await self._scan_content_directory()
                if new_media_files:
                    self.logger.info(f"Found {len(new_media_files)} media files after delay")

            # Check if content has changed
            new_content_hash = self._calculate_content_hash(new_media_files)
            if new_content_hash == self.content_hash and self.media_files:
                self.logger.debug("No content changes detected")
                return

            # Content has changed
            self.content_hash = new_content_hash

            if not new_media_files:
                # No content — clean up everything and show waiting scene
                await self._cleanup_all_digital_signage_content()
                async with self._rotation_lock:
                    self.media_files = []
                    self.rotation_active = False
                self.logger.warning("No valid media files found")
                await self._create_waiting_scene()
                await self._activate_waiting_scene()
                return

            # Sort files alphabetically
            new_media_files.sort(key=lambda x: x.filename.lower())

            # Calculate durations BEFORE creating OBS scenes
            await self._calculate_media_durations(new_media_files)

            # Determine if this is first load or incremental update
            is_first_load = not self.media_files

            if is_first_load:
                # First load or after folder switch — full rebuild with sync scene
                await self._full_rebuild(new_media_files)
            else:
                # Incremental update — seamless, no visual disruption
                old_names = {mf.filename for mf in self.media_files}
                new_names = {mf.filename for mf in new_media_files}
                added = new_names - old_names
                removed = old_names - new_names
                await self._incremental_update(new_media_files, added, removed)

        except Exception as e:
            self.logger.error(f"Content scan and update failed: {e}")

    async def _full_rebuild(self, new_media_files: list) -> None:
        """Full scene teardown and rebuild. Shows 'Sync in Progress' briefly."""
        sync_scene = "Sync in Progress"
        sync_scene_created = await self.obs_manager.create_scene(sync_scene)
        if not sync_scene_created:
            self.logger.warning(f"Could not create '{sync_scene}' — proceeding without it")
        else:
            await self.obs_manager.set_current_scene(sync_scene)
            self.logger.info(f"Created and switched to '{sync_scene}'")

        try:
            await self._cleanup_all_digital_signage_content(exclude_scenes={sync_scene})

            async with self._rotation_lock:
                self.media_files = new_media_files

            await self._create_scenes_for_media()
            await self._create_waiting_scene()  # Always maintain placeholder
            await self._cleanup_orphaned_scenes(exclude_scenes={sync_scene})

            async with self._rotation_lock:
                self.current_index = 0
                self.rotation_active = True
                self.playback_start_time = time.time()

            if new_media_files:
                await self._switch_to_media(0)

            self.logger.info(f"Content rebuilt: {len(self.media_files)} media files")

        finally:
            if sync_scene_created:
                await self.obs_manager.remove_scene(sync_scene)

    async def _incremental_update(self, new_media_files: list, added: set, removed: set) -> None:
        """Add/remove scenes incrementally without disrupting playback."""
        # Phase 1: Create scenes for NEW files (while old content keeps playing)
        new_file_map = {mf.filename: mf for mf in new_media_files}
        for filename in added:
            media_file = new_file_map[filename]
            try:
                if await self._create_scene_for_media(media_file):
                    self.logger.info(f"Added new scene: {filename}")
                else:
                    self.logger.error(f"Failed to create scene for {filename}")
            except Exception as e:
                self.logger.error(f"Failed to add scene for {filename}: {e}")

        # Phase 2: Update media_files list and rotation state
        need_switch = False
        async with self._rotation_lock:
            currently_playing = None
            if self.media_files and 0 <= self.current_index < len(self.media_files):
                currently_playing = self.media_files[self.current_index].filename
            self.media_files = new_media_files
            # Preserve current playback position if the currently-playing file still exists
            if currently_playing:
                if currently_playing in removed:
                    # Currently-playing file was removed — reset to start
                    self.current_index = 0
                    self.playback_start_time = time.time()
                    need_switch = True
                else:
                    for i, mf in enumerate(self.media_files):
                        if mf.filename == currently_playing:
                            self.current_index = i
                            break
                    else:
                        # File not found (shouldn't happen) — reset
                        self.current_index = 0
                        self.playback_start_time = time.time()
                        need_switch = True
            if not self.rotation_active and self.media_files:
                self.rotation_active = True
                self.playback_start_time = time.time()
                need_switch = True

        # Switch if needed (updates self.current_scene)
        if need_switch and self.media_files:
            await self._switch_to_media(0)

        # Phase 3: Remove scenes for DELETED files (safe now — we've switched away)
        # Guard with managed set membership — on_file_deleted() may have already cleaned up
        for filename in removed:
            scene_name = MediaFile._sanitize_obs_name(f"{filename}_scene")
            source_name = MediaFile._sanitize_obs_name(f"{filename}_source")
            if source_name in self.managed_inputs:
                await self.obs_manager.remove_input(source_name)
                self.managed_inputs.discard(source_name)
            if scene_name in self.managed_scenes:
                await self.obs_manager.remove_scene(scene_name)
                self.managed_scenes.discard(scene_name)
            self.logger.info(f"Removed scene: {filename}")

        # Ensure waiting scene exists as safety net
        await self._create_waiting_scene()

        self.logger.info(
            f"Content updated seamlessly: +{len(added)} -{len(removed)} "
            f"= {len(self.media_files)} total"
        )
    
    def _check_ffprobe(self) -> None:
        """Check that FFprobe is installed and accessible."""
        import subprocess
        try:
            subprocess.run(
                ["ffprobe", "-version"],
                capture_output=True, timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
            )
            self.logger.debug("FFprobe is available")
        except FileNotFoundError:
            self.logger.warning(
                "FFprobe not found! Video duration detection will use fallback values. "
                "Install FFmpeg: sudo apt install ffmpeg (Linux) / choco install ffmpeg (Windows)"
            )

    def _cleanup_tmp_files(self) -> None:
        """Delete leftover .tmp files from interrupted downloads."""
        try:
            count = 0
            for tmp_file in self.content_folder.rglob("*.tmp"):
                try:
                    tmp_file.unlink()
                    count += 1
                except Exception:
                    pass
            if count > 0:
                self.logger.info(f"Cleaned up {count} leftover .tmp file(s)")
        except Exception as e:
            self.logger.warning(f"Error cleaning .tmp files: {e}")

    async def _scan_content_directory(self) -> List[MediaFile]:
        """Scan directory for supported media files."""
        media_files = []

        try:
            for file_path in self.content_folder.iterdir():
                if file_path.is_file():
                    media_file = MediaFile(file_path, self.settings)

                    # Only include video and image files (audio handled separately)
                    if media_file.is_video or media_file.is_image:
                        # Validate file is not corrupted
                        if await self._validate_media_file(media_file):
                            media_files.append(media_file)
                        else:
                            self.logger.warning(f"Skipping corrupted file: {file_path.name}")
                    elif file_path.suffix.lower() not in self.settings.SUPPORTED_AUDIO_FORMATS:
                        self.logger.warning(f"Skipping unsupported format: {file_path.name} ({file_path.suffix})")

        except Exception as e:
            self.logger.error(f"Error scanning content directory: {e}")

        return media_files
    
    async def _validate_media_file(self, media_file: MediaFile) -> bool:
        """Validate media file is not corrupted."""
        try:
            # Basic file size check
            if media_file.file_path.stat().st_size == 0:
                return False
            
            # For images and videos, basic validation
            return True
                
        except Exception as e:
            self.logger.warning(f"File validation error for {media_file.filename}: {e}")
            return False
    
    def _calculate_content_hash(self, media_files: List[MediaFile]) -> str:
        """Calculate hash of content for change detection using lightweight metadata."""
        content_data = []
        for media_file in media_files:
            # Use filename, size, and modification time (much faster than MD5)
            content_data.append(f"{media_file.filename}:{media_file.file_size}:{media_file.file_mtime}")

        return "|".join(sorted(content_data))
    
    async def _cleanup_old_content(self) -> None:
        """Clean up old scenes and inputs."""
        try:
            # Remove old managed scenes
            for scene_name in self.managed_scenes.copy():
                await self.obs_manager.remove_scene(scene_name)
                self.managed_scenes.discard(scene_name)
            
            # Remove old managed inputs
            for input_name in self.managed_inputs.copy():
                await self.obs_manager.remove_input(input_name)
                self.managed_inputs.discard(input_name)
                
        except Exception as e:
            self.logger.error(f"Cleanup error: {e}")
    
    async def _cleanup_all_digital_signage_content(self, exclude_scenes: Set[str] = None) -> None:
        """Clean up ALL existing digital signage scenes and inputs."""
        try:
            self.logger.info("Cleaning up existing digital signage content...")
            
            if exclude_scenes is None:
                exclude_scenes = set()

            # Check how many scenes exist and will be removed (OBS minimum 1 scene constraint)
            all_scenes = await self.obs_manager.get_scene_list()
            total_scene_count = len(all_scenes) if all_scenes else 0

            # Count scenes that match our pattern (will be removed)
            scenes_to_remove_count = 0
            for scene_name in all_scenes:
                if scene_name in exclude_scenes:
                    continue
                    
                if (scene_name.endswith('_scene') or
                    scene_name == 'waiting_for_content_scene' or
                    'slideshow' in scene_name.lower() or
                    'digital_signage' in scene_name.lower()):
                    scenes_to_remove_count += 1

            scenes_remaining = total_scene_count - scenes_to_remove_count

            # If we're about to leave only 1 scene or 0 scenes, don't remove sources
            # OBS won't let us delete the last scene, so we should keep its sources too
            # BUT if we have exclude_scenes (like Sync in Progress), we are safe
            skip_input_removal = scenes_remaining <= 1 and total_scene_count > 0 and not exclude_scenes

            if skip_input_removal:
                self.logger.info(f"Only {scenes_remaining} scene(s) would remain after cleanup - keeping sources (OBS requires minimum 1 scene)")

            # First, get all inputs and remove matching ones (unless skipping)
            all_inputs = await self.obs_manager.get_input_list()
            inputs_removed = 0

            # Only remove inputs if we're not keeping the last scene's sources
            if not skip_input_removal:
                for input_name in all_inputs:
                    # Remove inputs that match our naming pattern
                    if input_name.endswith('_source'):
                        try:
                            await self.obs_manager.remove_input(input_name)
                            inputs_removed += 1
                            self.logger.debug(f"Removed old input: {input_name}")
                        except Exception as e:
                            self.logger.warning(f"Could not remove input {input_name}: {e}")

                if inputs_removed > 0:
                    self.logger.info(f"Removed {inputs_removed} old inputs")
            else:
                self.logger.debug("Skipping input removal to preserve last scene's sources")

            # Then, get all existing scenes and remove matching ones
            all_scenes = await self.obs_manager.get_scene_list()

            scenes_removed = 0
            for scene_name in all_scenes:
                if scene_name in exclude_scenes:
                    continue

                # Remove scenes that match our naming pattern or are from previous runs
                if (scene_name.endswith('_scene') or
                    scene_name == 'waiting_for_content_scene' or
                    'slideshow' in scene_name.lower() or
                    'digital_signage' in scene_name.lower()):

                    try:
                        await self.obs_manager.remove_scene(scene_name)
                        scenes_removed += 1
                        self.logger.debug(f"Removed old scene: {scene_name}")
                    except Exception as e:
                        self.logger.warning(f"Could not remove scene {scene_name}: {e}")

            self.logger.info(f"Removed {scenes_removed} old scenes")

        except Exception as e:
            self.logger.error(f"Full cleanup error: {e}")
    
    async def _cleanup_orphaned_scenes(self, exclude_scenes: Set[str] = None) -> None:
        """
        Clean up orphaned scenes that don't match our managed content.

        This removes scenes like 'J' or any other user-created scenes that aren't
        part of our digital signage system. Ensures OBS only has our managed scenes.
        """
        try:
            if exclude_scenes is None:
                exclude_scenes = set()

            # Get all scenes currently in OBS
            all_scenes = await self.obs_manager.get_scene_list()

            # Get list of scenes we should keep
            valid_scenes = set(self.managed_scenes)
            valid_scenes.add('waiting_for_content_scene')  # Always keep waiting scene
            valid_scenes.update(exclude_scenes)

            orphaned_removed = 0
            for scene_name in all_scenes:
                # If scene is not in our managed list, remove it
                if scene_name not in valid_scenes:
                    try:
                        await self.obs_manager.remove_scene(scene_name)
                        orphaned_removed += 1
                        self.logger.info(f"Removed orphaned scene: {scene_name}")
                    except Exception as e:
                        self.logger.warning(f"Could not remove orphaned scene {scene_name}: {e}")

            if orphaned_removed > 0:
                self.logger.info(f"Cleaned up {orphaned_removed} orphaned scene(s)")

        except Exception as e:
            self.logger.error(f"Orphaned scene cleanup error: {e}")
    
    async def _create_scenes_for_media(self) -> None:
        """Create OBS scenes for all media files."""
        # Clear tracking sets before rebuilding — prevents unbounded growth
        # and ensures on_file_deleted() only matches current content
        self.managed_scenes.clear()
        self.managed_inputs.clear()

        success_count = 0
        for media_file in self.media_files:
            try:
                if await self._create_scene_for_media(media_file):
                    success_count += 1
            except Exception as e:
                self.logger.error(f"Failed to create scene for {media_file.filename}: {e}")

        self.logger.info(f"Created {success_count}/{len(self.media_files)} scenes successfully")
    
    def _get_input_config(self, media_file: MediaFile) -> tuple[Optional[str], Optional[Dict]]:
        """
        Get input kind and settings for a media file.
        
        Returns:
            Tuple of (input_kind, input_settings) or (None, None) if unsupported
        """
        if media_file.is_image:
            input_kind = "image_source"
            input_settings = {
                "file": str(media_file.file_path),
                "unload": False
            }
            return input_kind, input_settings
            
        elif media_file.is_video:
            input_kind = "ffmpeg_source"
            input_settings = {
                "local_file": str(media_file.file_path),
                "looping": False,
                "restart_on_activate": True,
                "clear_on_media_end": False,
                "close_when_inactive": True,   # Allow unloading to save memory
                "hw_decode": True              # Enable HW decode for smooth playback during transitions
            }
            return input_kind, input_settings
            
        else:
            self.logger.error(f"Unsupported media type: {media_file.filename}")
            return None, None

    async def _create_scene_for_media(self, media_file: MediaFile) -> bool:
        """Create OBS scene and source for a media file. Returns True on success."""
        try:
            scene_name = media_file.get_scene_name()
            source_name = media_file.get_source_name()

            # Create scene — check return value
            if not await self.obs_manager.create_scene(scene_name):
                self.logger.error(f"Failed to create OBS scene for {media_file.filename}")
                return False
            self.managed_scenes.add(scene_name)

            # Determine source type and settings
            input_kind, input_settings = self._get_input_config(media_file)

            if not input_kind:
                self.logger.warning(f"Skipping {media_file.filename}: unsupported media type")
                return False

            # Create input and add to scene
            success = await self.obs_manager.create_input(
                scene_name=scene_name,
                input_name=source_name,
                input_kind=input_kind,
                input_settings=input_settings
            )

            # If creation failed (source already exists), try adding existing source to scene
            if not success:
                self.logger.info(f"Source '{source_name}' already exists - checking if it's in scene '{scene_name}'")

                # Check if source is ALREADY in the scene to avoid duplicates
                existing_items = await self.obs_manager.get_scene_items(scene_name)

                if existing_items is None:
                    self.logger.warning(f"Could not check duplicates for {scene_name} (request failed)")
                    existing_items = []

                source_already_in_scene = False

                for item in existing_items:
                    # Handle both dict and object access for robustness
                    item_source_name = item.get('sourceName') if isinstance(item, dict) else getattr(item, 'source_name', None)
                    if item_source_name == source_name:
                        source_already_in_scene = True
                        break

                if source_already_in_scene:
                    self.logger.info(f"Source {source_name} already in scene {scene_name} - skipping addition")
                else:
                    scene_item_id = await self.obs_manager.add_source_to_scene(scene_name, source_name)
                    if not scene_item_id:
                        self.logger.error(f"Failed to recover source {source_name} for scene {scene_name}")
                        return False

            self.managed_inputs.add(source_name)

            # Mute video audio if it's a video file
            if media_file.is_video:
                await self.obs_manager.set_input_mute(source_name, True)

            # Configure scene item transform for 1920x1080 canvas
            await self._configure_scene_item_transform(media_file)

            self.logger.debug(f"Created scene and source for: {media_file.filename}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to create scene for {media_file.filename}: {e}")
            return False
    
    async def _configure_scene_item_transform(self, media_file: MediaFile) -> None:
        """Configure scene item to fit 1920x1080 canvas."""
        try:
            scene_name = media_file.get_scene_name()
            source_name = media_file.get_source_name()

            self.logger.debug(f"Configuring transform for {media_file.filename} in scene {scene_name}")

            # Get scene item ID
            scene_item_id = await self.obs_manager.get_scene_item_id(scene_name, source_name)

            if scene_item_id is None:
                self.logger.error(f"Could not get scene item ID for {source_name}")
                return

            self.logger.debug(f"Got scene_item_id={scene_item_id} for {source_name}")

            # Fill canvas completely with centered content (no black bars)
            # OBS_BOUNDS_SCALE_OUTER: scales to fill bounds, overflow hidden by projection
            # alignment=5 (top-left) anchors the bounds box at position (0,0)
            # boundsAlignment=0 (center) centers the content within the bounds
            transform = {
                "positionX": 0,
                "positionY": 0,
                "alignment": 5,
                "boundsType": "OBS_BOUNDS_SCALE_OUTER",
                "boundsWidth": float(self.settings.VIDEO_WIDTH),
                "boundsHeight": float(self.settings.VIDEO_HEIGHT),
                "boundsAlignment": 0
            }

            self.logger.debug(f"Applying transform with bounds {self.settings.VIDEO_WIDTH}x{self.settings.VIDEO_HEIGHT}")
            result = await self.obs_manager.set_scene_item_transform(scene_name, scene_item_id, transform)
            self.logger.debug(f"Transform result: {result}")

        except Exception as e:
            self.logger.error(f"Failed to configure transform for {media_file.filename}: {e}")
    
    async def _calculate_media_durations(self, media_files: Optional[List[MediaFile]] = None) -> None:
        """
        Calculate duration for each media file BEFORE creating OBS scenes.

        ARCHITECTURE IMPROVEMENT:
        - Durations are detected from video files directly using FFprobe
        - This happens BEFORE OBS scene creation (not after)
        - No dependency on OBS state or WebSocket API
        - Durations are stored in MediaFile objects for use during playback
        """
        if media_files is None:
            media_files = self.media_files
        self.logger.info("Detecting media durations using FFprobe...")

        for media_file in media_files:
            try:
                if media_file.is_image:
                    # Images use configured slide duration
                    media_file.duration = self.settings.SLIDE_TRANSITION_SECONDS
                    self.logger.debug(f"Image {media_file.filename}: {media_file.duration}s")

                elif media_file.is_video:
                    # Get video duration using FFprobe (industry-standard method)
                    duration_seconds = await self._get_video_duration_ffprobe(media_file.file_path)

                    if duration_seconds is not None:
                        # Apply maximum video duration limit
                        if duration_seconds > self.settings.MAX_VIDEO_DURATION:
                            self.logger.warning(
                                f"Video {media_file.filename} exceeds maximum duration "
                                f"({duration_seconds:.1f}s), capping at {self.settings.MAX_VIDEO_DURATION}s"
                            )
                            media_file.duration = self.settings.MAX_VIDEO_DURATION
                        else:
                            media_file.duration = duration_seconds

                        self.logger.info(
                            f"Video {media_file.filename}: {media_file.duration:.2f}s"
                        )
                    else:
                        # Fallback duration for videos
                        self.logger.warning(
                            f"Could not get duration for {media_file.filename}, using fallback (10s)"
                        )
                        media_file.duration = 10.0  # 10 second fallback

            except Exception as e:
                self.logger.error(f"Failed to calculate duration for {media_file.filename}: {e}")
                # Set fallback duration
                media_file.duration = 8.0 if media_file.is_image else 10.0

        self.logger.info(
            f"Duration detection complete: {len(media_files)} files processed"
        )

    async def _get_video_duration_ffprobe(self, file_path: Path) -> Optional[float]:
        """
        Get video duration using FFprobe (PROFESSIONAL INDUSTRY-STANDARD SOLUTION).

        WHY FFprobe:
        - OBS WebSocket GetMediaInputStatus returns null for inactive sources
        - FFprobe reads video file container metadata directly
        - Industry-standard method used by professional applications
        - Fast (<100ms), accurate, and reliable
        - No dependency on OBS state

        How it works:
        - Uses FFprobe (part of FFmpeg suite) to read video metadata
        - Reads duration from container format without decoding frames
        - Returns precise duration in seconds

        Args:
            file_path: Path to video file

        Returns:
            Duration in seconds, or None if unable to determine
        """
        try:
            import subprocess
            import json

            # FFprobe command to get duration in JSON format
            cmd = [
                'ffprobe',
                '-v', 'error',  # Only show errors
                '-show_entries', 'format=duration',  # Get duration from format
                '-of', 'json',  # Output as JSON
                str(file_path)
            ]

            # Run FFprobe asynchronously
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=5,
                    creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
                )
            )

            if result.returncode == 0:
                # Parse JSON output
                data = json.loads(result.stdout)
                duration_str = data.get('format', {}).get('duration')

                if duration_str:
                    duration_seconds = float(duration_str)
                    if duration_seconds > 0.5:
                        return duration_seconds
                    self.logger.warning(f"FFprobe returned near-zero duration ({duration_seconds}s) for {file_path.name}")
                    return None
                else:
                    self.logger.warning(f"FFprobe returned no duration for {file_path.name}")
                    return None
            else:
                self.logger.warning(f"FFprobe failed for {file_path.name}: {result.stderr}")
                return None

        except FileNotFoundError:
            self.logger.error(
                "FFprobe not found! Please install FFmpeg:"
            )
            self.logger.error("  Windows: choco install ffmpeg  OR  winget install FFmpeg")
            self.logger.error("  Or download from: https://ffmpeg.org/download.html")
            self.logger.error("  Add FFmpeg/bin to your system PATH")
            return None
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse FFprobe output for {file_path.name}: {e}")
            return None
        except subprocess.TimeoutExpired:
            self.logger.error(f"FFprobe timeout for {file_path.name} (file may be corrupted)")
            return None
        except Exception as e:
            self.logger.error(f"Error getting duration for {file_path.name}: {e}")
            return None

    async def _create_waiting_scene(self) -> None:
        """Create a 'waiting for content' scene."""
        try:
            waiting_scene_name = "waiting_for_content_scene"

            # Check if scene already exists
            existing_scenes = await self.obs_manager.get_scene_list()
            if waiting_scene_name in existing_scenes:
                return

            # Create simple empty scene (text sources are platform-specific and may not be available)
            await self.obs_manager.create_scene(waiting_scene_name)

            self.logger.info("Created waiting scene")

        except Exception as e:
            self.logger.error(f"Failed to create waiting scene: {e}")
    
    async def _activate_waiting_scene(self) -> None:
        """Activate the waiting for content scene."""
        try:
            await self.obs_manager.set_current_scene("waiting_for_content_scene")
            self.current_scene = "waiting_for_content_scene"
            self.rotation_active = False
            
        except Exception as e:
            self.logger.error(f"Failed to activate waiting scene: {e}")
    
    async def process_content_rotation(self) -> None:
        """Process content rotation logic."""
        if not self.rotation_active or not self.media_files:
            return

        try:
            # Snapshot state under lock
            async with self._rotation_lock:
                if not self.rotation_active or not self.media_files:
                    return
                media_files = list(self.media_files)
                current_index = self.current_index
                playback_start = self.playback_start_time
                transition_offset = self.transition_offset

            current_time = time.time()
            elapsed_time = current_time - playback_start

            # Get current media file
            if current_index >= len(media_files):
                current_index = 0

            current_media = media_files[current_index]

            # MANUAL TRANSITION TIMING (configured in settings or scheduler):
            # User controls exactly when transition starts via TRANSITION_START_OFFSET
            # Example: 2.0 = start transition 2 seconds before media ends
            if current_media.is_video:
                # For videos: Start transition BEFORE video ends
                switch_time = current_media.duration - transition_offset
                if switch_time < 0:
                    switch_time = 0
            else:
                # For images: Display for FULL duration, then transition
                switch_time = current_media.duration

            # Debug logging for transition timing (only log near transition)
            if elapsed_time >= switch_time - 0.5:
                self.logger.debug(
                    f"Transition check: elapsed={elapsed_time:.1f}s, switch_time={switch_time:.1f}s, "
                    f"duration={current_media.duration}s, offset={transition_offset:.1f}s, "
                    f"current={current_media.filename}"
                )

            if elapsed_time >= switch_time:
                # Time to switch to next content
                next_index = (current_index + 1) % len(media_files)
                self.logger.info(f"Switching from {current_media.filename} to {media_files[next_index].filename}")
                await self._switch_to_media(next_index)
                async with self._rotation_lock:
                    self.current_index = next_index
                    self.playback_start_time = current_time

        except Exception as e:
            self.logger.error(f"Content rotation error: {e}")
    
    async def _switch_to_media(self, index: int) -> None:
        """Switch to specific media file."""
        try:
            if index >= len(self.media_files):
                return

            media_file = self.media_files[index]
            scene_name = media_file.get_scene_name()

            # Switch to the scene
            await self.obs_manager.set_current_scene(scene_name)
            self.current_scene = scene_name

            self.logger.debug(f"Switched to: {media_file.filename}")

        except Exception as e:
            self.logger.error(f"Failed to switch to media {index}: {e}")

    async def switch_content_folder(self, new_folder: Path, transition_offset: float) -> bool:
        """
        Switch to a different content folder dynamically (for scheduling).

        Args:
            new_folder: Path to new content folder
            transition_offset: New transition offset for timing

        Returns:
            True if successful, False otherwise
        """
        try:
            old_folder = self.content_folder
            old_offset = self.transition_offset
            self.logger.info(f"Switching content folder: {old_folder.name} → {new_folder.name}")

            # Update internal properties (used by _scan_content_directory)
            self.content_folder = new_folder
            self.transition_offset = transition_offset

            # Force full rebuild — different folder means entirely different content
            self.content_hash = None
            async with self._rotation_lock:
                self.media_files = []  # Clear so is_first_load triggers full rebuild

            # Create folder if it doesn't exist
            new_folder.mkdir(parents=True, exist_ok=True)

            # Rescan and update content (will do a full rebuild)
            await self.scan_and_update_content()

            self.logger.info(f"Content folder switched successfully to: {new_folder.name}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to switch content folder: {e}")
            # Revert to old folder on error
            self.content_folder = old_folder
            self.transition_offset = old_offset
            return False

    async def on_content_change(self, file_path: Path) -> None:
        """Handle content change events from file monitor."""
        try:
            self.logger.info(f"Content change detected: {file_path}")

            # Trigger content rescan after a short delay
            await asyncio.sleep(2)  # Allow file operations to complete
            await self.scan_and_update_content()

        except Exception as e:
            self.logger.error(f"Error handling content change: {e}")

    async def on_file_deleted(self, filename: str) -> None:
        """Handle file deletion from WebDAV sync.

        Args:
            filename: May be a relative path (e.g. "subfolder/video.mp4") from WebDAV.
                      We extract the basename to match scene/source naming conventions.
        """
        try:
            # WebDAV passes relative paths like "subfolder/video.mp4" but scenes
            # are keyed by basename (e.g. "video.mp4_scene"). Extract basename.
            basename = Path(filename).name
            self.logger.info(f"Handling deletion for: {filename} (basename: {basename})")

            # Generate scene and source names based on basename (must match get_scene_name/get_source_name)
            scene_name = MediaFile._sanitize_obs_name(f"{basename}_scene")
            source_name = MediaFile._sanitize_obs_name(f"{basename}_source")

            # B3: Ensure waiting scene exists before removing what might be the last content scene
            all_scenes = await self.obs_manager.get_scene_list()
            content_scene_count = sum(1 for s in all_scenes if s.endswith('_scene'))
            if content_scene_count <= 1:
                await self._create_waiting_scene()

            # Remove the scene from OBS
            if scene_name in self.managed_scenes:
                await self.obs_manager.remove_scene(scene_name)
                self.managed_scenes.discard(scene_name)
                self.logger.info(f"Removed OBS scene: {scene_name}")

            # Remove the input from OBS
            if source_name in self.managed_inputs:
                await self.obs_manager.remove_input(source_name)
                self.managed_inputs.discard(source_name)
                self.logger.info(f"Removed OBS input: {source_name}")

            # Update media files and rotation state under lock
            need_switch = False
            files_empty = False
            async with self._rotation_lock:
                self.media_files = [mf for mf in self.media_files if mf.filename != basename]
                if not self.media_files:
                    files_empty = True
                    self.rotation_active = False
                elif self.current_scene == scene_name:
                    self.current_index = 0
                    self.playback_start_time = time.time()
                    need_switch = True

            # B2: If all files deleted, show waiting scene
            if files_empty:
                self.logger.info("All content files deleted — activating waiting scene")
                await self._create_waiting_scene()
                await self._activate_waiting_scene()
            elif need_switch:
                await self._switch_to_media(0)

        except Exception as e:
            self.logger.error(f"Error handling file deletion for {filename}: {e}")