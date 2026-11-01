# Real object detection -> TCP -> WebSocket bridge

This component **only** publishes real YOLO detection metadata. It does not
send video frames or perform hand/gaze target selection. Do not demonstrate it
as a finished *Find the Object* gameplay selection technique.

## Install and run

Use the separate YOLO virtual environment already created at
`$HOME\Projects\.venv-hci-detector` (Ultralytics / PyTorch). It must be kept
separate from the MediaPipe environment.

Terminal A (backend, from `phase2`):

```powershell
.\.venv\Scripts\python.exe backend\server.py
```

Terminal B (React, from `phase2\frontend`):

```powershell
npm.cmd run dev
```

Terminal C (real detector, from `phase2`):

```powershell
& "$HOME\Projects\.venv-hci-detector\Scripts\python.exe" backend\object_detector.py --model yolo11n.pt --camera 0 --device cpu --publish
```

Close the Windows Camera app and MediaPipe pose tracker before running the
object-facing detector, as this laptop currently has one available webcam.
The YOLO model must already exist locally for an offline discussion demo.

## Verification

Run the local observer in a fourth terminal (from `phase2`):

```powershell
.\.venv\Scripts\python.exe backend\monitor_objects.py
```

Or connect to `ws://127.0.0.1:8766` directly. In the JSON `state.payload`, inspect:
`object_detection_active`, `detected_objects` (each contains `object`,
`confidence`, normalized `box`, temporary `target_id`), and
`object_detection_source`.

- A visible cup or book should produce actual detections (not guaranteed in
  every frame). Apple remains **untested** until a physical prop is available.
- Moving the same visible object gradually should usually keep its temporary
  `target_id`; leave/re-enter or occlusion may assign a new ID.
- When no eligible item is detected, the object list must be **empty**.
- Press ESC/Q to close the detector. A normal exit sends `active:false` and
  clears boxes; a crashed/stalled detector is cleared automatically after 2.5s.
- Browser mode selection/restart, MediaPipe tracking, Bluetooth, and learner
  content continue using their existing protocols and state fields.

## Tests

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

No camera, PyTorch or YOLO weights are required to run the new validation,
tracking, and TCP/WebSocket tests in this suite. These tests establish the
**socket pipeline**, not the accuracy of a pretrained detector on real props.

## Privacy and scope

Only local labels, confidence numbers and bounding boxes are sent. No camera
frames are sent to React. All ports are bound to 127.0.0.1. The TCP local event
source is not authenticated; only the real detector window and actual physical
prop test establish that the detections came from the camera.

The UI owner must explicitly implement camera preview/box overlay before this
can replace any emoji choice cards. The team must implement genuine hand/gaze
selection and validate selected target IDs against eligible detections before
counting answers.
