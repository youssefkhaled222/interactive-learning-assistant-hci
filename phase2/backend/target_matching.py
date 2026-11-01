"""Pure safety gate for a future hand/gaze-to-object selection adapter.

IMPORTANT: Does not send game.select, process sensor streams, or calibrate
camera coordinates. A selection point must already be mapped onto the SAME
object-facing camera preview that produced YOLO's normalized bounding boxes.
"""
import math
import time


def resolve_target(tracker, *, x, y, coordinate_space, target_id=None,
                   now=None, min_observations=2, max_age_seconds=0.8,
                   min_confidence=0.35):
    """Return a candidate only for one fresh, visible, sufficiently stable box.

    This is a *candidate*, not proof of a real gaze/pinch or a validated answer.
    Callers must independently verify real gesture/dwell, mode, session state,
    release/debounce, and current question before dispatching game.select.
    """
    if coordinate_space != 'object_view':
        return {'accepted': False, 'reason': 'coordinate-space-not-calibrated'}
    if (type(x) not in (int, float) or type(y) not in (int, float) or
            not math.isfinite(x) or not math.isfinite(y) or
            not (0 <= x <= 1 and 0 <= y <= 1)):
        return {'accepted': False, 'reason': 'invalid-point'}
    if target_id is not None and (not isinstance(target_id, str) or not target_id):
        return {'accepted': False, 'reason': 'invalid-target-id'}
    current = time.monotonic() if now is None else now
    if not tracker.active or tracker.last_seen is None or current - tracker.last_seen > max_age_seconds:
        return {'accepted': False, 'reason': 'detector-unavailable-or-stale'}

    # Include *all* boxes when determining overlap ambiguity. An unstable
    # detection must not accidentally make a second overlapping target safe.
    overlapping = [obj for obj in tracker.objects
                   if obj['box']['x_min'] <= x <= obj['box']['x_max']
                   and obj['box']['y_min'] <= y <= obj['box']['y_max']]
    if not overlapping:
        return {'accepted': False, 'reason': 'no-visible-target-at-point'}
    if len(overlapping) != 1:
        return {'accepted': False, 'reason': 'ambiguous-overlapping-targets'}
    obj = overlapping[0]
    if target_id is not None and obj['target_id'] != target_id:
        return {'accepted': False, 'reason': 'target-id-mismatch'}
    track = tracker._recent.get(obj['target_id'])
    if track is None or track['hits'] < min_observations:
        return {'accepted': False, 'reason': 'target-not-stable-yet'}
    if obj['confidence'] < min_confidence:
        return {'accepted': False, 'reason': 'low-detection-confidence'}
    return {'accepted': True, 'reason': 'candidate-only',
            'target_id': obj['target_id'], 'object': obj['object'],
            'confidence': obj['confidence']}
