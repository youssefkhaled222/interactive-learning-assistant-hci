"""Synthetic unit tests; real 2-camera eye-gaze remains to be tested on hardware."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'backend'))
from gaze_dwell import GazeDwellGate
from object_tracking import ObjectTracker

APPLE={'object':'apple','confidence':0.92,
       'box':{'x_min':0.2,'x_max':0.6,'y_min':0.2,'y_max':0.7}}
BOOK={'object':'book','confidence':0.92,
      'box':{'x_min':0.65,'x_max':0.95,'y_min':0.2,'y_max':0.7}}

class GazeDwellTests(unittest.TestCase):
    def setUp(self):
        self.gate=GazeDwellGate()
        self.tracker=ObjectTracker()
        self.tracker.update({'type':'objects.detected','source':'yolo','active':True,
                             'detections':[APPLE,BOOK]}, now=10.0)
        self.tracker.update({'type':'objects.detected','source':'yolo','active':True,
                             'detections':[APPLE,BOOK]}, now=10.1)
        self.seq=0

    def look(self,t, x=.4,y=.4,calibrated=True,ready=True,mode='gaze'):
        self.seq+=1
        return self.gate.observe(x=x,y=y,calibrated=calibrated,
                frame_sequence=self.seq,tracker=self.tracker,ready=ready,mode=mode,now=t)

    def test_1500ms_dwell_selects_once_then_requires_look_away(self):
        self.assertIsNone(self.look(10.15))
        for t in (10.5, 11.0, 11.5):
            self.tracker.update({'type':'objects.detected','source':'yolo',
                 'active':True,'detections':[APPLE,BOOK]}, now=t)
        self.assertIsNone(self.look(11.49))
        self.assertEqual(self.look(11.66),'apple')
        self.assertIsNone(self.look(11.7))
        self.assertIsNone(self.look(11.9,x=.01,y=.01))
        self.look(12.35,x=.01,y=.01)
        self.assertEqual(self.gate.phase,'ready')

    def test_invalid_tracking_and_uncalibrated_cannot_score(self):
        self.look(10.15,calibrated=False)
        self.assertEqual(self.gate.phase,'calibrate')
        self.look(10.3,ready=False)
        self.assertEqual(self.gate.phase,'blocked')
        self.assertIsNone(self.look(11.7,x=None,y=None))
        self.assertIsNone(self.look(12.0,mode='gesture'))

    def test_no_stale_box_commit(self):
        self.look(10.15)
        self.assertIsNone(self.look(11.7))
        self.assertNotEqual(self.gate.phase,'selected')

    def test_no_wrong_target_on_switch(self):
        self.look(10.15)
        self.look(10.5,x=.8,y=.4)
        self.tracker.update({'type':'objects.detected','source':'yolo',
                 'active':True,'detections':[BOOK]},now=11.9)
        self.assertIsNone(self.look(12.1,x=.8,y=.4))

    def test_no_duplicate_frame_sequence(self):
        self.look(10.15)
        self.assertIsNone(self.gate.observe(x=.4,y=.4,calibrated=True,
            frame_sequence=self.seq,tracker=self.tracker,ready=True,mode='gaze',now=50))
        self.assertEqual(self.gate.progress,0)

    def test_expiry_forces_new_calibration(self):
        self.look(10.15)
        self.assertTrue(self.gate.expired(now=12))
        self.assertFalse(self.gate.calibrated)
        self.assertEqual(self.gate.last_sequence,0)

    def test_gaze_point_cannot_score_when_object_overlap(self):
        self.tracker.update({'type':'objects.detected','source':'yolo',
                'active':True,'detections':[APPLE,{**BOOK,'box':APPLE['box']}]}, now=10.2)
        self.assertIsNone(self.look(10.3))
        self.assertEqual(self.gate.phase,'ambiguous-overlapping-targets')

if __name__ == '__main__':unittest.main()
