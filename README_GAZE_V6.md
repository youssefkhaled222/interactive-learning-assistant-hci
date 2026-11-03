# HCI Phase II — Real eye-gaze v6 (one-ZIP installer)

**What this is:** An integration release candidate built against the committed gesture milestone `f3602a7` on `feature/real-hand-object-selection`. It adds a **second, player-facing** MediaPipe Face Landmarker webcam adapter, nine-point screen calibration with an unseen center validation target, a 1.5-second backend-held dwell selector gated by **fresh and stable YOLO object boxes**, an estimated gaze dot, progress feedback, tests, and alternate launchers. **Physical calibration/5-question gaze gameplay remain to be tested on your Windows computer.**

**What it is not:** It is not an infrared/medical-grade eye tracker and cannot reliably work with an object-facing webcam alone. It does **not** use mouse hover or clicks to submit answers; adult clicks record gaze calibration samples only. No face frames are saved or sent over the backend TCP/WebSocket connection. The MediaPipe bundle is downloaded separately once from Google's official URL (not included in the small ZIP).

## Hardware

- Camera 0: the **object-facing** webcam already used by YOLO11s and your hand adapter; point it at apple/book/cup.
- Camera 1: **another webcam facing the player's face** (your built-in laptop webcam can be this one, if it maps to index 1). Place it close to the center/top of the screen, keep face well lit and head reasonably still.
- A screen with the React application visible; the player looks at objects **in the large live object-camera preview displayed on screen**, not at real objects on the desk.
- The two camera indices must be different. If there is no second camera, gaze mode is not yet physically usable; keep using the existing gesture demo.

## Install (PowerShell, repository root)

```powershell
cd C:\Users\youss\Projects\interactive-learning-assistant-hci
Expand-Archive -LiteralPath "$HOME\Downloads\hci-phase2-real-gaze-v6.zip" -DestinationPath . -Force
.\phase2\.venv\Scripts\python.exe .\install_hci_gaze_v6.py
git diff --check
```

**The ZIP extracts into its own `hci_gaze_v6_payload` folder; it does not overwrite your game source simply by extracting it.** Installer preflights patches against V5.2, preserves the project's original Windows line endings and copies changed files to `.hci-gaze-v6-backups/<timestamp>`. On an unfamiliar source anchor it refuses to change project files. It never commits, pushes or merges.

## Test and launch

```powershell
cd phase2
.\Run-HCI-Tests.cmd
.\Download-Gaze-Model.cmd
.\Run-HCI-Gaze.cmd
```

- The test script runs **all** Python and React unit tests, followed by the Vite production build. Existing V5.2 gesture launch `Run-HCI.cmd` remains unchanged.
- The one-time model downloader uses **Google's official Face Landmarker `.task`** HTTPS URL and writes to `phase2/models/face_landmarker.task`. Needs internet at download time, **no internet for local tracking**.
- **Close existing HCI terminals before `Run-HCI-Gaze.cmd`**, or ports/cameras will be busy.
- `Run-HCI-Gaze.cmd` starts the four existing HCI processes **plus** a face-tracker terminal (five total; Bluetooth would be a sixth if needed).
- If camera index 1 is not the face camera, stop the terminals, set `$env:HCI_GAZE_CAMERA = '2'` in PowerShell and launch again. If it is index 0, choose a different index for YOLO instead (not automatically supported by this package).
- Open `http://127.0.0.1:5173` in your normal local browser. Choose **Eye Tracking**.

## Calibration and real-world demonstration

1. Sit still at the same distance from the player-facing webcam, with both eyes visible and good lighting. Maximize browser; do not resize or zoom during the session.
2. Follow the nine highlighted dots; for each dot, **look at it for at least one second**, then ask the adult/tester to press **Capture point**. You must actually move your gaze from dot to dot.
3. The last dot is a held-out accuracy check. If calibration fails, press **Reset calibration**, improve camera placement and light, and repeat. A failed calibration never unlocks scoring.
4. After **Calibration passed**, click **Continue to objects**, then **Open game**. Keep the same seating position and browser size.
5. The game shows the real YOLO preview prominently. **Look at the image of the apple/book/cup in the preview** for **1.5 seconds**, without using a mouse click or pinch. The backend validates an active matching detection box and commits `game.select` only after continuous dwell.
6. Look away from the selected object briefly to rearm, click Next Object after a correct answer, repeat until all five questions are complete.
7. During a successful event, backend prints `Real gaze dwell proposed object=...`; this is evidence from actual face-camera iris landmarks and a validated current YOLO target. Save screenshot(s), but don't claim 5/5 until you actually complete it.

## Failure explanations

- `Face camera ... cannot open`: second webcam missing, another process owns it, or index differs. Verify physical second camera and device index.
- `Model missing`: run `Download-Gaze-Model.cmd`; internet is needed one time, files aren't in the ZIP.
- `Face not visible`: aim player-facing camera at eyes, improve light, move closer.
- `Cannot see steady eyes yet`: hold gaze steady at dot for a full second before pressing Capture.
- `Calibration quality too low`: pupil features were nearly identical, head moved, or eye measurement is inaccurate; reset and retry. This is intentionally fail-closed.
- `Viewport changed`: restore initial browser size, re-enter Eye Tracking and reset calibration.
- `no-visible-target-at-point`: projected screen gaze is not over a current YOLO box. Align face camera, recalibrate, and ensure the correct object is visible inside the **large preview**.
- `detector-unavailable-or-stale`: restart object detector or show the real object more clearly.
- `find-face-or-screen`: face is out of view, gaze is outside large preview, or browser geometry is stale.
- If the current eye-camera accuracy is not sufficient for tiny boxes, enlarge the preview, use larger physical objects, improve illumination, and recalibrate. **Do not bypass calibration or change dwell to fake completion.**

## Privacy and project scope

This is a local classroom demonstration, **not secure identity verification** or a medical eye-tracking device. Numeric iris measurements are held in memory only; no face-image storage, uploads, remote URLs, or browser-originated answer events. All service endpoints bind to `127.0.0.1`. Bluetooth is independent and untouched. Mostafa's Pose/DollarPy functionality and the tested real hand-gesture gate are left unchanged.

**Final verification still required:** Run the full Windows regression suite; a real successful nine-point calibration, several gaze-driven answers and eventually 5/5 with the two actual cameras; recheck gesture 5/5 after installing; combined Bluetooth and Pose demos; documentation/merge review. On failure, send the **exact installer error and gaze terminal messages** instead of deleting/reinstalling previous packages.
