"""Detection metadata validation, stable short-lived IDs and live loopback bridge."""
import asyncio
import json
import math
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'backend'))
import server
from engine import Engine
from object_tracking import ObjectTracker
from sensor_events import validate_sensor_event
from websockets.asyncio.server import serve
from websockets.asyncio.client import connect

BOX = {'x_min': .2, 'y_min': .2, 'x_max': .5, 'y_max': .7}

def event(label='cup', active=True, box=None):
    return {'type':'objects.detected','source':'yolo', 'active':active,
            'detections':([{'object':label,'confidence':.83,'box':box or BOX}] if active else [])}


class TestObjectMetadata(unittest.TestCase):
    def test_valid_and_inactive(self):
        self.assertEqual(validate_sensor_event(event())['detections'][0]['object'], 'cup')
        self.assertEqual(validate_sensor_event(event(active=False))['detections'], [])

    def test_strict_rejection(self):
        bad = [
            {**event(), 'active': 'true'},
            {**event(), 'detections': [{'object':'person','confidence':.9,'box':BOX}]},
            {**event(), 'detections': [{'object':'cup','confidence':float('nan'),'box':BOX}]},
            {**event(), 'detections': [{'object':'cup','confidence':.9,'box':{**BOX,'x_max':.1}}]},
            {**event(), 'detections': [{'object':'cup','confidence':True,'box':BOX}]},
            {**event(), 'detections': [{'object':'cup','confidence':.9,'box':BOX,'target_id':'fake'}]},
            {**event(active=False), 'detections': [{'object':'cup','confidence':.9,'box':BOX}]},
            {**event(), 'detections': [{'object':'cup','confidence':.9,'box':BOX}]*11},
        ]
        for item in bad:
            with self.subTest(item=str(item)[:60]), self.assertRaises(ValueError):
                validate_sensor_event(item)

    def test_stable_id_on_overlap_and_reset(self):
        tracker = ObjectTracker()
        tracker.update(event(), now=10.0)
        first = tracker.objects[0]['target_id']
        moved = {**BOX, 'x_min':.22, 'x_max':.52}
        tracker.update(event(box=moved), now=10.2)
        self.assertEqual(tracker.objects[0]['target_id'],first)
        tracker.update(event(box={**BOX,'x_min':.65,'x_max':.85}), now=10.3)
        self.assertNotEqual(tracker.objects[0]['target_id'], first)
        tracker.update(event(active=False), now=10.4)
        self.assertFalse(tracker.active)
        self.assertEqual(tracker.objects, [])

    def test_expires_stale_detection(self):
        tracker = ObjectTracker()
        tracker.update(event(), now=20)
        self.assertFalse(tracker.expire(now=21))
        self.assertTrue(tracker.expire(now=23))
        self.assertFalse(tracker.expire(now=24))
        self.assertEqual(tracker.state()['detected_objects'],[])


class TestRealSocketObjectEvents(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.old_engine, self.old_lock, self.old_tracker = server.engine, server.lock, server.object_tracker
        server.engine = Engine()
        server.lock = asyncio.Lock()
        server.object_tracker = ObjectTracker()
        server.subscribers.clear()
        self.tcp = await asyncio.start_server(server.tcp_client, '127.0.0.1',0,limit=16384)
        self.tcp_port = self.tcp.sockets[0].getsockname()[1]
        self.ws = await serve(server.ws_client,'127.0.0.1',0)
        self.ws_port = self.ws.sockets[0].getsockname()[1]

    async def asyncTearDown(self):
        self.tcp.close();await self.tcp.wait_closed()
        self.ws.close();await self.ws.wait_closed()
        server.subscribers.clear()
        server.engine,server.lock,server.object_tracker = self.old_engine,self.old_lock,self.old_tracker

    async def tcp_send(self,e):
        r,w=await asyncio.open_connection('127.0.0.1',self.tcp_port)
        try:
            w.write((json.dumps(e)+'\n').encode()); await w.drain()
            return json.loads(await asyncio.wait_for(r.readline(),2))
        finally:
            w.close();await w.wait_closed()

    async def recv(self,ws):
        return json.loads(await asyncio.wait_for(ws.recv(),2))['payload']

    async def test_real_tcp_publish_ws_and_remove(self):
        async with connect(f'ws://127.0.0.1:{self.ws_port}') as ws:
            state=await self.recv(ws)
            self.assertEqual(state['detected_objects'],[])
            self.assertFalse(state['object_detection_active'])
            self.assertTrue((await self.tcp_send(event()))['ok'])
            state=await self.recv(ws)
            self.assertEqual(state['detected_objects'][0]['object'],'cup')
            self.assertEqual(state['detected_objects'][0]['target_id'],'obj-1')
            self.assertTrue(state['object_detection_active'])
            self.assertEqual(state['question_index'],0)
            self.assertTrue((await self.tcp_send(event(active=False)))['ok'])
            state=await self.recv(ws)
            self.assertFalse(state['object_detection_active'])
            self.assertEqual(state['detected_objects'],[])

    async def test_bad_event_no_mutation_and_timeout_clear(self):
        async with connect(f'ws://127.0.0.1:{self.ws_port}') as ws:
            await self.recv(ws)
            await self.tcp_send(event())
            state=await self.recv(ws)
            bad={**event(), 'detections':[{'object':'cup','confidence':'100%','box':BOX}]}
            self.assertFalse((await self.tcp_send(bad))['ok'])
            self.assertEqual(server.object_tracker.state()['detected_objects'],state['detected_objects'])
            self.assertTrue(await server.expire_object_detections(now=server.object_tracker.last_seen+4))
            expired=await self.recv(ws)
            self.assertFalse(expired['object_detection_active'])
            self.assertEqual(expired['detected_objects'],[])
