import asyncio
from bleak import BleakScanner, BleakClient
from send_event import send

DEVICE_NAME = "hci-test-device"

CHAR_UUID = "00002222-0000-1000-8000-00805f9b34fb"

EXPECTED_USERID = "demo-device-beginner"


async def main():

    print("Searching for HCI Bluetooth device...")

    try:
        device = await BleakScanner.find_device_by_filter(
            lambda d, adv: (
                (adv.local_name or d.name or "").strip().lower()
                == DEVICE_NAME.lower()
            ),
            timeout=20
        )

        if device is None:
            print("Device not found!")
            return

        print("Device found!")
        print("Connecting...")

        async with BleakClient(
            device,
            timeout=20,
            winrt={"use_cached_services": False}
        ) as client:

            print("Connected successfully!")

            characteristic = client.services.get_characteristic(
                CHAR_UUID
            )

            if characteristic is None:
                print("UserID characteristic not found!")
                return

            if "read" not in characteristic.properties:
                print("Characteristic is not readable!")
                return

            print("Reading Bluetooth UserID...")

            data = await client.read_gatt_char(
                characteristic,
                use_cached=False
            )

            userid = bytes(data).decode("utf-8").strip()

            print("Bluetooth UserID:", userid)

            if userid != EXPECTED_USERID:
                print("Unknown Bluetooth UserID!")
                print("No event sent.")
                return

            print("\nRegistered test device verified!")

            # Send real Bluetooth event to HCI backend
            event = {
                "type": "device.discovered",
                "device_id": userid,
                "source": "bleak"
            }

            print("\nSending Bluetooth event to backend...")

            response = send(event)

            print("Backend response:", response)

            if response.get("ok") is True:
                print("\nSUCCESS!")
                print("Real Bluetooth event accepted by backend.")
                print("Check your React application!")
            else:
                print("Backend did not accept the event.")

    except Exception as error:
        print("\nBluetooth error:", error)
        print("Error type:", type(error).__name__)


if __name__ == "__main__":
    asyncio.run(main())