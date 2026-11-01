"""Pure object-target matching tests; no fabricated game or sensor results."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'backend'))
from object_tracking import ObjectTracker
from target_matching import resolve_target

BOX = {'x_min': .1, 'y_min': .2, 'x_max': .5, 'y_max': .7}


def event(items=None, active=True):
    if items is None:
        items = [{'object': 'cup', 'confidence': .82, 'box': BOX}]
    return {'type': 'objects.detected', 'source': 'yolo',
            'active': active, 'detections': items if active else []}


def pick(tracker, now, **kwargs):
    return resolve_target(tracker, x=.25, y=.35, coordinate_space='object_view',
                          now=now, **kwargs)


class TestTargetTracking(unittest.TestCase):
    def test_return_after_single_missing_frame_reuses_id_but_not_ghost(self):
        tracker = ObjectTracker()
        tracker.update(event(), now=10)
        original = tracker.objects[0]['target_id']
        tracker.update(event([]), now=10.35)
        self.assertEqual(tracker.state()['detected_objects'], [])
        self.assertFalse(pick(tracker, 10.36)['accepted'])
        tracker.update(event(), now=10.70)
        self.assertEqual(tracker.objects[0]['target_id'], original)
        self.assertTrue(pick(tracker, 10.71)['accepted'])

    def test_return_after_long_gap_gets_new_id(self):
        tracker = ObjectTracker()
        tracker.update(event(), now=10)
        original = tracker.objects[0]['target_id']
        tracker.update(event([]), now=10.2)
        tracker.update(event(), now=11.0)
        self.assertNotEqual(tracker.objects[0]['target_id'], original)
        self.assertFalse(pick(tracker, 11.01)['accepted'])

    def test_camera_stop_resets_history_even_when_same_object_returns(self):
        tracker = ObjectTracker()
        tracker.update(event(), now=10)
        original = tracker.objects[0]['target_id']
        tracker.update(event([], active=False), now=10.1)
        tracker.update(event(), now=10.2)
        self.assertNotEqual(tracker.objects[0]['target_id'], original)

    def test_one_prior_box_never_assigned_to_two_simultaneous_detections(self):
        tracker = ObjectTracker()
        tracker.update(event(), now=10)
        tracker.update(event([{'object':'cup', 'confidence':.8, 'box':BOX},
                              {'object':'cup', 'confidence':.7, 'box':BOX}]), now=10.2)
        self.assertEqual(len({x['target_id'] for x in tracker.objects}), 2)

    def test_expiry_prevents_reusing_ids(self):
        tracker = ObjectTracker()
        tracker.update(event(), now=10)
        original = tracker.objects[0]['target_id']
        self.assertTrue(tracker.expire(now=13))
        tracker.update(event(), now=13.1)
        self.assertNotEqual(tracker.objects[0]['target_id'], original)


class TestSelectionGate(unittest.TestCase):
    def setUp(self):
        self.t = ObjectTracker()
        self.t.update(event(), now=10)

    def test_first_observation_is_not_yet_selectable(self):
        self.assertEqual(pick(self.t, 10.01)['reason'], 'target-not-stable-yet')

    def test_stable_fresh_target_matching_point(self):
        self.t.update(event(), now=10.2)
        matched = pick(self.t, 10.3, target_id=self.t.objects[0]['target_id'])
        self.assertTrue(matched['accepted'])
        self.assertEqual(matched['object'], 'cup')
        self.assertEqual(matched['reason'], 'candidate-only')

    def test_wrong_point_and_wrong_id_are_rejected(self):
        self.t.update(event(), now=10.2)
        self.assertEqual(resolve_target(self.t, x=.9, y=.9, coordinate_space='object_view', now=10.3)['reason'],
                         'no-visible-target-at-point')
        self.assertEqual(pick(self.t, 10.3, target_id='obj-999')['reason'], 'target-id-mismatch')

    def test_stale_detector_not_selectable(self):
        self.t.update(event(), now=10.2)
        self.assertEqual(pick(self.t, 11.1)['reason'], 'detector-unavailable-or-stale')

    def test_camera_frame_requires_calibrated_mapping(self):
        self.t.update(event(), now=10.2)
        self.assertEqual(resolve_target(self.t, x=.25, y=.35, coordinate_space='child_camera', now=10.3)['reason'],
                         'coordinate-space-not-calibrated')
        self.assertEqual(resolve_target(self.t, x=.25, y=.35, coordinate_space='screen', now=10.3)['reason'],
                         'coordinate-space-not-calibrated')

    def test_overlapping_objects_are_ambiguous(self):
        other = {'object':'book', 'confidence':.9, 'box': BOX}
        self.t.update(event([event()['detections'][0], other]), now=10.2)
        self.assertEqual(pick(self.t, 10.3)['reason'], 'ambiguous-overlapping-targets')

    def test_invalid_coordinates_and_low_confidence_rejected(self):
        self.t.update(event([{'object':'cup', 'confidence':.31, 'box':BOX}]), now=10.2)
        self.assertEqual(pick(self.t, 10.3)['reason'], 'low-detection-confidence')
        for x in (float('nan'), -1, 1.5, True):
            self.assertEqual(resolve_target(self.t, x=x, y=.4, coordinate_space='object_view', now=10.3)['reason'],
                             'invalid-point')

    def test_detections_do_not_change_learning_engine(self):
        # The gate is non-mutating and does not fabricate game.select events.
        from engine import Engine
        e = Engine()
        before = e.view()
        self.t.update(event(), now=10.2)
        pick(self.t, 10.3)
        self.assertEqual(e.view(), before)


class TestTargetTCPWebSocket(unittest.IsolatedAsyncioTestCase):
    """Use separate local TCP and WS connections, not a mocked state feed."""
    async def asyncSetUp(self):
        import asyncio
        import server
        from engine import Engine
        self.server = server
        self.original = (server.engine, server.lock, server.object_tracker,
                         set(server.subscribers))
        server.engine = Engine()
        server.lock = asyncio.Lock()
        server.object_tracker = ObjectTracker()
        server.subscribers.clear()
        self.tcp = await asyncio.start_server(server.tcp_client, '127.0.0.1', 0, limit=16384)
        self.port = self.tcp.sockets[0].getsockname()[1]
        from websockets.asyncio.server import serve
        self.websocket = await serve(server.ws_client, '127.0.0.1', 0)
        self.wsport = self.websocket.sockets[0].getsockname()[1]

    async def asyncTearDown(self):
        self.tcp.close()
        await self.tcp.wait_closed()
        self.websocket.close()
        await self.websocket.wait_closed()
        self.server.subscribers.clear()
        self.server.engine, self.server.lock, self.server.object_tracker, subscribers = self.original
        self.server.subscribers.update(subscribers)

    async def send_event(self, value):
        import asyncio
        import json
        reader, writer = await asyncio.open_connection('127.0.0.1', self.port)
        try:
            writer.write((json.dumps(value) + '\n').encode())
            await writer.drain()
            return json.loads(await asyncio.wait_for(reader.readline(), 2))
        finally:
            writer.close()
            await writer.wait_closed()

    async def test_missing_frame_hides_target_then_restores_id_without_gameplay(self):
        import asyncio
        import json
        from websockets.asyncio.client import connect
        async with connect(f'ws://127.0.0.1:{self.wsport}') as ws:
            initial = json.loads(await asyncio.wait_for(ws.recv(), 2))['payload']
            self.assertEqual(initial['question_index'], 0)
            self.assertTrue((await self.send_event(event()))['ok'])
            first = json.loads(await asyncio.wait_for(ws.recv(), 2))['payload']
            tid = first['detected_objects'][0]['target_id']
            self.assertTrue((await self.send_event(event([])))['ok'])
            missing = json.loads(await asyncio.wait_for(ws.recv(), 2))['payload']
            self.assertEqual(missing['detected_objects'], [])
            self.assertTrue((await self.send_event(event()))['ok'])
            returned = json.loads(await asyncio.wait_for(ws.recv(), 2))['payload']
            self.assertEqual(returned['detected_objects'][0]['target_id'], tid)
            self.assertEqual(returned['question_index'], 0)
            self.assertEqual(returned['first_try_correct'], 0)
            self.assertTrue(resolve_target(self.server.object_tracker, x=.25, y=.35,
                                           coordinate_space='object_view')['accepted'])


if __name__ == '__main__':
    unittest.main()
