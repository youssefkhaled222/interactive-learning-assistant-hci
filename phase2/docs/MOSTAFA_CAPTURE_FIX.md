# Wrist capture diagnosis and preparation countdown

This update follows the uploaded HCI_Wrist_Debug.zip: 4 training and 18 test recordings.
The unchanged DollarPy evaluator reproduced 0 accepted correct predictions out of 18
at threshold 0.5. Before applying rejection, 6 labels were correct, 6 incorrect,
and 6 returned no label. No improvement in real-world accuracy is claimed yet.

## Observed cause of poor matching

The recorded trajectories have substantial turns/retracing and do not form
consistent horizontal versus vertical templates. In 5 of 8 horizontal test
recordings, the vertical span is greater than the horizontal span. The four
training trajectories also contain large turns. These are measurements of the
tracker output, not proof of what the adult physically did.

Possible contributors include reaching to/from the keyboard, returning the hand
before recording ends, moving a different hand, or incorrect/noisy landmark
tracking. Coordinates alone cannot establish which contributor occurred.
The original recorder began immediately after SPACE, leaving no preparation time.

## What changed

- SPACE now starts a 3-second preparation countdown; no preparation points are saved.
- At GO the full 1.8-second recording begins; move once and hold until Saved.
- A cyan circle and RIGHT WRIST label identify the exact tracked landmark.
- An orange trail shows the trajectory being captured.
- Saved messages include the number saved during this run, and the preview shows
  the label and split, reducing accidental capture into the wrong class.
- Tracking loss still cancels the whole recording. No smoothing, relabeling,
  automatic sample deletion, score changes, or threshold reductions were applied.

The data schema, TCP events, and classifier remain unchanged. This update does not
repair the shapes in earlier files; keep the original recordings and failed report.

## Apply and check (PowerShell)

Extract HCI_Mostafa_CaptureFix.zip to Downloads/HCI_Mostafa_CaptureFix.
Close the tracker window before applying. Use the existing feature branch:

```powershell
cd "$HOME\Projects\interactive-learning-assistant-hci"
py -3.11 "$HOME\Downloads\HCI_Mostafa_CaptureFix\apply_capture_fix.py" --repo "$PWD" --apply
cd phase2
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The updater requires the expected Iteration2 tracker/classifier and the feature
branch. Existing uncommitted Iteration2 work is expected, so a clean tree is not
required. Only the tracker, one new test file and this document are changed.
No commit, push, merge, recording deletion or model download is performed.

## Small pilot before a new formal evaluation

Use an adult who agrees to local recording. Keep the camera fixed and torso/hips
visible. Confirm the cyan circle follows the anatomical RIGHT wrist. Prefer
pressing SPACE with the left hand. During GET READY, bring the right hand to the
start position; start moving only at GO. Make ONE straight stroke, then HOLD the
endpoint until Saved. Do not move back to the keyboard during recording.
If the circle jumps to a different place while the real wrist stays still, stop
and inspect camera framing/lighting/occlusion before collecting more samples.

The following separate directory is under the existing ignored local-data tree.
Do not mix these pilot samples with the earlier train/test folders.

Capture TWO training samples for each command (SPACE twice, waiting for Saved):

```powershell
.\.venv\Scripts\python.exe backend\pose_tracker.py --camera 0 --record-label horizontal --split train --data-dir templates\local\capture_pilot --consenting-adult --offline
.\.venv\Scripts\python.exe backend\pose_tracker.py --camera 0 --record-label vertical --split train --data-dir templates\local\capture_pilot --consenting-adult --offline
```

Capture ONE new pilot test per class, then evaluate without changing threshold:

```powershell
.\.venv\Scripts\python.exe backend\pose_tracker.py --camera 0 --record-label horizontal --split test --data-dir templates\local\capture_pilot --consenting-adult --offline
.\.venv\Scripts\python.exe backend\pose_tracker.py --camera 0 --record-label vertical --split test --data-dir templates\local\capture_pilot --consenting-adult --offline
.\.venv\Scripts\python.exe backend\pose_tracker.py --evaluate --min-test 1 --data-dir templates\local\capture_pilot --report recordings\wrist_pilot.json
```

This tiny pilot is for diagnosis, not final accuracy evidence. If acceptable, fix
the collection procedure and templates, then collect a NEW independent held-out
set (at least 5 per class) for final reporting. If not acceptable, preserve all
pilot samples/errors and inspect them before changing the recognizer.

For a follow-up diagnosis:

```powershell
Compress-Archive -Path .\templates\local\capture_pilot\right_wrist, .\recordings\wrist_pilot.json -DestinationPath "$HOME\Downloads\HCI_Wrist_Pilot.zip" -Force
```

## Validation limits

Automated capture tests simulate time and coordinates. They verify exclusion of
preparation movement, full capture duration, cancellation at lost tracking, and
repeated-key handling. They do not establish webcam accuracy or UI usability on
Windows. The actual user must verify those after applying.

Before committing this follow-up, include the new files with the original scoped
changes: phase2/tests/test_mostafa_countdown.py and
phase2/docs/MOSTAFA_CAPTURE_FIX.md. Raw recordings and diagnostics stay local.
