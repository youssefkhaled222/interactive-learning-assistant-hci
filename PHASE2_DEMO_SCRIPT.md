# Phase II physical demonstration — one pass

## Installation

Stop running YOLO, hand tracker, React, backend before updating; keep the repo on `feature/real-hand-object-selection`.

```powershell
cd C:\Users\youss\Projects\interactive-learning-assistant-hci
Expand-Archive -LiteralPath "$HOME\Downloads\hci-phase2-onezip-v5.zip" -DestinationPath . -Force
.\phase2\.venv\Scripts\python.exe .\apply_phase2_ready_v5.py
git diff --check
cd phase2
.\Run-HCI-Tests.ps1
```

V5 installer refuses unknown modified selector versions and saves originals under `.phase2-v5-backups/<timestamp>` before changes. It does NOT commit or push.

## Start all processes in four separate windows

```powershell
cd C:\Users\youss\Projects\interactive-learning-assistant-hci\phase2
.\Run-HCI.ps1
```

The launcher starts broker with `HCI_REQUIRE_NEXT=1`, React, YOLO11s on camera 0 and real MediaPipe Hands with `--enable-gameplay`. The YOLO environment must already be installed at `$HOME\Projects\.venv-hci-detector\Scripts\python.exe`. Model weights may need a first-use download.

1. Open `http://127.0.0.1:5173`, choose **Hand Gestures**; do not choose Eye Tracking for real hardware proof.
2. Keep one real object still and in focus. Wait for a single clear YOLO box. A book is often better **open** and facing the camera.
3. Move your **open index fingertip** into the object's box. Check React's hand hint: `Finger on book. Pinch and hold.` (or the relevant object).
4. Close thumb to index fingertip **without sliding out of the box**. Hold about 0.3–0.6 seconds, then release. YOLO can briefly miss the target at the pinch onset; V5 allows recent *hover* as a tentative candidate but still requires a real box again before scoring.
5. Check React answer feedback. Correct answer advances the score; wrong answer should show retry, not a falsely earned star. Use Next Object between questions.
6. If it doesn't score, look at **Hand selection** and **Pinch stage** in React. The backend `PINCH_DIAG` lines are available if v4.1 was previously installed. A rejected pinch should NEVER silently increase the score.

## Stop

Use `Ctrl+C` inside each child PowerShell window. Do not kill arbitrary Python processes or reset data folders. Avoid running `pose_tracker.py` on camera 0 at the same time as YOLO.

## Team role/testing evidence

Capture exactly which sensor ran, the camera preview and recognized box, fingertip/pinch overlay, the broker's game update, the learner pack/score, and the final results. Describe gaze mode as **prototype/unverified** until an actual calibrated gaze implementation exists. Avoid presenting any simulator output as a real hardware event.
