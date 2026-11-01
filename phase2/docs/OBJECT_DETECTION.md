# Real Object Detection — Separate Hardware Feasibility Test

**Purpose.** This module is an experimental standalone component to validate
real object localization for the Phase I *Find the Object* design. It is NOT
the final gameplay implementation, a trained project-specific model, eye gaze
tracking, or a substitute for the Phase II grading requirements. It does not
send `game.select` and cannot mark a question as answered.

## Why use this model?

A COCO-pretrained YOLO11n model (`yolo11n.pt`) recognizes object categories
`apple`, `cup`, and `book` (COCO class IDs 47, 41, 73). These are *model
categories*, not proof that the actual physical props are reliably detected.
Test each real item. Books in particular can be difficult to recognize.

## Environment (Windows PowerShell)

Ultralytics depends on PyTorch and installs an OpenCV distribution. Avoid
introducing conflicting `cv2` wheels into our existing MediaPipe virtualenv.
Create a separate test virtualenv **outside the Git repository**:

```powershell
cd C:\Users\youss\Projects\interactive-learning-assistant-hci\phase2
py -3.11 -m venv "$HOME\Projects\.venv-hci-detector"
& "$HOME\Projects\.venv-hci-detector\Scripts\python.exe" -m pip install ultralytics
& "$HOME\Projects\.venv-hci-detector\Scripts\python.exe" -m pip check
```

The first run may download `yolo11n.pt` to the current directory. It is ignored
by the Phase II `.gitignore` and should be retained on the demonstration laptop.
Weights may be copied into the permitted Moodle submission when appropriate,
subject to file-size and license restrictions. Offline demos must preload weights.

## Live webcam run

Close the Windows Camera app and `pose_tracker.py` first; Windows currently
reports only one webcam on this laptop.

```powershell
& "$HOME\Projects\.venv-hci-detector\Scripts\python.exe" backend\object_detector.py --model yolo11n.pt --camera 0 --device cpu
```

Put **a real apple**, **a physical book**, and **a cup** in view one at a time,
then together. Observe actual labeled bounding boxes, model confidence,
false positives, and cases where the model misses objects. `ESC` or `Q` closes
the window. No frames or recordings are saved by default.

You may adjust `--min-confidence 0.25` if needed, but record the threshold
used. Lower thresholds can introduce more false positives. If detection lags,
try `--image-size 416`; this may reduce accuracy.

## Still-image run

```powershell
& "$HOME\Projects\.venv-hci-detector\Scripts\python.exe" backend\object_detector.py --image "$HOME\Pictures\test-objects.jpg" --model yolo11n.pt
```

`--save-annotated` is opt-in for a still image; do not store children's faces.
The module prints JSON records of *real model predictions* with normalized
bounding boxes. Example shape ONLY (do not treat values as measured results):

```json
{"kind":"detector.preview.v1","source":"yolo","frame_width":640,"frame_height":480,"detections":[]}
```

**IMPORTANT:** `detector.preview.v1` is currently a LOCAL diagnostic format,
not a valid TCP event in `docs/EVENT_CONTRACT.md`. Don't feed it into port 8765
or claim it updates React yet. The user-facing game still needs a camera feed,
tracked object IDs, coordinate alignment, a sensor-specific selection mechanism,
and a validated `objects.detected` event contract coordinated with the engine
and frontend teams.

## What constitutes a real test?

- The camera/window opens and uses actual YOLO inference.
- Each object is physically placed in view and detection/misses are logged.
- Confidence and bounding boxes are derived from real model results.
- Test under adequate/poor lighting and separate/overlapping objects.
- Record an honest observed detection table and relevant failure cases.
- Do not count mocked boxes or untested COCO class support as real accuracy.

Ultralytics YOLO11 weights/software are distributed under AGPL-3.0 / Enterprise
terms; review license requirements before commercial reuse or redistribution.
