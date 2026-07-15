"""
camera.py — Circular video buffer for BikeBox.

Uses picamera2 with a circular output to maintain a rolling buffer
of the last CIRCULAR_BUFFER_SECONDS of video. When save_clip()
is called (by alert.py on crash), the buffer is dumped to an H264 file.

IMPORTANT: Uses picamera2 (libcamera-based), NOT legacy picamera.
"""

import os
import time
import threading
import subprocess

from config import (
    VIDEO_RESOLUTION, VIDEO_FRAMERATE,
    CIRCULAR_BUFFER_SECONDS, CLIP_POST_CRASH_SECONDS, CLIP_SAVE_DIR,
    CLIP_FORMAT
)

try:
    from picamera2 import Picamera2
    from picamera2.encoders import H264Encoder
    from picamera2.outputs import CircularOutput
    PICAMERA2_AVAILABLE = True
except ImportError:
    PICAMERA2_AVAILABLE = False
    print("WARNING: picamera2 not available. Camera functions disabled.")


class CameraManager:
    """Manages circular video recording and crash clip saving."""

    def __init__(self) -> None:
        self._picam = None
        self._encoder = None
        self._output = None
        self._recording = False
        self._lock = threading.Lock()

    def start(self) -> None:
        """Initialize camera and start circular recording."""
        if not PICAMERA2_AVAILABLE:
            print("Camera: picamera2 not available. Skipping.")
            return

        try:
            self._picam = Picamera2()
            video_config = self._picam.create_video_configuration(
                main={"size": VIDEO_RESOLUTION}
            )
            self._picam.configure(video_config)

            self._encoder = H264Encoder()
            buffer_frames = VIDEO_FRAMERATE * CIRCULAR_BUFFER_SECONDS
            self._output = CircularOutput(buffersize=buffer_frames)

            self._picam.start_recording(self._encoder, self._output)
            self._recording = True
            print(f"Camera recording to circular buffer "
                  f"({CIRCULAR_BUFFER_SECONDS}s @ "
                  f"{VIDEO_RESOLUTION[0]}x{VIDEO_RESOLUTION[1]})")

        except Exception as e:
            print(f"Camera initialization failed: {e}")
            self._recording = False

    def stop(self) -> None:
        """Stop recording and release camera resources."""
        if self._recording and self._picam:
            try:
                self._picam.stop_recording()
                self._picam.close()
            except Exception as e:
                print(f"Camera stop error: {e}")
            self._recording = False
            print("Camera stopped.")

    def save_clip(self, timestamp: float = None) -> str:
        """
        Save the circular buffer contents to a file.
        Called when a crash is detected.

        Returns:
            Path to saved clip, or None if camera not recording.
        """
        with self._lock:
            if not self._recording or not self._output:
                print("Camera: not recording, cannot save clip.")
                return None

            if timestamp is None:
                timestamp = time.time()

            time_str = time.strftime('%Y%m%d_%H%M%S', time.localtime(timestamp))
            filename = f"crash_{time_str}.h264"
            filepath = os.path.join(CLIP_SAVE_DIR, filename)

            os.makedirs(CLIP_SAVE_DIR, exist_ok=True)

            try:
                self._output.fileoutput = filepath
                self._output.start()
                time.sleep(CLIP_POST_CRASH_SECONDS)
                self._output.stop()

                file_size = os.path.getsize(filepath) / 1024
                print(f"Camera: raw clip saved -> {filepath} ({file_size:.0f} KB)")

                if CLIP_FORMAT == 'mp4':
                    filepath = self._convert_to_mp4(filepath)

                return filepath

            except Exception as e:
                print(f"Camera: failed to save clip: {e}")
                return None

    @staticmethod
    def _convert_to_mp4(h264_path: str) -> str:
        """Remux raw H.264 to MP4 container via ffmpeg. Returns final path."""
        mp4_path = h264_path.replace('.h264', '.mp4')
        try:
            result = subprocess.run(
                ['ffmpeg', '-y', '-i', h264_path, '-c', 'copy', mp4_path],
                capture_output=True, timeout=30
            )
            if result.returncode == 0:
                os.remove(h264_path)
                file_size = os.path.getsize(mp4_path) / 1024
                print(f"Camera: converted to MP4 -> {mp4_path} ({file_size:.0f} KB)")
                return mp4_path
            else:
                print(f"Camera: ffmpeg error (code {result.returncode}), keeping .h264")
                return h264_path
        except FileNotFoundError:
            print("Camera: ffmpeg not installed, keeping .h264")
            return h264_path
        except subprocess.TimeoutExpired:
            print("Camera: ffmpeg timed out, keeping .h264")
            return h264_path

    def is_recording(self) -> bool:
        """Check if the camera is currently recording."""
        return self._recording
