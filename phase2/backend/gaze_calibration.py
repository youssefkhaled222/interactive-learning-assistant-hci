"""Per-session 9-target, local MediaPipe iris-feature calibration.

The data structure contains only small numeric eye measurements, no face images.
Fit screen-normalized gaze locations from actual facial landmarks. Calibration
quality is measured against an unseen (held-out) center calibration target.
"""
import math
from collections import deque

import numpy as np

TARGET_COUNT = 9
MIN_SAMPLE_COUNT = 6


def _point(landmarks, index):
    p = landmarks[index]
    return float(p.x), float(p.y)


def _between(value, a, b):
    return (value - min(a, b)) / max(abs(a - b), 0.0001)


def eye_features(landmarks):
    """Require actual 478 iris landmarks. Never manufacture an eye position."""
    if len(landmarks) < 478:
        return None
    try:
        rh = _between(_point(landmarks, 468)[0], _point(landmarks, 33)[0],
                      _point(landmarks, 133)[0])
        lh = _between(_point(landmarks, 473)[0], _point(landmarks, 362)[0],
                      _point(landmarks, 263)[0])
        rv = _between(_point(landmarks, 468)[1], _point(landmarks, 159)[1],
                      _point(landmarks, 145)[1])
        lv = _between(_point(landmarks, 473)[1], _point(landmarks, 386)[1],
                      _point(landmarks, 374)[1])
        nose = _point(landmarks, 1)
        feature = np.array([1.0, (rh + lh) / 2, (rv + lv) / 2,
                            nose[0], nose[1]], dtype=float)
        if not np.isfinite(feature).all() or any(abs(v) > 3 for v in feature):
            return None
        # Very approximate eye visibility: iris must remain reasonably near eyes.
        if not (0 <= feature[1] <= 1 and -0.3 <= feature[2] <= 1.3):
            return None
        return feature
    except (IndexError, TypeError, ValueError, OverflowError):
        return None


class GazeCalibrator:
    def __init__(self):
        self.samples = deque(maxlen=120)
        self.points = []
        self.coefficients = None
        self.quality = None
        self.viewport = None

    @property
    def calibrated(self):
        return self.coefficients is not None

    def reset(self):
        self.samples.clear()
        self.points.clear()
        self.coefficients = None
        self.quality = None
        self.viewport = None

    def track(self, feature, now):
        if feature is not None:
            self.samples.append((now, feature))
        while self.samples and now - self.samples[0][0] > 1.5:
            self.samples.popleft()

    def capture(self, *, index, x, y, width, height, now):
        if type(index) is not int or index != len(self.points) or index >= TARGET_COUNT:
            raise ValueError('Unexpected calibration target; use the displayed dot in order')
        if not (all(type(v) in (int, float) and math.isfinite(v) for v in (x, y, width, height))
                and 0.02 <= x <= 0.98 and 0.02 <= y <= 0.98
                and 320 <= width <= 10000 and 240 <= height <= 10000):
            raise ValueError('Invalid calibration target or screen geometry')
        size = (int(width), int(height))
        if self.viewport is not None and size != self.viewport:
            raise ValueError('Browser size changed; reset calibration')
        recent = [feature for timestamp, feature in self.samples if now - timestamp <= 0.95]
        if len(recent) < MIN_SAMPLE_COUNT:
            raise ValueError('Cannot see steady eyes yet; face the camera and wait one second')
        group = np.stack(recent, axis=0)
        if float(np.max(np.std(group[:, 1:3], axis=0))) > 0.15:
            raise ValueError('Eyes moved too much; keep looking at the dot and retry')
        self.viewport = size
        self.points.append((np.mean(group, axis=0), np.array([x, y], dtype=float)))
        if len(self.points) == TARGET_COUNT:
            self.fit()
        return len(self.points)

    def fit(self):
        # Last target is held out to reject degenerate, position-independent fit.
        a = np.stack([f for f, _ in self.points[:8]])
        b = np.stack([p for _, p in self.points[:8]])
        # Light ridge stabilization of correlated head/pupil features.
        penalty = np.eye(a.shape[1]) * 0.0005
        penalty[0, 0] = 0.0
        coefficients = np.linalg.solve(a.T @ a + penalty, a.T @ b)
        predicted = a @ coefficients
        train_error = float(np.median(np.linalg.norm(predicted - b, axis=1)))
        held_feature, held_target = self.points[8]
        test_error = float(np.linalg.norm(held_feature @ coefficients - held_target))
        # Explicitly require distinguishable eye observations across calibration.
        if (np.ptp(a[:, 1]) < 0.025 or np.ptp(a[:, 2]) < 0.025 or
                train_error > 0.15 or test_error > 0.20):
            self.coefficients = None
            self.quality = {'train': round(train_error, 3),
                            'held_out': round(test_error, 3), 'accepted': False}
            raise ValueError('Calibration quality too low. Reset, improve lighting and retry.')
        self.coefficients = coefficients
        self.quality = {'train': round(train_error, 3),
                        'held_out': round(test_error, 3), 'accepted': True}

    def predict(self, feature):
        if not self.calibrated or feature is None:
            return None
        result = feature @ self.coefficients
        if not np.isfinite(result).all():
            return None
        return float(result[0]), float(result[1])
