"""Loopback-only MJPEG preview for the existing YOLO webcam detector.

Video is never carried in our game-state WebSocket or TCP event contracts.
Only approved local development origins can request video in a normal browser.
This is a demo privacy guard, not authentication against local programs.
"""

import json
import threading
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
        self.active = True

    def publish(self, jpeg):
        if not isinstance(jpeg, bytes) or not jpeg:
            raise ValueError('Expected nonempty JPEG bytes')
        with self.condition:
            if not self.active:
                return
            self.frame = jpeg
            self.serial += 1
            self.condition.notify_all()

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
            self.condition.notify_all()


class PreviewHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/health':
            origin = self.headers.get('Origin')
            if origin and not approved_origin(origin):
                self.send_error(403)
                return
            payload = json.dumps({
                'active': self.server.buffer.active,
                'has_frame': self.server.buffer.frame is not None,
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
