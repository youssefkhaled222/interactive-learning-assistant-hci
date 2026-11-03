"""Hardware-independent tests; these do not prove webcam input works."""
import math
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from hand_pointer_preview import PinchState, landmark_xy, normalized_pinch_ratio


def make_hand():
    p = [SimpleNamespace(x=.5, y=.5) for _ in range(21)]
    p[5] = SimpleNamespace(x=.4, y=.55)
    p[17] = SimpleNamespace(x=.6, y=.55)
    p[8] = SimpleNamespace(x=.5, y=.35)
    p[4] = SimpleNamespace(x=.5, y=.36)
    return p


class HandGeometryTests(unittest.TestCase):
    def test_realistic_pinch_ratio(self):
        self.assertAlmostEqual(normalized_pinch_ratio(make_hand()), .05)

    def test_open_hand(self):
        p = make_hand()
        p[4] = SimpleNamespace(x=.8, y=.8)
        self.assertGreater(normalized_pinch_ratio(p), 1)

    def test_missing_landmarks(self):
        self.assertIsNone(normalized_pinch_ratio([]))
        self.assertIsNone(landmark_xy([], 8))

    def test_out_of_bounds_and_nan_fail_closed(self):
        p = make_hand()
        p[8] = SimpleNamespace(x=math.nan, y=.35)
        self.assertIsNone(normalized_pinch_ratio(p))
        p[8] = SimpleNamespace(x=-.1, y=.35)
        self.assertIsNone(normalized_pinch_ratio(p))

    def test_tiny_palm_rejected(self):
        p = make_hand()
        p[17] = SimpleNamespace(x=.401, y=.55)
        self.assertIsNone(normalized_pinch_ratio(p))

    def test_hysteresis_prevents_flicker(self):
        s = PinchState()
        self.assertFalse(s.update(.9))
        self.assertTrue(s.update(.30))
        self.assertTrue(s.update(.49))
        self.assertFalse(s.update(.66))

    def test_missing_hand_resets_indicator(self):
        s = PinchState()
        self.assertTrue(s.update(.2))
        self.assertFalse(s.update(None))

    def test_invalid_thresholds(self):
        with self.assertRaises(ValueError):
            PinchState(.8, .6)


if __name__ == '__main__':
    unittest.main()
