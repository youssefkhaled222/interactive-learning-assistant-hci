"""V5 real hardware selection gate: stable open-hand hover, then deliberate pinch.

This file never fabricates detections or dispatches game.select by itself. The
broker validates actual MediaPipe hand.pointer events against genuine YOLO boxes.
A recently seen real box can *arm* a pinch across a missed detector frame, but
ONLY a visible, stable, recent YOLO box can authorize the final commit.
"""
import time
from target_matching import resolve_target


class HandSelectionGate:
    """Open -> stable target hover -> pinch onset -> live target -> hold -> release."""

    def __init__(self, *, hold_seconds=0.25, release_observations=2,
                 max_wait_seconds=1.65, tracking_timeout=1.5,
                 hover_grace_seconds=0.60, max_pointer_drift=0.13,
                 clock=time.monotonic):
        self.hold_seconds = hold_seconds
        self.release_observations = release_observations
        self.max_wait_seconds = max_wait_seconds
        self.tracking_timeout = tracking_timeout
        self.hover_grace_seconds = hover_grace_seconds
        self.max_pointer_drift = max_pointer_drift
        self.clock = clock
        self.last_hand_at = None
        self.reset()

    def reset(self, *, forget_heartbeat=False):
        self.open_count = 0
        self.armed = False
        self.pinch_started = None
        self.candidate_id = None
        self.candidate_object = None
        self.selected = False
        self.hover_id = None
        self.hover_object = None
        self.hover_at = None
        self.hover_point = None
        self.phase = 'waiting-for-hand'
        self.hint = 'Show your open hand to the camera.'
        if forget_heartbeat:
            self.last_hand_at = None

    def expired(self, now=None):
        t = self.clock() if now is None else now
        if self.last_hand_at is not None and t - self.last_hand_at > self.tracking_timeout:
            self.reset(forget_heartbeat=True)
            return True
        return False

    def view(self):
        return {'phase': self.phase, 'hint': self.hint,
                'armed': bool(self.armed), 'target': self.candidate_object or self.hover_object,
                'pinch_active': self.pinch_started is not None}

    def _forget_hover(self):
        self.hover_id = None
        self.hover_object = None
        self.hover_at = None
        self.hover_point = None

    def _recent_hover(self, t, x, y):
        return (self.hover_id is not None and self.hover_at is not None
                and self.hover_point is not None
                and 0 <= t - self.hover_at <= self.hover_grace_seconds
                and abs(x - self.hover_point[0]) <= self.max_pointer_drift
                and abs(y - self.hover_point[1]) <= self.max_pointer_drift)

    def observe(self, *, x, y, pinching, tracker, ready, mode, now=None):
        t = self.clock() if now is None else now
        if x is None or y is None:
            self.reset()
            self.last_hand_at = t
            return None
        self.last_hand_at = t
        if not ready or mode != 'gesture':
            self.reset()
            self.phase = 'blocked'
            self.hint = ('Switch to Gesture mode.' if mode != 'gesture'
                         else 'Camera or hand tracking is not ready.')
            return None

        if not pinching:
            self.pinch_started = None
            self.candidate_id = None
            self.candidate_object = None
            self.selected = False
            self.open_count = min(self.release_observations, self.open_count + 1)
            self.armed = self.open_count >= self.release_observations
            match = resolve_target(tracker, x=x, y=y,
                                   coordinate_space='object_view', now=t)
            if match['accepted']:
                self.hover_id, self.hover_object = match['target_id'], match['object']
                self.hover_point, self.hover_at = (x, y), t
            elif match['reason'] not in ('no-visible-target-at-point',
                                        'detector-unavailable-or-stale') or not self._recent_hover(t, x, y):
                self._forget_hover()

            if not self.armed:
                self.phase = 'open-to-arm'
                self.hint = 'Keep your thumb and index finger apart briefly.'
            elif self._recent_hover(t, x, y):
                self.phase = 'ready-to-pinch'
                self.hint = f'Finger on {self.hover_object}. Pinch and hold.'
            else:
                self.phase = 'point-at-object'
                self.hint = 'Move your open fingertip inside one detected object box.'
            return None

        self.open_count = 0
        if self.pinch_started is None:
            # An initially closed hand or invalid closing edge cannot later
            # slide onto a new object and score. Opening re-arms the gate.
            if not self.armed:
                self.phase = 'release-to-arm'
                self.hint = 'Release the pinch, show your open hand, then try again.'
                return None
            self.armed = False
            self.pinch_started = t
            match = resolve_target(tracker, x=x, y=y,
                                   coordinate_space='object_view', now=t)
            if match['accepted']:
                self.candidate_id = match['target_id']
                self.candidate_object = match['object']
            elif (match['reason'] in ('no-visible-target-at-point',
                                     'detector-unavailable-or-stale')
                  and self._recent_hover(t, x, y)):
                # The hand can hide the object at the closing edge. The cached
                # box is only a tentative candidate, never scoring evidence.
                self.candidate_id = self.hover_id
                self.candidate_object = self.hover_object
            else:
                self.phase = 'pinch-start-rejected'
                self.hint = f'No stable object at pinch start ({match["reason"]}). Release and retry.'
                return None
            self.phase = 'pinch-holding'
            self.hint = f'Keep pinching the {self.candidate_object} briefly.'
            return None

        if self.selected:
            self.phase = 'release-after-select'
            self.hint = 'Answer accepted. Release your fingers before the next object.'
            return None
        if self.candidate_id is None:
            # Do not reinterpret a failed closing edge as a new selection.
            if self.phase != 'pinch-start-rejected':
                self.phase = 'release-to-retry'
                self.hint = 'Release your fingers, then try another pinch.'
            return None
        if t - self.pinch_started > self.max_wait_seconds:
            self.candidate_id = None
            self.candidate_object = None
            self.phase = 'pinch-timeout'
            self.hint = 'Selection timed out. Release and try again.'
            return None
        if t - self.pinch_started < self.hold_seconds:
            self.phase = 'pinch-holding'
            self.hint = 'Keep pinching for a moment.'
            return None

        # Final commit is never based on hover memory; this must be a fresh
        # and stable real detection matching the same temporary target ID.
        final = resolve_target(tracker, x=x, y=y,
                               coordinate_space='object_view',
                               target_id=self.candidate_id, now=t)
        if final['accepted'] and final['object'] == self.candidate_object:
            self.selected = True
            self.phase = 'selection-accepted'
            self.hint = f'Selected {final["object"]}. Release your fingers.'
            return final['object']
        if final['reason'] in ('no-visible-target-at-point',
                               'detector-unavailable-or-stale'):
            self.phase = 'waiting-for-detection'
            self.hint = 'Keep your finger still: waiting for the object box to reappear.'
            return None
        self.candidate_id = None
        self.candidate_object = None
        self.phase = 'selection-rejected'
        self.hint = f'Target changed or became ambiguous ({final["reason"]}). Release and retry.'
        return None
