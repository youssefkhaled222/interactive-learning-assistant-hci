"""Real body skeleton tracking + DollarPy gesture recording/classification.
Hardware integration entry point; needs a downloaded model and a real webcam.
Run in project root:
  python backend/pose_tracker.py --model models/pose_landmarker.task --record-label swipe_left
  python backend/pose_tracker.py --model models/pose_landmarker.task --record-label swipe_right
  python backend/pose_tracker.py --model models/pose_landmarker.task
Press SPACE to capture a 1.8-second right-wrist motion. ESC to quit.
"""
import argparse
import json
from pathlib import Path
import time

import cv2
import mediapipe as mp
from dollarpy import Point, Template, Recognizer
from send_event import send

POSE_EDGES = [(11,12),(11,13),(13,15),(12,14),(14,16),(11,23),(12,24),
              (23,24),(23,25),(25,27),(24,26),(26,28)]
TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"


def model_templates():
    templates = []
    for path in TEMPLATE_DIR.glob("*.json"):
        pts = json.loads(path.read_text(encoding="utf-8"))
        if len(pts) >= 10:
            templates.append(Template(path.stem, [Point(x, y) for x, y in pts]))
    return templates


def maybe_send(e):
    try:
        send(e)
    except OSError:
        print("Broker not running; camera demo continues locally")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--record-label", choices=["swipe_left", "swipe_right"], default=None)
    args = parser.parse_args()
    if not Path(args.model).is_file():
        raise SystemExit("Model missing: download a compatible MediaPipe Pose Landmarker .task model first")
    camera = cv2.VideoCapture(args.camera, cv2.CAP_DSHOW)
    if not camera.isOpened():
        raise SystemExit("Camera not accessible. Close other apps using webcam; check --camera index.")
    maybe_send({"type":"camera.status", "ready":True, "source":"mediapipe"})
    options = mp.tasks.vision.PoseLandmarkerOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=args.model),
        running_mode=mp.tasks.vision.RunningMode.VIDEO,
        num_poses=1)
    trajectory, started = [], None
    start_clock = time.monotonic()
    last_visibility = None
    with mp.tasks.vision.PoseLandmarker.create_from_options(options) as landmarker:
        try:
            while True:
                ok, frame = camera.read()
                if not ok:
                    print("Camera read failed"); break
                frame = cv2.flip(frame, 1)
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                ts = int((time.monotonic() - start_clock) * 1000)
                result = landmarker.detect_for_video(img, ts)
                visible = bool(result.pose_landmarks)
                if visible != last_visibility:
                    maybe_send({"type":"pose.tracking","visible":visible,"source":"mediapipe"})
                    last_visibility = visible
                if visible:
                    lm = result.pose_landmarks[0]
                    h, w = frame.shape[:2]
                    for a, b in POSE_EDGES:
                        if lm[a].visibility > 0.4 and lm[b].visibility > 0.4:
                            cv2.line(frame, (int(lm[a].x*w), int(lm[a].y*h)),
                                     (int(lm[b].x*w), int(lm[b].y*h)), (0,255,0),2)
                    if started is not None and lm[16].visibility > 0.5:
                        trajectory.append([round(lm[16].x,5),round(lm[16].y,5)])
                if started is not None and time.monotonic() - started >= 1.8:
                    if len(trajectory) < 10:
                        print("Not enough visible right-wrist points; retry")
                    elif args.record_label:
                        TEMPLATE_DIR.mkdir(exist_ok=True)
                        outfile = TEMPLATE_DIR / (args.record_label + ".json")
                        outfile.write_text(json.dumps(trajectory, indent=2), encoding="utf-8")
                        print(f"Saved REAL recorded {args.record_label} template: {outfile}")
                    else:
                        templates = model_templates()
                        if len(templates) < 2:
                            print("Record both swipe_left and swipe_right templates first")
                        else:
                            name, score = Recognizer(templates).recognize([Point(x,y) for x,y in trajectory])
                            print("DollarPy prediction:", name, "similarity score:", score)
                            # Score is NOT a calibrated probability.
                            if name:
                                maybe_send({"type":"gesture.recognized", "name":name,
                                            "score":score, "source":"dollarpy"})
                    trajectory, started = [], None
                cv2.putText(frame, "SPACE: record/classify 1.8s | ESC: quit", (15,30),
                            cv2.FONT_HERSHEY_SIMPLEX, .58, (255,255,255),2)
                if started is not None:
                    cv2.putText(frame, "RECORDING...", (15,65), cv2.FONT_HERSHEY_SIMPLEX,
                                .8,(0,0,255),2)
                cv2.imshow("MediaPipe Pose + DollarPy", frame)
                key = cv2.waitKey(1) & 0xFF
                if key == 27: break
                if key == 32 and started is None:
                    trajectory, started = [], time.monotonic()
                    print("Recording 1.8 seconds; move your RIGHT WRIST clearly")
        finally:
            camera.release()
            cv2.destroyAllWindows()
            maybe_send({"type":"camera.status", "ready":False, "source":"mediapipe"})

if __name__ == "__main__":
    main()
