# Phase II React-to-Python WebSocket Commands (additive v0.1)

**Audience:** Ahmed (React), Youssef (socket broker), Mohamed (game engine).

This document *adds* browser-originated commands without changing the existing
`EVENT_CONTRACT.md` sensor JSONL contract. No webcam or Bluetooth simulation is
created by a browser command.

Connect to `ws://127.0.0.1:8766` from Vite at `http://127.0.0.1:5173`.
On connect and after **every successful event** (TCP or browser command), the
server pushes `{"type":"state","payload":{...}}` to all clients.

## Allowed browser commands

```json
{"type":"command","action":"mode.selected","payload":{"mode":"gesture"}}
```

Change the mode to `"gaze"` if the user selects Eye Tracking. This changes the
mode state, but does **not** claim the camera or gaze calibration is functional.

```json
{"type":"command","action":"game.restart","payload":{}}
```

Reset learning session statistics and question index using the existing engine.
The server attributes these events itself with `"source":"ui_bridge"`.
Do not attach a `source` field; unrecognized/extra fields are rejected.

### Browser example for Ahmed

```js
const socket = new WebSocket('ws://127.0.0.1:8766');
socket.onmessage = (event) => {
  const message = JSON.parse(event.data);
  if (message.type === 'state') updateAppState(message.payload);
  if (message.type === 'error') showError(message.message);
};
function sendCommand(action, payload = {}) {
  if (socket.readyState !== WebSocket.OPEN) return false;
  socket.send(JSON.stringify({ type: 'command', action, payload }));
  return true;
}
// sendCommand('mode.selected', { mode: 'gesture' });
// sendCommand('game.restart');
```

Invalid messages receive `{"type":"error","message":"..."}`. The browser
must handle disconnects and prevent commands while disconnected.

## Not yet allowed from the browser

- `game.select`: only verified camera/sensor target-selection events (TCP) may
  cause a real gameplay answer. A mouse-click simulation cannot claim hardware.
- `game.next`: **pending agreement with Mohamed**. Phase I requires a Correct
  Answer feedback state and explicit Next object before the index advances;
  the baseline engine currently advances immediately. Mohamed owns this state
  machine change; contact Youssef before enabling the next command.
- BLE, pose, lighting and camera status events: originate from sensor adapters,
  not frontend buttons.

The WebSocket server is loopback-only, limits message size, and accepts only
local approved frontend Origin values (`http://127.0.0.1:5173`,
`http://localhost:5173`) or origin-less local development tools. If Vite picks
another port, stop the conflicting process or coordinate a config change.

## Smoke test

1. Start the backend with `python backend/server.py` from `phase2`.
2. Run all tests: `python -m unittest discover -s tests -v`.
3. Launch Vite on port 5173 and open the developer console.
4. From another terminal, run `python backend/demo_ui_commands.py`. Observe the
   React preview switch to gaze mode and print the server-attributed responses.
5. For browser security validation, `game.select` from WebSocket gets a
   `type:error` response (automatically tested by `test_socket_bridge.py`).
6. Run `backend/demo_sequence.py`; TCP adapters must still update the preview.

Important: this command channel tests software communication only.
