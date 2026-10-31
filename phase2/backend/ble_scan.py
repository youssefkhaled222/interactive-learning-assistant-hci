"""Real BLE discovery via Bleak. No claim of reading a person's identity.
Registered-device provisioning must occur explicitly; scanning only reports
radio device identifiers visible to OS. Start with: python backend/ble_scan.py
"""
import asyncio
from bleak import BleakScanner

async def main():
    print("Scanning for BLE advertisements for 8 seconds...")
    devices = await BleakScanner.discover(timeout=8.0)
    if not devices:
        print("No BLE advertisers found. Confirm Bluetooth is enabled and the peripheral advertises BLE.")
    for device in devices:
        print(f"Name: {device.name or '(unknown)'} | OS device identifier: {device.address}")
    print("An OS device identifier is not a person's UserID. Enrollment/GATT data is required for identity mapping.")

if __name__ == "__main__":
    asyncio.run(main())
