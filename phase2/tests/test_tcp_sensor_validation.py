"""Actual TCP JSONL validation + WebSocket broadcast integration tests."""
import asyncio
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
import server
from engine import Engine
from websockets.asyncio.server import serve
from websockets.asyncio.client import connect


class TestTCPSensorValidation(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.old_engine = server.engine
        self.old_lock = server.lock
        server.engine = Engine()
        server.lock = asyncio.Lock()
        server.subscribers.clear()
        self.tcp = await asyncio.start_server(server.tcp_client, "127.0.0.1", 0, limit=16384)
        self.port = self.tcp.sockets[0].getsockname()[1]
        self.ws = await serve(server.ws_client, "127.0.0.1", 0)
        self.ws_port = self.ws.sockets[0].getsockname()[1]

    async def asyncTearDown(self):
        self.tcp.close()
        await self.tcp.wait_closed()
        self.ws.close()
        await self.ws.wait_closed()
        server.subscribers.clear()
        server.engine = self.old_engine
        server.lock = self.old_lock

    async def _response(self, reader, writer, payload):
        writer.write((payload + "\n").encode("utf-8"))
        await writer.drain()
        return json.loads(await asyncio.wait_for(reader.readline(), 2))

    async def test_bad_sensors_rejected_without_state_mutation_then_recover(self):
        async with connect(f"ws://127.0.0.1:{self.ws_port}") as ws:
            self.assertEqual(json.loads(await ws.recv())["type"], "state")
            reader, writer = await asyncio.open_connection("127.0.0.1", self.port)
            before = server.engine.view()
            for raw in (
                '{"type":"pose.tracking","visible":"false","source":"mediapipe"}',
                '{"type":"camera.status","ready":"false","source":"mediapipe"}',
                '{"type":"device.discovered","device_id":[],"source":"bleak"}',
                '{"type":"lighting.changed","level":"bogus","source":"camera"}',
                '{"type":"gesture.recognized","name":"test","score":NaN,"source":"dollarpy"}',
                'not-json',
            ):
                response = await self._response(reader, writer, raw)
                self.assertFalse(response["ok"], raw)
                self.assertEqual(server.engine.view(), before, raw)
            result = await self._response(reader, writer, '{"type":"pose.tracking","visible":true,"source":"mediapipe"}')
            self.assertTrue(result["ok"])
            state = json.loads(await asyncio.wait_for(ws.recv(), 2))
            self.assertTrue(state["payload"]["tracking"])
            self.assertEqual(state["payload"]["event_source"], "mediapipe")
            writer.close()
            await writer.wait_closed()

    async def test_fragmented_and_multiple_events_one_connection(self):
        reader, writer = await asyncio.open_connection("127.0.0.1", self.port)
        writer.write(b'{"type":"camera.status","ready":')
        await writer.drain()
        writer.write(b'true,"source":"mediapipe"}\n')
        await writer.drain()
        self.assertTrue(json.loads(await reader.readline())["ok"])
        self.assertTrue(server.engine.view()["camera_ready"])
        result = await self._response(reader, writer, '{"type":"camera.status","ready":false,"source":"mediapipe"}')
        self.assertTrue(result["ok"])
        self.assertFalse(server.engine.view()["camera_ready"])
        writer.close()
        await writer.wait_closed()

    async def test_oversized_line_is_rejected_and_connection_closed(self):
        reader, writer = await asyncio.open_connection("127.0.0.1", self.port)
        payload = '{"type":"pose.tracking","visible":true,"source":"' + 'x' * 9000 + '"}\n'
        writer.write(payload.encode())
        await writer.drain()
        result = json.loads(await asyncio.wait_for(reader.readline(), 2))
        self.assertFalse(result["ok"])
        self.assertFalse(server.engine.view()["tracking"])
        self.assertEqual(await asyncio.wait_for(reader.readline(), 2), b"")
        writer.close()
        await writer.wait_closed()


if __name__ == "__main__":
    unittest.main()
