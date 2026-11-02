"""Capture timing regressions; simulated coordinates, not hardware evidence."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from pose_tracker import Capture, main


class CountdownTests(unittest.TestCase):
    def test_preparation_excluded_and_full_capture_duration_retained(self):
        capture = Capture(seconds=1.8)
        capture.arm(10, 3)
        for now, point in [(10.1, (.1,.9)), (12.9, (.9,.1))]:
            self.assertIsNone(capture.update(now, point, (640,480)))
        self.assertEqual([], capture.points)
        self.assertIsNone(capture.started)
        capture.update(13, (.2,.4), (640,480))
        self.assertEqual([[.2,.4,0]], capture.points)
        self.assertIsNone(capture.update(14.7, (.7,.4), (640,480)))
        points = capture.update(14.9, (.8,.4), (640,480))
        self.assertEqual(3, len(points))
        self.assertEqual([.2,.4,0], points[0])
        self.assertIsNone(capture.started)

    def test_missing_point_at_go_cancels_without_stale_points(self):
        capture = Capture()
        capture.arm(0,3)
        with self.assertRaisesRegex(ValueError, 'at GO'):
            capture.update(3,None,(640,480))
        self.assertIsNone(capture.armed_until)
        self.assertIsNone(capture.started)
        capture.arm(4,3)
        capture.update(7,(.5,.5),(640,480))
        self.assertEqual([[.5,.5,0]],capture.points)

    def test_repeated_space_cannot_restart_countdown_or_capture(self):
        capture = Capture()
        capture.arm(10,3)
        capture.arm(12,3)
        self.assertEqual(13,capture.armed_until)
        capture.update(13,(.5,.5),(640,480))
        capture.arm(14,3)
        self.assertIsNone(capture.armed_until)
        self.assertEqual(13,capture.started)

    def test_tracking_loss_after_go_still_discards_entire_capture(self):
        capture = Capture()
        capture.arm(0,0)
        capture.update(.1,(.5,.5),(640,480))
        with self.assertRaisesRegex(ValueError, 'tracking lost'):
            capture.update(.2,None,(640,480))
        self.assertEqual([],capture.points)
        self.assertIsNone(capture.started)

    def test_invalid_countdown_rejected_before_camera(self):
        for delay in ['-1','nan','inf','11']:
            with self.subTest(delay=delay), self.assertRaises(SystemExit) as raised:
                main(['--countdown',delay])
            self.assertEqual(2,raised.exception.code)


if __name__ == '__main__':
    unittest.main()
