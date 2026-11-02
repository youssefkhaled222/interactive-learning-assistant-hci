# Test Results: Context-Aware Content Engine

Only results that were actually observed are recorded here. Fill in the empty rows when each test is run.

## A. Automated tests

Command (PowerShell, from `phase2`):
```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

| Where | Python | Result | Date / who |
|---|---|---|---|
| Development copy of the starter snapshot (Linux, not the team laptop) | 3.11.18 | 38 tests, all OK (6 baseline + 32 new) | 2026-11-01, during development |
| Mohamed's Windows laptop on `feature/context-aware-engine` | | *not run yet* | |
| Integration run after merge (Youssef) | | *not run yet* | |

Baseline note: `test_completed_and_first_try_separate` was updated from 3 answers to the full 5-answer beginner pack,
because the packs now have 5 questions (a 3-question assertion cannot hold any more). The other five baseline tests
are unchanged.

## B. Software pipeline (simulator only — not hardware proof)

`server.py` + `context_demo.py` (`source:"simulator"`) + a WebSocket listener, in the development copy:

| Step | Question received over WebSocket | Status |
|---|---|---|
| no device | Can you find the apple? (guest) | Ready for setup / New session |
| beginner device | Find the red apple | Registered profile loaded: Beginner pack |
| answer apple | Find the cup | Correct! Next question |
| same device again | Find the cup (no reset) | unchanged |
| tracking lost | Find the cup, `input_blocked:true` | Tracking lost - show your hand… |
| select while paused | Find the cup (ignored) | Tracking lost… |
| tracking back | Find the cup | Tracking is back - continue question 2 |
| low light | Find the cup | Low light - turn on a lamp… |
| advanced device | Which object do we use for reading? | Registered profile loaded: Advanced pack |
| advanced device lost | Can you find the apple? (guest) | Device lost; guest content loaded |

To repeat on Windows: run the three terminals in `docs/CONTEXT_ENGINE.md` §6 and fill in:

| Check on Mohamed's laptop (React preview) | Seen? |
|---|---|
| Prompt and choice cards change guest → beginner → advanced → guest | |
| Paused message appears while tracking is lost | |
| Low-light message appears | |
| Side panel shows "SIMULATION" for these events | |

## C. Real hardware context (with teammates; consenting adult tester only)

| Scenario | Real source | Expected | Observed |
|---|---|---|---|
| Malak's enrolled beginner device discovered | `bleak` | Beginner questions on screen | *pending* |
| Second enrolled device (if available) | `bleak` | Advanced questions on screen | *pending* |
| Device switched off / out of range | `bleak` | Guest questions after lost event | *pending* |
| Tester steps out of camera view | `mediapipe` | Input paused, progress kept | *pending* |
| Tester returns | `mediapipe` | "Tracking is back", same question | *pending* |
| Camera unplugged / closed | `mediapipe` | Camera-not-ready message | *pending* |
| Low light | only if a real camera adapter sends `lighting.changed` | Guidance message | *pending / not implemented by camera adapter yet* |


## Integration review (November 2, 2026)

Corrected version was tested against the full reconstructed repo at latest known commit
`199108d`, not just Mohamed's standalone patch. Result: **104/104 automated tests PASSED**
(Linux container with Python 3.13). Includes live loopback TCP/WebSocket context handoff,
`game.next` browser command, strict production sensor readiness, invalid/stale BLE events,
and camera shutdown regressions. This is *not yet* an execution on Youssef's Windows machine;
run `phase2\.venv\Scripts\python.exe -m unittest discover -s phase2\tests -q` there.
Actual Bluetooth enrollment, DollarPy/pinch, gaze and two-camera live demos remain pending.
