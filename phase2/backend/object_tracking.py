"""Short-lived, normalized YOLO detection metadata for the local UI.

Only currently observed boxes are exposed. A brief missed detection can reuse a
previous temporary ID, but a missing box is NEVER returned as a selectable box.
No video or face images are transmitted. Temporary IDs are not identities.
"""
import time

# A model may miss a physical object between adjacent inference frames. Retain
# *only identity history* briefly; do not expose missing targets as present.
ID_REACQUIRE_SECONDS = 0.85
MIN_MATCH_IOU = 0.30


def _iou(a, b):
    x1 = max(a['x_min'], b['x_min'])
    y1 = max(a['y_min'], b['y_min'])
    x2 = min(a['x_max'], b['x_max'])
    y2 = min(a['y_max'], b['y_max'])
    inter = max(0.0, x2-x1)*max(0.0, y2-y1)
    area_a = (a['x_max']-a['x_min'])*(a['y_max']-a['y_min'])
    area_b = (b['x_max']-b['x_min'])*(b['y_max']-b['y_min'])
    union = area_a+area_b-inter
    return inter/union if union > 0 else 0.0


class ObjectTracker:
    """Associate recent same-class detection boxes with temporary target IDs.

    Coordinates are in the *object-facing camera frame* (0..1), not a separate
    child-facing hand/gaze camera. No game selection happens in this class.
    """
    def __init__(self):
        self.next_id = 1
        self.objects = []  # ONLY objects observed in the most recent update
        self._recent = {}  # ID -> {item, seen_at, hits}, never exposed to React
        self.active = False
        self.last_seen = None
        self.source = None

    def update(self, event, now=None):
        current = time.monotonic() if now is None else now
        self.active = event['active']
        self.source = event['source']
        self.last_seen = current
        if not self.active:
            self.objects = []
            self._recent.clear()
            return

        # Expired IDs cannot be recycled. A returning object gets a new ID.
        self._recent = {tid: track for tid, track in self._recent.items()
                        if current - track['seen_at'] <= ID_REACQUIRE_SECONDS}
        detections = event['detections']
        matches = []
        for incoming_idx, item in enumerate(detections):
            for tid, track in self._recent.items():
                prev = track['item']
                if item['object'] != prev['object']:
                    continue
                score = _iou(item['box'], prev['box'])
                if score >= MIN_MATCH_IOU:
                    matches.append((score, incoming_idx, tid))

        # Globally choose one-to-one associations. Prevent duplicate IDs when
        # two detections overlap the same prior box.
        assigned = {}
        used_tracks = set()
        for score, idx, tid in sorted(matches, key=lambda value: value[0], reverse=True):
            if idx not in assigned and tid not in used_tracks:
                assigned[idx] = tid
                used_tracks.add(tid)

        current_objects = []
        for idx, item in enumerate(detections):
            tid = assigned.get(idx)
            if tid is None:
                tid = f'obj-{self.next_id}'
                self.next_id += 1
                hits = 1
            else:
                hits = self._recent[tid]['hits'] + 1
            visible = {**item, 'target_id': tid}
            self._recent[tid] = {'item': visible, 'seen_at': current, 'hits': hits}
            current_objects.append(visible)
        self.objects = current_objects

    def expire(self, now=None, timeout=2.5):
        current = time.monotonic() if now is None else now
        if self.active and self.last_seen is not None and current-self.last_seen >= timeout:
            self.active = False
            self.objects = []
            self._recent.clear()
            return True
        return False

    def state(self):
        return {'object_detection_active': self.active,
                'detected_objects': [dict(item) for item in self.objects],
                'object_detection_source': self.source}
