# Phase II end-to-end integration smoke test

This is a **software pipeline test using simulated events**. It does **not** verify real Bluetooth hardware, MediaPipe skeleton detection, DollarPy recognition, camera light sensing, object detection, eye tracking, or real child interactions. Never present it as proof that those functions are implemented.

## Running the check on the discussion laptop

1. Make sure you are on the expected Git branch. From `phase2/`, start **one** backend process:
   `\.venv\Scripts\python.exe backend\server.py`
2. Optionally run `npm.cmd run dev` from `phase2/frontend/` and open `http://127.0.0.1:5173/`.
3. In a **second** terminal from `phase2/`, run:
   `\.venv\Scripts\python.exe backend\integration_smoke.py`
4. Review the PASS lines. The script connects to **real** local TCP `127.0.0.1:8765` and WebSocket `127.0.0.1:8766`, checks the initial state, pushes simulated contexts and sensor events, verifies their broadcast, verifies invalid message rejection, sends browser-mode commands, then returns to guest/gesture state.

**Do not run it while a teammate is demonstrating a real sensor.** It changes the single running server's shared demo session. It resets most demo context but not every diagnostic field (e.g. last recognized gesture); for a completely fresh demonstration, restart the backend once after smoke testing.

## Automated checks

From `phase2/`:
`\.venv\Scripts\python.exe -m unittest discover -s tests -v`

`test_integration_smoke.py` starts its own ephemeral local TCP and WebSocket ports, so it does not require the normal server or compete with its usual ports.

## Real hardware acceptance (separate from this smoke test)

- Mostafa: webcam displays an actual human skeleton; saved DollarPy templates classify actual held-out motion and publish an event.
- Malak: an explicitly enrolled BLE peripheral is genuinely discovered/identified and causes a profile update.
- Mohamed: content switches between five-question learning packs in genuine UI updates and respects Phase I retry/Next Object behavior.
- Ahmed: all approved Figma screens render and respond to live backend messages.
- Youssef: observe each actual sensor process, TCP acknowledgement, corresponding WebSocket state and React update; document limitations. A `source` label alone is not hardware proof.
