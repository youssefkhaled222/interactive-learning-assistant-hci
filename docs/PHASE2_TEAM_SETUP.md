# HCI Phase II — fresh-computer teammate setup (Windows)

**Purpose:** Help the teammate reproduce the current V6 branch without relying on old ZIP installers or untracked files on the original student's laptop. **Do not start the physical two-camera gaze acceptance test until the final team-testing stage.** Setup can be reviewed earlier.

## A. Prerequisites

- Windows with Python **3.11** (original environment was Python 3.11.9), Node.js and npm, Git, and permission to access webcams.
- A functioning **object-facing webcam** for YOLO + shared MediaPipe Hand frames. The launchers default to camera index **0**.
- **For gaze only:** another independent webcam facing the participant's face, default index **1**. A compatible Android-phone webcam may appear as an additional Windows camera if its integration works on that PC.
- Internet only for dependency and official-model downloads; regular app/sensor work is local.
- An apple, a reasonably visible book and a cup for the physical demonstration.
- No child video, recordings or private profiles should be copied between devices without permission.

## B. Clone the correct branch

```powershell
cd $HOME\Projects
git clone --branch feature/real-eye-tracking --single-branch https://github.com/youssefkhaled222/interactive-learning-assistant-hci.git
cd interactive-learning-assistant-hci\phase2
```

The tested V6 code landed at `a927371`; verify `git log -1 --oneline` and record the specific commit used. **Do not install old V4/V5/V6 patch ZIPs onto a fresh clone**: the branch already contains their code. Do not switch to `main` expecting the same behavior.

## C. Prepare local Python packages and two environments

Use a normal PowerShell terminal. The following are **setup guidance based on source imports**, not yet confirmed as a clean-machine lockfile installation; check dependency failures on the teammate's machine instead of claiming the exact versions are pinned.

```powershell
# From project\phase2:
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements-core.txt
.\.venv\Scripts\python.exe -m pip install mediapipe numpy opencv-python bleak

# The YOLO launcher requires this separate environment at an exact path:
py -3.11 -m venv "$HOME\Projects\.venv-hci-detector"
& "$HOME\Projects\.venv-hci-detector\Scripts\python.exe" -m pip install --upgrade pip
& "$HOME\Projects\.venv-hci-detector\Scripts\python.exe" -m pip install ultralytics opencv-python
```

The detector launcher (`phase2/launchers/detector.ps1`) **hardcodes** the YOLO interpreter to `$HOME\Projects\.venv-hci-detector\Scripts\python.exe`. If a teammate intentionally keeps it elsewhere, they must update that path locally and document the modification. Ultralytics can download `yolo11s.pt` on first use; do not copy its weight into Git. Package installations may require additional compatible versions if the teammate's Windows/Python setup differs.

## D. Install frontend and official MediaPipe models

```powershell
# From phase2:
cd frontend
npm.cmd ci
cd ..

.\.venv\Scripts\python.exe backend\download_tracker_model.py --kind hand
# Only needed for Pose/DollarPy, if the approved model isn't already present:
.\.venv\Scripts\python.exe backend\download_tracker_model.py --kind pose
# Only needed for the final two-camera gaze validation:
.\Download-Gaze-Model.cmd
```

`backend/download_tracker_model.py` verifies official hand/pose model hashes. The gaze downloader obtains the official Face Landmarker `.task` bundle. Model bundles go under `phase2/models/` and are **not a substitute for source-control files**. Make sure `models/hand_landmarker.task` exists before starting the hand adapter. See `README_GAZE_V6.md` for gaze setup/quality limitations.

## E. Automated tests and browser launch

```powershell
# From phase2:
.\Run-HCI-Tests.cmd
```

The initial V6 author's observed baseline was **198 Python unit/integration tests**, **22 React unit tests**, **Vite build success**. A teammate should record *their own* counts and errors; those initial results do not guarantee their hardware or local package compatibility.

For previously tested **gesture mode**:

```powershell
.\Run-HCI.cmd
```

It opens separate backend, React, YOLO and hand-tracking Windows PowerShell consoles. Wait for Vite readiness; visit `http://127.0.0.1:5173`. The hand interaction sequence is **open finger → hover over fresh YOLO object box → pinch and hold → release**. Stop all four windows using `Ctrl+C` before changing modes or restarting services.

For **final teammate-only gaze mode** (requires a second functioning camera):

```powershell
.\Run-HCI-Gaze.cmd
```

This starts those four processes **plus** a fifth face-camera tracker. To change only the face camera index when Windows assigns it a different number, run from PowerShell before launching:

```powershell
$env:HCI_GAZE_CAMERA = '2'
.\Run-HCI-Gaze.cmd
```

The YOLO launcher still uses camera 0, regardless of this variable. Changing YOLO's camera needs a separate change to the detector launcher, and the hand adapter must continue reading the **same YOLO-owned** camera feed. Do not run Pose tracker on the YOLO-owned webcam at the same time.

## F. Optional Malak BLE test — not needed for hand/gaze launch

```powershell
.\.venv\Scripts\python.exe backend\ble_monitor.py
```

The monitor requires the specific enrolled **BLE peripheral** prepared in Malak's separate demonstration: advertising name `hci-test-device`, readable GATT characteristic `00002222-0000-1000-8000-00805f9b34fb`, UTF-8 value `demo-device-beginner`. The device is expected to show `learner_01 / Beginner` when verified. If the phone isn't advertising that peripheral, the monitor will remain in Guest mode; this is not a failure of YOLO or hand selection. A simulated TCP event can test UI profile switching but **is not physical BLE evidence**.

## G. Troubleshooting without touching teammates' work

| Symptom | First checks |
|---|---|
| `python.exe`/environment not found | Check Python 3.11 installation and paths; create both environments; avoid another user's drive-specific path |
| PowerShell `.ps1` blocked | Use the provided `.cmd` launcher rather than changing global execution policy |
| `Cannot open webcam` | Close Camera/Teams/Zoom/older HCI processes; verify camera permission, correct indices and distinct cameras |
| Object preview offline | YOLO terminal running `--stream --publish`? Local HTTP `8767` and camera 0 free? |
| Hand not selecting | Show open fingertip over a stable box **before** pinch; check React hand-selection hint and backend `PINCH_DIAG` |
| Gaze service offline | Confirm **second** face webcam, `models/face_landmarker.task`, index and port `8770` |
| Gaze calibration rejected | Follow all nine targets with actual eye movement, steady head, bright lighting; reset and do not bypass validation |
| Gaze dwell doesn't score | Look at object **in the on-screen preview**, not the desk; ensure fresh YOLO box, stable gaze for 1.5 s and unchanged browser viewport |
| Bluetooth not changing profile | Verify configured LightBlue peripheral, correct readable key and that `ble_monitor.py` runs on the computer near that phone |

Stop existing HCI processes before relaunching. **Do not reset Git, delete teammates' work, or add model weights, private recordings, `node_modules` or `.venv` to a commit.** If a clean-machine package or camera issue persists, report the full terminal error, device/camera indices, and commit tested.
