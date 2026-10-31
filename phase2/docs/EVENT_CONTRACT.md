# Phase II Event Contract — FROZEN v0.1

All processes run locally. Sensor modules write **one JSON object per line** to TCP `127.0.0.1:8765` (UTF-8, JSONL). The broker replies `{ "ok": true }` or `{ "ok": false, "error": "..." }`. The frontend receives the resulting full state over WebSocket `ws://127.0.0.1:8766` as `{ "type": "state", "payload": { ... } }`.

| Event | JSON example | Responsible person |
|---|---|---|
| `device.discovered` | `{"type":"device.discovered","device_id":"demo-device-beginner","source":"bleak"}` | Malak |
| `device.lost` | `{"type":"device.lost","source":"bleak"}` | Malak |
| `pose.tracking` | `{"type":"pose.tracking","visible":true,"source":"mediapipe"}` | Mostafa |
| `gesture.recognized` | `{"type":"gesture.recognized","name":"swipe_right","score":0.8,"source":"dollarpy"}` | Mostafa |
| `camera.status` | `{"type":"camera.status","ready":true,"source":"mediapipe"}` | Mostafa |
| `lighting.changed` | `{"type":"lighting.changed","level":"low","source":"camera"}` | Mohamed + Mostafa |
| `mode.selected` | `{"type":"mode.selected","mode":"gesture","source":"ui_bridge"}` | Youssef + Ahmed |
| `game.select` | `{"type":"game.select","object":"apple","source":"gesture"}` | Youssef + Mostafa |
| `game.restart` | `{"type":"game.restart","source":"ui_bridge"}` | Youssef + Ahmed |

**Strict rules**

1. `source:"simulator"` is only for testing the software pipeline. Never present that as hardware proof.
2. Detected Bluetooth identifiers are NOT human UserIDs. Only explicitly enrolled demo devices can map to pseudonymous IDs. The current `ble_scan.py` only scans, not enrollment or GATT capture.
3. DollarPy recognizes **trajectory templates**, not automatically a finger pinch. Actual pinch input needs a hand landmark detector and pinching threshold, not included in this starter.
4. The `game.select` event is an integration contract and currently the demo generator supplies it. Production code must validate the target using actual gesture/gaze/object sensor output.
5. This starter does not implement real object detection or calibrated eye tracking. Both remain work for the team.
6. Python TCP and WebSocket bridge run locally; do not expose ports to the internet.

## Browser command extension

For validated **React-to-Python** commands, see `WS_COMMANDS.md`.
This extension does not change or replace the existing TCP sensor event contract.
