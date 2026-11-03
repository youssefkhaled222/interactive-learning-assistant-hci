"""Real two-camera HCI gaze tracking (local-only and face-image-free storage).

Object-facing camera stays owned by YOLO. This *second* webcam looks at the
player and tracks MediaPipe's iris landmarks. Nine click-confirmed gaze points
fit a per-session screen mapping, then browser-reported live preview geometry
maps gaze into YOLO's normalized object-image coordinates. The backend alone
handles 1.5 s dwell and validates stabilized YOLO boxes. Clicking never scores.

Run from phase2: .venv/Scripts/python.exe backend/gaze_tracker.py --camera 1
"""
import argparse
import json
import math
import os
import socket
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import numpy as np

from gaze_calibration import GazeCalibrator, eye_features

HOST = '127.0.0.1'
HTTP_PORT = 8770
ORIGINS = {'http://127.0.0.1:5173', 'http://localhost:5173'}


def post_backend(event):
    """No network dependency and a bounded wait if backend is unavailable."""
    try:
        with socket.create_connection((HOST, 8765), timeout=0.3) as sock:
            sock.settimeout(0.3)
            sock.sendall((json.dumps(event, separators=(',', ':')) + '\n').encode())
            reply = sock.recv(512)
        return b'"ok":true' in reply or b'"ok": true' in reply
    except (OSError, ValueError):
        return False


class GazeState:
    def __init__(self):
        self.lock = threading.RLock()
        self.calibration = GazeCalibrator()
        self.face_at = None
        self.feature = None
        self.geometry = None
        self.geometry_at = None
        self.sequence = 0
        self.last_backend_ok = False
        self.predicted = None
        self.smoothed = None

    def observe(self, feature, now):
        with self.lock:
            self.feature = feature
            if feature is not None:
                self.face_at = now
                self.calibration.track(feature, now)
            self.sequence += 1
            raw = self.calibration.predict(feature)
            if raw is None:
                self.smoothed = None  # Never hold a stale gaze position after face loss.
            else:
                incoming = np.array(raw, dtype=float)
                self.smoothed = (incoming if self.smoothed is None
                                 else 0.7 * self.smoothed + 0.3 * incoming)
            self.predicted = tuple(self.smoothed) if self.smoothed is not None else None
            mapped = self.map_point(self.predicted, now)
            return {'type': 'gaze.point', 'source': 'mediapipe-gaze',
                    'frame_sequence': self.sequence,
                    'calibrated': self.calibration.calibrated,
                    'x': mapped[0] if mapped else None,
                    'y': mapped[1] if mapped else None}

    def map_point(self, raw, now):
        if raw is None or self.geometry is None or self.geometry_at is None:
            return None
        if now - self.geometry_at > 2.0:
            return None
        left, top, right, bottom = self.geometry
        x = (raw[0] - left) / (right - left)
        y = (raw[1] - top) / (bottom - top)
        if not (0 <= x <= 1 and 0 <= y <= 1):
            return None
        return x, y

    def health(self):
        with self.lock:
            now = time.monotonic()
            return {'face_visible': self.face_at is not None and now - self.face_at < 0.8,
                    'calibrated': self.calibration.calibrated,
                    'calibration_count': len(self.calibration.points),
                    'required_targets': 9,
                    'calibration_quality': self.calibration.quality,
                    'preview_geometry_ready': self.geometry_at is not None and now - self.geometry_at < 2.0,
                    'backend_connected': self.last_backend_ok,
                    'eye_features_live': self.feature is not None,
                    'predicted_screen_point': list(self.predicted) if self.predicted is not None else None}

    def apply(self, path, data):
        now = time.monotonic()
        with self.lock:
            if path == '/reset':
                if data:
                    raise ValueError('Reset has no parameters')
                self.calibration.reset()
                self.predicted = None
                self.smoothed = None
                self.geometry = None
                self.geometry_at = None
                return self.health()
            if path == '/capture':
                if set(data) != {'index', 'x', 'y', 'width', 'height'}:
                    raise ValueError('Expected index, x, y, width, height')
                self.calibration.capture(index=data['index'], x=data['x'], y=data['y'],
                                         width=data['width'], height=data['height'], now=now)
                return self.health()
            if path == '/geometry':
                if set(data) != {'rect', 'width', 'height'}:
                    raise ValueError('Expected preview rect and viewport dimensions')
                r = data['rect']
                if not isinstance(r, list) or len(r) != 4:
                    raise ValueError('Invalid preview rectangle')
                if any(type(v) not in (float, int) or not math.isfinite(v) or not 0 <= v <= 1 for v in r):
                    raise ValueError('Preview coordinates must be normalized')
                left, top, right, bottom = r
                if right - left < 0.05 or bottom - top < 0.05:
                    raise ValueError('Preview too small for gaze selection')
                w, h = data['width'], data['height']
                if type(w) not in (int, float) or type(h) not in (int, float):
                    raise ValueError('Invalid viewport dimensions')
                if self.calibration.viewport != (int(w), int(h)):
                    self.geometry = None
                    raise ValueError('Viewport changed or gaze not calibrated; recalibrate')
                self.geometry = (left, top, right, bottom)
                self.geometry_at = now
                return {'ok': True}
            raise ValueError('Unknown command')


class GazeHTTP(BaseHTTPRequestHandler):
    def _origin(self):
        origin = self.headers.get('Origin')
        return origin if origin in ORIGINS else None

    def _send(self, code, data):
        content = json.dumps(data, separators=(',', ':')).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        if self._origin():
            self.send_header('Access-Control-Allow-Origin', self._origin())
            self.send_header('Vary', 'Origin')
        self.send_header('Content-Length', str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def do_OPTIONS(self):
        if self._origin() is None or self.path not in ('/capture', '/reset', '/geometry'):
            self.send_error(403)
            return
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', self._origin())
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()

    def do_GET(self):
        if self.path != '/health' or self._origin() is None:
            self.send_error(403)
            return
        self._send(200, self.server.state.health())

    def do_POST(self):
        if self._origin() is None or self.path not in ('/capture', '/reset', '/geometry'):
            self.send_error(403)
            return
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 1024:
                raise ValueError('Invalid payload size')
            data = json.loads(self.rfile.read(length))
            if not isinstance(data, dict):
                raise ValueError('Expected JSON object')
            result = self.server.state.apply(self.path, data)
            self._send(200, result)
        except (ValueError, TypeError, OverflowError) as exc:
            self._send(422, {'error': str(exc)[:180]})

    def log_message(self, *_):
        pass


class LocalServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def run(args):
    import cv2
    import mediapipe as mp

    if not args.model.is_file() or args.model.stat().st_size < 100_000:
        raise RuntimeError('Face model missing. First run Download-Gaze-Model.cmd.')
    camera = cv2.VideoCapture(args.camera, cv2.CAP_DSHOW if sys.platform == 'win32' else cv2.CAP_ANY)
    if not camera.isOpened():
        raise RuntimeError(f'Face camera {args.camera} cannot open. Object camera 0 is used by YOLO; connect a second webcam or set HCI_GAZE_CAMERA.')
    state = GazeState()
    http = LocalServer((HOST, args.http_port), GazeHTTP)
    http.state = state
    thread = threading.Thread(target=http.serve_forever, daemon=True)
    thread.start()
    print(f'Gaze calibration: http://{HOST}:{args.http_port} (browser origin restricted)', flush=True)
    print(f'Face camera index {args.camera}. No face frames recorded, saved, or sent to game backend.', flush=True)
    print('Look at nine UI dots; adult clicks Capture after 1 second. Then gaze at objects in LARGE camera preview.', flush=True)
    vision = mp.tasks.vision
    opts = vision.FaceLandmarkerOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=str(args.model)),
        running_mode=vision.RunningMode.VIDEO, num_faces=1,
        min_face_detection_confidence=0.5, min_face_presence_confidence=0.5,
        min_tracking_confidence=0.5)
    last_ts = -1
    started = time.monotonic()
    last_send = 0.0
    last_log = 0.0
    try:
        with vision.FaceLandmarker.create_from_options(opts) as landmarker:
            while True:
                ok, frame = camera.read()
                if not ok:
                    # Pause rather than using an old frozen image to score.
                    state.observe(None, time.monotonic())
                    time.sleep(0.1)
                    continue
                image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                ts = max(last_ts+1, int((time.monotonic() - started)*1000))
                last_ts = ts
                result = landmarker.detect_for_video(
                    mp.Image(image_format=mp.ImageFormat.SRGB, data=image), ts)
                feature = eye_features(result.face_landmarks[0]) if len(result.face_landmarks) == 1 else None
                now = time.monotonic()
                event = state.observe(feature, now)
                if now - last_send >= 0.15:
                    state.last_backend_ok = post_backend(event)
                    last_send = now
                if now - last_log >= 3:
                    info = state.health()
                    print(f'Face={info["face_visible"]} calibration={info["calibration_count"]}/9 ready={info["calibrated"]} backend={info["backend_connected"]} geometry={info["preview_geometry_ready"]}', flush=True)
                    last_log = now
    except KeyboardInterrupt:
        print('Gaze tracking stopped.', flush=True)
    finally:
        camera.release()
        http.shutdown()
        http.server_close()
        thread.join(timeout=2)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--camera', type=int, default=1,
                   help='SECOND, player-facing webcam index (YOLO already owns object camera 0)')
    p.add_argument('--model', type=Path, default=Path('models/face_landmarker.task'))
    p.add_argument('--http-port', type=int, default=HTTP_PORT)
    args = p.parse_args()
    try:
        run(args)
    except (OSError, RuntimeError, ValueError, ImportError) as error:
        print(f'GAZE ERROR: {error}', file=sys.stderr, flush=True)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
