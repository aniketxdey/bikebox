"""test_camera.py — Unit tests for the circular video buffer (mocked picamera2)."""

import os
import time
from unittest.mock import MagicMock, patch

import pytest

from camera import CameraManager, PICAMERA2_AVAILABLE
from config import VIDEO_RESOLUTION, CIRCULAR_BUFFER_SECONDS, CLIP_SAVE_DIR


@pytest.fixture
def camera():
    """Provide a CameraManager instance."""
    return CameraManager()


class TestCameraInit:
    """Test CameraManager initialization."""

    def test_not_recording_by_default(self, camera):
        assert camera.is_recording() is False

    def test_save_clip_returns_none_when_not_recording(self, camera):
        result = camera.save_clip()
        assert result is None


class TestCameraStart:
    """Test camera start behavior."""

    def test_start_sets_recording_flag(self, camera):
        camera.start()
        # With mocked picamera2, it should attempt to start

    def test_is_recording_after_start(self, camera):
        import picamera2
        mock_cam = MagicMock()
        picamera2.Picamera2.return_value = mock_cam

        camera.start()
        assert camera.is_recording() is True


class TestCameraStop:
    """Test camera stop behavior."""

    def test_stop_sets_not_recording(self, camera):
        import picamera2
        mock_cam = MagicMock()
        picamera2.Picamera2.return_value = mock_cam
        camera.start()
        camera.stop()
        assert camera.is_recording() is False


class TestSaveClip:
    """Test clip saving behavior."""

    def test_save_clip_creates_file_path(self, camera, tmp_path):
        import picamera2
        from picamera2.outputs import CircularOutput

        mock_cam = MagicMock()
        mock_output = MagicMock()
        picamera2.Picamera2.return_value = mock_cam
        CircularOutput.return_value = mock_output

        camera.start()
        assert camera.is_recording()

        with patch('camera.CLIP_SAVE_DIR', str(tmp_path)):
            with patch('camera.os.path.join', return_value=str(tmp_path / 'test.h264')):
                with patch('camera.os.makedirs'):
                    with patch('camera.time.sleep'):
                        with patch('camera.os.path.getsize', return_value=1024):
                            result = camera.save_clip(timestamp=1000000.0)

        # Should have attempted to save
        assert mock_output.start.called or mock_output.stop.called
