"""Loopback-only MJPEG preview for the existing YOLO webcam detector.

Video is never carried in our game-state WebSocket or TCP event contracts.
Only approved local development origins can request video in a normal browser.
This is a demo privacy guard, not authentication against local programs.
"""

import json
import math
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

HOST = '127.0.0.1'
PORT = 8767
APP_ORIGINS = frozenset({
    'http://127.0.0.1:5173', 'http://localhost:5173',
    'http://127.0.0.1:5174', 'http://localhost:5174',
})


def approved_origin(url):
    """A strict origin comparison; no suffix/path/host trickery."""
    if not isinstance(url, str) or not url:
        return False
    try:
        parsed = urlsplit(url)
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            return False
        return f'{parsed.scheme}://{parsed.netloc}' in APP_ORIGINS
    except ValueError:
        return False


class FrameBuffer:
    def __init__(self):
        self.condition = threading.Condition()
        self.serial = 0
        self.frame = None
        self._last_jpeg_at = None  # HCI_SNAPSHOT_RECOVERY_V3
        self.raw_frame = None  # Unannotated frames for the real Hand Landmarker
        self.raw_sequence = 0
        self.raw_detections = []
        self.hand_state = None  # SHARED_OVERLAY_V2; never scoring
        self.raw_at = None
        self.active = True

    def publish(self, jpeg):
        if not isinstance(jpeg, bytes) or not jpeg:
            raise ValueError('Expected nonempty JPEG bytes')
        with self.condition:
            if not self.active:
                return
            self.frame = jpeg
            self.serial += 1
            self._last_jpeg_at = time.monotonic()
            self.condition.notify_all()

    def publish_raw(self, jpeg, detections=None):
        if not isinstance(jpeg, bytes) or not jpeg:
            raise ValueError("Expected nonempty raw-frame JPEG bytes")
        with self.condition:
            if not self.active:
                return
            self.raw_frame = jpeg
            self.raw_sequence += 1
            self.raw_detections = list(detections or [])
            self.raw_at = time.monotonic()

    def latest_raw(self, max_age=2.5):
        with self.condition:
            if (not self.active or self.raw_frame is None or self.raw_at is None
                    or time.monotonic() - self.raw_at > max_age):
                return None, None
            return self.raw_frame, self.raw_sequence

    def hand_frame(self, max_age=1.0):
        """One coherent raw-frame+YOLO-box observation; not a gameplay target gate."""
        with self.condition:
            if (not self.active or self.raw_frame is None or self.raw_at is None
                    or time.monotonic() - self.raw_at > max_age):
                return None, None, []
            return self.raw_frame, self.raw_sequence, list(self.raw_detections)

    def update_hand(self, report):
        """Accept only recent reports corresponding to frames we actually supplied."""
        if not isinstance(report, dict) or set(report) != {'frame_sequence', 'pointer', 'pinching'}:
            return False
        seq, point, pinching = report['frame_sequence'], report['pointer'], report['pinching']
        if type(seq) is not int or seq < 1 or type(pinching) is not bool:
            return False
        if point is None:
            if pinching:
                return False
        elif (not isinstance(point, list) or len(point) != 2 or
              any(type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v <= 1 for v in point)):
            return False
        with self.condition:
            if (not self.active or self.raw_at is None or
                time.monotonic() - self.raw_at > 1.0 or
                not 0 <= self.raw_sequence - seq <= 8):
                return False
            self.hand_state = (seq, list(point) if point is not None else None,
                               pinching, time.monotonic())
            return True

    def recent_hand(self, max_age=0.75, max_lag=8):
        with self.condition:
            if not self.active or self.hand_state is None:
                return None
            seq, point, pinching, reported_at = self.hand_state
            if (time.monotonic() - reported_at > max_age or
                    not 0 <= self.raw_sequence - seq <= max_lag):
                return None
            return {'pointer': point, 'pinching': pinching}

    def snapshot(self, max_age=2.5):
        """Return a fresh rendered JPEG and monotonic version; stale feed fails closed."""
        with self.condition:
            if (not self.active or self.frame is None or self._last_jpeg_at is None
                    or time.monotonic() - self._last_jpeg_at > max_age):
                return 0, None
            return self.serial, self.frame

    def next_frame(self, previous, timeout=2):
        with self.condition:
            self.condition.wait_for(
                lambda: not self.active or self.serial != previous,
                timeout=timeout,
            )
            return self.serial, self.frame, self.active

    def close(self):
        with self.condition:
            self.active = False
            self.frame = None
            self.raw_frame = None
            self.raw_detections = []
            self.hand_state = None
            self.condition.notify_all()


class PreviewHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/health':
            origin = self.headers.get('Origin')
            if origin and not approved_origin(origin):
                self.send_error(403)
                return
            frame_sequence, jpeg = self.server.buffer.snapshot()
            payload = json.dumps({
                'active': self.server.buffer.active,
                'has_frame': jpeg is not None,
                'frame_sequence': frame_sequence,
            }).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            if origin and approved_origin(origin):
                self.send_header('Access-Control-Allow-Origin', origin)
                self.send_header('Vary', 'Origin')
            self.send_header('Content-Length', str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return

        if self.path == '/hand-frame':
            # Browser image tags cannot attach this header. Local-only API;
            # diagnostic protocol, not strong authentication of local apps.
            if self.headers.get("X-HCI-Sensor-Client") != "local-hand-landmarker-v1":
                self.send_error(403)
                return
            jpeg, sequence, detections = self.server.buffer.hand_frame()
            if jpeg is None:
                self.send_error(503)
                return
            self.send_response(200)
            self.send_header("Content-Type", "image/jpeg")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Sequence", str(sequence))
            self.send_header("X-HCI-Detections", json.dumps(detections, separators=(",", ":")))
            self.send_header("Content-Length", str(len(jpeg)))
            self.end_headers()
            self.wfile.write(jpeg)
            return

        # Browser snapshot fallback: each request finishes independently, so a
        # stalled multipart image cannot leave a permanently frozen UI.
        if urlsplit(self.path).path == '/snapshot':
            query = urlsplit(self.path).query
            if query and not (query.startswith('frame=') and query[6:].isdigit()
                              and len(query) <= 30):
                self.send_error(400)
                return
            if not approved_origin(self.headers.get('Referer')):
                self.send_error(403)
                return
            frame_sequence, jpeg = self.server.buffer.snapshot()
            if jpeg is None:
                self.send_error(503)
                return
            self.send_response(200)
            self.send_header('Content-Type', 'image/jpeg')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('X-Frame-Sequence', str(frame_sequence))
            self.send_header('Content-Length', str(len(jpeg)))
            self.end_headers()
            self.wfile.write(jpeg)
            return

        if self.path != '/video':
            self.send_error(404)
            return

        # <img> loads from the local app send its page as Referer. A remote
        # website embedding this private webcam stream must be rejected.
        if not approved_origin(self.headers.get('Referer')):
            self.send_error(403)
            return

        self.send_response(200)
        self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=frame')
        self.send_header('Cache-Control', 'no-cache, no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        previous = 0
        try:
            while True:
                serial, frame, active = self.server.buffer.next_frame(previous)
                if not active:
                    break
                if serial == previous or frame is None:
                    continue
                previous = serial
                self.wfile.write(b'--frame\r\nContent-Type: image/jpeg\r\n')
                self.wfile.write(f'Content-Length: {len(frame)}\r\n\r\n'.encode())
                self.wfile.write(frame)
                self.wfile.write(b'\r\n')
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, TimeoutError, OSError):
            pass  # User navigated away or shut down the preview.

    def do_POST(self):
        # Local Python process only. Header is a CSRF barrier, NOT authentication.
        if (self.path != '/hand-state' or self.headers.get('Origin') or
                self.headers.get('X-HCI-Sensor-Client') != 'local-hand-landmarker-v1'):
            self.send_error(403)
            return
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 300:
                raise ValueError('Invalid payload length')
            report = json.loads(self.rfile.read(length))
        except (ValueError, UnicodeDecodeError):
            self.send_error(400)
            return
        if not self.server.buffer.update_hand(report):
            self.send_error(409)
            return
        self.send_response(204)
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()

    def log_message(self, *_args):
        return  # Avoid logging video endpoints and request headers.


class PreviewServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, port=PORT):
        super().__init__((HOST, port), PreviewHandler)
        self.buffer = FrameBuffer()
        self.thread = None

    def start(self):
        self.thread = threading.Thread(target=self.serve_forever, daemon=True)
        self.thread.start()
        return self

    def close(self):
        self.buffer.close()
        self.shutdown()
        self.server_close()
        if self.thread:
            self.thread.join(timeout=2)


def start_preview(port=PORT):
    return PreviewServer(port).start()
