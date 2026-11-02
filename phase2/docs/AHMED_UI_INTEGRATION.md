# Ahmed's Figma React UI — reviewed integration

Scope: **frontend only**, based on Ahmed Wahba's submitted source-only ZIP. The existing Python engine, validators, YOLO bridge, and sensor adapters are unchanged.

## Implemented

- Retains all eight screen sections: Welcome, Mode, Hand Tutorial, Gaze Calibration visual, Camera Setup, Gameplay, Feedback, Results.
- Uses the real backend state (`pack_title`, `question`, `show_hint`, `notices`, `input_blocked`, `questions_completed`, `awaiting_next`, `detected_objects`).
- Correct feedback triggers when `questions_completed` increases, **even when `question_index` remains unchanged** in the Next Object mode.
- During `HCI_REQUIRE_NEXT=1`, the Feedback screen sends the existing `game.next` browser command and waits for the backend state change before showing the next question.
- After the fifth correct answer, Feedback offers "View results"; score distinguishes completed questions from first-try correct.
- Does not infer the answer from the question prompt or reveal its emoji in the main stage.
- Eye calibration remains **clearly nonfunctional**, not a fake mouse-based calibration.
- Shows sanitized object detection *metadata*, not a video preview. Mouse option cards are labeled local preview only; they never submit `game.select`.

## Non-goals / remaining integration

- No browser-initiated `game.select`, fake sensor events, or unverified pinch/gaze commands.
- Does not bring in Ahmed's archived backend files: they predate Mohamed's five-question engine.
- Ahmed's combined YOLO/hand tracker is **not merged** here. Mostafa's gesture adapter and actual pinch selection need review; no live hand-to-box-to-engine pipeline has been certified.
- Neither camera pixels nor eye-tracking samples are streamed through the socket; React shows metadata only.
- A second physical camera and real BLE enrollment are not verified.

## Test on Windows

From the repo root:

```powershell
.\phase2\.venv\Scripts\python.exe -m unittest discover -s phase2\tests -q
cd phase2\frontend
npm.cmd ci
npm.cmd test
npm.cmd run build
```

For live UI (two terminal windows):

```powershell
# Terminal 1, from phase2:
$env:HCI_REQUIRE_NEXT="1"
.\.venv\Scripts\python.exe backend\server.py
# Terminal 2, from phase2/frontend:
npm.cmd run dev
```

Open http://127.0.0.1:5173. Click through Welcome → Hand tutorial → Camera Setup → Gameplay. This is UI navigation and backend state only; verified physical hand or gaze selection is a separate hardware test. Use backend-supported simulator only if explicitly labeling it as simulated. On the Feedback screen a correct sensor event will enable **Next Object**, and the Results screen follows five correct answers.
