"""Real local sockets, simulated payloads. This is NOT webcam/UI evidence."""
import asyncio
import importlib.util
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))


@unittest.skipUnless(importlib.util.find_spec('websockets'),'Install requirements-core.txt')
class SocketTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        import server
        from engine import Engine
        from object_tracking import ObjectTracker
        self.original = (server.engine, server.subscribers, server.lock, server.object_tracker)
        server.engine = Engine(require_sensor_ready=True)
        server.subscribers = set()
        server.lock = asyncio.Lock()
        server.object_tracker = ObjectTracker()

    async def asyncTearDown(self):
        import server
        server.engine, server.subscribers, server.lock, server.object_tracker = self.original

    async def test_existing_broker_ack_and_websocket_state(self):
        import server
        from engine import Engine
        from send_event import send
        from websockets.asyncio.client import connect
        from websockets.asyncio.server import serve
        tcp=await asyncio.start_server(server.tcp_client,'127.0.0.1',0)
        port=tcp.sockets[0].getsockname()[1]
        async with tcp,serve(server.ws_client,'127.0.0.1',0) as ws_server:
            ws_port=ws_server.sockets[0].getsockname()[1]
            async with connect(f'ws://127.0.0.1:{ws_port}') as ws:
                await asyncio.wait_for(ws.recv(),2)
                for event,key,value in [
                    (dict(type='camera.status',ready=True,source='simulator'),'camera_ready',True),
                    (dict(type='pose.tracking',visible=True,source='simulator'),'tracking',True),
                    (dict(type='gesture.recognized',name='horizontal',score=.8,source='simulator'),'last_gesture','horizontal'),
                    (dict(type='camera.status',ready=False,source='simulator'),'camera_ready',False),
                    (dict(type='camera.status',ready=True,source='simulator'),'tracking',False)]:
                    ack=await asyncio.to_thread(send,event,'127.0.0.1',port)
                    self.assertEqual({'ok':True},ack)
                    state=json.loads(await asyncio.wait_for(ws.recv(),2))['payload']
                    self.assertEqual(value,state[key])
                    self.assertTrue(state['demo_mode'])
                    self.assertEqual(0,state['question_index'])
                    if event['type'] == 'camera.status' and not event['ready']:
                        self.assertFalse(state['tracking'])
                ack=await asyncio.to_thread(send,dict(type='invalid',source='simulator'),'127.0.0.1',port)
                self.assertFalse(ack['ok'])
