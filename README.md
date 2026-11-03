# Interactive Learning Assistant for Children — Little Explorers

**MSA University | Human–Computer Interaction | Fall 2026**

**Project:** A camera-based, context-aware **Find the Object** learning activity for children aged approximately 5–10.

> **Status as of 3 November 2026:** Gesture-based gameplay has completed a real five-question session; the V6 eye-gaze feature is **implemented and automated-tested but not physically verified**. Work is on `feature/real-eye-tracking` (`a927371` at the time of this documentation update), **not yet merged into `main`**. This repository does not claim completed child-user evaluation or measured gaze accuracy.

## What the application does

A child is asked to find a real **apple**, **book**, or **cup** in a live object-camera view. YOLO11s detects supported objects, and a local Python engine evaluates selections, maintains a five-question activity, offers hints after mistakes, moves through **Next Object**, and shows a results screen. Guest, Beginner and Advanced content packs are supported; an enrolled BLE demo device can switch the learner profile.

Two touch-free interaction paths are provided:

1. **Hand gestures — demonstrated working.** The object-facing camera feeds both YOLO and MediaPipe Hands. The child first points an **open index finger** inside a live object box, then pinches, holds briefly, and releases. The backend checks a fresh, stable target; mouse clicks do not submit answers.
2. **Gaze — implemented, awaiting real-device validation.** A **second, player-facing camera** tracks MediaPipe face/iris landmarks. An adult assists with nine-point screen calibration (the final center point is held out for validation). The child looks at the corresponding object **inside the large live preview on screen** for about **1.5 seconds**. The backend requires valid calibration and a fresh, stable YOLO box before accepting a selection. This is a low-cost camera-based estimate, **not** specialized infrared eye-tracking equipment.

## Current verification (do not confuse tests with hardware proof)

| Capability | Verified evidence | Remaining limits |
|---|---|---|
| Python backend, event validation, game rules | **198/198 automated tests passed** on 3 Nov 2026 after installing V6 | The full two-camera deployment is not yet verified |
| React frontend | **22/22 tests passed**, production Vite build passed | Live gaze UI still needs real calibration testing |
| YOLO object detection + MediaPipe hand selection | Real **5/5 correct first try**, **zero wrong attempts** in a physical gesture session; screenshot recorded | Run final hand-loss/occlusion regression after gaze changes |
| Malak's BLE enrolled device workflow | Reported working in Malak's separate hardware test; automated tests pass | Combined application + BLE device demonstration still pending |
| Mostafa's Pose + DollarPy | Code integrated, and separate teammate/component testing reported | Final demonstration and camera coordination pending |
| MediaPipe gaze calibration + dwell | 13 additional Python and 3 frontend tests in V6; implementation is present | **Nine-point physical calibration and complete gaze-driven session have NOT been verified** |
| User study / HCI evaluation | Prototype, rules, and metrics are prepared for demonstration | No measured child-participant dataset or comparative usability results are claimed |

## System overview

```text
Object-facing camera (normally index 0)
   -> YOLO11s detector -> fresh object boxes + temporary IDs
   -> local preview HTTP :8767 -> React camera image
   -> shared raw frames -> MediaPipe Hands -> guarded pinch events

Second face-facing camera (gaze mode; normally index 1)
   -> MediaPipe Face Landmarker -> iris features
   -> local 9-point calibration / screen mapping :8770
   -> backend dwell gate (1.5 seconds)

Optional BLE device -> Malak's local Bleak monitor -> learner profile events
Optional Pose/DollarPy tracker -> recognized gesture events (run separately when sharing one camera)

All sensor events -> Python TCP broker :8765 -> context-aware game engine
Validated state -> WebSocket :8766 -> React/Vite UI http://127.0.0.1:5173
```

The React UI cannot score a question by mouse click. The browser controls mode selection, restart and next-question navigation; sensor events reach the local Python broker. Services are local demonstration tools, not public internet services or hardened identity/authentication systems.

## Get started (Windows / PowerShell)

Use **[the teammate setup guide](docs/PHASE2_TEAM_SETUP.md)** when starting on another computer. Existing machine, after environments and required models are ready:

```powershell
cd C:\Users\youss\Projects\interactive-learning-assistant-hci\phase2
.\Run-HCI-Tests.cmd        # Python tests, React tests, production build
.\Run-HCI.cmd              # four processes: backend, React, YOLO, hand tracking
# Or, with a second player-facing camera and downloaded Face Landmarker model:
.\Run-HCI-Gaze.cmd         # five processes; adds gaze tracker
```

If model setup is needed, `Download-Gaze-Model.cmd` downloads the Face Landmarker bundle, and `backend/download_tracker_model.py --kind hand` downloads the pinned hand tracker model. The YOLO launcher uses a separate virtual environment at `$HOME\Projects\.venv-hci-detector` and `yolo11s.pt` on CPU. **Do not run both launchers at the same time**; stop the prior processes first.

## Documentation

- [Architecture and design decisions](docs/PHASE2_ARCHITECTURE.md)
- [Teammate setup, dependencies and troubleshooting](docs/PHASE2_TEAM_SETUP.md)
- [Current evidence and outstanding validations](docs/PHASE2_TEST_EVIDENCE.md)
- [Discussion guide](docs/PHASE2_DISCUSSION_GUIDE.md)
- [Demonstration sequence](PHASE2_DEMO_SCRIPT.md)
- [Completion checklist](PHASE2_FINAL_CHECKLIST.md)
- [Gaze implementation technical guide](README_GAZE_V6.md)

## Team and contribution context

| Member | Student ID | Phase I responsibility recorded in the original README | Phase II contribution / evidence available |
|---|---|---|---|
| Youssef Khaled | 247637 | Context-Aware & Interaction Design / Team Leader | Frontend/backend integration, object-detection and physical hand-gameplay work |
| Malak Gamal | 247419 | PACT Analysis | BLE enrolled-device identification; separately tested by Malak |
| Mostafa Mohamed | 249141 | Scenario & User Journey | Pose tracking and DollarPy wrist-gesture component |
| Mohamed Ramadan | 246813 | Survey & Critical Analysis | Phase I contribution documented; confirm any further Phase II responsibilities with the team |
| Ahmed Wahba | 245559 | Application Design & HCI Principles | React screens, live camera integration and frontend polish |

Do not interpret this table as an exhaustive allocation of work. Verify exact contribution claims with the team before final submission.

## Project links

- [Figma prototype](https://www.figma.com/design/ldE4Mbl0MEigqCEDxKZZfo/Interactive-Learning-Assistant-for-Children?node-id=0-1)
- [Team Trello](https://trello.com/b/lo6uzFCW/hci-project-fall-2026)
- [Current V6 implementation branch](https://github.com/youssefkhaled222/interactive-learning-assistant-hci/tree/feature/real-eye-tracking)

**Before submitting:** Confirm the official Phase II rubric, course code, required screenshots, team declarations, deliverable format and deadline with the TA/course page. The source repository does not itself establish those administrative requirements.
