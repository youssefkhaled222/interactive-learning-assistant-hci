# Bluetooth UserID — Test Evidence

**Project:** MSA CS484 Interactive Learning Assistant for Children, Phase II  
**Contributor:** Malak Gamal (247419)  
**Evidence date:** November 2, 2026  
**Branch used during testing:** `feature/bluetooth-userid`

## Hardware verification (performed on teammate's Windows laptop and iPhone)

| Test | Observed outcome | Status |
| --- | --- | --- |
| Real BLE scan with Bleak | `hci-test-device` appeared when LightBlue advertised, disappeared when stopped, then reappeared | PASS |
| GATT connection | Bleak printed `Connected successfully!` | PASS (after some intermittent Windows connection errors) |
| GATT characteristic discovery | Service `00001111-0000-1000-8000-00805f9b34fb` and readable characteristic `00002222-0000-1000-8000-00805f9b34fb` appeared | PASS |
| Read enrolled test key | `Bluetooth UserID: demo-device-beginner` | PASS |
| Backend real-event acknowledgment | `Backend accepted device.discovered (source=bleak)` | PASS |
| Duplicate suppression | `Enrolled device still present; no duplicate event.` | PASS |
| Loss debouncing | Consecutive absence messages `1/3`, `2/3`, `3/3`, then acknowledged `device.lost` | PASS |
| React fallback | User confirmed app changed to Guest after stopping advertising | PASS (user-observed) |
| React recovery | User confirmed app returned to `learner_01` / Beginner pack after re-advertising without restarting monitor | PASS (user-observed) |

## Automated tests

Final reported command:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

User-reported terminal output:

```text
Ran 118 tests in 4.735s

OK
```

**Interpretation:** 118 project tests passed, including **7 dedicated mock-based Bluetooth monitor tests** and the 111 previously passing project tests. The mock tests cover missing peripherals, valid/unknown GATT keys, missing characteristics, connection failure, backend acknowledgments, and presence/loss/reappearance event transitions. The tests do not themselves measure real BLE radio reliability.

## Known issues / limitations

- On Windows, initial runs intermittently produced `Characteristic ... was not found`, `The parameter is incorrect`, and `The object has been closed`. A later GATT service enumeration confirmed the test characteristic and the live read succeeded. These intermittent failures have not been proven permanently resolved.
- The BLE test key is provisioned in LightBlue and matched against a configured constant; it is **not secure human authentication**, and no general-purpose enrollment UI has been built.
- Temporary scan failures are not proof that a device has disconnected. The monitor waits for three separate missing-advertisement checks before sending `device.lost`.
- No numeric accuracy/latency benchmark or multiple-device field trial has been performed.
- Only the authorized LightBlue demonstration peripheral has been hardware-verified; other device types remain untested.

## Before team integration

- Verify `phase2/requirements-bluetooth.txt` correctly includes Bleak and the existing core requirements.
- Review modified files and confirm that Phase I PDF and any personal addresses/identifiers are not committed.
- Ask the integration lead to review the feature branch in a pull request before merging.
