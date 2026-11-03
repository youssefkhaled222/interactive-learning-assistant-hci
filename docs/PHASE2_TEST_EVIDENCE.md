# HCI Phase II — test evidence and limitations register

**Snapshot:** 3 November 2026; latest documented implementation commit `a927371` on `feature/real-eye-tracking`. This is an evidence log, **not** a claim that all course acceptance criteria have been met.

## Confirmed from developer's Windows logs

| Observation | Evidence | Interpretation |
|---|---|---|
| V5.2 installer successful | `SUCCESS: Phase II V5.2 safely installed ...` | Gesture feature integrated without overwriting unrelated code |
| Python V5.2 | **185 tests**, `OK` | Automated backend suite passed before gaze implementation |
| React V5.2 | **19 passed, 0 failed** | Frontend regression suite passed before gaze implementation |
| Vite V5.2 | Built successfully | Frontend compiles |
| Live gesture physical game | Screenshot: **5/5 questions completed, 5/5 correct on first try, wrong attempts 0** | Real camera-based gesture gameplay finished one full session; not necessarily every negative/recovery scenario |
| Git milestone | Commit `f3602a7` pushed to `feature/real-hand-object-selection` | Proven gesture code preserved remotely |
| V6 installer and model setup | `SUCCESS: HCI gaze V6 installed ...`; official Face Landmarker model download success | Gaze code installed and model obtained on original development PC |
| Python V6 | **198 tests**, `OK` | Adds 13 Python tests covering gaze and integration logic; not camera accuracy |
| React V6 | **22 passed, 0 failed** | Adds 3 frontend tests covering calibration points and preview geometry |
| Vite V6 | Built successfully | Current React source compiles |
| Git V6 milestone | Commit `a927371` pushed to `feature/real-eye-tracking` | Gaze implementation preserved remotely but still experimental on hardware |

The deliberate invalid-input test messages and simulated WebSocket disconnect warnings in unittest output are expected **when the final suite result is `OK`**. Do not erase them from raw evidence.

## Teammate-reported results (separately tested)

- **Malak's BLE:** She reported her configured real LightBlue/peripheral identification test succeeded when she delivered her code. The application contains a Bleak monitor and registered learner mapping; the latest combined V6 deployment has not been physically demonstrated alongside her phone.
- **Mostafa's Pose + DollarPy:** Component and templates had separate testing and code is present in the combined repository; the final classroom combined sequence and camera coordination are still pending. Tests contain simulated event acceptance; this is **not** the same as a new live body-tracking run.

## Not yet evidenced

- A passing **real, nine-point gaze calibration** on two live cameras.
- Real 1.5-second gaze-driven selection and a completed five-question gaze session.
- Measured gaze calibration error on real users across multiple repetitions or lighting conditions.
- Combined Bluetooth + Pose + gaze/gesture end-to-end classroom demonstration.
- A timed, consented usability study with child participants, task-completion distributions, SUS-type scales, or statistical hand-versus-gaze comparison.
- Confirmation of the course's latest Phase II submission rubric, deadline or required artifact format.

## Required final gaze-test report template

**Only the assigned teammate fills this in after the last physical test.** Do not prefill success values.

| Field | Tester's actual observation |
|---|---|
| Date, tester and consent | TBD |
| Git commit | TBD |
| Windows/Python/MediaPipe/Ultralytics versions | TBD |
| Object-camera device and index | TBD |
| Face-camera device and index | TBD |
| Detected physical objects | TBD |
| Nine-point calibration status / error | TBD |
| Gaze pointer alignment and notable drift | TBD |
| First successful dwell, exact backend log | TBD |
| Correct/incorrect count out of five | TBD |
| Face loss, short hold, stale box, ambiguous overlap responses | TBD |
| Gesture regression after V6 | TBD |
| Screenshots/console log references | TBD |
| Open issues or conclusion | TBD |

**Evidence rule:** An application result screen is evidence of backend-recorded completion, but any claim that the selection came from the physical gaze pipeline should also include face-camera tracking/calibration status and the backend's gaze-selection log. Avoid relying on simulated sensor events.
