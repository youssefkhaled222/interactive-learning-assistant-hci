# HCI Phase II — completion criteria and current evidence

The archive is a **software integration release candidate**, not independent proof of every physical requirement or a substitute for the course rubric. It is designed for your current branch `feature/real-hand-object-selection`, after v4. It does not overwrite Mostafa's Pose/DollarPy, Malak's BLE test setup, the YOLO model, or personal recordings.

## Already demonstrated and automated

- Python backend, TCP 8765, WebSocket 8766; browser React interface and responsive camera preview.
- Context-aware three learner packs, five questions per pack, Next Object and results view.
- YOLO detections for real cup/apple/book; `yolo11s.pt` performed better on the book on this machine.
- Genuine MediaPipe hand landmark extraction, pinch indicator, same-camera bounding boxes.
- BLE enrolled device identity demo by teammate; Pose + DollarPy separately tested by teammate.
- Before v5: 178 Python and 19 frontend tests passed. These are **not** physical end-to-end proof.

## V5 in this archive

- Retains a validated **open-hand hover candidate** for at most 0.60s as YOLO briefly misses a box at pinch start. The pinch can NEVER score from cached data alone: a fresh, single, stable matching detection must be visible at commit.
- Keeps pinch release/rearm and ambiguous/stale target safety protections.
- Adds human-readable **Hand selection** guidance in React, and a precise **Pinch stage** in the sensor panel; no source impersonation or browser `game.select` path added.
- Removes misleading always-false `game_select_sent` diagnostic text.
- Adds one-command four-terminal Windows launcher, complete regression runner, demo walkthrough, and focused additional gate tests.

## Must still be physically verified on the student's laptop

- [ ] Restart all processes with V5 and confirm moving live preview and synced boxes.
- [ ] Pick a real apple, book, and cup with a full open -> hover -> pinch -> release sequence; verify browser progress and backend logs.
- [ ] Complete one **real five-question** session with Next Object, retries, score and final results. Record the result, not a simulator run.
- [ ] Verify prolonged hand loss, duplicate boxes, and object removal do NOT earn points.
- [ ] Confirm Malak's BLE profile switches and appropriate question packs with her device/test account.
- [ ] Demonstrate Mostafa's Pose + DollarPy separately unless a second webcam is available; do not fight YOLO for camera index 0.
- [ ] Run regression script, review `git diff --check`, then commit the intended work (avoid unrelated files and secrets).
- [ ] Prepare team/supervisor-required submission report, demo proof, team responsibilities, and slides according to **actual Phase II rubric**.

## Unfinished feature scope (cannot be certified by this archive)

**Real calibrated gaze selection** is NOT implemented/verified here. The React Eye Tracking screen is a prototype and the original concept called for 1.5-second gaze dwell; the architecture has no validated calibrated gaze-to-object adapter. If the rubric requires a fully working eye mode, the project is NOT complete until a separate genuine gaze pipeline, calibration, and physical test are performed.

An automated ZIP cannot prove eye-tracking accuracy, physical sensor reliability, BLE pairing on another person's laptop, or a successful five-question real-world demonstration.
