"""Local-only calibrated gaze-to-YOLO dwell gate; never infer gaze from mouse input.

The caller must supply coordinates mapped by a calibrated *face camera* onto
*object camera* normalized image coordinates. Requires fresh stabilized YOLO ID.
No result is emitted from a stale/missing box or an absent gaze sample.
"""
import math
import time

from target_matching import resolve_target

DWELL_SECONDS = 1.50
RELEASE_SECONDS = 0.40
STALE_SECONDS = 1.20
MISSING_GRACE_SECONDS = 0.20


class GazeDwellGate:
    def __init__(self, dwell_seconds=DWELL_SECONDS):
        self.dwell_seconds = dwell_seconds
        self.reset()

    def reset(self, forget_heartbeat=False):
        self.candidate_id = None
        self.since = None
        self.missing_since = None
        self.latched = False
        self.off_since = None
        self.phase = 'calibrate'
        self.point = None
        self.progress = 0.0
        self.calibrated = False
        if forget_heartbeat or not hasattr(self, 'last_seen'):
            self.last_seen = None
            self.last_sequence = 0

    def expired(self, now=None):
        now = time.monotonic() if now is None else now
        if self.last_seen is None or now - self.last_seen <= STALE_SECONDS:
            return False
        self.reset(forget_heartbeat=True)
        self.phase = 'gaze-camera-offline'
        return True

    def observe(self, *, x, y, calibrated, frame_sequence, tracker, ready,
                mode, now=None):
        now = time.monotonic() if now is None else now
        if frame_sequence <= self.last_sequence:
            return None
        self.last_sequence = frame_sequence
        self.last_seen = now
        self.calibrated = calibrated
        valid = (type(x) in (int, float) and type(y) in (int, float) and
                 math.isfinite(x) and math.isfinite(y) and
                 0 <= x <= 1 and 0 <= y <= 1)
        self.point = {'x': float(x), 'y': float(y)} if valid else None
        if mode != 'gaze' or not calibrated or not ready:
            self.reset()
            self.calibrated = calibrated
            self.phase = 'inactive' if mode != 'gaze' else ('calibrate' if not calibrated else 'blocked')
            return None
        if not valid:
            # Losing face/preview mapping cannot accumulate dwell time.
            self.candidate_id = None
            self.since = None
            self.progress = 0.0
            self.missing_since = None
            self.phase = 'find-face-or-screen'
            if self.latched:
                self.off_since = self.off_since or now
                if now - self.off_since >= RELEASE_SECONDS:
                    self.latched = False
            return None
        target = resolve_target(tracker, x=x, y=y,
                                coordinate_space='object_view', now=now)
        if self.latched:
            self.phase = 'look-away-to-rearm'
            if not target['accepted'] or target['target_id'] != self.candidate_id:
                self.off_since = self.off_since or now
                if now - self.off_since >= RELEASE_SECONDS:
                    self.latched = False
                    self.candidate_id = None
                    self.since = None
                    self.progress = 0.0
                    self.phase = 'ready'
            else:
                self.off_since = None
            return None
        if not target['accepted']:
            if self.missing_since is None:
                self.missing_since = now
            if (self.candidate_id is not None and
                    now - self.missing_since <= MISSING_GRACE_SECONDS):
                self.phase = 'brief-detection-gap'
                return None
            self.candidate_id = None
            self.since = None
            self.progress = 0.0
            self.phase = target['reason']
            return None
        self.missing_since = None
        tid = target['target_id']
        if tid != self.candidate_id:
            self.candidate_id = tid
            self.since = now
            self.progress = 0.0
            self.phase = 'dwelling'
            return None
        elapsed = max(0.0, now - self.since)
        self.progress = min(1.0, elapsed / self.dwell_seconds)
        self.phase = 'dwelling'
        if elapsed < self.dwell_seconds:
            return None
        # A fresh target is required on this very frame; no remembered boxes.
        self.latched = True
        self.off_since = None
        self.phase = 'selected'
        return target['object']

    def view(self):
        return {'calibrated': self.calibrated,
                'phase': self.phase, 'point': self.point,
                'progress': round(self.progress, 3),
                'target_id': self.candidate_id,
                'dwell_seconds': self.dwell_seconds}
