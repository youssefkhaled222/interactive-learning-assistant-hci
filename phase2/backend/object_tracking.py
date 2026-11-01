"""Short-lived, normalized YOLO detection metadata for the local UI.

No video or face images are transmitted. Tracking IDs are temporary and local;
never use them as identities, nor allow detections alone to select an answer.
"""
import time


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
    """Associate adjacent frame detections using matching class and IoU."""
    def __init__(self):
        self.next_id = 1
        self.objects = []
        self.active = False
        self.last_seen = None
        self.source = None

    def update(self, event, now=None):
        self.active = event['active']
        self.source = event['source']
        self.last_seen = time.monotonic() if now is None else now
        if not self.active:
            self.objects = []
            return
        next_objects = []
        used = set()
        for item in event['detections']:
            best_idx, best_iou = None, 0.30
            for i, prev in enumerate(self.objects):
                if i in used or prev['object'] != item['object']:
                    continue
                score = _iou(prev['box'], item['box'])
                if score >= best_iou:
                    best_idx, best_iou = i, score
            if best_idx is None:
                target_id = f"obj-{self.next_id}"
                self.next_id += 1
            else:
                used.add(best_idx)
                target_id = self.objects[best_idx]['target_id']
            next_objects.append({**item, 'target_id': target_id})
        self.objects = next_objects

    def expire(self, now=None, timeout=2.5):
        current = time.monotonic() if now is None else now
        if self.active and self.last_seen is not None and current-self.last_seen >= timeout:
            self.active = False
            self.objects = []
            return True
        return False

    def state(self):
        return {'object_detection_active': self.active,
                'detected_objects': [dict(item) for item in self.objects],
                'object_detection_source': self.source}
