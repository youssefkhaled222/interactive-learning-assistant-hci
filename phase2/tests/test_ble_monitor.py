"""Mock-only unit tests for Phase II Bluetooth presence monitoring.

These tests do NOT scan a radio or prove hardware functionality.
Run from phase2 with the standard unittest discovery command.
"""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

# Keep application code in phase2/backend without changing shared modules.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
import ble_monitor


class BleMonitorTests(unittest.IsolatedAsyncioTestCase):
    async def test_device_not_advertising_is_absent(self):
        with patch.object(ble_monitor.BleakScanner, "find_device_by_filter", new_callable=AsyncMock) as scan:
            scan.return_value = None
            self.assertEqual(await ble_monitor.check_device(), "absent")

    async def test_matching_readable_gatt_key_is_verified(self):
        characteristic = SimpleNamespace(properties=["read"])
        client = SimpleNamespace(
            services=SimpleNamespace(get_characteristic=lambda uuid: characteristic),
            read_gatt_char=AsyncMock(return_value=b"demo-device-beginner"),
        )
        with (
            patch.object(ble_monitor.BleakScanner, "find_device_by_filter", new_callable=AsyncMock) as scan,
            patch.object(ble_monitor, "BleakClient") as client_factory,
        ):
            scan.return_value = object()  # mocked discovered test peripheral
            client_factory.return_value.__aenter__ = AsyncMock(return_value=client)
            self.assertEqual(await ble_monitor.check_device(), "verified")
            client.read_gatt_char.assert_awaited_once_with(characteristic, use_cached=False)

    async def test_unknown_gatt_key_is_not_enrolled(self):
        characteristic = SimpleNamespace(properties=["read"])
        client = SimpleNamespace(
            services=SimpleNamespace(get_characteristic=lambda uuid: characteristic),
            read_gatt_char=AsyncMock(return_value=b"unknown-demo-device"),
        )
        with (
            patch.object(ble_monitor.BleakScanner, "find_device_by_filter", new_callable=AsyncMock) as scan,
            patch.object(ble_monitor, "BleakClient") as client_factory,
        ):
            scan.return_value = object()
            client_factory.return_value.__aenter__ = AsyncMock(return_value=client)
            self.assertEqual(await ble_monitor.check_device(), "unverified")

    async def test_missing_characteristic_is_not_verified(self):
        client = SimpleNamespace(
            services=SimpleNamespace(get_characteristic=lambda uuid: None)
        )
        with (
            patch.object(ble_monitor.BleakScanner, "find_device_by_filter", new_callable=AsyncMock) as scan,
            patch.object(ble_monitor, "BleakClient") as client_factory,
        ):
            scan.return_value = object()
            client_factory.return_value.__aenter__ = AsyncMock(return_value=client)
            self.assertEqual(await ble_monitor.check_device(), "unverified")

    async def test_connection_error_does_not_claim_absence(self):
        with (
            patch.object(ble_monitor.BleakScanner, "find_device_by_filter", new_callable=AsyncMock) as scan,
            patch.object(ble_monitor, "BleakClient") as client_factory,
        ):
            scan.return_value = object()
            client_factory.return_value.__aenter__ = AsyncMock(side_effect=OSError("temporary connection failure"))
            self.assertEqual(await ble_monitor.check_device(), "unverified")

    async def test_publish_only_succeeds_on_backend_ack(self):
        event = {"type": "device.discovered", "device_id": "demo-device-beginner", "source": "bleak"}
        with patch.object(ble_monitor, "send", return_value={"ok": True}) as send:
            self.assertTrue(await ble_monitor.publish(event))
            send.assert_called_once_with(event)
        with patch.object(ble_monitor, "send", return_value={"ok": False, "error": "rejected"}):
            self.assertFalse(await ble_monitor.publish(event))

    async def test_monitor_debounces_loss_and_deduplicates_reappearance(self):
        class StopTestLoop(Exception):
            pass

        observed = ["verified", "verified", "absent", "absent", "absent", "absent", "verified"]
        iterations = 0

        async def stop_after_each_iteration(_seconds):
            nonlocal iterations
            iterations += 1
            if iterations == len(observed):
                raise StopTestLoop()

        with (
            patch.object(ble_monitor, "check_device", new_callable=AsyncMock) as check,
            patch.object(ble_monitor, "publish", new_callable=AsyncMock) as publish,
            patch.object(ble_monitor.asyncio, "sleep", new=stop_after_each_iteration),
        ):
            check.side_effect = observed
            publish.return_value = True
            with self.assertRaises(StopTestLoop):
                await ble_monitor.main()
            self.assertEqual(
                [args.args[0]["type"] for args in publish.await_args_list],
                ["device.discovered", "device.lost", "device.discovered"],
            )
            self.assertEqual(
                [args.args[0]["source"] for args in publish.await_args_list],
                ["bleak", "bleak", "bleak"],
            )


if __name__ == "__main__":
    unittest.main()
