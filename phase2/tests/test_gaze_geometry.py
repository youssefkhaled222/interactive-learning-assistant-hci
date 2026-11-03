import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'backend'))
from gaze_tracker import GazeState

class GeometryTests(unittest.TestCase):
    def test_mapping_requires_fresh_preview(self):
        state=GazeState()
        self.assertIsNone(state.map_point((.5,.5),now=10))
        state.geometry=(.2,.2,.8,.8)
        state.geometry_at=10
        mapped=state.map_point((.5,.5),10.5)
        self.assertAlmostEqual(mapped[0],.5)
        self.assertAlmostEqual(mapped[1],.5)
        self.assertIsNone(state.map_point((.1,.5),10.5))
        self.assertIsNone(state.map_point((.5,.5),13))

    def test_uncalibrated_face_never_sends_position(self):
        state=GazeState()
        event=state.observe(None,10)
        self.assertIsNone(event['x'])
        self.assertIsNone(event['y'])
        self.assertFalse(event['calibrated'])
        self.assertEqual(event['frame_sequence'],1)

    def test_geometry_cannot_bypass_calibration(self):
        state=GazeState()
        with self.assertRaises(ValueError):
            state.apply('/geometry',{'rect':[.2,.2,.8,.8],'width':1200,'height':800})
        with self.assertRaises(ValueError):
            state.apply('/capture',{'index':0,'x':.5,'y':.5,'width':1200,'height':800})

if __name__=='__main__':unittest.main()
