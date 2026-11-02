"""Reviewed Mohamed context engine: socket integration and regression boundaries."""
import asyncio
import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'backend'))
from content_packs import PACKS, validate_packs
from engine import Engine
from sensor_events import InvalidSensorEvent, validate_sensor_event
import server
from websockets.asyncio.client import connect
from websockets.asyncio.server import serve


class FakeTime:
    def __init__(self): self.value = 100.0
    def __call__(self): return self.value


class TestCorrectedContextRules(unittest.TestCase):
    def test_rejected_old_device_loss_cannot_poison_timestamp(self):
        e = Engine()
        e.handle({'type':'device.discovered', 'device_id':'demo-device-beginner', 'ts':10.0})
        e.handle({'type':'device.discovered', 'device_id':'demo-device-advanced', 'ts':20.0})
        e.handle({'type':'device.lost', 'device_id':'demo-device-beginner', 'ts':1000.0})
        self.assertEqual(e.view()['level'], 'advanced')
        # The unrelated loss at 1000 must not invalidate an actual loss at 25.
        e.handle({'type':'device.lost', 'device_id':'demo-device-advanced', 'ts':25.0})
        self.assertEqual(e.view()['level'], 'guest')

    def test_empty_loss_does_not_advance_time(self):
        e = Engine()
        e.handle({'type':'device.lost', 'ts':9999})
        e.handle({'type':'device.discovered', 'device_id':'demo-device-beginner', 'ts':10})
        self.assertEqual(e.view()['level'], 'beginner')

    def test_invalid_device_timestamp_rejected_at_both_boundaries(self):
        for value in (True, '10', -1, float('nan'), float('inf')):
            for event_type in ('device.discovered', 'device.lost'):
                msg = {'type':event_type, 'source':'bleak', 'ts':value}
                if event_type == 'device.discovered': msg['device_id']='demo-device-beginner'
                with self.subTest(value=value, t=event_type):
                    with self.assertRaises(ValueError): validate_sensor_event(msg)
                    with self.assertRaises(ValueError): Engine().handle(msg)

    def test_optional_device_loss_identity_is_validated(self):
        self.assertEqual(validate_sensor_event({'type':'device.lost','source':'bleak'}),
                         {'type':'device.lost','source':'bleak'})
        payload={'type':'device.lost','source':'bleak','device_id':'demo-device-advanced','ts':15.5}
        self.assertEqual(validate_sensor_event(payload), payload)
        with self.assertRaises(InvalidSensorEvent):
            validate_sensor_event({'type':'device.lost','source':'bleak','device_id':''})

    def test_missing_choice_rejected(self):
        bad=copy.deepcopy(PACKS)
        bad['guest'][0]['choices']=['apple','cup']
        with self.assertRaises(ValueError): validate_packs(bad)

    def test_strict_sensor_gate_and_gaze_not_pretended(self):
        e = Engine(require_sensor_ready=True)
        self.assertTrue(e.view()['input_blocked'])
        self.assertEqual(e.view()['block_reason'],'camera_not_ready')
        e.handle({'type':'game.select','object':'apple','source':'gesture'})
        self.assertEqual(e.view()['question_index'], 0)
        e.handle({'type':'camera.status','ready':True,'source':'mediapipe'})
        self.assertEqual(e.view()['block_reason'], 'tracking_lost')
        e.handle({'type':'pose.tracking','visible':True,'source':'mediapipe'})
        self.assertFalse(e.view()['input_blocked'])
        e.handle({'type':'mode.selected','mode':'gaze','source':'ui_bridge'})
        self.assertTrue(e.view()['input_blocked'])
        self.assertEqual(e.view()['block_reason'],'gaze_not_ready')
        e.handle({'type':'game.select','object':'apple','source':'gaze'})
        self.assertEqual(e.view()['question_index'], 0)
        e.handle({'type':'mode.selected','mode':'gesture','source':'ui_bridge'})
        self.assertFalse(e.view()['input_blocked'])

    def test_select_same_class_after_question_advance_not_discarded(self):
        clock=FakeTime()
        e=Engine(clock=clock)
        e.handle({'type':'game.select','object':'apple'})
        self.assertEqual(e.view()['question_index'], 1)
        e.handle({'type':'game.select','object':'apple'})
        self.assertEqual(e.view()['wrong_attempts'], 1)
        e.handle({'type':'game.select','object':'apple'})
        self.assertEqual(e.view()['wrong_attempts'], 1)

    def test_next_state_prevents_early_advance(self):
        e=Engine(require_next=True)
        e.handle({'type':'game.select','object':'apple'})
        self.assertTrue(e.view()['awaiting_next'])
        self.assertEqual(e.view()['question_index'],0)
        e.handle({'type':'game.select','object':'book'})
        self.assertEqual(e.view()['question_index'],0)
        e.handle({'type':'game.next'})
        self.assertEqual(e.view()['question_index'],1)


class TestRealSockets(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.old_engine, self.old_lock, self.old_tracker = server.engine, server.lock, server.object_tracker
        server.engine=Engine(require_next=True, require_sensor_ready=True)
        server.lock=asyncio.Lock()
        from object_tracking import ObjectTracker
        server.object_tracker=ObjectTracker()
        server.subscribers.clear()
        self.tcp=await asyncio.start_server(server.tcp_client,'127.0.0.1',0,limit=16384)
        self.tcp_port=self.tcp.sockets[0].getsockname()[1]
        self.ws=await serve(server.ws_client,'127.0.0.1',0)
        self.ws_port=self.ws.sockets[0].getsockname()[1]

    async def asyncTearDown(self):
        self.tcp.close(); await self.tcp.wait_closed()
        self.ws.close(); await self.ws.wait_closed()
        server.subscribers.clear()
        server.engine,server.lock,server.object_tracker=self.old_engine,self.old_lock,self.old_tracker

    async def sensor(self, **event):
        rd,wr=await asyncio.open_connection('127.0.0.1',self.tcp_port)
        try:
            wr.write((json.dumps(event)+'\n').encode()); await wr.drain()
            return json.loads(await asyncio.wait_for(rd.readline(),2))
        finally:
            wr.close(); await wr.wait_closed()

    async def recv(self, ws):
        msg=json.loads(await asyncio.wait_for(ws.recv(),2))
        self.assertEqual(msg['type'],'state')
        return msg['payload']

    async def test_ble_sensor_and_browser_next_with_live_sockets(self):
        async with connect(f'ws://127.0.0.1:{self.ws_port}') as browser:
            self.assertEqual((await self.recv(browser))['block_reason'],'camera_not_ready')
            self.assertEqual(await self.sensor(type='device.discovered',device_id='demo-device-beginner',ts=10.0,source='bleak'), {'ok':True})
            self.assertEqual((await self.recv(browser))['level'],'beginner')
            self.assertEqual(await self.sensor(type='game.select',object='apple',source='gesture'),{'ok':True})
            state=await self.recv(browser)
            self.assertEqual(state['question_index'],0)
            self.assertTrue(state['input_blocked'])
            await self.sensor(type='camera.status',ready=True,source='mediapipe'); await self.recv(browser)
            await self.sensor(type='pose.tracking',visible=True,source='mediapipe'); await self.recv(browser)
            await self.sensor(type='game.select',object='apple',source='gesture')
            state=await self.recv(browser)
            self.assertTrue(state['awaiting_next'])
            self.assertEqual(state['question_index'],0)
            await browser.send(json.dumps({'type':'command','action':'game.next','payload':{}}))
            state=await self.recv(browser)
            self.assertEqual(state['question_index'],1)
            self.assertEqual(state['question']['answer'],'cup')
            self.assertFalse(state['awaiting_next'])
            self.assertEqual(await self.sensor(type='device.lost',device_id='demo-device-beginner',ts=11.0,source='bleak'),{'ok':True})
            state=await self.recv(browser)
            self.assertEqual(state['level'],'guest')
            self.assertEqual(state['question_index'],0)

    async def test_bad_ble_timestamp_is_rejected_without_broadcast(self):
        async with connect(f'ws://127.0.0.1:{self.ws_port}') as browser:
            await self.recv(browser)
            result=await self.sensor(type='device.discovered',device_id='demo-device-beginner',ts='bad',source='bleak')
            self.assertFalse(result['ok'])
            self.assertEqual(server.engine.view()['level'],'guest')
            with self.assertRaises(asyncio.TimeoutError):
                await asyncio.wait_for(browser.recv(),0.1)

if __name__=='__main__': unittest.main()
