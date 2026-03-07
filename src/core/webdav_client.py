"""
WebDAV client for Synology NAS synchronization.
Handles automated content downloading and change detection.
"""

import asyncio
import logging
from pathlib import Path
from typing import Optional, Set, Dict
import time

from webdav4.client import Client

from config.settings import Settings


class WebDAVClient:
    """WebDAV client for content synchronization."""

    def __init__(self, settings: Settings, deletion_callback=None):
        self.settings = settings
        self.logger = logging.getLogger(__name__)
        self.deletion_callback = deletion_callback  # Callback for handling file deletions

        # WebDAV client configuration for webdav4
        self.client = Client(
            base_url=f"{settings.WEBDAV_HOST}:{settings.WEBDAV_PORT}",
            auth=(settings.WEBDAV_USERNAME, settings.WEBDAV_PASSWORD),
            timeout=settings.WEBDAV_TIMEOUT
        )

        # State tracking
        self.last_sync_time = 0.0
        self.remote_file_cache: Dict[str, Dict] = {}
        self._sync_lock = asyncio.Lock()
        # For scheduling: sync to base directory to preserve subfolder structure
        # Derives local folder name from WEBDAV_ROOT_PATH (e.g., "/my_slides/" -> "my_slides")
        root_folder = settings.WEBDAV_ROOT_PATH.strip("/").split("/")[0] if settings.WEBDAV_ROOT_PATH.strip("/") else "content"
        self.local_content_dir = Path(settings.CONTENT_BASE_DIR) / root_folder
        
    async def test_connection(self) -> bool:
        """Test WebDAV connection to Synology NAS."""
        try:
            # Test connection with a simple list operation (with timeout)
            timeout = self.settings.WEBDAV_TIMEOUT + 10
            await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(
                    None, self.client.ls, self.settings.WEBDAV_ROOT_PATH
                ),
                timeout=timeout
            )
            self.logger.info("WebDAV connection test successful")
            return True

        except asyncio.TimeoutError:
            self.logger.error(f"WebDAV connection test timed out after {self.settings.WEBDAV_TIMEOUT + 10}s")
            return False
        except Exception as e:
            self.logger.error(f"WebDAV connection test failed: {e}")
            return False
    
    async def sync_content(self) -> bool:
        """Synchronize content from WebDAV to local directory."""
        # Prevent concurrent sync operations
        if self._sync_lock.locked():
            self.logger.debug("Sync already in progress, skipping")
            return False

        async with self._sync_lock:
            try:
                self.logger.info("Starting WebDAV content synchronization...")

                # Ensure local directory exists
                self.local_content_dir.mkdir(parents=True, exist_ok=True)

                # Clean up files marked for deletion from previous session
                await self._cleanup_deletion_markers()

                # Get remote file list
                remote_files = await self._get_remote_file_list()
                if remote_files is None:
                    return False

                # Update cache with current remote files
                self.remote_file_cache = remote_files

                # Get local file list
                local_files = self._get_local_file_list()

                # Determine what needs to be synced
                changes_detected = False

                # Download new or updated files
                for remote_file, remote_info in remote_files.items():
                    # Preserve subfolder structure in local path
                    local_path = self.local_content_dir / remote_file

                    # Create parent directories if needed
                    local_path.parent.mkdir(parents=True, exist_ok=True)

                    if await self._should_download_file(remote_file, remote_info, local_path):
                        if await self._download_file(remote_file, local_path):
                            changes_detected = True
                            self.logger.info(f"Downloaded: {remote_file}")

                # Remove local files that no longer exist remotely
                self.logger.debug(f"Checking for deletions: {len(local_files)} local files, {len(remote_files)} remote files")
                for local_file in local_files:
                    if local_file not in remote_files:
                        local_path = self.local_content_dir / local_file
                        try:
                            self.logger.info(f"File removed from remote: {local_file}")

                            # First, notify via callback to remove OBS scenes (if callback provided)
                            if self.deletion_callback:
                                try:
                                    await self.deletion_callback(local_file)
                                    self.logger.info(f"OBS content removed for: {local_file}")
                                except Exception as e:
                                    self.logger.error(f"Failed to remove OBS content for {local_file}: {e}")
                                    # Skip file deletion if OBS cleanup failed - file still in use
                                    continue

                            # Then delete the local file
                            try:
                                local_path.unlink()
                                changes_detected = True
                                self.logger.info(f"Successfully deleted local file: {local_file}")
                            except PermissionError:
                                # File is locked - rename it to mark for deletion
                                deletion_marker = local_path.with_suffix(local_path.suffix + '.delete')
                                if not deletion_marker.exists():
                                    local_path.rename(deletion_marker)
                                    self.logger.warning(f"File locked, marked for deletion on next restart: {local_file}")
                                changes_detected = True

                        except Exception as e:
                            self.logger.error(f"Failed to remove {local_file}: {e}")

                self.last_sync_time = time.time()

                if changes_detected:
                    self.logger.info("WebDAV synchronization completed with changes")
                else:
                    self.logger.debug("WebDAV synchronization completed - no changes")

                return changes_detected

            except Exception as e:
                self.logger.error(f"WebDAV sync error: {e}")
                return False
    
    async def _get_remote_file_list(self) -> Optional[Dict[str, Dict]]:
        """Get list of remote files with metadata (recursively scans subdirectories)."""
        try:
            file_info = {}

            # Recursively scan the WebDAV root path and all subdirectories
            await self._scan_remote_directory(self.settings.WEBDAV_ROOT_PATH, "", file_info)

            self.logger.debug(f"Found {len(file_info)} remote media files")
            return file_info

        except Exception as e:
            self.logger.error(f"Error getting remote file list: {e}")
            return None

    async def _scan_remote_directory(self, remote_path: str, relative_path: str, file_info: Dict[str, Dict]) -> None:
        """
        Recursively scan a remote directory and collect file information.

        Args:
            remote_path: Full WebDAV path to scan (e.g., "/my_slides/default_slideshow")
            relative_path: Relative path from root (e.g., "default_slideshow")
            file_info: Dictionary to populate with file information
        """
        try:
            # List contents of this directory (with timeout)
            items = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(
                    None, self.client.ls, remote_path
                ),
                timeout=self.settings.WEBDAV_TIMEOUT + 10
            )

            for item in items:
                item_name = item.get('name', '')
                if not item_name:
                    continue

                # Extract just the filename/dirname (last component of path)
                item_basename = item_name.rstrip('/').split('/')[-1]

                # Build relative path for this item
                if relative_path:
                    item_relative_path = f"{relative_path}/{item_basename}"
                else:
                    item_relative_path = item_basename

                if item.get('type') == 'directory':
                    # Recursively scan subdirectory
                    subdir_path = f"{remote_path.rstrip('/')}/{item_basename}"
                    await self._scan_remote_directory(subdir_path, item_relative_path, file_info)
                else:
                    # It's a file - check if it's a supported media file
                    if self._is_supported_media_file(item_basename):
                        file_info[item_relative_path] = {
                            'size': item.get('content_length', 0) or 0,
                            'modified': item.get('modified', ''),
                            'etag': item.get('etag', ''),
                            'path': item.get('href', f"/{item_relative_path}")
                        }

        except Exception as e:
            self.logger.warning(f"Error scanning remote directory {remote_path}: {e}")

    def _get_local_file_list(self) -> Set[str]:
        """Get set of local media files with relative paths (including subfolders)."""
        local_files = set()

        try:
            # Recursively scan all subfolders
            for file_path in self.local_content_dir.rglob('*'):
                if file_path.is_file() and self._is_supported_media_file(file_path.name):
                    # Get relative path from local_content_dir
                    relative_path = file_path.relative_to(self.local_content_dir)
                    # Convert to forward slashes for consistency
                    local_files.add(str(relative_path).replace('\\', '/'))

        except Exception as e:
            self.logger.error(f"Error scanning local files: {e}")

        return local_files
    
    def _is_supported_media_file(self, filename: str) -> bool:
        """Check if file is a supported media format."""
        file_ext = Path(filename).suffix.lower()
        
        supported_formats = (
            self.settings.SUPPORTED_VIDEO_FORMATS |
            self.settings.SUPPORTED_IMAGE_FORMATS |
            self.settings.SUPPORTED_AUDIO_FORMATS
        )
        
        return file_ext in supported_formats
    
    async def _should_download_file(self, filename: str, remote_info: Dict, local_path: Path) -> bool:
        """Determine if file should be downloaded."""
        try:
            # File doesn't exist locally
            if not local_path.exists():
                return True
            
            # Check file size
            local_size = local_path.stat().st_size
            remote_size = remote_info.get('size', 0)
            
            if local_size != remote_size:
                self.logger.debug(f"Size mismatch for {filename}: local={local_size}, remote={remote_size}")
                return True
            
            return False  # File appears to be up to date
            
        except Exception as e:
            self.logger.error(f"Error checking if should download {filename}: {e}")
            return True  # Download on error to be safe
    
    async def _download_file(self, remote_filename: str, local_path: Path) -> bool:
        """Download file from WebDAV to local path."""
        # Define temp_path before try so finally can always clean it up
        temp_path = local_path.with_suffix(local_path.suffix + '.tmp')
        try:
            # Construct the full remote path (webdav4 handles URL encoding internally)
            remote_path = f"{self.settings.WEBDAV_ROOT_PATH}/{remote_filename}".replace('//', '/')
            if not remote_path.startswith('/'):
                remote_path = '/' + remote_path

            self.logger.debug(f"Downloading from remote path: {remote_path}")

            # Download file (webdav4 library handles URL encoding automatically)
            # Use generous timeout for large files (5 minutes max)
            await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(
                    None, self.client.download_file, remote_path, str(temp_path)
                ),
                timeout=300
            )

            # Verify download completed successfully
            if temp_path.exists() and temp_path.stat().st_size > 0:
                # Move temp file to final location
                if local_path.exists():
                    local_path.unlink()
                temp_path.rename(local_path)

                self.logger.debug(f"Successfully downloaded: {remote_filename}")
                return True
            else:
                self.logger.error(f"Download failed or empty file: {remote_filename}")
                return False

        except Exception as e:
            self.logger.error(f"Error downloading {remote_filename}: {type(e).__name__}: {e}", exc_info=True)
            return False
        finally:
            # Clean up partial temp file on any failure
            try:
                if temp_path.exists():
                    temp_path.unlink()
            except Exception:
                pass

    async def _cleanup_deletion_markers(self) -> None:
        """Remove files marked for deletion (with .delete extension)."""
        try:
            deleted_count = 0
            for file_path in self.local_content_dir.rglob('*.delete'):
                try:
                    file_path.unlink()
                    deleted_count += 1
                    self.logger.info(f"Cleaned up deletion marker: {file_path.name}")
                except Exception as e:
                    self.logger.error(f"Failed to delete {file_path.name}: {e}")

            if deleted_count > 0:
                self.logger.info(f"Cleaned up {deleted_count} file(s) marked for deletion")

        except Exception as e:
            self.logger.error(f"Error during deletion marker cleanup: {e}")