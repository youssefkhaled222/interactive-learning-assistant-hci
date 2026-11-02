"""Real BLE presence monitor for the existing HCI Phase II backend.

Classroom demonstration only: the static GATT test key is not secure
authentication. Run from phase2 with `python backend/ble_monitor.py`.
"""

import asyncio

from bleak import BleakClient, BleakScanner
from send_event import send

DEVICE_NAME = "hci-test-device"
CHAR_UUID = "00002222-0000-1000-8000-00805f9b34fb"
REGISTERED_KEY = "demo-device-beginner"
SCAN_SECONDS = 10
ABSENCE_LIMIT = 3  # Require 3 separate scans with no matching advertisement.
PAUSE_SECONDS = 2


async def check_device():
    """Return 'verified', 'absent', or 'unverified'."""
    device = await BleakScanner.find_device_by_filter(
        lambda dev, adv: (adv.local_name or dev.name or "").strip().casefold()
        == DEVICE_NAME.casefold(),
        timeout=SCAN_SECONDS,
    )
    if device is None:
        return "absent"

    try:
        async with BleakClient(
            device, timeout=20, winrt={"use_cached_services": False}
        ) as client:
            characteristic = client.services.get_characteristic(CHAR_UUID)
            if characteristic is None or "read" not in characteristic.properties:
                print("Device appeared, but the expected readable characteristic is missing.")
                return "unverified"
            data = await client.read_gatt_char(characteristic, use_cached=False)
            device_key = bytes(data).decode("utf-8").strip()
            if device_key != REGISTERED_KEY:
                print("Unrecognized GATT test key: no learner event sent.")
                return "unverified"
            return "verified"
    except Exception as error:
        # Do not print OS device identifiers from Bluetooth exception messages.
        print(f"Temporary BLE connection/read problem: {type(error).__name__}")
        return "unverified"


async def publish(event):
    """Only treat a state transition as sent when the backend acknowledges it."""
    try:
        response = await asyncio.to_thread(send, event)
        if response.get("ok") is True:
            print(f"Backend accepted {event['type']} (source=bleak).")
            return True
        print("Backend rejected event:", response.get("error", "unknown reason"))
    except (OSError, ValueError) as error:
        print(f"Backend unavailable or invalid response: {type(error).__name__}")
    return False


async def main():
    print("Monitoring your enrolled LightBlue test device. Press Ctrl+C to stop.")
    print("Keep the HCI backend running on TCP 127.0.0.1:8765.")
    reported_present = False
    consecutive_absences = 0

    while True:
        try:
            result = await check_device()
        except Exception as error:
            print(f"BLE scanning failed: {type(error).__name__}")
            result = "unverified"  # A scan error is NOT proof of device loss.

        if result == "verified":
            consecutive_absences = 0
            if not reported_present:
                if await publish({
                    "type": "device.discovered",
                    "device_id": REGISTERED_KEY,
                    "source": "bleak",
                }):
                    reported_present = True
                    print("Verified device present: learner_01 / beginner pack.")
            else:
                print("Enrolled device still present; no duplicate event.")

        elif result == "absent":
            if reported_present:
                consecutive_absences += 1
                print(f"Device not advertised: {consecutive_absences}/{ABSENCE_LIMIT} checks.")
                if consecutive_absences >= ABSENCE_LIMIT:
                    if await publish({"type": "device.lost", "source": "bleak"}):
                        reported_present = False
                        consecutive_absences = 0
                        print("Guest profile expected in React.")
            else:
                print("Enrolled device not currently advertising.")

        else:
            print("Device status unverified; keeping the previous profile until confirmed.")

        await asyncio.sleep(PAUSE_SECONDS)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Monitor stopped. This does not prove the Bluetooth device was lost.")
