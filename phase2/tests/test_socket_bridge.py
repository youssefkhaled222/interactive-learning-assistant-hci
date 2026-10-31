"""Real loopback TCP/WebSocket tests using ephemeral ports (no camera required)."""
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


class TestSocketBridge(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.original_engine = server.engine
        self.original_lock = server.lock
        server.engine = Engine()
        server.lock = asyncio.Lock()
        server.subscribers.clear()
        self.tcp_server = await asyncio.start_server(server.tcp_client, "127.0.0.1", 0, limit=16384)
        self.tcp_port = self.tcp_server.sockets[0].getsockname()[1]
        self.ws_server = await serve(server.ws_client, "127.0.0.1", 0)
        self.ws_port = self.ws_server.sockets[0].getsockname()[1]

    async def asyncTearDown(self):
        self.tcp_server.close()
        await self.tcp_server.wait_closed()
        self.ws_server.close()
        await self.ws_server.wait_closed()
        server.subscribers.clear()
        server.engine = self.original_engine
        server.lock = self.original_lock

    async def recv(self, ws):
        return json.loads(await asyncio.wait_for(ws.recv(), timeout=2))

    async def test_mode_command_broadcasts_to_two_browsers(self):
        async with connect(f"ws://127.0.0.1:{self.ws_port}") as a, connect(f"ws://127.0.0.1:{self.ws_port}") as b:
            self.assertEqual((await self.recv(a))["type"], "state")
            self.assertEqual((await self.recv(b))["type"], "state")
            await a.send(json.dumps({"type":"command","action":"mode.selected","payload":{"mode":"gaze"}}))
            for ws in (a,b):
                result = await self.recv(ws)
                self.assertEqual(result["type"], "state")
                self.assertEqual(result["payload"]["mode"], "gaze")
                self.assertEqual(result["payload"]["event_source"], "ui_bridge")

    async def test_restart_changes_session_state(self):
        async with connect(f"ws://127.0.0.1:{self.ws_port}") as ws:
            await self.recv(ws)
            server.engine.handle({"type":"game.select","object":"apple","source":"simulator"})
            await ws.send(json.dumps({"type":"command","action":"game.restart","payload":{}}))
            result = await self.recv(ws)
            self.assertEqual(result["payload"]["question_index"], 0)
            self.assertEqual(result["payload"]["event_source"], "ui_bridge")

    async def test_browser_cannot_fake_hardware_or_selection(self):
        async with connect(f"ws://127.0.0.1:{self.ws_port}") as ws:
            await self.recv(ws)
            for command in ({"type":"command","action":"game.select","payload":{"object":"apple"}},
                            {"type":"device.discovered","device_id":"demo-device-advanced"},
                            {"type":"command","action":"mode.selected","payload":{"mode":"gaze"},"source":"mediapipe"}):
                await ws.send(json.dumps(command))
                result = await self.recv(ws)
                self.assertEqual(result["type"], "error")
            self.assertEqual(server.engine.view()["question_index"], 0)
            self.assertEqual(server.engine.view()["level"], "guest")

    async def test_invalid_json_does_not_disconnect_client(self):
        async with connect(f"ws://127.0.0.1:{self.ws_port}") as ws:
            await self.recv(ws)
            await ws.send("not json")
            self.assertEqual((await self.recv(ws))["type"], "error")
            await ws.send(json.dumps({"type":"command","action":"game.restart","payload":{}}))
            self.assertEqual((await self.recv(ws))["type"], "state")

    async def test_existing_tcp_adapter_still_broadcasts(self):
        async with connect(f"ws://127.0.0.1:{self.ws_port}") as ws:
            await self.recv(ws)
            reader, writer = await asyncio.open_connection("127.0.0.1", self.tcp_port)
            writer.write((json.dumps({"type":"device.discovered","device_id":"demo-device-beginner","source":"simulator"})+"\n").encode())
            await writer.drain()
            self.assertTrue(json.loads(await asyncio.wait_for(reader.readline(),2))["ok"])
            state = await self.recv(ws)
            self.assertEqual(state["payload"]["level"], "beginner")
            writer.close()
            await writer.wait_closed()


if __name__ == '__main__':
    unittest.main()
