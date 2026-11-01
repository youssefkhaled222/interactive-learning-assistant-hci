"""Socket resilience: stalled browsers and disconnected TCP producers."""
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


class SlowBrowser:
    async def send(self, message):
        await asyncio.Event().wait()  # Remains stalled until cancellation.


class FailedBrowser:
    async def send(self, message):
        raise ConnectionResetError("simulated browser disconnect")


class TestSocketReliability(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.old_engine = server.engine
        self.old_lock = server.lock
        self.old_timeout = server.WS_SEND_TIMEOUT_SECONDS
        server.engine = Engine()
        server.lock = asyncio.Lock()
        server.WS_SEND_TIMEOUT_SECONDS = 0.07
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
        server.WS_SEND_TIMEOUT_SECONDS = self.old_timeout

    async def test_stalled_browser_does_not_hold_tcp_ack_or_healthy_client(self):
        async with connect(f"ws://127.0.0.1:{self.ws_port}") as ws:
            self.assertEqual(json.loads(await ws.recv())["type"], "state")
            hung = SlowBrowser()
            server.subscribers.add(hung)
            reader, writer = await asyncio.open_connection("127.0.0.1", self.port)
            try:
                writer.write(b'{"type":"camera.status","ready":true,"source":"mediapipe"}\n')
                await writer.drain()
                ack = json.loads(await asyncio.wait_for(reader.readline(), 1))
                self.assertTrue(ack["ok"])
                state = json.loads(await asyncio.wait_for(ws.recv(), 1))
                self.assertTrue(state["payload"]["camera_ready"])
                self.assertNotIn(hung, server.subscribers)
            finally:
                writer.close()
                await writer.wait_closed()

    async def test_broken_browser_removed_healthy_browser_still_receives(self):
        async with connect(f"ws://127.0.0.1:{self.ws_port}") as ws:
            await ws.recv()
            failed = FailedBrowser()
            server.subscribers.add(failed)
            await server.apply_event({"type": "mode.selected", "mode": "gaze", "source": "ui_bridge"})
            state = json.loads(await asyncio.wait_for(ws.recv(), 1))
            self.assertEqual(state["payload"]["mode"], "gaze")
            self.assertNotIn(failed, server.subscribers)

    async def test_tcp_client_exit_on_reset_during_ack(self):
        class Reader:
            def __init__(self): self.done = False
            async def readline(self):
                if not self.done:
                    self.done = True
                    return b'{"type":"pose.tracking","visible":true,"source":"mediapipe"}\n'
                return b''

        class Writer:
            def __init__(self): self.closed = False
            def write(self, data): pass
            async def drain(self): raise ConnectionResetError("producer vanished")
            def close(self): self.closed = True
            async def wait_closed(self): raise ConnectionResetError("producer vanished")

        writer = Writer()
        await server.tcp_client(Reader(), writer)
        self.assertTrue(writer.closed)
        self.assertTrue(server.engine.view()["tracking"])

    async def test_tcp_client_exit_on_reset_during_read(self):
        class Reader:
            async def readline(self): raise ConnectionResetError("producer vanished")

        class Writer:
            def __init__(self): self.closed = False
            def write(self, data): raise AssertionError("should not send")
            async def drain(self): raise AssertionError("should not drain")
            def close(self): self.closed = True
            async def wait_closed(self): pass

        writer = Writer()
        await server.tcp_client(Reader(), writer)
        self.assertTrue(writer.closed)


if __name__ == "__main__":
    unittest.main()
