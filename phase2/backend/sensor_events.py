"""Validate the frozen local TCP JSONL event contract before engine mutation.

This is schema validation, not proof that sensor data came from real hardware:
loopback TCP clients can claim any `source`. Never use source labels alone as
hardware evidence or as an authorization mechanism.
"""
import math


class InvalidSensorEvent(ValueError):
    """An incoming event violates the Phase II TCP JSONL contract."""


# Required fields in addition to `type` and `source`, plus optional fields.
# Keep these event names/fields consistent with docs/EVENT_CONTRACT.md.
SCHEMAS = {
    "device.discovered": ({"device_id"}, {"ts"}),
    "device.lost": (set(), {"device_id", "ts"}),
    "pose.tracking": ({"visible"}, set()),
    "camera.status": ({"ready"}, set()),
    "gesture.recognized": ({"name"}, {"score"}),
    "lighting.changed": ({"level"}, set()),
    "mode.selected": ({"mode"}, set()),
    "game.select": ({"object"}, set()),
    "game.next": (set(), set()),
    "game.restart": (set(), set()),
    "objects.detected": ({"active", "detections"}, set()),
    "gaze.point": ({"x", "y", "calibrated", "frame_sequence"}, set()),  # HCI_GAZE_V6
    "hand.pointer": ({"x", "y", "pinching", "frame_sequence"}, set()),  # HCI_REAL_PINCH_V4
}


def _text(value, field, max_length=60):
    if not isinstance(value, str) or not value.strip() or len(value) > max_length:
        raise InvalidSensorEvent(f"{field} must be non-empty text (max {max_length} chars)")
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise InvalidSensorEvent(f"{field} contains a control character")
    return value.strip()


def validate_sensor_event(event):
    """Return a validated, normalized *copy*; reject malformed data atomically.

    The engine must never see invalid payloads because several state mutations
    (such as event provenance) happen before the engine checks event semantics.
    This function intentionally does not attempt to authenticate hardware.
    """
    if not isinstance(event, dict):
        raise InvalidSensorEvent("Expected a JSON object")
    kind = event.get("type")
    if not isinstance(kind, str) or kind not in SCHEMAS:
        raise InvalidSensorEvent("Unknown event type")
    required, optional = SCHEMAS[kind]
    expected = {"type", "source"} | required
    present = set(event)
    if not expected <= present or present - expected - optional:
        raise InvalidSensorEvent(f"Invalid fields for {kind}")

    result = dict(event)
    result["source"] = _text(result["source"], "source")

    if kind in ("device.discovered", "device.lost"):
        if "device_id" in result:
            result["device_id"] = _text(result["device_id"], "device_id", 128)
        if "ts" in result:
            ts = result["ts"]
            if type(ts) not in (int, float) or not math.isfinite(ts) or ts < 0:
                raise InvalidSensorEvent("ts must be a finite nonnegative timestamp")
    elif kind in ("pose.tracking", "camera.status"):
        field = "visible" if kind == "pose.tracking" else "ready"
        if type(result[field]) is not bool:
            raise InvalidSensorEvent(f"{field} must be true or false")
    elif kind == "gesture.recognized":
        result["name"] = _text(result["name"], "name")
        if "score" in result:
            score = result["score"]
            if type(score) not in (int, float) or not math.isfinite(score):
                raise InvalidSensorEvent("score must be a finite number")
    elif kind == 'gaze.point':
        if type(result['calibrated']) is not bool:
            raise InvalidSensorEvent('calibrated must be boolean')
        seq = result['frame_sequence']
        if type(seq) is not int or seq < 1:
            raise InvalidSensorEvent('gaze frame_sequence must be a positive integer')
        x, y = result['x'], result['y']
        if x is None or y is None:
            if x is not None or y is not None:
                raise InvalidSensorEvent('gaze coordinates must both be absent')
        elif (not result['calibrated'] or
              any(type(v) not in (int, float) or not math.isfinite(v)
                  or not 0 <= v <= 1 for v in (x, y))):
            raise InvalidSensorEvent('gaze point needs calibrated finite normalized coordinates')
    elif kind == "hand.pointer":
        if type(result['pinching']) is not bool:
            raise InvalidSensorEvent('pinching must be boolean')
        seq = result['frame_sequence']
        if type(seq) is not int or seq < 1:
            raise InvalidSensorEvent('frame_sequence must be a positive integer')
        x, y = result['x'], result['y']
        if x is None or y is None:
            if x is not None or y is not None or result['pinching']:
                raise InvalidSensorEvent('missing hand cannot pinch or give a point')
        elif any(type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v <= 1
                 for v in (x, y)):
            raise InvalidSensorEvent('hand pointer must be normalized finite coordinates')
    elif kind == "objects.detected":
        if type(result["active"]) is not bool:
            raise InvalidSensorEvent("active must be true or false")
        detections = result["detections"]
        if not isinstance(detections, list) or len(detections) > 10:
            raise InvalidSensorEvent("detections must be a list with at most 10 objects")
        if not result["active"] and detections:
            raise InvalidSensorEvent("inactive detector must have empty detections")
        checked = []
        for item in detections:
            if not isinstance(item, dict) or set(item) != {"object", "confidence", "box"}:
                raise InvalidSensorEvent("Invalid detection fields")
            if item["object"] not in ("apple", "book", "cup"):
                raise InvalidSensorEvent("Unsupported detected object")
            conf = item["confidence"]
            if type(conf) not in (int, float) or not math.isfinite(conf) or not 0 <= conf <= 1:
                raise InvalidSensorEvent("confidence must be between 0 and 1")
            box = item["box"]
            keys = ("x_min", "y_min", "x_max", "y_max")
            if not isinstance(box, dict) or set(box) != set(keys):
                raise InvalidSensorEvent("Invalid detection box")
            if not all(type(box[k]) in (int, float) and math.isfinite(box[k]) and 0 <= box[k] <= 1 for k in keys):
                raise InvalidSensorEvent("Box coordinates must be finite numbers in [0,1]")
            if box["x_max"] <= box["x_min"] or box["y_max"] <= box["y_min"]:
                raise InvalidSensorEvent("Detection box must have positive area")
            checked.append({"object": item["object"], "confidence": float(conf),
                            "box": {k: float(box[k]) for k in keys}})
        result["detections"] = checked
    elif kind == "lighting.changed":
        if result["level"] not in ("good", "low", "unknown"):
            raise InvalidSensorEvent("level must be good, low or unknown")
    elif kind == "mode.selected":
        if result["mode"] not in ("gesture", "gaze"):
            raise InvalidSensorEvent("mode must be gesture or gaze")
    elif kind == "game.select":
        result["object"] = _text(result["object"], "object")
    return result
