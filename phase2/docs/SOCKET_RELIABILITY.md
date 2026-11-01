# Socket resilience (additive; no event contract changes)

The Python TCP JSONL broker remains on `127.0.0.1:8765` and the browser WebSocket on `127.0.0.1:8766`. Existing JSON events and browser commands are unchanged.

- On every state update, WebSocket broadcasts are concurrent. One stalled browser is allowed at most 1 second for sending before being removed from the subscriber set. Responsive browsers continue to get updates; the sensor process is not indefinitely blocked waiting for a slow client.
- A browser that reconnects receives an initial snapshot of the current state. The application must still handle reconnects on the React side; this change does not add frontend reconnect logic.
- If a TCP sensor producer exits or resets its socket unexpectedly, the server cleans up that connection and continues serving other producers.
- Schema validation (see `EVENT_CONTRACT.md`) still takes place *before* an event reaches the engine. It is **not proof of hardware origin** or authorization. A successful TCP acknowledgment does not prove the React screen rendered the event.
- Lost sensor processes do **not** automatically mean that a previously detected BLE device was disconnected or that tracking stopped: those require actual `device.lost` / `pose.tracking` events or an agreed sensor-liveness mechanism, which are not part of this change.

Test from `phase2/`: `python -m unittest discover -s tests -v`.

For local smoke tests, start `python backend/server.py`, then send a valid event using `backend/send_event.py` and verify the connected React UI. If port 8765/8766 is already occupied, stop the old server process instead of starting another.
