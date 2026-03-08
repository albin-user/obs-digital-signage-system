"""Tests for content manager utilities."""

import asyncio
import sys
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestMediaFile:
    """Test MediaFile metadata and naming."""

    def _settings(self):
        s = MagicMock()
        s.SUPPORTED_VIDEO_FORMATS = {".mp4", ".mov", ".avi", ".mkv", ".wmv", ".webm", ".m4v"}
        s.SUPPORTED_IMAGE_FORMATS = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tiff", ".webp"}
        s.SUPPORTED_AUDIO_FORMATS = {".mp3", ".wav", ".ogg", ".flac", ".m4a"}
        return s

    def _import_media_file(self):
        """Import MediaFile with obs_manager mocked out."""
        # Mock obsws_python before importing content_manager
        sys.modules.setdefault("obsws_python", MagicMock())
        from core.content_manager import MediaFile
        return MediaFile

    def test_video_detection(self, tmp_path):
        MediaFile = self._import_media_file()
        f = tmp_path / "test.mp4"
        f.write_bytes(b"\x00" * 100)
        mf = MediaFile(f, self._settings())
        assert mf.is_video is True
        assert mf.is_image is False

    def test_image_detection(self, tmp_path):
        MediaFile = self._import_media_file()
        f = tmp_path / "slide.png"
        f.write_bytes(b"\x89PNG" + b"\x00" * 100)
        mf = MediaFile(f, self._settings())
        assert mf.is_video is False
        assert mf.is_image is True

    def test_scene_name(self, tmp_path):
        MediaFile = self._import_media_file()
        f = tmp_path / "hello.mp4"
        f.write_bytes(b"\x00" * 100)
        mf = MediaFile(f, self._settings())
        assert mf.get_scene_name() == "hello.mp4_scene"
        assert mf.get_source_name() == "hello.mp4_source"

    def test_unsupported_format(self, tmp_path):
        MediaFile = self._import_media_file()
        f = tmp_path / "readme.txt"
        f.write_text("hello")
        mf = MediaFile(f, self._settings())
        assert mf.is_video is False
        assert mf.is_image is False

    def test_file_metadata(self, tmp_path):
        MediaFile = self._import_media_file()
        f = tmp_path / "vid.mp4"
        f.write_bytes(b"\x00" * 500)
        mf = MediaFile(f, self._settings())
        assert mf.file_size == 500
        assert mf.file_mtime > 0


def _make_settings(content_dir: Path):
    """Create a mock Settings object for ContentManager tests."""
    s = MagicMock()
    s.SUPPORTED_VIDEO_FORMATS = {".mp4", ".mov", ".avi", ".mkv", ".wmv", ".webm", ".m4v"}
    s.SUPPORTED_IMAGE_FORMATS = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tiff", ".webp"}
    s.SUPPORTED_AUDIO_FORMATS = {".mp3", ".wav", ".ogg", ".flac", ".m4a"}
    s.CONTENT_DIR = content_dir
    s.VIDEO_WIDTH = 1920
    s.VIDEO_HEIGHT = 1080
    s.SLIDE_TRANSITION_SECONDS = 15
    s.MAX_VIDEO_DURATION = 900
    s.TRANSITION_START_OFFSET = 2.0
    return s


def _make_obs_manager():
    """Create a mock OBSManager with all async methods stubbed."""
    obs = MagicMock()
    obs.create_scene = AsyncMock(return_value=True)
    obs.remove_scene = AsyncMock()
    obs.create_input = AsyncMock(return_value=True)
    obs.remove_input = AsyncMock()
    obs.set_current_scene = AsyncMock()
    obs.get_scene_list = AsyncMock(return_value=[])
    obs.get_input_list = AsyncMock(return_value=[])
    obs.get_scene_items = AsyncMock(return_value=[])
    obs.get_scene_item_id = AsyncMock(return_value=1)
    obs.set_scene_item_transform = AsyncMock(return_value=True)
    obs.set_input_mute = AsyncMock()
    obs.add_source_to_scene = AsyncMock(return_value=1)
    return obs


def _make_media_file(tmp_path: Path, name: str, is_video: bool = False):
    """Create a MediaFile with pre-set duration."""
    sys.modules.setdefault("obsws_python", MagicMock())
    from core.content_manager import MediaFile

    f = tmp_path / name
    f.write_bytes(b"\x00" * 100)
    settings = _make_settings(tmp_path)
    mf = MediaFile(f, settings)
    mf.duration = 10.0 if is_video else 15.0
    return mf


def _make_content_manager(tmp_path: Path):
    """Create a ContentManager with mocked OBS manager."""
    sys.modules.setdefault("obsws_python", MagicMock())
    from core.content_manager import ContentManager

    settings = _make_settings(tmp_path)
    obs = _make_obs_manager()
    cm = ContentManager(settings, obs)
    return cm, obs


@pytest.mark.asyncio
class TestIncrementalUpdate:
    """Tests for _incremental_update (Gaps 1 and 2)."""

    async def test_adds_scene_for_new_file(self, tmp_path):
        cm, obs = _make_content_manager(tmp_path)
        mf = _make_media_file(tmp_path, "new.png")
        new_files = [mf]

        await cm._incremental_update(new_files, added={"new.png"}, removed=set())

        obs.create_scene.assert_called()
        obs.create_input.assert_called()

    async def test_removes_scene_for_deleted_file(self, tmp_path):
        cm, obs = _make_content_manager(tmp_path)
        # Simulate an existing managed scene/input
        cm.managed_scenes.add("old.mp4_scene")
        cm.managed_inputs.add("old.mp4_source")

        mf = _make_media_file(tmp_path, "keep.png")
        cm.media_files = [mf]

        await cm._incremental_update([mf], added=set(), removed={"old.mp4"})

        obs.remove_input.assert_called_once_with("old.mp4_source")
        obs.remove_scene.assert_called_once_with("old.mp4_scene")
        assert "old.mp4_scene" not in cm.managed_scenes
        assert "old.mp4_source" not in cm.managed_inputs

    async def test_skips_already_removed_scenes(self, tmp_path):
        """Gap 1: If on_file_deleted() already cleaned up, Phase 3 should not call OBS."""
        cm, obs = _make_content_manager(tmp_path)
        # Scenes NOT in managed sets (already removed by on_file_deleted)
        mf = _make_media_file(tmp_path, "keep.png")
        cm.media_files = [mf]

        await cm._incremental_update([mf], added=set(), removed={"gone.mp4"})

        obs.remove_input.assert_not_called()
        obs.remove_scene.assert_not_called()

    async def test_preserves_playback_position(self, tmp_path):
        cm, obs = _make_content_manager(tmp_path)

        mf1 = _make_media_file(tmp_path, "a.png")
        mf2 = _make_media_file(tmp_path, "b.png")
        mf3 = _make_media_file(tmp_path, "c.png")

        cm.media_files = [mf1, mf2]
        cm.current_index = 1  # Playing b.png
        cm.current_scene = "b.png_scene"
        cm.rotation_active = True
        cm.playback_start_time = time.time()

        # Add c.png while b.png is playing
        await cm._incremental_update([mf1, mf2, mf3], added={"c.png"}, removed=set())

        assert cm.current_index == 1  # Still pointing at b.png
        assert cm.media_files[cm.current_index].filename == "b.png"

    async def test_logs_failure_on_scene_creation_error(self, tmp_path):
        """Gap 2: Failed scene creation should log error, not success."""
        cm, obs = _make_content_manager(tmp_path)
        obs.create_scene = AsyncMock(return_value=False)

        mf = _make_media_file(tmp_path, "fail.png")
        cm.media_files = []

        # Should not raise; should log error internally
        await cm._incremental_update([mf], added={"fail.png"}, removed=set())


@pytest.mark.asyncio
class TestFullRebuild:
    """Tests for _full_rebuild (Gap 3)."""

    async def test_creates_waiting_scene(self, tmp_path):
        cm, obs = _make_content_manager(tmp_path)
        obs.get_scene_list = AsyncMock(return_value=[])

        mf = _make_media_file(tmp_path, "img.png")

        await cm._full_rebuild([mf])

        # waiting_for_content_scene should be created
        scene_names = [call.args[0] for call in obs.create_scene.call_args_list]
        assert "waiting_for_content_scene" in scene_names

    async def test_skips_sync_scene_removal_when_creation_failed(self, tmp_path):
        """Gap 3: If sync scene creation failed, finally block should not try to remove it."""
        cm, obs = _make_content_manager(tmp_path)
        obs.get_scene_list = AsyncMock(return_value=[])

        # First call (sync scene) fails, rest succeed
        obs.create_scene = AsyncMock(side_effect=[False, True, True])

        mf = _make_media_file(tmp_path, "img.png")
        await cm._full_rebuild([mf])

        # remove_scene should NOT have been called for "Sync in Progress"
        remove_calls = [call.args[0] for call in obs.remove_scene.call_args_list]
        assert "Sync in Progress" not in remove_calls


@pytest.mark.asyncio
class TestOnFileDeleted:
    """Tests for on_file_deleted edge cases."""

    async def test_last_file_activates_waiting_scene(self, tmp_path):
        """B2: When all files are deleted, rotation stops and waiting scene activates."""
        cm, obs = _make_content_manager(tmp_path)

        mf = _make_media_file(tmp_path, "only.png")
        cm.media_files = [mf]
        cm.rotation_active = True
        cm.current_scene = "only.png_scene"
        cm.managed_scenes = {"only.png_scene"}
        cm.managed_inputs = {"only.png_source"}

        obs.get_scene_list = AsyncMock(return_value=["only.png_scene", "waiting_for_content_scene"])

        await cm.on_file_deleted("only.png")

        assert cm.rotation_active is False
        assert cm.media_files == []
        obs.set_current_scene.assert_called_with("waiting_for_content_scene")


@pytest.mark.asyncio
class TestScanAndUpdate:
    """Tests for scan_and_update_content routing to full_rebuild vs incremental."""

    async def test_first_load_uses_full_rebuild(self, tmp_path):
        cm, obs = _make_content_manager(tmp_path)
        obs.get_scene_list = AsyncMock(return_value=[])

        # Create a content file
        content_dir = tmp_path
        (content_dir / "photo.png").write_bytes(b"\x89PNG" + b"\x00" * 100)

        # Stub ffprobe to avoid needing real binary
        cm._check_ffprobe = MagicMock()
        cm._get_video_duration_ffprobe = AsyncMock(return_value=10.0)

        await cm.scan_and_update_content()

        # Should have called create_scene for "Sync in Progress" (full rebuild path)
        scene_names = [call.args[0] for call in obs.create_scene.call_args_list]
        assert "Sync in Progress" in scene_names

    async def test_incremental_on_file_added(self, tmp_path):
        cm, obs = _make_content_manager(tmp_path)

        # Set up existing state (simulating previous scan)
        existing = _make_media_file(tmp_path, "existing.png")
        cm.media_files = [existing]
        cm.managed_scenes = {"existing.png_scene"}
        cm.managed_inputs = {"existing.png_source"}
        cm.rotation_active = True
        cm.playback_start_time = time.time()
        cm.content_hash = cm._calculate_content_hash([existing])

        # Add a new file to the directory
        (tmp_path / "new.png").write_bytes(b"\x89PNG" + b"\x00" * 50)

        cm._get_video_duration_ffprobe = AsyncMock(return_value=10.0)

        await cm.scan_and_update_content()

        # Should NOT have created "Sync in Progress" (incremental path, not full rebuild)
        scene_names = [call.args[0] for call in obs.create_scene.call_args_list]
        assert "Sync in Progress" not in scene_names
        assert len(cm.media_files) == 2
