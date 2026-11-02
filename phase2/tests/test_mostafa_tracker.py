"""Synthetic regression fixtures are NOT training data or hardware evidence."""
import copy
import importlib.util
import json
import math
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from gesture_data import (classify,evaluate,fingerprint,load_samples,make_sample,
                          save_sample,validate_points)
from pose_tracker import Capture,FrameClock,main,pose_visible,run_live
from tracker_events import EventPublisher
from download_tracker_model import download


def fixture(label='horizontal',split='train',variant=0,channel='right_wrist'):
    points=[]
    for i in range(40):
        u=i/39
        wiggle=.003*math.sin(u*6+variant)
        x,y=(.2+u*.5,.4+wiggle) if label=='horizontal' else (.4+wiggle,.2+u*.5)
        points.append([x+variant*.0001,y, i*.04])
    return make_sample(points,label,split,channel,[640,480],0,'synthetic-unit-test')


class DataTests(unittest.TestCase):
    def test_multiple_samples_do_not_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            a=save_sample(d,fixture()); b=save_sample(d,fixture(variant=1))
            self.assertNotEqual(a,b)
            self.assertEqual(2,len(load_samples(d,'right_wrist','train')))

    def test_split_isolation(self):
        with tempfile.TemporaryDirectory() as d:
            save_sample(d,fixture()); save_sample(d,fixture(split='test',variant=1))
            self.assertEqual('train',load_samples(d,'right_wrist','train')[0]['split'])

    def test_corrupt_file_reports_path(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'right_wrist'/'train'/'horizontal'; p.mkdir(parents=True)
            (p/'bad.json').write_text('{')
            with self.assertRaisesRegex(ValueError,'bad.json'):
                load_samples(d,'right_wrist','train')

    def test_short_empty_stationary_nan_and_bad_time(self):
        good=fixture()['points']
        bad_time=copy.deepcopy(good); bad_time[2][2]=bad_time[1][2]
        for points in ([],good[:5],[[.5,.5,i*.04] for i in range(40)],
                       [[float('nan'),.4,i*.04] for i in range(40)],bad_time):
            with self.subTest(points=points[:2]):
                with self.assertRaises(ValueError): validate_points(points)

    def test_path_like_label_is_rejected(self):
        with self.assertRaises(ValueError): fixture(label='../bad')

    def test_train_test_duplicates_fail_before_classification(self):
        a=fixture(); b=copy.deepcopy(a); b.update(sample_id='other',split='test')
        with self.assertRaisesRegex(ValueError,'leakage'):
            evaluate([a],[b])

    def test_minimum_per_class_enforced(self):
        training=[fixture(k,variant=i) for k in ['horizontal','vertical'] for i in range(2)]
        testing=[fixture(k,'test',4) for k in ['horizontal','vertical']]
        with self.assertRaisesRegex(ValueError,'5 held-out'):
            evaluate(training,testing)


@unittest.skipUnless(importlib.util.find_spec('dollarpy'),'Install requirements-mostafa.txt for actual DollarPy tests')
class DollarTests(unittest.TestCase):
    def setUp(self):
        self.training=[fixture(k,variant=i) for k in ['horizontal','vertical'] for i in range(2)]

    def test_real_library_distinguishes_shapes_and_does_not_mutate(self):
        before=copy.deepcopy(self.training)
        for k in ['horizontal','vertical']:
            for _ in range(3):
                out=classify(fixture(k,'test',3),self.training)
                self.assertEqual(k,out['predicted']); self.assertTrue(out['accepted'])
        self.assertEqual(before,self.training)

    def test_full_evaluation_and_confusion(self):
        testing=[fixture(k,'test',i+3) for k in ['horizontal','vertical'] for i in range(5)]
        result=evaluate(self.training,testing)
        self.assertEqual(10,len(result['predictions']))
        self.assertEqual(1,result['accuracy'])
        self.assertEqual(5,result['confusion']['horizontal']['horizontal'])

    def test_errors_and_rejections_are_in_report(self):
        testing=[fixture(k,'test',4) for k in ['horizontal','vertical']]
        with patch('gesture_data.classify',return_value=dict(predicted='vertical',score=.1,accepted=False)):
            report=evaluate(self.training,testing,min_test=1)
        self.assertEqual(0,report['accuracy'])
        self.assertEqual(1,report['confusion']['horizontal']['REJECTED'])

    def test_mixed_channel_and_test_training_fail(self):
        with self.assertRaisesRegex(ValueError,'same landmark'):
            classify(fixture(channel='thumb'),self.training)
        self.training[0]['split']='test'
        with self.assertRaises(ValueError): classify(fixture(),self.training)

    def test_replay_never_constructs_publisher(self):
        with tempfile.TemporaryDirectory() as d:
            for s in self.training: save_sample(d,s)
            held=save_sample(d,fixture('horizontal','test',6))
            with patch('pose_tracker.EventPublisher') as pub:
                self.assertEqual(0,main(['--data-dir',d,'--replay',str(held)]))
                pub.assert_not_called()


class CaptureTests(unittest.TestCase):
    def test_timestamps_strictly_increase_even_same_millisecond(self):
        with patch('pose_tracker.time.monotonic',return_value=1):
            c=FrameClock(); self.assertEqual([0,1,2],[c.next(),c.next(),c.next()])

    def test_tracking_loss_cancels_not_splices_recording(self):
        c=Capture(); c.start(10,(640,480)); c.update(10.1,(.5,.5),(640,480))
        with self.assertRaisesRegex(ValueError,'tracking lost'):
            c.update(10.2,None,(640,480))
        self.assertIsNone(c.started); self.assertEqual([],c.points)

    def test_capture_finishes_once(self):
        c=Capture(.5); c.start(0,(640,480))
        self.assertIsNone(c.update(.1,(.2,.2),(640,480)))
        self.assertEqual(2,len(c.update(.6,(.8,.2),(640,480))))
        self.assertIsNone(c.update(.7,(.8,.2),(640,480)))

    def test_pose_requires_visible_torso(self):
        lm=[SimpleNamespace(x=.5,y=.5,visibility=.9) for _ in range(33)]
        self.assertTrue(pose_visible(lm)); lm[11].visibility=.1
        self.assertFalse(pose_visible(lm)); self.assertFalse(pose_visible([]))

    def test_missing_model_is_actionable(self):
        self.assertEqual(2,main(['--check-model','--model','missing-test-file.task']))

    @unittest.skipUnless(importlib.util.find_spec('mediapipe'),'MediaPipe not installed')
    def test_camera_and_landmarker_release_on_read_failure(self):
        from unittest.mock import MagicMock
        cam=MagicMock(); cam.read.return_value=(False,None)
        lm=MagicMock()
        args=SimpleNamespace(channel='right_wrist',record_label='horizontal',offline=True,
            model=Path('unused'),camera=0,backend='auto',seconds=1.8)
        with patch('pose_tracker.create_landmarker',return_value=lm),patch('pose_tracker.open_camera',return_value=cam):
            with self.assertRaisesRegex(ValueError,'frames'): run_live(args,'digest')
        cam.release.assert_called_once(); lm.close.assert_called_once()


class EventTests(unittest.TestCase):
    def test_publisher_payloads_pass_current_strict_contract(self):
        from sensor_events import validate_sensor_event
        events=[]
        def sender(event):
            validate_sensor_event(event)
            events.append(event)
            return {'ok':True}
        publisher=EventPublisher(sender)
        try:
            publisher.status('camera.status',True)
            publisher.status('pose.tracking',True)
            publisher.gesture(dict(predicted='horizontal',score=.8,accepted=True))
            self.wait_for(lambda: len(events)==3)
        finally:
            publisher.close()
        self.assertEqual(['mediapipe','mediapipe','dollarpy'],[e['source'] for e in events])

    def wait_for(self,predicate):
        deadline=time.monotonic()+2
        while time.monotonic()<deadline:
            if predicate(): return
            time.sleep(.01)
        self.fail('Sender did not reach expected state')

    def test_status_dedup_and_no_game_select(self):
        events=[]
        def sender(e): events.append(e); return {'ok':True}
        p=EventPublisher(sender)
        try:
            for _ in range(50): p.status('pose.tracking',True)
            self.wait_for(lambda: len(events)==1)
            p.gesture(dict(predicted='horizontal',score=.9,accepted=True))
            self.wait_for(lambda:len(events)==2)
            p.gesture(dict(predicted='vertical',score=.1,accepted=False))
        finally: p.close()
        self.assertEqual(['pose.tracking','gesture.recognized'],[e['type'] for e in events])

    def test_broker_rejection_is_retried(self):
        events=[]
        def sender(e):
            events.append(e)
            return {'ok':len(events)>1}
        p=EventPublisher(sender,retry_seconds=.02)
        try:
            p.status('camera.status',True)
            self.wait_for(lambda:len(events)>=2)
        finally:p.close()
        self.assertEqual(True,events[-1]['ready'])

    def test_unavailable_broker_never_blocks_producer(self):
        def sender(e): raise OSError('offline-test')
        p=EventPublisher(sender)
        start=time.monotonic()
        for _ in range(100):p.status('camera.status',True)
        self.assertLess(time.monotonic()-start,.2)
        p.close(); self.assertFalse(p.thread.is_alive())

    def test_download_mismatch_preserves_model(self):
        from unittest.mock import MagicMock
        with tempfile.TemporaryDirectory() as d:
            target=Path(d)/'pose_landmarker.task';target.write_bytes(b'old')
            response=MagicMock();response.__enter__.return_value.read.return_value=b'bad'
            with patch('download_tracker_model.urllib.request.urlopen',return_value=response):
                with self.assertRaisesRegex(ValueError,'checksum'): download('pose',d)
            self.assertEqual(b'old',target.read_bytes())


if __name__=='__main__': unittest.main()
