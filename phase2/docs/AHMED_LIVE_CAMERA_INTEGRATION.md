# Local live-camera preview — independent integration (2 November 2026)

## Why this implementation

Ahmed's updated project demonstrated a localhost MJPEG camera stream, but also
contained an old 2–3-question `engine.py`, a permissive WebSocket origin override
and pointing-triggered `game.select`. We **did not merge** those old backend
changes. This implementation adapts the useful MJPEG preview to our already
verified `object_detector.py` and current React UI.

## Security and meaning

- YOLO detects **real** apples, books and cups and annotates actual webcam frames.
- Frames are served only from `127.0.0.1:8767` over MJPEG; the frontend reads
  the live preview with an `<img>`. Nothing is sent in the game's WebSocket.
- Browser image requests require the expected localhost React development
  Referer (`:5173` or `:5174`). This is defense against ordinary remote
  website embedding, **not authentication against another local program**.
- `/health` reports only availability, with CORS limited to the same origins.
- **No `game.select`, hand gesture or gaze action is produced by the preview**.
  Live hand/pinch controls are pending Mostafa's implementation. The camera shown
  here is the **object-facing** camera; hand readiness remains separate.
- No photo or video recording or file save is performed by this integration.

## Run on Windows (three terminals)

Terminal 1 (existing backend):

```powershell
cd C:\Users\youss\Projects\interactive-learning-assistant-hci\phase2
$env:HCI_REQUIRE_NEXT = '1'
.\.venv\Scripts\python.exe backend\server.py
```

Terminal 2 (React):

```powershell
cd C:\Users\youss\Projects\interactive-learning-assistant-hci\phase2\frontend
npm.cmd run dev
```

Terminal 3 (existing YOLO environment, no new Python packages):

```powershell
cd C:\Users\youss\Projects\interactive-learning-assistant-hci\phase2
& "$HOME\Projects\.venv-hci-detector\Scripts\python.exe" backend\object_detector.py --model yolo11n.pt --camera 0 --device cpu --publish --stream --no-window
```

Open `http://127.0.0.1:5173`, then Camera & Object Setup or Gameplay. The
annotated camera frames should appear; show a real apple and cup to verify.
Stop detector with Ctrl+C. The UI should return to **Preview unavailable**
within a couple seconds and object detections should clear. Don't run a second
YOLO or MediaPipe webcam process on camera 0 concurrently.

`--stream` serves the MJPEG preview; `--publish` sends the existing validated
metadata to TCP. Both are optional in the independent detector. `--no-window`
means Ctrl+C replaces the old OpenCV ESC-to-close behavior. Without `--stream`,
the original detector behaves as before.

## Tests / acceptance

- From root: `python -m unittest discover -s phase2/tests -q`.
- From `phase2/frontend`: `npm.cmd test` then `npm.cmd run build`.
- Open UI and confirm real video and detected metadata; close camera and
  confirm offline placeholder and cleared detection state.
- Check no `game.select` is sent simply by showing an object or pointing at it.
- The live stream can only be accessed by a local browser from the approved
  React origin; production hosting requires a separate security review.

## Still pending

The original proposal's **two-camera** arrangement, MediaPipe/DollarPy pinch,
actual target selection, Bluetooth UserID and real gaze calibration are not
implemented by this camera-preview integration.
