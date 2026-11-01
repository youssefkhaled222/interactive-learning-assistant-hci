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

## TCP sensor ingress validation (additive v0.2)

The broker now validates **types and allowed fields before applying any event**.
These are the same event names and payloads already documented above. There
are no extra fields to add to Mostafa's or Malak's messages. Every TCP event
must contain a non-empty string `source` field; the existing examples do.

- `pose.tracking.visible` and `camera.status.ready` must be JSON booleans
  (`true`/`false`), **not** strings such as `"false"`, or integers such as `0`.
- `device.discovered.device_id`, `gesture.recognized.name` and
  `game.select.object` must be non-empty strings. `gesture.recognized.score`,
  when included, must be a finite JSON number, not a percentage string.
- `lighting.changed.level` must be `good`, `low` or `unknown`.
- Unexpected event names, missing fields and extra fields are rejected with
  `{"ok":false,"error":"..."}`. The TCP connection remains usable after a
  valid-size invalid event; one event rejection does not change game state or
  broadcast to React. Oversized events (over 8192 bytes) close that connection.
- Valid messages still receive `{"ok":true}` and broadcast full current state.

**Trust boundary:** Schema validation is **not authentication**. Any local
program able to connect to the TCP port can claim `source:"mediapipe"` or
`source:"bleak"`. Those strings are debugging labels, never proof of real
hardware. The hardware demonstrations must show the source process, sensors
and output independently. Real target matching and gaze calibration are not
implemented by this validation change.

Run `python -m unittest discover -s tests -v` before submitting changes.
