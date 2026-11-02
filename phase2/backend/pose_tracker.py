"""Adult validation tool for the existing Phase II application (not child gameplay).
SPACE starts a countdown, then one recording; ESC quits. Only live accepted predictions emit events.
See docs/MOSTAFA_DEMO.md. No game.select, face video, or automatic answers.
"""
import argparse
import hashlib
import json
import math
import platform
import sys
import time
from pathlib import Path

from gesture_data import (LABEL, classify, evaluate, load_samples, make_sample,
                          save_sample, validate_sample)
from send_event import send
from tracker_events import EventPublisher

ROOT = Path(__file__).resolve().parent.parent
POSE_EDGES = [(0,1),(1,2),(2,3),(3,7),(0,4),(4,5),(5,6),(6,8),(9,10),
              (11,12),(11,13),(13,15),(15,17),(15,19),(15,21),(17,19),
              (12,14),(14,16),(16,18),(16,20),(16,22),(18,20),
              (11,23),(12,24),(23,24),(23,25),(25,27),(27,29),(29,31),(27,31),
              (24,26),(26,28),(28,30),(30,32),(28,32)]
HAND_EDGES = [(0,1),(1,2),(2,3),(3,4),(0,5),(5,6),(6,7),(7,8),
              (5,9),(9,10),(10,11),(11,12),(9,13),(13,14),(14,15),(15,16),
              (13,17),(0,17),(17,18),(18,19),(19,20)]


class FrameClock:
    def __init__(self):
        self.start = time.monotonic()
        self.last = -1

    def next(self):
        self.last = max(self.last + 1, int((time.monotonic() - self.start) * 1000))
        return self.last


class Capture:
    def __init__(self, seconds=1.8):
        self.seconds = seconds
        self.started = None
        self.points = []
        self.frame_size = None
        self.armed_until = None

    def arm(self, now, delay):
        if self.started is not None or self.armed_until is not None:
            return
        self.points = []
        self.armed_until = now + delay

    def start(self, now, size):
        self.started, self.points, self.frame_size = now, [], size

    def update(self, now, point, size):
        if self.armed_until is not None:
            if now < self.armed_until:
                return None  # Keyboard/repositioning movement is not recorded.
            self.armed_until = None
            if point is None:
                raise ValueError('Recording cancelled: show tracked wrist/fingertip at GO; retry')
            self.start(now, size)
        if self.started is None:
            return None
        if point is None or size != self.frame_size:
            self.started = None
            self.points = []
            raise ValueError('Recording cancelled: tracking lost or image size changed; retry')
        t = now - self.started
        if not self.points or t > self.points[-1][2]:
            self.points.append([point[0], point[1], t])
        if t >= self.seconds:
            points, self.points, self.started = self.points, [], None
            return points
        return None


def usable(lm, visibility=False):
    return (math.isfinite(lm.x) and math.isfinite(lm.y) and
            0 <= lm.x <= 1 and 0 <= lm.y <= 1 and
            (not visibility or (lm.visibility is not None and lm.visibility >= .5)))


def pose_visible(landmarks):
    return len(landmarks) == 33 and all(usable(landmarks[i], True) for i in (11, 12, 23, 24))


def create_landmarker(mp, model, channel):
    base = mp.tasks.BaseOptions(model_asset_path=str(model))
    vision = mp.tasks.vision
    if channel == 'right_wrist':
        options = vision.PoseLandmarkerOptions(base_options=base,
            running_mode=vision.RunningMode.VIDEO, num_poses=1,
            min_pose_detection_confidence=.5, min_pose_presence_confidence=.5,
            min_tracking_confidence=.5)
        return vision.PoseLandmarker.create_from_options(options)
    options = vision.HandLandmarkerOptions(base_options=base,
        running_mode=vision.RunningMode.VIDEO, num_hands=1,
        min_hand_detection_confidence=.5, min_hand_presence_confidence=.5,
        min_tracking_confidence=.5)
    return vision.HandLandmarker.create_from_options(options)


def model_check(model, channel):
    if not model.is_file():
        raise ValueError(f'Model missing: {model}. Run backend/download_tracker_model.py')
    if not 100_000 <= model.stat().st_size <= 100_000_000:
        raise ValueError('Model size is invalid; download the official .task bundle again')
    import mediapipe as mp
    try:
        with create_landmarker(mp, model, channel):
            pass
    except Exception as exc:
        raise ValueError(f'Cannot load {channel} model: {exc}') from exc
    digest = hashlib.sha256(model.read_bytes()).hexdigest()
    print(json.dumps(dict(model=str(model), sha256=digest,
        mediapipe=mp.__version__, python=sys.version.split()[0], os=platform.platform())))
    return digest


def open_camera(cv2, index, backend):
    api = {'auto': cv2.CAP_ANY, 'dshow': cv2.CAP_DSHOW, 'msmf': cv2.CAP_MSMF}[backend]
    camera = cv2.VideoCapture(index, api)
    if not camera.isOpened():
        camera.release()
        raise ValueError(f'Camera {index} unavailable ({backend}). Close Teams/Zoom; check Windows camera permission; try --camera 1 or --backend msmf')
    return camera


def camera_check(args):
    import cv2
    camera = open_camera(cv2, args.camera, args.backend)
    try:
        for _ in range(30):
            ok, frame = camera.read()
            if ok and frame is not None and frame.size:
                print(json.dumps(dict(camera=args.camera, backend=camera.getBackendName(),
                    frame_size=[frame.shape[1],frame.shape[0]], opencv=cv2.__version__,
                    time=time.strftime('%Y-%m-%d %H:%M:%S'), result='FRAME_READ_OK')))
                return
        raise ValueError('Camera opened but no usable frame arrived')
    finally:
        camera.release()


def draw(cv2, frame, landmarks, pose):
    h, w = frame.shape[:2]
    edges = POSE_EDGES if pose else HAND_EDGES
    for a, b in edges:
        if max(a,b) < len(landmarks) and usable(landmarks[a],pose) and usable(landmarks[b],pose):
            cv2.line(frame,(int(landmarks[a].x*w),int(landmarks[a].y*h)),
                     (int(landmarks[b].x*w),int(landmarks[b].y*h)),(50,220,80),2)
    for p in landmarks:
        if usable(p,pose):
            cv2.circle(frame,(int(p.x*w),int(p.y*h)),3,(0,210,255),-1)


def run_live(args, digest):
    import cv2
    import mediapipe as mp
    pose = args.channel == 'right_wrist'
    training = [] if args.record_label else load_samples(args.data_dir, args.channel, 'train')
    if not args.record_label and len({s['label'] for s in training}) < 2:
        raise ValueError('Record at least two gesture classes before live classification')
    publisher = None if args.offline else EventPublisher(send, args.event_log)
    camera = None
    landmarker = None
    capture = Capture(args.seconds)
    clock = FrameClock()
    notice = 'SPACE: capture | ESC: exit | Preview is NOT mirrored'
    saved_count = 0
    try:
        # Load model before opening camera. Every subsequent failure reaches finally.
        landmarker = create_landmarker(mp, args.model, args.channel)
        camera = open_camera(cv2, args.camera, args.backend)
        while True:
            ok, frame = camera.read()
            if not ok or frame is None or not frame.size:
                raise ValueError('Camera stopped delivering frames; reconnect and restart')
            if publisher:
                publisher.status('camera.status', True)
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            result = landmarker.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB,data=rgb),clock.next())
            detections = result.pose_landmarks if pose else result.hand_landmarks
            landmarks = detections[0] if detections else []
            visible = pose_visible(landmarks) if pose else len(landmarks) == 21
            if publisher and pose:
                publisher.status('pose.tracking', visible)
            point = None
            index = 16 if pose else (4 if args.channel == 'thumb' else 8)
            if visible and usable(landmarks[index], pose):
                point = (landmarks[index].x, landmarks[index].y)
            draw(cv2, frame, landmarks, pose)
            now = time.monotonic()
            size = (frame.shape[1],frame.shape[0])
            try:
                points = capture.update(now, point, size)
                if points is not None:
                    sample = make_sample(points, args.record_label or 'live', args.split,
                        args.channel, size, args.camera, digest)
                    if args.record_label:
                        filename = save_sample(args.data_dir, sample)
                        saved_count += 1
                        notice = f'Saved {args.split}: {args.record_label} (this run: {saved_count})'
                        print(json.dumps(dict(saved=str(filename),sample_id=sample['sample_id'],samples=len(points))),flush=True)
                    else:
                        prediction = classify(sample, training, args.threshold)
                        notice = f"{prediction['predicted']} score={prediction['score']:.3f} accepted={prediction['accepted']}"
                        print(json.dumps(prediction),flush=True)
                        if publisher:
                            publisher.gesture(prediction)
            except ValueError as exc:
                notice = str(exc)
                print(notice,flush=True)
            if point is not None:
                center = (int(point[0]*size[0]), int(point[1]*size[1]))
                cv2.circle(frame, center, 12, (255,255,0), 3)
                marker = 'RIGHT WRIST' if pose else args.channel.upper() + ' TIP'
                cv2.putText(frame, marker, (max(0,center[0]-55),max(120,center[1]-18)),
                    cv2.FONT_HERSHEY_SIMPLEX,.5,(255,255,0),2)
            if capture.started is not None:
                for a, b in zip(capture.points, capture.points[1:]):
                    cv2.line(frame, (int(a[0]*size[0]),int(a[1]*size[1])),
                        (int(b[0]*size[0]),int(b[1]*size[1])), (0,180,255), 3)
            status = notice
            if capture.armed_until is not None:
                status = f'GET READY {math.ceil(capture.armed_until-now)} - position your hand'
            elif capture.started is not None:
                remaining = max(0, capture.seconds-(now-capture.started))
                status = f'GO! RECORDING {remaining:.1f}s - one stroke, then HOLD'
            lines = [f'{args.channel} | camera={args.camera} | point={point is not None}',
                f'{args.split}: {args.record_label or "live"} | SPACE: ready | ESC: quit',
                status,
                time.strftime('%Y-%m-%d %H:%M:%S') + ' | Unmirrored']
            for row, text in enumerate(lines):
                cv2.putText(frame,text,(10,25+row*24),cv2.FONT_HERSHEY_SIMPLEX,.52,(255,255,255),2)
            cv2.imshow('Mostafa - MediaPipe + DollarPy (adult validation)', frame)
            key = cv2.waitKey(1) & 0xff
            if key == 27 or cv2.getWindowProperty('Mostafa - MediaPipe + DollarPy (adult validation)',cv2.WND_PROP_VISIBLE) < 1:
                break
            if key == 32 and capture.started is None and capture.armed_until is None:
                if point is None:
                    notice = 'Show torso + right wrist' if pose else 'Show ONE hand and selected fingertip'
                else:
                    capture.arm(now,args.countdown)
    finally:
        if camera is not None:
            camera.release()
        if landmarker is not None:
            landmarker.close()
        cv2.destroyAllWindows()
        if publisher:
            if pose:
                publisher.status('pose.tracking', False)
            publisher.status('camera.status', False)
            publisher.close()


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--model', type=Path)
    p.add_argument('--camera', type=int, default=0)
    p.add_argument('--backend', choices=['auto','dshow','msmf'], default='dshow' if sys.platform=='win32' else 'auto')
    p.add_argument('--channel', choices=['right_wrist','thumb','index'], default='right_wrist')
    p.add_argument('--record-label')
    p.add_argument('--split', choices=['train','test'], default='train')
    p.add_argument('--data-dir', type=Path, default=ROOT/'templates'/'local')
    p.add_argument('--seconds', type=float, default=1.8)
    p.add_argument('--countdown', type=float, default=3, help='Preparation time after SPACE, before recording (0..10 seconds)')
    p.add_argument('--threshold', type=float, default=.5)
    p.add_argument('--consenting-adult', action='store_true', help='Confirm adult agrees to local landmark recording')
    p.add_argument('--offline', action='store_true', help='Disable broker events')
    p.add_argument('--event-log', type=Path, default=ROOT/'recordings'/'tracker_events.jsonl')
    p.add_argument('--check-camera', action='store_true')
    p.add_argument('--check-model', action='store_true')
    p.add_argument('--evaluate', action='store_true')
    p.add_argument('--replay', type=Path, help='Classify one saved test recording; NEVER emits broker events')
    p.add_argument('--min-test', type=int, default=5)
    p.add_argument('--report', type=Path)
    return p


def main(argv=None):
    p = parser()
    args = p.parse_args(argv)
    if not math.isfinite(args.seconds) or not .5 <= args.seconds <= 10:
        p.error('--seconds must be 0.5..10')
    if not math.isfinite(args.countdown) or not 0 <= args.countdown <= 10:
        p.error('--countdown must be 0..10')
    if not math.isfinite(args.threshold) or not 0 <= args.threshold <= 1:
        p.error('--threshold must be 0..1')
    if args.camera < 0 or args.min_test < 1:
        p.error('Camera must be nonnegative; --min-test must be positive')
    if args.record_label and not LABEL.fullmatch(args.record_label):
        p.error('Invalid --record-label')
    if sum(bool(x) for x in [args.check_camera,args.check_model,args.evaluate,args.replay]) > 1:
        p.error('Choose only one check/evaluate/replay operation')
    try:
        if args.evaluate or args.replay:
            training = load_samples(args.data_dir,args.channel,'train')
            if args.replay:
                sample = validate_sample(json.loads(args.replay.read_text(encoding='utf-8')))
                if sample['split'] != 'test':
                    raise ValueError('Replay requires a held-out test recording')
                from gesture_data import fingerprint
                if any(s['sample_id']==sample['sample_id'] or fingerprint(s)==fingerprint(sample) for s in training):
                    raise ValueError('Train/test leakage in replay')
                report = dict(operation='offline replay; no events', **classify(sample,training,args.threshold))
            else:
                report = evaluate(training,load_samples(args.data_dir,args.channel,'test'),args.threshold,args.min_test)
            print(json.dumps(report,indent=2))
            if args.report:
                args.report.parent.mkdir(parents=True,exist_ok=True)
                args.report.write_text(json.dumps(report,indent=2),encoding='utf-8')
            return 0
        if args.check_camera:
            camera_check(args)
            return 0
        args.model = args.model or ROOT/'models'/('pose_landmarker.task' if args.channel=='right_wrist' else 'hand_landmarker.task')
        digest = model_check(args.model,args.channel)
        if args.check_model:
            return 0
        if not args.consenting_adult:
            raise ValueError('Live validation requires --consenting-adult after the adult agrees')
        if args.channel != 'right_wrist' and not args.offline:
            raise ValueError('Lab shape exercise is offline: use --offline; no invented pose event for a hand')
        run_live(args,digest)
        return 0
    except (ValueError,OSError,ImportError,RuntimeError) as exc:
        print(f'ERROR: {exc}',file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130


if __name__ == '__main__':
    raise SystemExit(main())
