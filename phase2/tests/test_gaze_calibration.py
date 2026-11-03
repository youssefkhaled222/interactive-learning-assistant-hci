import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'backend'))
import numpy as np
from gaze_calibration import GazeCalibrator, eye_features

P = [(0.12,0.12),(0.5,0.12),(0.88,0.12),(0.12,0.5),
     (0.88,0.5),(0.12,0.88),(0.5,0.88),(0.88,0.88),(0.5,0.5)]

class CalibrationTests(unittest.TestCase):
    def test_linear_gaze_is_calibrated_with_held_out_target(self):
        model=GazeCalibrator()
        for i,(x,y) in enumerate(P):
            feature=np.array([1.0,0.2+0.6*x,0.2+0.6*y,0.49,0.52])
            for n in range(10):model.track(feature,now=i*3+n*.05)
            model.capture(index=i,x=x,y=y,width=1200,height=800,now=i*3+.5)
        self.assertTrue(model.calibrated)
        predicted=model.predict(np.array([1.0,0.2+0.6*.3,0.2+0.6*.7,.49,.52]))
        self.assertAlmostEqual(predicted[0],.3,delta=.03)
        self.assertAlmostEqual(predicted[1],.7,delta=.03)
        self.assertTrue(model.quality['accepted'])

    def test_cannot_calibrate_without_real_iris_variation(self):
        model=GazeCalibrator()
        for i,(x,y) in enumerate(P):
            for n in range(10):model.track(np.array([1,.5,.5,.5,.5]),i*3+n*.05)
            if i < 8:model.capture(index=i,x=x,y=y,width=1200,height=800,now=i*3+.5)
            else:
                with self.assertRaises(ValueError):
                    model.capture(index=i,x=x,y=y,width=1200,height=800,now=i*3+.5)
        self.assertFalse(model.calibrated)

    def test_short_or_wrong_index_rejected(self):
        model=GazeCalibrator()
        self.assertIsNone(eye_features([]))
        with self.assertRaises(ValueError):model.capture(index=2,x=.5,y=.5,width=1200,height=800,now=10)
        with self.assertRaises(ValueError):model.capture(index=0,x=.5,y=.5,width=1200,height=800,now=10)

if __name__ == '__main__':unittest.main()
