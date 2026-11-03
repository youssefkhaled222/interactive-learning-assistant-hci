"""No simulated objects are presented as hardware results: gate logic only."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'backend'))
from object_tracking import ObjectTracker
from hand_selection import HandSelectionGate

BOX = {'x_min': .1, 'y_min': .2, 'x_max': .5, 'y_max': .7}


def observed(tracker, t, items=None):
    if items is None:
        items = [{'object': 'cup', 'confidence': .85, 'box': BOX}]
    tracker.update({'type':'objects.detected','active':True,'source':'yolo','detections':items}, now=t)


class HandSelectionTests(unittest.TestCase):
    def setUp(self):
        self.tracker = ObjectTracker()
        observed(self.tracker, 10)
        observed(self.tracker, 10.1)
        self.gate = HandSelectionGate()

    def hand(self, t, x=.25, y=.35, pinching=False, mode='gesture', ready=True):
        return self.gate.observe(x=x, y=y, pinching=pinching, tracker=self.tracker,
                                 mode=mode, ready=ready, now=t)

    def test_real_sequence_requires_open_hold_and_release(self):
        self.assertIsNone(self.hand(10.11, pinching=True))  # initially closed
        self.assertIsNone(self.hand(10.12))
        self.assertIsNone(self.hand(10.13))
        self.assertIsNone(self.hand(10.14, pinching=True))
        self.assertIsNone(self.hand(10.30, pinching=True))
        self.assertEqual(self.hand(10.42, pinching=True), 'cup')
        self.assertIsNone(self.hand(10.43, pinching=True))
        self.assertIsNone(self.hand(10.50))
        self.assertIsNone(self.hand(10.51))
        observed(self.tracker, 10.55)
        self.assertIsNone(self.hand(10.56, pinching=True))
        self.assertEqual(self.hand(10.85, pinching=True), 'cup')

    def test_cannot_start_closed_or_start_outside_target_then_slide(self):
        self.hand(10.11); self.hand(10.12)
        self.hand(10.13, x=.95, y=.95, pinching=True)
        self.assertIsNone(self.hand(10.45, pinching=True))
        self.assertIsNone(self.hand(10.65, pinching=True))

    def test_ambiguous_overlap_never_selects(self):
        observed(self.tracker, 10.11, items=[
            {'object':'cup','confidence':.8,'box':BOX},
            {'object':'book','confidence':.8,'box':BOX}])
        self.hand(10.12); self.hand(10.13)
        self.hand(10.14,pinching=True)
        self.assertIsNone(self.hand(10.50,pinching=True))

    def test_wrong_mode_cannot_select_and_requires_rearming(self):
        self.hand(10.11); self.hand(10.12)
        self.assertIsNone(self.hand(10.13,pinching=True,mode='gaze'))
        self.assertIsNone(self.hand(10.46,pinching=True))

    def test_tracking_loss_cancels(self):
        self.hand(10.11); self.hand(10.12)
        self.hand(10.13,pinching=True)
        self.assertIsNone(self.gate.observe(x=None,y=None,pinching=False,
            tracker=self.tracker,ready=True,mode='gesture',now=10.20))
        self.assertIsNone(self.hand(10.50,pinching=True))

    def test_intermit_empty_can_recover_but_must_have_real_box_on_commit(self):
        self.hand(10.11); self.hand(10.12)
        self.hand(10.13,pinching=True)
        observed(self.tracker,10.20,items=[])
        self.assertIsNone(self.hand(10.40,pinching=True))
        observed(self.tracker,10.45)
        self.assertEqual(self.hand(10.46,pinching=True),'cup')

    def test_watchdog_disarms_old_hand(self):
        self.hand(10.11); self.hand(10.12)
        self.assertTrue(self.gate.expired(now=12))
        self.assertIsNone(self.hand(12.01,pinching=True))

    def test_not_ready_rejected(self):
        self.hand(10.11); self.hand(10.12)
        self.assertIsNone(self.hand(10.13,pinching=True,ready=False))
        self.assertIsNone(self.hand(10.48,pinching=True,ready=True))


if __name__ == '__main__':
    unittest.main()
