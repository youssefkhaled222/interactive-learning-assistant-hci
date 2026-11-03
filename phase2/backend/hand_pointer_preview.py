"""Real MediaPipe hand diagnostics using frames from the YOLO-owned webcam.

This module NEVER opens a camera or submits a gameplay selection. It observes
raw, same-camera JPEG frames from a loopback-only snapshot endpoint. This first
hardware check must pass before wiring genuine selections to the game engine.

Run with the existing MediaPipe environment while object_detector.py runs with
--stream; no new packages are required.
"""
import argparse
import json
import math
import socket
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

FRAME_URL = 'http://127.0.0.1:8767/hand-frame'
CLIENT_HEADER = 'local-hand-landmarker-v1'
HCI_REAL_PINCH_V4 = True


def send_hardware(event, timeout=0.65):
    """Best-effort local JSONL event with backend ACK; never fake success."""
    data = (json.dumps(event, separators=(',', ':')) + '\n').encode()
    try:
        with socket.create_connection(('127.0.0.1', 8765), timeout=timeout) as connection:
            connection.settimeout(timeout)
            connection.sendall(data)
            response = b''
            while not response.endswith(b'\n') and len(response) <= 8192:
                chunk = connection.recv(8192)
                if not chunk:
                    break
                response += chunk
        return json.loads(response) if response else {'ok': False, 'error':'No ACK'}
    except (OSError, ValueError) as exc:
        return {'ok':False, 'error':type(exc).__name__}



def landmark_xy(landmarks, idx):
    if len(landmarks) != 21:
        return None
    pt = landmarks[idx]
    x, y = float(pt.x), float(pt.y)
    if not math.isfinite(x) or not math.isfinite(y) or not (0 <= x <= 1 and 0 <= y <= 1):
        return None
    return (x, y)


def normalized_pinch_ratio(landmarks):
    """Use palm width as a size proxy; NaN, missing data, tiny palms fail closed."""
    thumb = landmark_xy(landmarks, 4)
    index = landmark_xy(landmarks, 8)
    index_mcp = landmark_xy(landmarks, 5)
    pinky_mcp = landmark_xy(landmarks, 17)
    if None in (thumb, index, index_mcp, pinky_mcp):
        return None
    palm_width = math.dist(index_mcp, pinky_mcp)
    if not math.isfinite(palm_width) or palm_width < 0.035:
        return None
    return math.dist(thumb, index) / palm_width


class PinchState:
    """Hysteretic pinch indicator only: not a game selection/debouncer."""
    def __init__(self, close_threshold=0.40, release_threshold=0.65):
        if not (0 < close_threshold < release_threshold):
            raise ValueError('release threshold must exceed close threshold')
        self.close_threshold = close_threshold
        self.release_threshold = release_threshold
        self.closed = False

    def update(self, ratio):
        if ratio is None or not math.isfinite(ratio) or ratio < 0:
            self.closed = False
        elif self.closed:
            if ratio >= self.release_threshold:
                self.closed = False
        elif ratio <= self.close_threshold:
            self.closed = True
        return self.closed


def post_hand_state(frame_url, sequence, pointer, pinching, timeout=1):
    """Display-only hand report to local YOLO preview service; not a game event."""
    url = frame_url.rsplit('/', 1)[0] + '/hand-state'
    body = json.dumps({'frame_sequence': sequence,
                       'pointer': list(pointer) if pointer is not None else None,
                       'pinching': bool(pinching)}).encode('utf-8')
    req = Request(url, data=body, method='POST', headers={
        'X-HCI-Sensor-Client': CLIENT_HEADER,
        'Content-Type': 'application/json',
        'Cache-Control': 'no-store'})
    with urlopen(req, timeout=timeout) as resp:
        return resp.status == 204


def boxes_at_point(detections, pointer):
    """Display-only overlap check; NOT sufficient for selection authorization."""
    if pointer is None:
        return []
    x, y = pointer
    return [d['object'] for d in detections if
            d['box']['x_min'] <= x <= d['box']['x_max'] and
            d['box']['y_min'] <= y <= d['box']['y_max']]


def fetch_frame(url, last_sequence=None, timeout=2):
    req = Request(url, headers={'X-HCI-Sensor-Client': CLIENT_HEADER,
                                'Cache-Control': 'no-store'})
    with urlopen(req, timeout=timeout) as resp:
        sequence = int(resp.headers['X-Frame-Sequence'])
        if sequence < 1:
            raise ValueError('invalid frame sequence')
        if last_sequence is not None and sequence <= last_sequence:
            return None, sequence, []
        payload = resp.read(1_000_001)
        if not payload or len(payload) > 1_000_000:
            raise ValueError('invalid or oversized local JPEG')
        detections = json.loads(resp.headers.get('X-HCI-Detections', '[]'))
        if not isinstance(detections, list) or len(detections) > 10:
            raise ValueError('Invalid YOLO frame metadata')
        return payload, sequence, detections


def run(args):
    import cv2
    import numpy as np
    import mediapipe as mp

    base = mp.tasks.BaseOptions(model_asset_path=str(args.model))
    vision = mp.tasks.vision
    options = vision.HandLandmarkerOptions(base_options=base,
        running_mode=vision.RunningMode.VIDEO, num_hands=1,
        min_hand_detection_confidence=.5,
        min_hand_presence_confidence=.5, min_tracking_confidence=.5)
    pinch = PinchState()
    last_sequence = None
    first_ts = time.monotonic()
    last_timestamp = -1
    last_log = 0
    camera_announced = False
    last_broker_warning = 0
    print('Hand preview: real same-camera frames; backend alone authorizes game.select.', flush=True)
    print('Press ESC or Q in the hand preview window to stop.', flush=True)
    if args.enable_gameplay:
        print('REAL GAMEPLAY ENABLED: hardware hand pointer → guarded broker selection', flush=True)
    with vision.HandLandmarker.create_from_options(options) as detector:
        while True:
            try:
                jpeg, sequence, detections = fetch_frame(args.frame_url, last_sequence)
            except (OSError, HTTPError, URLError, ValueError) as exc:
                pinch.update(None)
                if time.monotonic() - last_log >= 2:
                    print(f'Frame source unavailable: {exc}', flush=True)
                    last_log = time.monotonic()
                if cv2.waitKey(50) & 0xff in (27, ord('q')):
                    break
                time.sleep(0.15)
                continue
            if jpeg is None:
                if cv2.waitKey(1) & 0xff in (27, ord('q')):
                    break
                time.sleep(0.025)
                continue
            last_sequence = sequence
            image = cv2.imdecode(np.frombuffer(jpeg, dtype=np.uint8), cv2.IMREAD_COLOR)
            if image is None:
                continue
            rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            timestamp = max(last_timestamp + 1, int((time.monotonic() - first_ts) * 1000))
            last_timestamp = timestamp
            observation = detector.detect_for_video(
                mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb), timestamp)
            landmarks = observation.hand_landmarks[0] if observation.hand_landmarks else []
            pointer = landmark_xy(landmarks, 8)
            ratio = normalized_pinch_ratio(landmarks)
            closed = pinch.update(ratio)
            if args.enable_gameplay:
                # Only actual MediaPipe output from real shared camera frames
                # can drive this adapter. Broker validates the current YOLO box.
                now = time.monotonic()
                if not camera_announced:
                    status_ack = send_hardware({'type':'camera.status','ready':True,
                                                'source':'mediapipe-hand'})
                    camera_announced = bool(status_ack.get('ok'))
                ack = send_hardware({'type':'hand.pointer', 'source':'mediapipe-hand',
                    'x':pointer[0] if pointer is not None else None,
                    'y':pointer[1] if pointer is not None else None,
                    'pinching':closed, 'frame_sequence':sequence})
                if not ack.get('ok'):
                    camera_announced = False  # Reannounce camera on broker restart.
                    if now - last_broker_warning > 2:
                        print(f'Hand gameplay bridge rejected/unavailable: {ack}', flush=True)
                        last_broker_warning = now
            try:
                post_hand_state(args.frame_url, sequence, pointer, closed)
            except (OSError, HTTPError, URLError, ValueError):
                # Overlay is informational; the hand tracker must keep running.
                pass
            h, w = image.shape[:2]
            for detection in detections:
                try:
                    box = detection['box']
                    x1, y1 = int(box['x_min'] * w), int(box['y_min'] * h)
                    x2, y2 = int(box['x_max'] * w), int(box['y_max'] * h)
                    cv2.rectangle(image, (x1, y1), (x2, y2), (0, 200, 90), 2)
                    cv2.putText(image, f"{detection['object']} {detection['confidence']:.2f}",
                                (x1, max(54, y1 - 6)), cv2.FONT_HERSHEY_SIMPLEX,
                                .5, (0, 200, 90), 2)
                except (ValueError, KeyError, TypeError):
                    continue
            if pointer is not None:
                cv2.circle(image, (int(pointer[0]*w), int(pointer[1]*h)),
                           12, (0, 0, 255) if closed else (0, 255, 0), 3)
            cv2.putText(image,
                f'Hand={pointer is not None} Pinch={closed} Ratio={ratio:.2f}' if ratio is not None
                else f'Hand={pointer is not None} Pinch=False',
                (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255,255,255), 2)
            if time.monotonic() - last_log >= 1.5:
                print(json.dumps({'hardware':'mediapipe-hand', 'frame_sequence':sequence,
                    'hand_visible':pointer is not None, 'index_point':pointer,
                    'pinch_ratio':round(ratio,3) if ratio is not None else None,
                    'pinching':closed, 'yolo_objects':[d.get('object') for d in detections],
                    'pointer_over':boxes_at_point(detections, pointer),
                    'gameplay_events_enabled':args.enable_gameplay}), flush=True)
                last_log = time.monotonic()
            if not args.no_window:
                cv2.imshow('Find the Object - Shared Camera Hand Pointer', image)
                if cv2.waitKey(1) & 0xff in (27, ord('q')):
                    break
    if args.enable_gameplay:
        send_hardware({'type':'camera.status','ready':False,'source':'mediapipe-hand'})
    cv2.destroyAllWindows()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--model', default='models/hand_landmarker.task')
    p.add_argument('--frame-url', default=FRAME_URL)
    p.add_argument('--no-window', action='store_true')
    p.add_argument('--enable-gameplay', action='store_true',
                   help='Opt in to real hand.pointer events; backend validates selections')
    args = p.parse_args()
    try:
        run(args)
    except KeyboardInterrupt:
        pass
    except (OSError, RuntimeError, ValueError, ImportError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
