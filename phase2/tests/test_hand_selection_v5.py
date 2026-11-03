"""V5 regression for real-sensor-only candidate policy (synthetic logic inputs)."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'backend'))
from hand_selection import HandSelectionGate
from object_tracking import ObjectTracker

CUP = {'object':'cup','confidence':.85, 'box':{
    'x_min':.1,'y_min':.2,'x_max':.5,'y_max':.7}}
BOOK = {'object':'book','confidence':.85, 'box':{
    'x_min':.62,'y_min':.2,'x_max':.93,'y_max':.7}}

def update(t, tracker, detections):
    tracker.update({'type':'objects.detected','source':'yolo',
                    'active':True,'detections':detections}, now=t)

class LiveHoverSafetyTests(unittest.TestCase):
    def setUp(self):
        self.tracker = ObjectTracker()
        self.gate = HandSelectionGate()
        update(10, self.tracker, [CUP])
        update(10.1, self.tracker, [CUP])

    def point(self, t, closed=False, x=.25, y=.35):
        return self.gate.observe(x=x,y=y,pinching=closed,
            tracker=self.tracker,ready=True,mode='gesture',now=t)

    def test_armed_hover_survives_one_missing_detection_at_pinch_start(self):
        self.point(10.11); self.point(10.12)
        self.assertEqual(self.gate.view()['phase'],'ready-to-pinch')
        update(10.18,self.tracker,[])
        self.point(10.2,closed=True)
        self.assertEqual(self.gate.candidate_object, 'cup')
        self.assertIsNone(self.point(10.35,closed=True))  # cannot score missing box
        update(10.42,self.tracker,[CUP])
        self.assertEqual(self.point(10.48,closed=True),'cup')
        self.assertEqual(self.gate.view()['phase'],'selection-accepted')

    def test_hover_does_not_score_if_box_never_reappears(self):
        self.point(10.11);self.point(10.12)
        update(10.18,self.tracker,[])
        self.point(10.20,closed=True)
        for t in (10.5,10.9,11.5,12.0):
            self.assertIsNone(self.point(t,closed=True))
        self.assertEqual(self.gate.view()['phase'],'pinch-timeout')

    def test_open_hand_moves_away_clears_hover(self):
        self.point(10.11);self.point(10.12)
        self.point(10.15,x=.91,y=.91)
        self.assertIsNone(self.gate.hover_id)
        update(10.18,self.tracker,[])
        self.point(10.20,closed=True,x=.91,y=.91)
        self.assertIsNone(self.gate.candidate_id)

    def test_no_reused_hover_after_tracking_lost(self):
        self.point(10.11);self.point(10.12)
        self.gate.observe(x=None,y=None,pinching=False,
            tracker=self.tracker,ready=True,mode='gesture',now=10.14)
        update(10.16,self.tracker,[])
        self.point(10.17,closed=True)
        self.assertIsNone(self.gate.candidate_id)

    def test_unstable_different_object_cannot_be_committed(self):
        self.point(10.11);self.point(10.12)
        update(10.18,self.tracker,[])
        self.point(10.20,closed=True)
        update(10.42,self.tracker,[BOOK])
        self.assertIsNone(self.point(10.45,closed=True,x=.7,y=.35))
        self.assertNotEqual(self.gate.view()['phase'],'selection-accepted')

    def test_overlapping_targets_remain_ambiguous(self):
        self.point(10.11);self.point(10.12)
        self.point(10.13,closed=True)
        update(10.42,self.tracker,[CUP,{**BOOK,'box':CUP['box']}])
        self.assertIsNone(self.point(10.44,closed=True))

    def test_releasing_rearms_for_next_answer(self):
        self.point(10.11);self.point(10.12)
        self.point(10.13,closed=True)
        self.assertEqual(self.point(10.43,closed=True),'cup')
        self.assertIsNone(self.point(10.44,closed=True))
        self.point(10.45);self.point(10.46)
        update(10.50,self.tracker,[CUP])
        self.point(10.52,closed=True)
        self.assertEqual(self.point(10.80,closed=True),'cup')

if __name__ == '__main__':
    unittest.main()
