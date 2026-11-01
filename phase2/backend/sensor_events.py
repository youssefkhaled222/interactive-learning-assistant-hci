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
    "device.discovered": ({"device_id"}, set()),
    "device.lost": (set(), set()),
    "pose.tracking": ({"visible"}, set()),
    "camera.status": ({"ready"}, set()),
    "gesture.recognized": ({"name"}, {"score"}),
    "lighting.changed": ({"level"}, set()),
    "mode.selected": ({"mode"}, set()),
    "game.select": ({"object"}, set()),
    "game.restart": (set(), set()),
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

    if kind == "device.discovered":
        result["device_id"] = _text(result["device_id"], "device_id", 128)
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
    elif kind == "lighting.changed":
        if result["level"] not in ("good", "low", "unknown"):
            raise InvalidSensorEvent("level must be good, low or unknown")
    elif kind == "mode.selected":
        if result["mode"] not in ("gesture", "gaze"):
            raise InvalidSensorEvent("mode must be gesture or gaze")
    elif kind == "game.select":
        result["object"] = _text(result["object"], "object")
    return result
