# Mostafa - MediaPipe + DollarPy: current-source integration

Mostafa Mohamed (249141), CS484. Prepared 2 November 2026.
Discussion: Wednesday 4 November 2026; confirm the time on Moodle.

## What this iteration does

The existing `backend/pose_tracker.py` now runs the MediaPipe Tasks Pose Landmarker on a real camera stream, draws the body connections, captures right-wrist trajectories, and uses the actual DollarPy library. It sends the existing camera/tracking/gesture events through the unchanged `send(event)` function. It never emits `game.select`.

This is an adult-operated feature-validation tool inside the existing project. SPACE is a developer recording control, not a replacement for the planned child hand-pointer/pinch interface. Live webcam validation remains required; see `MOSTAFA_TEST_RESULTS.md`.

## Audit and implementation order

1. **P0 camera/pose:** validate the official model before opening the camera, strictly increasing frame timestamps, confidence-gated torso and wrist, clean release, actionable errors.
2. **P0 classification:** multiple unique recordings per label, separate train/test directories, actual DollarPy, explicit rejection threshold, no stationary/short/nonfinite trajectories, no joining recordings across tracking loss.
3. **P0 integration:** background sender, broker acknowledgment checks, coalesced status changes, limited retry/heartbeat, no replay of stale gestures.
4. **P1 lab:** the same tool can use the Hand Landmarker with actual thumb-tip (4) or index-tip (8) points. Run the shape experiment offline and evaluate each finger separately.
5. **P2 gameplay:** pointer/pinch selection still needs mapping and coordination with Youssef/Ahmed. The current source includes stable object targets; this patch does not emit selections.

### Important differences found

- The original recorder overwrote `swipe_left.json` / `swipe_right.json`, with no independent test set.
- DollarPy is a **$P point-cloud recognizer**, not a direction-sensitive $1 classifier. A left/right traversal of the same line is a poor two-class experiment. This iteration recommends `horizontal` and `vertical`. These are movement-status labels accepted by the existing event contract, not object answers. Tell Youssef these labels when integrating.
- DollarPy 0.1.1 modifies lists during resampling; fresh Point/Template objects are created for each classification.
- The starter may mark the camera ready before a frame is read, leak the camera on model creation failure, block the video on network timeouts, ignore rejected acknowledgments, and splice a wrist path across missing tracking.
- `poseEstimator.ipynb` and the classification notebook use the older `mp.solutions.holistic`; the implementation uses Tasks. The pose notebook also has inconsistent flipped/non-flipped image handling. This tool uses unmirrored inference AND preview.
- The lab's boxing video files under `Dataset/hook`, `uppercut`, and `right` are absent. They are not used or claimed.
- Final Phase I report: five prompts, a separate Next object confirmation, completed questions distinct from first-try successes. The current source already has five-question packs, separate completion/first-try counts, and optional Next object behavior. Those team files are unchanged here.
- Final Phase I corrects the earlier interpretation of the illustrative Figma `Objects Found 3/5`. Use the final report's explicit completion/first-attempt distinction.
- The official Phase II form lists eight criteria totaling **9 allocated marks**, despite a /10 heading. No extra point is invented.

## 1. Apply only to the latest feature branch

Use the outer ZIP's `START_HERE.md` and `apply_mostafa_patch.py`. They guard the original tracker and interfaces before applying. Do not copy the reference starter over main. If the guards find changed source, stop and reconcile the listed files against the latest repository.

No private GitHub access was available to the authoring session. This patch is based on HCI_Current_Source.zip, commit 012883c17920ed2114097af1ac8a5bd53f3d09d3. No remote branch or PR was created here.

## 2. Clean PowerShell setup

Run from the real repository's `phase2` folder. `.venv` is already ignored. Use a fresh environment if your current one already contains conflicting OpenCV installations; do not delete a teammate's environment.

```powershell
py -3.11 --version
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements-core.txt -r requirements-mostafa.txt
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -c "import cv2, mediapipe, dollarpy; print('OpenCV:', cv2.__version__, 'MediaPipe:', mediapipe.__version__)"
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The dedicated requirements file is for Mostafa's tracker only; shared dependencies are unchanged. `opencv-contrib-python` supplies `cv2`: do not also install `opencv-python` in this environment. The pinned direct dependencies were checked on Linux Python 3.11; Windows still needs the commands above. `pip freeze` in the evidence folder records the full tested Linux environment, not a guaranteed Windows lockfile.

## 3. Download and validate the real models

```powershell
.\.venv\Scripts\python.exe backend\download_tracker_model.py --kind pose
.\.venv\Scripts\python.exe backend\pose_tracker.py --check-model
.\.venv\Scripts\python.exe backend\pose_tracker.py --camera 0 --check-camera
```

Expected camera check: `FRAME_READ_OK`, actual resolution and camera backend. A successful model check is not proof of human tracking. On camera failure, close Camera/Teams/Zoom, enable Windows Settings > Privacy & security > Camera > desktop app access, then try:

```powershell
.\.venv\Scripts\python.exe backend\pose_tracker.py --camera 1 --check-camera
.\.venv\Scripts\python.exe backend\pose_tracker.py --camera 0 --backend msmf --check-camera
```

The chosen `--camera` and `--backend` must also be used in subsequent recording commands. Do not guess that every laptop camera is index 0.

Official versioned model URLs and SHA256:

| Model | Version | SHA256 |
|---|---|---|
| Pose Landmarker Lite, float16 | 1 | `59929e1d1ee95287735ddd833b19cf4ac46d29bc7afddbbf6753c459690d574a` |
| Hand Landmarker, float16 | 1 | `fbc2a30080c3c557093b5ddfc334698132eb341044ccee322ccf8bcf3607cde1` |

The downloader uses the versioned `storage.googleapis.com/mediapipe-models/.../float16/1/` URLs in its source, verifies the checksum, and writes a local source manifest. A failed download never replaces a model. The hashes were calculated from the official downloads in this session; they are not a separate publisher signature. Model binaries are not in this delivery or committed to Git.

## 4. Record genuine wrist training data

A consenting adult should be alone in the camera view. Stand/sit far enough away for shoulders, hips and the right wrist to be visible. Move the **anatomical right wrist**; the preview is not mirrored. Keep the torso still. No video is saved; only local landmark trajectories and metadata are saved.

For the first class, draw one clear horizontal line with the wrist. Press SPACE, move for the displayed 1.8-second window, then wait for `Saved train: horizontal`. Repeat at least **two times**. ESC exits. Do not use repetitive back-and-forth waves for one sample.

```powershell
.\.venv\Scripts\python.exe backend\pose_tracker.py --camera 0 --record-label horizontal --split train --consenting-adult --offline
```

Repeat with a vertical line, at least **two separate recordings**:

```powershell
.\.venv\Scripts\python.exe backend\pose_tracker.py --camera 0 --record-label vertical --split train --consenting-adult --offline
```

Each sample is saved in `templates/local/right_wrist/train/<label>/<unique_id>.json`. Multiple recordings do not overwrite one another. The local subtree is ignored by Git. Do not commit identifiable recordings. `--consenting-adult` is an operator attestation, not automated verification of consent.

If tracking drops at any point, the whole current capture is cancelled. Reposition and retry. If the motion is too short/small, no sample is saved. SPACE should be pressed only when the torso and wrist are visible.

## 5. Capture held-out tests and evaluate

Do this **after** the training set and provisional threshold are fixed. Do not reuse the training movements' files. Record **five fresh examples per class** (10 total). Do not delete mistakes to improve reported accuracy.

```powershell
.\.venv\Scripts\python.exe backend\pose_tracker.py --camera 0 --record-label horizontal --split test --consenting-adult --offline
.\.venv\Scripts\python.exe backend\pose_tracker.py --camera 0 --record-label vertical --split test --consenting-adult --offline
.\.venv\Scripts\python.exe backend\pose_tracker.py --evaluate --min-test 5 --report recordings\wrist_evaluation.json
```

The evaluator requires >=2 training recordings per class, >=5 test recordings per class, at least two classes, consistent channels, and no duplicated IDs/coordinate sequences. It logs every expected label, prediction, score, acceptance and mistake, plus counts and a confusion table. The score is **template similarity, not probability**. The default rejection threshold 0.5 is provisional and has not been calibrated on real users. If tuning is needed, use separate pilot/development recordings, then collect a fresh held-out test set.

A single offline replay is available and NEVER sends a broker event:

```powershell
$samplePath = (Get-ChildItem templates\local\right_wrist\test\horizontal\*.json | Select-Object -First 1).FullName
.\.venv\Scripts\python.exe backend\pose_tracker.py --replay "$samplePath"
```

File metadata alone is not proof that the trajectories came from a webcam. Pair the local recordings and aggregate report with a witnessed adult demo.

## 6. Live integration into the existing application

The skeleton preview opens in a separate OpenCV window. React's video panel is the team's YOLO MJPEG stream on port 8767; this tracker does not supply that stream. An offline YOLO video panel does not mean the pose events failed.

With one webcam, stop YOLO before running this tracker. For simultaneous integration, coordinate separate camera indexes or a shared capture design with Youssef. Do not start both processes on the same camera. Camera readiness events here belong to the pose tracker.

Terminal 1, from `phase2`:

```powershell
.\.venv\Scripts\python.exe backend\server.py
```

Terminal 2, from `phase2`:

```powershell
cd frontend
# If latest main includes package-lock.json:
npm.cmd ci
# If it has no lockfile, use npm.cmd install instead.
npm.cmd run dev
```

Open the local URL printed by Vite. Terminal 3, from `phase2`:

```powershell
.\.venv\Scripts\python.exe backend\pose_tracker.py --camera 0 --consenting-adult
```

Use SPACE and perform one trained movement. Verify all of these **in a live run**:

1. Camera preview shows a real adult skeleton and date/device index.
2. Console logs actual `camera.status` / `pose.tracking`, `source: mediapipe`, with broker `ack: {"ok": true}`.
3. Console logs accepted `gesture.recognized`, `source: dollarpy`, with the observed label and acknowledgment.
4. React's tracking status and last gesture update. The current frontend has tracking and last-gesture fields; inspect those fields during the live run.
5. Stepping out of view changes tracking to false; returning recovers. ESC releases the camera and sends false camera/tracking states.
6. Stopping the broker does not freeze the video. Restarting resynchronizes current statuses. Statuses are sent on change, retried after failure, and refreshed at most once per 10 seconds. Gesture events are not retried after failure and expire after 2 seconds; perform a new movement after reconnecting.

`recordings/tracker_events.jsonl` captures actual sends/ACKs/errors from this run. Do not use unit-test logs or simulator events as hardware proof. A broker ACK proves ingestion, **not** that a human saw the React update; verify the browser separately. The existing broker keeps only the last event's provenance, so correlate the log timestamp and label.

## 7. P1 Lab 5 shape experiment (separate, offline)

This uses real **Hand Landmarker fingertips**, not pose wrist or coarse pose finger locations. Show exactly one hand, use the same hand throughout, keep it visible, and trace shapes by moving the hand/fingertip in the air. Rectangle should be clearly wider than tall; square should have equal physical side lengths. Aspect-ratio correction preserves this distinction before DollarPy normalization.

```powershell
.\.venv\Scripts\python.exe backend\download_tracker_model.py --kind hand
.\.venv\Scripts\python.exe backend\pose_tracker.py --channel thumb --check-model
```

For each finger (`thumb`, then `index`) and each class (`circle`, `rectangle`, `square`), capture **two train samples** and **one fresh test sample**. This is 18 recordings total (12 train, 6 test). Use the following commands, changing the channel/label as needed. Press SPACE twice in the first command and once in the second; ESC exits each command.

```powershell
.\.venv\Scripts\python.exe backend\pose_tracker.py --channel thumb --record-label circle --split train --seconds 3 --camera 0 --consenting-adult --offline
.\.venv\Scripts\python.exe backend\pose_tracker.py --channel thumb --record-label circle --split test --seconds 3 --camera 0 --consenting-adult --offline
```

| Finger | Circle train/test | Rectangle train/test | Square train/test |
|---|---|---|---|
| Thumb | 2 / 1 | 2 / 1 | 2 / 1 |
| Index | 2 / 1 | 2 / 1 | 2 / 1 |

```powershell
.\.venv\Scripts\python.exe backend\pose_tracker.py --channel thumb --evaluate --min-test 1 --report recordings\thumb_evaluation.json
.\.venv\Scripts\python.exe backend\pose_tracker.py --channel index --evaluate --min-test 1 --report recordings\index_evaluation.json
```

Confirm each report contains all THREE named classes and the exact table counts above. This is the lab's tiny demonstration split, not strong statistical evidence. Hardware collection and classification accuracy for these shapes are not yet verified. This exercise does not claim a gameplay pointer or pinch implementation.

## 8. Human validation record to complete

Keep adult face footage local; use a body-only crop or a live demonstration for submission. Do not upload identifiable child/adult video or raw private trajectories to GitHub. No evidence is pre-filled as a pass.

| Check | Actual result to fill |
|---|---|
| Test date, Windows version, camera/device/index, resolution | PENDING |
| Adult agreed; no children recorded | PENDING |
| Real skeleton shown; tracking loss and return | PENDING |
| Wrist training counts: horizontal / vertical | PENDING |
| Wrist held-out counts: >=5 per class | PENDING |
| Actual predictions, mistakes and rejection count | PENDING |
| Real camera/pose and DollarPy ACKs | PENDING |
| React visibly updated from those exact events | PENDING |
| No camera, corrupt/missing model, broker offline and recovery | PENDING |
| ESC closes and camera can be reopened | PENDING |
| Thumb/index 18-recording experiment | PENDING |

## 9. Commit only scoped source and docs

After applying on the feature branch and rerunning checks:

```powershell
# From repository root:
git diff --check
git diff --stat
git status --short
git add phase2/backend/pose_tracker.py phase2/backend/gesture_data.py phase2/backend/tracker_events.py phase2/backend/download_tracker_model.py
git add phase2/tests/test_mostafa_tracker.py phase2/tests/test_mostafa_socket.py
git add phase2/requirements-mostafa.txt phase2/templates/local/.gitignore phase2/models/.gitignore
git add phase2/docs/MOSTAFA_DEMO.md phase2/docs/MOSTAFA_TEST_RESULTS.md
git diff --cached --stat
git diff --cached
git commit -m "Implement pose capture and DollarPy evaluation for Phase II"
git push -u origin feature/mediapipe-dollarpy
```

Open a PR **from feature/mediapipe-dollarpy into main**, assign/request Youssef's review, and include actual Windows/hardware results. Do not merge or push to main. If your actual main has different UI/state contracts, reconcile with Youssef first. `PR_DESCRIPTION.md` in the delivery is a draft, not a submitted message.

## Sources checked

- Official Pose Python Tasks guide: https://developers.google.com/edge/mediapipe/solutions/vision/pose_landmarker/python
- Pose models/landmarks: https://developers.google.com/edge/mediapipe/solutions/vision/pose_landmarker
- Hand models/landmarks: https://developers.google.com/edge/mediapipe/solutions/vision/hand_landmarker
- DollarPy upstream: https://github.com/sonovice/dollarpy
- Supplied official Phase II rubric, final Phase I submission, Mostafa handoff v03, Lab 5 deck and both notebooks.
