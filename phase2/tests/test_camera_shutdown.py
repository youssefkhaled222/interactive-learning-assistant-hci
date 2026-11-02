"""Regression: camera-off invalidates stale pose detection in the browser."""
import asyncio
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
import server
from engine import Engine
from websockets.asyncio.client import connect
from websockets.asyncio.server import serve


class TestCameraShutdown(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.old_engine, self.old_lock = server.engine, server.lock
        server.engine = Engine()
        server.lock = asyncio.Lock()
        server.subscribers.clear()
        self.tcp = await asyncio.start_server(server.tcp_client, "127.0.0.1", 0, limit=16384)
        self.tcp_port = self.tcp.sockets[0].getsockname()[1]
        self.ws = await serve(server.ws_client, "127.0.0.1", 0)
        self.ws_port = self.ws.sockets[0].getsockname()[1]

    async def asyncTearDown(self):
        self.tcp.close()
        await self.tcp.wait_closed()
        self.ws.close()
        await self.ws.wait_closed()
        server.subscribers.clear()
        server.engine, server.lock = self.old_engine, self.old_lock

    async def send_sensor(self, event):
        reader, writer = await asyncio.open_connection("127.0.0.1", self.tcp_port)
        try:
            writer.write((json.dumps(event) + "\n").encode("utf-8"))
            await writer.drain()
            response = json.loads(await asyncio.wait_for(reader.readline(), 2))
            self.assertEqual(response, {"ok": True})
        finally:
            writer.close()
            await writer.wait_closed()

    async def read_state(self, ws):
        message = json.loads(await asyncio.wait_for(ws.recv(), 2))
        self.assertEqual(message["type"], "state")
        return message["payload"]

    async def test_camera_exit_resets_tracking_in_one_broadcast(self):
        async with connect(f"ws://127.0.0.1:{self.ws_port}") as browser:
            initial = await self.read_state(browser)
            self.assertFalse(initial["tracking"])
            await self.send_sensor({"type": "camera.status", "ready": True, "source": "mediapipe"})
            state = await self.read_state(browser)
            self.assertTrue(state["camera_ready"])
            await self.send_sensor({"type": "pose.tracking", "visible": True, "source": "mediapipe"})
            state = await self.read_state(browser)
            self.assertTrue(state["tracking"])

            # Real tracker currently sends only camera.status=false on ESC.
            await self.send_sensor({"type": "camera.status", "ready": False, "source": "mediapipe"})
            state = await self.read_state(browser)
            self.assertFalse(state["camera_ready"])
            self.assertFalse(state["tracking"])
            self.assertEqual(state["block_reason"], "camera_not_ready")
            self.assertIn("camera", state["status"].lower())
            self.assertEqual(state["event_source"], "mediapipe")
            # No intermediate tracking-lost state broadcast.
            with self.assertRaises(asyncio.TimeoutError):
                await asyncio.wait_for(browser.recv(), 0.1)

    async def test_camera_restart_does_not_invent_pose_detection(self):
        await server.apply_event({"type": "pose.tracking", "visible": True, "source": "mediapipe"})
        await server.apply_event({"type": "camera.status", "ready": False, "source": "mediapipe"})
        await server.apply_event({"type": "camera.status", "ready": True, "source": "mediapipe"})
        state = server.engine.view()
        self.assertTrue(state["camera_ready"])
        self.assertFalse(state["tracking"], "Camera readiness is not proof of a visible person")

    async def test_normal_tracking_loss_still_works(self):
        await server.apply_event({"type": "camera.status", "ready": True, "source": "mediapipe"})
        await server.apply_event({"type": "pose.tracking", "visible": True, "source": "mediapipe"})
        await server.apply_event({"type": "pose.tracking", "visible": False, "source": "mediapipe"})
        state = server.engine.view()
        self.assertTrue(state["camera_ready"])
        self.assertFalse(state["tracking"])
        self.assertEqual(state["block_reason"], "tracking_lost")
        self.assertIn("tracking lost", state["status"].lower())


if __name__ == "__main__":
    unittest.main()
