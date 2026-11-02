# Bluetooth Discovery and UserID — Phase II

**Project:** Interactive Learning Assistant for Children (CS484, Fall 2026)  
**Contributor:** Malak Gamal (247419)  
**Scope:** Real BLE discovery, demonstration-device identification via GATT, backend events, and presence/loss monitoring.

## Implementation summary

A Windows laptop scans for an explicitly configured LightBlue virtual BLE peripheral running on a team member's iPhone. The test device advertises as `hci-test-device`. After discovery, `ble_monitor.py` connects through Bleak and reads an application-specific **test device key** from a GATT characteristic. Only the expected registered key (`demo-device-beginner`) can trigger a `device.discovered` event. The existing backend maps that key to the pseudonymous profile `learner_01` (beginner questions), and React receives the updated state through the existing WebSocket connection.

**The GATT value is an enrolled classroom test key, not a verified personal identity.** It is static, not cryptographically authenticated, and should not be used as secure login. Unknown keys never receive a known learner profile.

## Hardware and BLE configuration

- **Windows:** Bluetooth LE adapter enabled, with Python 3.12.10 used for the demonstrated test.
- **Peripheral:** Consenting team member's iPhone with LightBlue's Virtual Devices / virtual peripheral functionality.
- **Advertising name:** `hci-test-device` (keep LightBlue advertising and the phone available during the demonstration).
- **Service UUID:** `00001111-0000-1000-8000-00805f9b34fb`.
- **Readable characteristic UUID:** `00002222-0000-1000-8000-00805f9b34fb`.
- **Characteristic value (UTF-8):** `demo-device-beginner`.
- **Hex value:** `64656D6F2D6465766963652D626567696E6E6572`.

The test key is not an iPhone hardware address. The implementation intentionally avoids publishing real BLE device addresses, which may be unstable or privacy-sensitive.

## Setup and run (PowerShell)

From the repository root, create the environment if needed:

```powershell
cd phase2
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-bluetooth.txt
```

Start the team's existing backend in terminal 1:

```powershell
.\.venv\Scripts\python.exe .\backend\server.py
```

Start the existing frontend in terminal 2:

```powershell
cd frontend
npm.cmd install
npm.cmd run dev
```

Return to `phase2` and start the real device monitor in terminal 3 (LightBlue must be advertising):

```powershell
.\.venv\Scripts\python.exe .\backend\ble_monitor.py
```

For an independent one-off GATT check:

```powershell
.\.venv\Scripts\python.exe .\backend\ble_gatt_test.py
```

## Existing integration contract (no changes)

The monitor sends UTF-8 JSONL events to the already running TCP backend (`127.0.0.1:8765`):

```json
{"type":"device.discovered","device_id":"demo-device-beginner","source":"bleak"}
```

After three consecutive scans without the device advertising, it sends:

```json
{"type":"device.lost","source":"bleak"}
```

The existing backend broadcasts updated state to React over `ws://127.0.0.1:8766`. The monitor suppresses repeat discovery events while a registered device remains present. Connection/read failures are **unverified**, not automatically classified as absence. Event publication is considered successful only if the backend acknowledges it.

## Reproducible manual demonstration

1. Open React; confirm it connects to the backend.
2. Start advertising `hci-test-device` in LightBlue; run `ble_monitor.py`.
3. Verify the monitor reports the enrolled key and the backend acknowledges `device.discovered` with `source=bleak`. React should show `learner_01` / Beginner pack.
4. Stop LightBlue advertising. After **three consecutive absent checks**, verify the backend acknowledges `device.lost`; React should change to Guest.
5. Resume advertising **without restarting the monitor**. Verify discovery and the automatic return to `learner_01` / Beginner pack.
6. Check that continuous presence does not produce repeated duplicate `device.discovered` events.

## Automated tests

Run from `phase2`:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_ble_monitor.py" -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The seven dedicated tests use **mocked** BLE responses. They are not a replacement for the separate real-device demonstration.

## Limitations and safe handling

- LightBlue on an iPhone represents a **software-defined BLE peripheral using a real Bluetooth radio**. This demonstrates BLE communication, not a production identity solution.
- Device advertising names and the GATT test key are not secure authentication credentials; another device could imitate them. A production system would need an enrollment registry and authenticated device identity.
- iOS Bluetooth behavior and Windows GATT service caches can cause intermittent discovery/connection errors. Stop and restart advertising when necessary; log failures as unverified rather than as proof of absence.
- Three missed advertisement scans indicate **temporary non-observation**, not definitive physical disconnection.
- Do not store or commit real BLE MAC addresses, personal details, face recordings, or children's data. Demonstrations use a consenting adult's device.
- This contribution does not implement the other teammates' gaze tracking, object recognition, MediaPipe gestures, or Figma UI.
