# HCI Phase II — final demonstration script

**Scope:** A working five-question real-object game, individually validated BLE/Pose components, and a gaze-mode implementation awaiting its last **physical two-camera** test. **Do not present automated gaze tests as a physical gaze success.**

## Pre-demo setup

- Use branch `feature/real-eye-tracking` for the latest V6 software, **or** `feature/real-hand-object-selection` (`f3602a7`) as the stable gesture-only fallback. Neither is yet merged into `main`.
- Windows laptop with the relevant Python virtual environments, Node modules, YOLO11s weight and official MediaPipe hand model; see `docs/PHASE2_TEAM_SETUP.md`.
- For gaze only: a *second independent webcam* facing the user's face plus `phase2/models/face_landmarker.task`. Camera 0 normally sees real objects; camera 1 normally sees the face.
- Prepare a real apple, book and cup; provide good light and a clear live preview. Keep the demonstration local and obtain consent before filming anyone, particularly minors.
- Close all HCI processes from earlier runs; only one YOLO process should own object camera 0.

## Regression gate (before presentation)

```powershell
cd phase2
.\Run-HCI-Tests.cmd
```

Expected baseline measured on the original V6 installation: **198 Python + 22 React tests passed**, and **Vite build passed**. Counts may increase with later changes; always record current results. Test output containing intentionally rejected invalid inputs does not alone indicate a failure—check the final summary.

## Demonstration A: hand gestures — confirmed on 3 November 2026

```powershell
cd phase2
.\Run-HCI.cmd
```

The four windows run the TCP/WebSocket broker, React, YOLO11s (object webcam and preview) and MediaPipe hand pointer. Visit `http://127.0.0.1:5173`.

1. On **Start Learning**, choose **Hand Gestures** and complete the tutorial and camera setup.
2. Show a real object until YOLO draws a clear bounding box.
3. With fingers **open**, point the index finger **inside** that object's current box. Do **not** pinch before hovering.
4. Hold the finger steady; pinch thumb/index for approximately 0.3–0.6 seconds, then release. A fresh stabilized YOLO box must still support selection.
5. Confirm backend-controlled feedback, stars, **Next Object**, and final result; repeat for five questions.
6. Show that mouse-clicking an object card is a local preview, not an accepted answer; losing tracking or a stale box must not increment points.

**Recorded evidence:** A physical session finished **5/5**, all correct on first attempt, zero wrong attempts; save its screenshot. To demonstrate negative-path behavior, perform separate tests (do not pretend zero wrong attempts proves retry logic was physically exercised).

## Demonstration B: Malak's BLE — component separately verified

Run `backend/ble_monitor.py` from the same `phase2/.venv` **on the computer with the enrolled test device nearby**; the real backend must be running. A phone can use the configured LightBlue BLE peripheral with a readable custom characteristic, as explained by Malak. Verify Guest → Beginner `learner_01` → Guest after confirmed loss. See `docs/PHASE2_TEAM_SETUP.md` for the exact device constraints. **This is a real BLE demo, not secure login/authentication.** Do not submit synthetic `device.discovered` commands as proof of physical BLE.

## Demonstration C: Mostafa's Pose/DollarPy — separate camera session

The existing `backend/pose_tracker.py` classifier uses a camera directly. It can conflict with YOLO if both try to own index 0. Run his documented Pose/DollarPy demonstration separately, with approved local gesture samples and the appropriate official model. Confirm visible tracking and real recognized horizontal/vertical gestures; the `gesture.recognized` event updates backend status, not the YOLO object answer by itself. Record his own validation output and any remaining limitations.

## Demonstration D: gaze — **FINAL teammate test, not yet verified**

Only after the preceding work is ready, your teammate can run:

```powershell
cd phase2
.\Download-Gaze-Model.cmd
.\Run-HCI-Gaze.cmd
```

This opens five processes, including MediaPipe face/iris tracking on second camera index 1. Maximize the React browser window. Choose **Eye Tracking**, have an adult help capture nine genuine gaze points (one second per point), and require **Calibration passed**. Enter the game and look at an image of an **actually detected object in the large on-screen preview** continuously for **1.5 seconds**, without touching the mouse or pinching. Confirm backend `Real gaze dwell proposed object=...`, score change, look-away/rearm, and eventually all five questions.

**Mandatory negative tests:** Cannot score with no face, failed calibration, gaze outside an object, stale/missing/overlapping YOLO boxes, or a too-short gaze hold. Verify a repeated selection does not double-score. If the real system fails, report exactly where and leave gaze marked **unverified**. Full technical steps are in `README_GAZE_V6.md`.

## Close and capture evidence

- Stop child PowerShell processes with `Ctrl+C`. Do not run `Run-HCI.cmd` and `Run-HCI-Gaze.cmd` simultaneously.
- Save a **dated** console test summary and screenshot of actual gesture session. Distinguish real camera events from simulated tests and teammates' reports.
- The TA should be shown actual hardware, clear interaction steps, profile switching, backend-verifiable progress, and honest limitations rather than just polished screens.
- Final merge to `main` should follow verified results and team review, not precede physical gaze acceptance.
