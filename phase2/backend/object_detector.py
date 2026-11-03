"""Standalone, real webcam/image detector for the Phase I object set.

This is an *independent hardware proof*, not a gameplay selection module.
Nothing here sends synthetic game.select events to the backend. Because the
approved experiment needs two camera roles, do not run this on camera 0 at the
same time as pose_tracker.py unless a second camera is available.

Install Ultralytics in a separate environment. See docs/OBJECT_DETECTION.md.
"""

import argparse
import json
import math
import time
from pathlib import Path

SUPPORTED_OBJECTS = frozenset({"apple", "cup", "book"})
COCO_CLASS_IDS = {"cup": 41, "apple": 47, "book": 73}


def supported_class_indices(model_names):
    """Validate a model's label map; reject checkpoints without our classes."""
    mapping = dict(enumerate(model_names)) if not isinstance(model_names, dict) else model_names
    found = {}
    for index, label in mapping.items():
        if isinstance(label, str) and label.lower().strip() in SUPPORTED_OBJECTS:
            found[label.lower().strip()] = int(index)
    missing = SUPPORTED_OBJECTS.difference(found)
    if missing:
        raise ValueError("Model is missing expected object labels: " + ", ".join(sorted(missing)))
    return [found[name] for name in ("apple", "cup", "book")]


def _scalar(value):
    # PyTorch Tensor and NumPy scalar and one-element arrays are supported.
    if hasattr(value, "item"):
        return value.item()
    return value


def normalize_box(xyxy, width, height):
    """Convert detector pixels into normalized bounding boxes in [0,1]."""
    if not isinstance(width, int) or not isinstance(height, int) or width <= 0 or height <= 0:
        raise ValueError("Frame dimensions must be positive integers")
    if len(xyxy) != 4:
        raise ValueError("Bounding box needs four coordinates")
    coords = [float(_scalar(v)) for v in xyxy]
    if not all(math.isfinite(v) for v in coords):
        raise ValueError("Bounding box coordinates must be finite")
    x1, y1, x2, y2 = coords
    if x2 <= x1 or y2 <= y1:
        raise ValueError("Empty or inverted bounding box")
    clamped = [max(0.0, min(1.0, v / size)) for v, size in zip(coords, (width, height, width, height))]
    if clamped[2] <= clamped[0] or clamped[3] <= clamped[1]:
        return None  # Entire detection is outside the image.
    return {"x_min": round(clamped[0], 4), "y_min": round(clamped[1], 4),
            "x_max": round(clamped[2], 4), "y_max": round(clamped[3], 4)}


def parse_detections(result, width, height, min_confidence=0.35):
    """Extract real model outputs; no hardcoded 'detected' objects."""
    if not 0 < min_confidence <= 1:
        raise ValueError("min_confidence must be in (0, 1]")
    names = result.names
    mapping = dict(enumerate(names)) if not isinstance(names, dict) else names
    detections = []
    for item in result.boxes:
        class_idx = int(_scalar(item.cls[0]))
        label = str(mapping.get(class_idx, "")).lower().strip()
        if label not in SUPPORTED_OBJECTS:
            continue
        confidence = float(_scalar(item.conf[0]))
        if not math.isfinite(confidence) or confidence < min_confidence or confidence > 1:
            continue
        box_pixels = [float(_scalar(v)) for v in item.xyxy[0]]
        box = normalize_box(box_pixels, width, height)
        if box is not None:
            detections.append({"object": label, "confidence": round(confidence, 4), "box": box})
    return sorted(detections, key=lambda d: d["confidence"], reverse=True)


def preview_record(detections, width, height):
    """Local diagnostic JSON. NOT YET accepted as an engine/TCP event."""
    return {"kind": "detector.preview.v1", "source": "yolo", "frame_width": width,
            "frame_height": height, "detections": detections}


def draw_detections(frame, detections, cv2):
    height, width = frame.shape[:2]
    for detection in detections:
        b = detection["box"]
        x1, y1 = int(b["x_min"] * width), int(b["y_min"] * height)
        x2, y2 = int(b["x_max"] * width), int(b["y_max"] * height)
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 200, 90), 2)
        cv2.putText(frame, f'{detection["object"]} {detection["confidence"]:.2f}',
                    (x1, max(18, y1 - 6)), cv2.FONT_HERSHEY_SIMPLEX, .6, (0, 200, 90), 2)
    return frame


def run(args):
    # Deferred imports make all geometry/protocol tests work without GPU, torch,
    # model weights, or an available webcam.
    import cv2
    from ultralytics import YOLO

    model = YOLO(args.model)
    indices = supported_class_indices(model.names)
    print("Real detection model loaded. Objects: apple, cup, book. ESC/Q to exit.", flush=True)
    if args.image is not None:
        if args.publish:
            raise SystemExit("--publish is only supported in live webcam mode")
        frame = cv2.imread(str(args.image))
        if frame is None:
            raise SystemExit(f"Cannot read image: {args.image}")
        h, w = frame.shape[:2]
        prediction = model.predict(frame, classes=indices, conf=args.min_confidence,
                                   imgsz=args.image_size, device=args.device, verbose=False)[0]
        detections = parse_detections(prediction, w, h, args.min_confidence)
        print(json.dumps(preview_record(detections, w, h), ensure_ascii=False), flush=True)
        if args.save_annotated:
            dest = Path(args.save_annotated)
            dest.parent.mkdir(parents=True, exist_ok=True)
            cv2.imwrite(str(dest), draw_detections(frame, detections, cv2))
            print(f"Annotated image saved: {dest}", flush=True)
        return

    capture = cv2.VideoCapture(args.camera, cv2.CAP_DSHOW)
    if not capture.isOpened():
        raise SystemExit(f"Cannot open webcam index {args.camera}. Close Camera/MediaPipe first.")
    capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    preview_server = None
    if args.stream:
        from camera_preview import start_preview
        try:
            preview_server = start_preview(port=args.stream_port)
        except OSError as exc:
            capture.release()
            raise SystemExit(f'Cannot start local camera preview on port {args.stream_port}: {exc}') from exc
        print(f'Local camera preview: http://127.0.0.1:{args.stream_port}/video (React only)', flush=True)
    last_labels = None
    frame_num = 0
    last_publish = 0.0
    if args.publish:
        from send_event import send

        def publish(active, objects):
            try:
                ack = send({"type": "objects.detected", "source": "yolo",
                            "active": active, "detections": objects})
                if not ack.get("ok"):
                    print(f"Detection broker rejected event: {ack}", flush=True)
            except OSError as exc:
                print(f"Detection broker unavailable: {exc}", flush=True)
    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                print("Webcam stopped supplying frames.", flush=True)
                break
            h, w = frame.shape[:2]
            prediction = model.predict(frame, classes=indices, conf=args.min_confidence,
                                       imgsz=args.image_size, device=args.device, verbose=False)[0]
            detections = parse_detections(prediction, w, h, args.min_confidence)
            labels = tuple(sorted({d["object"] for d in detections}))
            if args.publish and (time.monotonic() - last_publish >= 0.35):
                publish(True, detections)
                last_publish = time.monotonic()
            frame_num += 1
            if labels != last_labels or (args.log_every and frame_num % args.log_every == 0):
                print(json.dumps(preview_record(detections, w, h), ensure_ascii=False), flush=True)
                last_labels = labels
            # Publish the SAME camera frame for MediaPipe before drawing boxes.
            # The MediaPipe process must never open camera 0 independently.
            if preview_server is not None:
                raw_ok, raw_jpeg = cv2.imencode(
                    ".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                if raw_ok:
                    preview_server.buffer.publish_raw(raw_jpeg.tobytes(), detections=detections)
            draw_detections(frame, detections, cv2)
            cv2.putText(frame, "Real YOLO detections | ESC/Q = exit", (8, 24),
                        cv2.FONT_HERSHEY_SIMPLEX, .48, (255, 255, 255), 2)
            # Hand landmarks are from the SAME camera, reported by MediaPipe.
            # Visualization only: stale/invalid reports fail closed and never score.
            if preview_server is not None:
                hand = preview_server.buffer.recent_hand()
                if hand and hand['pointer'] is not None:
                    px = int(hand['pointer'][0] * w)
                    py = int(hand['pointer'][1] * h)
                    cv2.circle(frame, (px, py), 12,
                               (0, 0, 255) if hand['pinching'] else (0, 255, 0), 3)
                    cv2.putText(frame, 'PINCH' if hand['pinching'] else 'FINGER',
                                (min(w-80, max(0,px+12)), max(28,py-12)),
                                cv2.FONT_HERSHEY_SIMPLEX, .5, (255,255,255), 2)
            if preview_server is not None:
                success, encoded = cv2.imencode('.jpg', frame,
                                               [cv2.IMWRITE_JPEG_QUALITY, 75])
                if success:
                    preview_server.buffer.publish(encoded.tobytes())
            if not args.no_window:
                cv2.imshow("Find the Object - Real Detection (standalone)", frame)
                if (cv2.waitKey(1) & 0xFF) in (27, ord("q")):
                    break
    except KeyboardInterrupt:
        print('Stopping detector and local camera preview.', flush=True)
    finally:
        if preview_server is not None:
            preview_server.close()
        if args.publish:
            publish(False, [])
        capture.release()
        if not args.no_window:
            cv2.destroyAllWindows()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--image", type=Path, help="Optional still-photo mode instead of webcam")
    parser.add_argument("--model", default="yolo11n.pt", help="Pretrained checkpoint; downloaded first time if absent")
    parser.add_argument("--min-confidence", type=float, default=.35)
    parser.add_argument("--image-size", type=int, default=640)
    parser.add_argument("--device", default="cpu", help="Start with cpu; CUDA only after verification")
    parser.add_argument("--log-every", type=int, default=60, help="Print diagnostic detection JSON every N frames")
    parser.add_argument("--publish", action="store_true", help="Publish real detection metadata to local TCP 127.0.0.1:8765")
    parser.add_argument("--stream", action="store_true", help="Serve annotated YOLO webcam frames to the local React preview (no answer selection)")
    parser.add_argument("--stream-port", type=int, default=8767, help="Local preview port (default 8767)")
    parser.add_argument("--no-window", action="store_true", help="Run without a separate OpenCV window; stop with Ctrl+C")
    parser.add_argument("--save-annotated", type=Path, help="Explicitly save annotated still image (not webcam)")
    args = parser.parse_args()
    if args.stream and args.image is not None:
        parser.error("--stream is only supported in webcam mode")
    if args.stream_port < 1 or args.stream_port > 65535:
        parser.error("stream-port must be in 1..65535")
    if args.image_size < 160 or args.image_size > 1280:
        parser.error("image-size should be between 160 and 1280")
    if args.log_every < 0:
        parser.error("log-every cannot be negative")
    if not 0 < args.min_confidence <= 1:
        parser.error("min-confidence must be in (0, 1]")
    run(args)


if __name__ == "__main__":
    main()
