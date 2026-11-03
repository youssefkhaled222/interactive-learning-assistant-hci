"""Broker regression tests: real hand input contract, not hardware validation."""
import asyncio
import sys
import time
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent/'backend'))
from engine import Engine
from hand_selection import HandSelectionGate
from object_tracking import ObjectTracker
from sensor_events import validate_sensor_event, InvalidSensorEvent
import server


class HandContractTests(unittest.TestCase):
    def test_valid_typed_sensor_event(self):
        event={'type':'hand.pointer','source':'mediapipe-hand',
               'x':.33,'y':.61,'pinching':True,'frame_sequence':5}
        self.assertEqual(validate_sensor_event(event),event)
        invisible={**event,'x':None,'y':None,'pinching':False}
        self.assertEqual(validate_sensor_event(invisible),invisible)

    def test_reject_invalid_without_loose_boolean(self):
        base={'type':'hand.pointer','source':'mediapipe-hand','x':.4,'y':.5,
              'pinching':False,'frame_sequence':5}
        for changed in ({'pinching':1}, {'x':float('nan')}, {'x':True},
                        {'y':None}, {'frame_sequence':0}, {'frame_sequence':1.5},
                        {'x':None,'y':None,'pinching':True}):
            with self.subTest(changed=changed), self.assertRaises(InvalidSensorEvent):
                validate_sensor_event({**base,**changed})

    def test_hand_tracking_is_distinct_from_pose(self):
        e=Engine(require_sensor_ready=True)
        e.handle({'type':'camera.status','ready':True,'source':'mediapipe-hand'})
        self.assertTrue(e.view()['input_blocked'])
        e.handle({'type':'hand.tracking','visible':True,'source':'mediapipe-hand'})
        self.assertFalse(e.view()['pose_tracking'])
        self.assertTrue(e.view()['tracking'])
        self.assertFalse(e.view()['input_blocked'])
        e.handle({'type':'mode.selected','mode':'gaze','source':'ui_bridge'})
        self.assertTrue(e.view()['input_blocked'])
        e.handle({'type':'hand.tracking','visible':False,'source':'mediapipe-hand'})
        self.assertFalse(e.view()['hand_tracking'])


class HandBrokerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.original=(server.engine,server.object_tracker,server.hand_selection_gate,
                       server.lock,server.subscribers)
        server.engine=Engine(require_next=True,require_sensor_ready=True)
        server.object_tracker=ObjectTracker()
        server.hand_selection_gate=HandSelectionGate(hold_seconds=0.0)
        server.lock=asyncio.Lock()
        server.subscribers=set()
        self.now=time.monotonic()
        obj={'object':'apple','confidence':.8,
             'box':{'x_min':.1,'x_max':.5,'y_min':.2,'y_max':.7}}
        ev={'type':'objects.detected','source':'yolo','active':True,'detections':[obj]}
        server.object_tracker.update(ev,now=self.now-.2)
        server.object_tracker.update(ev,now=self.now-.1)

    async def asyncTearDown(self):
        (server.engine,server.object_tracker,server.hand_selection_gate,
         server.lock,server.subscribers)=self.original

    def pointer(self, closed=False, x=.25, y=.35):
        return validate_sensor_event({'type':'hand.pointer','source':'mediapipe-hand',
            'x':x,'y':y,'pinching':closed,'frame_sequence':10})

    async def test_hand_can_select_real_candidate_through_broker(self):
        # Software test of bridge after actual physical tracking independently
        # established by user's camera run. No claim of synthetic hardware proof.
        await server.apply_event(self.pointer())
        await server.apply_event(self.pointer())
        await server.apply_event(self.pointer(closed=True))
        self.assertEqual(server.engine.view()['questions_completed'],0)
        await server.apply_event(self.pointer(closed=True))
        state=server.engine.view()
        self.assertEqual(state['questions_completed'],1)
        self.assertTrue(state['awaiting_next'])
        self.assertEqual(state['event_source'],'mediapipe-hand')
        await server.apply_event(self.pointer(closed=True))
        self.assertEqual(server.engine.view()['questions_completed'],1)

    async def test_gaze_mode_refuses_hand_selection(self):
        await server.apply_event({'type':'mode.selected','mode':'gaze','source':'ui_bridge'})
        for closed in [False,False,True,True]:
            await server.apply_event(self.pointer(closed=closed))
        self.assertEqual(server.engine.view()['questions_completed'],0)

    async def test_wrong_source_rejected(self):
        event=self.pointer()
        with self.assertRaises(ValueError):
            await server.apply_event({**event,'source':'simulator'})
        self.assertFalse(server.engine.view()['hand_tracking'])

    async def test_lost_hand_disarms_and_watchdog_blocks(self):
        await server.apply_event(self.pointer())
        await server.apply_event(self.pointer())
        await server.apply_event(self.pointer(closed=True))
        await server.apply_event(self.pointer(closed=False,x=None,y=None))
        await server.apply_event(self.pointer(closed=True))
        self.assertEqual(server.engine.view()['questions_completed'],0)
        server.hand_selection_gate.last_hand_at=time.monotonic()-3
        self.assertTrue(server.hand_selection_gate.expired())
        await server.apply_event({'type':'camera.status','ready':False,'source':'mediapipe-hand'})
        self.assertFalse(server.engine.view()['camera_ready'])
        self.assertFalse(server.engine.view()['hand_tracking'])

if __name__=='__main__':
    unittest.main()
