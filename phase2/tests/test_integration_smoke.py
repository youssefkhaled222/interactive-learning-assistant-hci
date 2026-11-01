"""Integration acceptance tests with actual loopback TCP + WebSocket sockets."""
import asyncio
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

import server
from engine import Engine
from integration_smoke import ProbeFailure, assert_state, probe
from websockets.asyncio.server import serve


class TestIntegrationSmoke(unittest.IsolatedAsyncioTestCase):
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

    async def test_full_integration_probe_and_state_restoration(self):
        lines = []
        await probe(tcp_port=self.port, ws_port=self.ws_port, print_progress=lines.append)
        self.assertIn("ALL INTEGRATION SMOKE CHECKS PASSED (SIMULATED EVENTS)", lines)
        state = server.engine.view()
        self.assertEqual(state["level"], "guest")
        self.assertEqual(state["mode"], "gesture")
        self.assertFalse(state["camera_ready"])
        self.assertFalse(state["tracking"])

    async def test_wrong_tcp_port_produces_failure(self):
        # The WebSocket connection succeeds, but an invalid TCP port fails.
        self.tcp.close()
        await self.tcp.wait_closed()
        with self.assertRaises(OSError):
            await probe(tcp_port=self.port, ws_port=self.ws_port,
                        timeout=0.3, print_progress=lambda msg: None)


class TestSmokeAssertion(unittest.TestCase):
    def test_malformed_state_is_rejected(self):
        for message in (None, {}, {"type": "state"}, {"type": "error"},
                        {"type": "state", "payload": {"level": "guest"}}):
            with self.assertRaises(ProbeFailure):
                assert_state(message, level="beginner")


if __name__ == "__main__":
    unittest.main()
