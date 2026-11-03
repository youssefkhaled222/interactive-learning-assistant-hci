# HCI Phase II — technical architecture and interaction rationale

**Reference implementation:** `feature/real-eye-tracking` as of `a927371` (3 November 2026). This document describes code paths and intended behavior, not a completed two-camera hardware validation.

## 1. Purpose and HCI design

Little Explorers is a context-aware **Find the Object** learning game for children around ages 5–10. The interaction avoids mouse-based answer submission and offers two sensor pathways: an index-finger + pinch gesture, and calibrated eye-gaze dwell. Each selected real object is checked against the current question. The content engine provides Guest, Beginner and Advanced five-question packs, feedback, retry/hints, Next Object, and a final result summary.

**Interaction sequence:** select a mode → learn/perform calibration → check the camera and objects → attempt five questions → receive per-answer feedback → final results. An adult may assist with device setup and nine-point gaze calibration. A BLE enrolled device changes the content pack without inferring an identity from an arbitrary Bluetooth MAC address.

## 2. Processes and ports

| Service | Main source | Input | Output |
|---|---|---|---|
| Python game broker | `phase2/backend/server.py` | Validated TCP sensor events, allow-listed browser commands | State on WebSocket `127.0.0.1:8766` |
| Game engine | `backend/engine.py`, `content_packs.py` | Sensor identity, mode, tracking, selections | Current question, progress, score, notices, learner pack |
| Object detector | `backend/object_detector.py`, `object_tracking.py` | Object-facing camera (normally index 0) | YOLO11s boxes for apple/book/cup, temporary IDs, `objects.detected` |
| Local camera preview | `backend/camera_preview.py` | Annotated and raw detector frames | Loopback HTTP `127.0.0.1:8767` for React and shared hand adapter |
| Hand adapter | `backend/hand_pointer_preview.py`, `hand_selection.py` | MediaPipe Hands on YOLO-shared camera frames | Index pointer + pinch → broker-validated real selection |
| Gaze adapter | `backend/gaze_tracker.py`, `gaze_calibration.py`, `gaze_dwell.py` | **Separate face-facing webcam** and iris landmarks | Local calibration service `127.0.0.1:8770`, gaze coordinates → backend dwell gate |
| BLE identity | `backend/ble_monitor.py` | Enrolled BLE advertisement and readable characteristic | `device.discovered` / `device.lost` after verification |
| Pose/DollarPy | `backend/pose_tracker.py`, gesture utilities | Webcam, stored gesture templates | `pose.tracking`, `gesture.recognized` during its separate demo |
| React UI | `phase2/frontend/src` | Backend WebSocket state, local camera previews | Tutorial, calibration, object view, feedback, results on `127.0.0.1:5173` |

**Port note:** TCP sensor intake is `8765`; the game UI WebSocket is `8766`; YOLO preview HTTP is `8767`; gaze calibration HTTP is `8770`. Server processes bind to localhost. This is local demo isolation, **not a secure login or anti-spoofing boundary** against processes on the same machine.

## 3. Hand mode — real physical result obtained

1. YOLO11s detects an object in the same camera frame from which the MediaPipe hand adapter reads landmarks.
2. The index fingertip is mapped to normalized coordinates in that shared object-facing image.
3. An **open-hand hover** on a stable, current object is observed first. The participant then pinches thumb/index while keeping the finger steady.
4. `hand_selection.py` enforces transition/arming/hold/release and resolves a current unambiguous box via `target_matching.py`. A short missed YOLO observation can retain a *tentative candidate*, but it **cannot authorize a score using stale box data**.
5. The broker sends the selected object to `Engine.handle(game.select)` and broadcasts engine-confirmed feedback. Browser click previews do not score.

**Verified:** A real hand-controlled session completed five questions correctly on the first try, zero recorded wrong attempts, as shown in the captured UI screenshot.

## 4. Gaze mode — code implemented, real physical acceptance pending

1. A second camera faces the player's eyes; MediaPipe Face Landmarker extracts iris landmarks. The object-facing YOLO camera must remain available independently.
2. The React calibration page presents nine targets. An adult captures numeric eye features only while the player looks at each displayed target. Eight points fit an approximate screen mapping; the final center point checks held-out error.
3. The calibrated gaze estimate is mapped into the actual painted rectangle of the large object-camera preview. This handles the `object-fit: contain` letterboxing geometry.
4. `GazeDwellGate` needs **1.5 seconds** on one fresh stable YOLO target; a short face/detector gap, stale object, lost calibration or off-target gaze cannot directly produce a selection.
5. When a fresh candidate passes at dwell completion, the backend proposes the corresponding object to the same engine used by gesture mode. The user looks away to rearm.

**Caution:** Consumer webcam iris features give an approximate gaze position, sensitive to camera placement, pupil visibility, lighting, head movement and screen scaling. The calibrator's synthetic unit tests do **not** establish empirical gaze accuracy. The teammate's physical calibration and five-question run are explicitly reserved as the final test.

## 5. Context awareness

- Registered demo BLE keys (`demo-device-beginner` and `demo-device-advanced`) map to pseudonymous user IDs and packs. Unknown identifiers fall back to Guest. Switching learner resets the relevant game session.
- Mode changes, camera readiness, tracking availability and low-light notices modify whether interactions are accepted or what guidance is shown.
- Question progression and stars are derived from backend-confirmed answers, not UI animation or a local click.
- The game prevents duplicate selections, ignores invalid event schemas, requires current sensor readiness, and blocks gaze mode without valid calibration.

## 6. Privacy, security and constraints

- No face images are intentionally stored by the gaze code, and no video is sent over the game WebSocket. The local preview exposes frames to the local UI; treat computer access and camera permissions as sensitive.
- Do not record or share children without guardian permission and any course-required approval. Test with consenting adults when possible.
- BLE demo device keys are **not** robust authentication credentials. TCP `source` labels identify code paths, **not a cryptographic proof** of authentic hardware.
- Both hand and gaze share the object detection service, but gaze requires a **separate camera looking at the face**; one object-facing camera is insufficient for the V6 design.
- Model weights, local Python environments and node modules are external dependencies, not part of the application code in Git.

## 7. Known limits and future HCI evaluation

Supported physical targets currently focus on the classes **apple/book/cup**. The current work does not establish child usability, gaze error in degrees/pixels, measured response times, statistically meaningful comparative effectiveness, or accessibility performance across participants. Such claims require a documented study, consent and measured data. See [test evidence](PHASE2_TEST_EVIDENCE.md) and [final checklist](../PHASE2_FINAL_CHECKLIST.md).
