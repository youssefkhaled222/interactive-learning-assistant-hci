# HCI Phase II — Shared Integration Starter (v0.2.1)

**Purpose:** a working, testable local integration baseline for CS484 Phase II. This **does not complete** the graded application. It provides event contracts, a real TCP/WebSocket bridge, an observable context engine, real-camera MediaPipe/DollarPy source scaffolding, BLE scanner source, and a replaceable React preview.

## Prerequisites

- Windows 10/11 laptop, Python **3.11** recommended and Node.js **20.19+ or 22.12+** for Vite 7.
- For camera work: install a suitable official MediaPipe Pose Landmarker `.task` model into `models/pose_landmarker.task` (see official Google AI Edge documentation). Model is **not included**.
- For Bluetooth: Bluetooth LE adapter and a test peripheral that actually advertises; IDs must be explicitly enrolled.

## Run core integration (no camera or Bluetooth required)

In PowerShell, from `phase2`:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-core.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe backend\server.py
```

Open a **second PowerShell** window in `phase2`:

```powershell
cd frontend
npm install
npm run dev
```

Open the localhost URL that Vite displays (usually http://127.0.0.1:5173).

Open a **third PowerShell** window in `phase2`:

```powershell
.\.venv\Scripts\python.exe backend\demo_sequence.py
```

Watch the learner context, question pack, camera and gesture status change live in the browser. **All events from this command are simulated** and only validate plumbing.

## Test actual hardware components (required for rubric)

Install separately:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-sensors.txt
.\.venv\Scripts\python.exe backend\ble_scan.py
.\.venv\Scripts\python.exe backend\pose_tracker.py --model models\pose_landmarker.task --record-label swipe_left
.\.venv\Scripts\python.exe backend\pose_tracker.py --model models\pose_landmarker.task --record-label swipe_right
.\.venv\Scripts\python.exe backend\pose_tracker.py --model models\pose_landmarker.task
```

In the MediaPipe camera window, press **SPACE** to record 1.8s of movement and **ESC** to exit. Make two real gesture templates with distinct movements. The DollarPy classifier output isn't a calibrated probability and should be tested with held-out examples. Only positive hardware tests count as actual device proof.

## What's working, what's not

| Component | Current status in starter |
|---|---|
| Python TCP JSONL event server | Implemented; test on your machine |
| WebSocket frontend updates | Implemented; test on your machine |
| Context engine + three different question packs | Implemented and unit-tested |
| React integration UI | Implemented (NOT final Figma screens) |
| MediaPipe pose and DollarPy recording source | Provided, requires real model and webcam testing |
| BLE discovery source | Provided, requires actual BLE adapter/peripheral |
| Bluetooth UserID enrollment | **Not implemented** — must use registered device/GATT data |
| Real object detection + gaze tracking | **Not implemented** |
| Live pointer/pinch selection | **Not implemented** |

## GitHub integration

Do not overwrite the repository's Phase I report. Copy this **`phase2/`** folder into the root of `interactive-learning-assistant-hci`. Each member should work in their own branch, open a PR, and merge changes after an integration test.

## Authors/tasks

- Youssef: TCP bridge, contracts and integration.
- Mostafa: MediaPipe body pose, DollarPy gestures, real template and capture tests.
- Malak: BLE device discovery + legitimate test UserID enrollment and loss handling.
- Mohamed: context rules, beginner/older question packs, fallback and lighting logic.
- Ahmed: replace integration preview with approved Figma screen implementation.

The Phase II grading rubric additionally requires printing Scenario + PACT, separate grading form with signatures, full team attendance and upload of all source code/notebooks. Check the official time slot.
