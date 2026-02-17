"""
Browse Storebox (WebDAV) NAS folders for the schedule editor.
"""

import logging
import posixpath

logger = logging.getLogger(__name__)

VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".wmv", ".webm", ".m4v"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tiff", ".webp"}


class StoreboxBrowser:
    """Browse folders on the Storebox NAS via WebDAV."""

    def __init__(self, webdav_client):
        self.client = webdav_client

    def list_folders(self, path: str = "/") -> list[dict]:
        """List folders at the given WebDAV path.

        Args:
            path: Relative path on NAS (e.g., "/" or "/sunday_service_slideshow")

        Returns:
            List of folder dicts with 'name' and 'path' keys
        """
        # Sanitize path - prevent traversal attacks
        # Reject null bytes and control characters
        if "\x00" in path or any(ord(c) < 32 for c in path):
            logger.warning(f"Rejected path with control characters: {path!r}")
            return []

        # Normalize and verify no traversal
        clean = posixpath.normpath(path)
        if ".." in clean.split("/"):
            logger.warning(f"Rejected path traversal attempt: {path!r}")
            return []

        if not clean.startswith("/"):
            clean = "/" + clean

        try:
            root = self.client.settings.WEBDAV_ROOT_PATH.rstrip("/")
            full_path = f"{root}{clean}".replace("//", "/")

            items = self.client.client.ls(full_path)
            folders = []
            for item in items:
                if item.get("type") == "directory":
                    name = item.get("name", "").rstrip("/").split("/")[-1]
                    if name and name != ".":
                        rel = f"{clean.rstrip('/')}/{name}".lstrip("/")
                        folders.append({"name": name, "path": rel})
            return folders
        except Exception as e:
            logger.warning(f"Failed to list folders at {path}: {e}")
            return []

    def list_files(self, path: str = "/") -> list[dict]:
        """List media files at the given WebDAV path.

        Args:
            path: Relative path on NAS (e.g., "/sunday_service_slideshow")

        Returns:
            List of file dicts with 'name' and 'type' keys
        """
        if "\x00" in path or any(ord(c) < 32 for c in path):
            logger.warning(f"Rejected path with control characters: {path!r}")
            return []

        clean = posixpath.normpath(path)
        if ".." in clean.split("/"):
            logger.warning(f"Rejected path traversal attempt: {path!r}")
            return []

        if not clean.startswith("/"):
            clean = "/" + clean

        try:
            root = self.client.settings.WEBDAV_ROOT_PATH.rstrip("/")
            full_path = f"{root}{clean}".replace("//", "/")

            items = self.client.client.ls(full_path)
            files = []
            for item in items:
                if item.get("type") == "directory":
                    continue
                name = item.get("name", "").rstrip("/").split("/")[-1]
                if not name:
                    continue
                ext = posixpath.splitext(name)[1].lower()
                if ext in VIDEO_EXTENSIONS:
                    files.append({"name": name, "type": "video"})
                elif ext in IMAGE_EXTENSIONS:
                    files.append({"name": name, "type": "image"})
            return files
        except Exception as e:
            logger.warning(f"Failed to list files at {path}: {e}")
            return []
