# Context-Aware Learning Content Engine (Mohamed Ramadan, 246813)

Rubric item: **Load Different Content based on Context (2 marks)**.
Branch: `feature/context-aware-engine`. Files owned: `backend/engine.py`, `backend/content_packs.py`,
`backend/context_demo.py`, `tests/test_engine.py`, `tests/test_context_engine.py`.
`server.py` now enables strict readiness; frontend remains unchanged. Socket contracts are extended compatibly.

## 1. Content packs (`backend/content_packs.py`)

| Pack | Who gets it | Prompt style | Answer order |
|---|---|---|---|
| `guest` | no device, unknown device, or device lost | "Can you find the apple?" | apple, book, cup, apple, book (Phase I order) |
| `beginner` | `demo-device-beginner` → `learner_01` (about 5-7) | names the object: "Find the cup" | apple, cup, book, apple, cup |
| `advanced` | `demo-device-advanced` → `learner_02` (about 8-10) | describes use, never names it: "Which object do we use for reading?" | book, cup, apple, book, cup |

Rules checked by `validate_packs()` when the engine is imported (the server refuses to start with a broken pack):
exactly 5 questions; choices are exactly apple/cup/book with no duplicates; the answer is one of the choices;
every object is asked at least once; never the same object twice in a row; no prompt is reused across packs.
Each question also has a `hint`, which the UI can show after a wrong attempt (`show_hint`).
Gaze and gesture mode use the same packs, so both techniques get the same task.

## 2. Context rules

| Context event | What the engine does |
|---|---|
| `device.discovered` registered ID | Loads that learner's pack. A different learner resets the session. |
| `device.discovered` unknown ID | Guest pack. If the learner was already guest, progress is kept. |
| Same `device_id` again (repeated BLE advert) | Ignored. Session and status are untouched. |
| `device.lost` | Back to guest, and a registered learner's session resets. Ignored if no device is connected, or if `device_id` names an older device. |
| Optional `ts` on device events | An event older than the last device event is ignored, so a late message can't overwrite a newer profile. |
| `pose.tracking visible:false` | Input blocked (`input_blocked`, `block_reason:"tracking_lost"`). The message depends on mode ("show your hand" / "look at the screen"). Progress is kept. |
| `pose.tracking visible:true` | Unblocks: "Tracking is back - continue question N". |
| `camera.status ready:false` | Input blocked (`camera_not_ready`) with a message for the supervising adult. |
| `lighting.changed low` | Non-blocking notice with an action ("turn on a lamp…"). The engine only reports what an adapter sends; it does not measure light itself. |
| `mode.selected` (different mode mid-session) | Restarts the same pack, so one session = one technique for the comparison. |
| `game.select` while blocked / complete | Ignored. Never counted as a wrong attempt. |
| Same `game.select` object within 1.5 s | Treated as a repeated detection and counted once. |
| Garbage values (`visible:"no"`, empty `device_id`, unknown type, non-string `source`, …) | `ValueError` before any state changes. The broker replies `{"ok":false,...}`. |

The live server blocks selections until camera readiness and gesture tracking are observed.
The pure `Engine()` retains a permissive default for legacy unit tests and simulated software-only flows.
When gaze mode is selected, the strict live server always blocks selections until genuine calibrated eye tracking is implemented.

## 3. New state fields (additive; existing fields keep their meaning)

`pack_id`, `pack_title`, `age_range`, `pack_description`, `question.number`, `question.hint`, `show_hint`,
`questions_completed`, `input_blocked`, `block_reason`, `notices` (list of `{code, message, blocking}`),
`awaiting_next`, `require_next`.
`status` shows the blocking message while input is blocked.
**Ahmed:** please render `question.prompt/choices` (already shown), `notices`, `show_hint` + `question.hint`, and use
`questions_completed` vs `first_try_correct` on the Results screen.

## 4. "Next object" (Phase I) vs auto-advance (starter): migration proposal

Phase I says that after a correct answer the child selects **Next object**. The starter auto-advances on `game.select`.
To avoid breaking the shared contract, the engine supports both:

- Default `Engine()` (what `server.py` builds today) = **auto-advance**, unchanged behaviour.
- `Engine(require_next=True)` = correct answer sets `awaiting_next:true` and keeps the question on screen.
  The new command `{"type":"game.next","source":"ui_bridge"}` moves on. In auto mode `game.next` is a harmless no-op.

The reviewed server accepts `game.next` through its strict browser command handler,
AND via validated local TCP events for future genuine gesture-based Next selection.
The production server enables the Next Object flow using `HCI_REQUIRE_NEXT=1`, e.g. in PowerShell:
`$env:HCI_REQUIRE_NEXT="1"; .\.venv\Scripts\python.exe backend\server.py`.
Do **not** enable this yet with Ahmed's old preview: it has no Next Object button and would stall
after the first correct answer. Ahmed must render `awaiting_next` and send
`{ "type":"command", "action":"game.next", "payload":{} }` on the explicit Next action.
For a genuine hands-free demo the Next action must come from real calibrated gesture/gaze integration, not a UI click.

## 5. Notes for teammates

- **Malak (BLE):** keep sending the enrolled `device_id` (`demo-device-beginner` / `demo-device-advanced`) with
  `source:"bleak"`. Please include `device_id` in `device.lost`, and add `ts` (e.g. `time.time()`) if you can.
  Repeated `device.discovered` for the same device is safe. Please debounce `device.lost` (e.g. ~10 s unseen),
  because a lost event for a registered learner resets the session.
- **Mostafa (camera):** `pose.tracking.visible` and `camera.status.ready` must be real booleans (they already are in
  `pose_tracker.py`). A `lighting.changed` event should only be sent if the camera adapter actually estimates brightness.
- **Youssef:** no `server.py` change is needed for the default mode. The `ValueError`s now cover more bad input; the
  broker already turns them into `{"ok":false}`.

## 6. Live demo (simulator, clearly labelled)

Terminal 1 `backend\server.py`, terminal 2 `npm.cmd run dev` in `frontend`, terminal 3:
`.\.venv\Scripts\python.exe backend\context_demo.py`. It prints each step and the question that should appear.
The React card's prompt and choices change (guest → beginner → advanced → guest), and the side panel shows
"Last source simulated? Yes - SIMULATION". The real-hardware version is the same steps with Malak's BLE device and
Mostafa's camera instead of the simulator.

## 7. Review corrections and integration status (November 2, 2026)

- `device.lost.device_id` and optional **finite, nonnegative** `ts` for `device.discovered` / `device.lost`
  are now supported by the TCP validator. Invalid or unrelated lost-device reports do not advance
  the timestamp guard or change the current learner. Without `device_id`, an un-timestamped loss
  cannot be tied to a particular device; Malak should supply the enrolled ID whenever available.
- Deduplication is scoped by question and reset on advance so real next-question attempts are preserved.
  A repeated sensor event can still be a true new attempt; hardware edge detection remains a separate task.
- Live `server.py` uses `Engine(require_sensor_ready=True)`, which requires `camera.status ready:true`
  and `pose.tracking visible:true` for gesture-mode selection. This is readiness checking, **not**
  proof of a genuine pinch or valid target. In gaze mode the server refuses selections because no
  calibrated eye-point input is implemented yet. Simulated tests instantiate the engine explicitly.
- The Next Object command is wired but opt-in until Ahmed integrates the corresponding feedback
  and Next screen. The legacy Vite preview will not navigate through a five-question Next flow itself.
- `validate_packs` enforces all 3 choices on every question. Original five-question content is preserved.
- Camera-off regressions were updated to assert the critical behavior and blocking notices rather
  than exact old strings. The live YOLO object-detection bridge is unchanged.
- 104 combined automated tests passed in reconstructed Linux baseline; Windows, live BLE/DollarPy,
  the new frontend and physical multi-camera system still require testing.
