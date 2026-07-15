"""
clip_server.py — Lightweight HTTP server for crash clip retrieval.

Serves saved crash clips over WiFi so the iOS app can download them.
Runs in a daemon thread alongside the main BikeBox system.

Endpoints:
    GET /clips          — JSON list of available clips
    GET /clips/<file>   — Download a specific clip file
    DELETE /clips/<file> — Remove a clip after successful download
"""

import json
import os
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import unquote

from config import CLIP_SAVE_DIR, CLIP_SERVER_HOST, CLIP_SERVER_PORT


class _ClipRequestHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        if self.path == '/clips':
            self._serve_clip_list()
        elif self.path.startswith('/clips/'):
            filename = unquote(self.path[len('/clips/'):])
            self._serve_clip_file(filename)
        else:
            self._send_error(404, 'Not found')

    def do_DELETE(self):
        if self.path.startswith('/clips/'):
            filename = unquote(self.path[len('/clips/'):])
            self._delete_clip(filename)
        else:
            self._send_error(404, 'Not found')

    def _serve_clip_list(self):
        clips = []
        if os.path.isdir(CLIP_SAVE_DIR):
            for f in sorted(os.listdir(CLIP_SAVE_DIR), reverse=True):
                if f.startswith('crash_') and (f.endswith('.mp4') or f.endswith('.h264')):
                    filepath = os.path.join(CLIP_SAVE_DIR, f)
                    stat = os.stat(filepath)
                    ts_str = f.replace('crash_', '').rsplit('.', 1)[0]
                    try:
                        ts = time.mktime(time.strptime(ts_str, '%Y%m%d_%H%M%S'))
                    except ValueError:
                        ts = stat.st_mtime
                    clips.append({
                        'filename': f,
                        'timestamp': int(ts),
                        'size_kb': int(stat.st_size / 1024),
                    })

        body = json.dumps(clips).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_clip_file(self, filename: str):
        if '/' in filename or '..' in filename:
            self._send_error(400, 'Invalid filename')
            return

        filepath = os.path.join(CLIP_SAVE_DIR, filename)
        if not os.path.isfile(filepath):
            self._send_error(404, 'Clip not found')
            return

        content_type = 'video/mp4' if filename.endswith('.mp4') else 'application/octet-stream'
        file_size = os.path.getsize(filepath)

        self.send_response(200)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(file_size))
        self.send_header('Content-Disposition', f'attachment; filename="{filename}"')
        self.end_headers()

        if ClipServer.on_download_activity:
            ClipServer.on_download_activity()

        with open(filepath, 'rb') as f:
            while True:
                chunk = f.read(65536)
                if not chunk:
                    break
                self.wfile.write(chunk)

    def _delete_clip(self, filename: str):
        if '/' in filename or '..' in filename:
            self._send_error(400, 'Invalid filename')
            return

        filepath = os.path.join(CLIP_SAVE_DIR, filename)
        if not os.path.isfile(filepath):
            self._send_error(404, 'Clip not found')
            return

        try:
            os.remove(filepath)
            self._send_json(200, {'deleted': filename})
        except OSError as e:
            self._send_error(500, str(e))

    def _send_json(self, code: int, obj: dict):
        body = json.dumps(obj).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, code: int, message: str):
        self._send_json(code, {'error': message})

    def log_message(self, format, *args):
        print(f"ClipServer: {args[0]}")


class ClipServer:
    """Manages the HTTP clip server lifecycle."""

    on_download_activity = None  # Callable set by main.py to reset hotspot timeout

    def __init__(self) -> None:
        self._server = None
        self._thread = None

    def start(self) -> None:
        """Start the clip HTTP server in a daemon thread."""
        try:
            self._server = HTTPServer(
                (CLIP_SERVER_HOST, CLIP_SERVER_PORT),
                _ClipRequestHandler
            )
            self._thread = threading.Thread(
                target=self._server.serve_forever,
                daemon=True,
                name='clip-server'
            )
            self._thread.start()
            print(f"ClipServer: serving on http://{CLIP_SERVER_HOST}:{CLIP_SERVER_PORT}")
        except OSError as e:
            print(f"ClipServer: failed to start — {e}")

    def stop(self) -> None:
        """Shut down the HTTP server."""
        if self._server:
            self._server.shutdown()
            print("ClipServer: stopped")
