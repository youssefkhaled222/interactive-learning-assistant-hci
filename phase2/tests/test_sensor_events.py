"""TCP event schema tests. No Bluetooth or camera hardware required."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
from sensor_events import InvalidSensorEvent, validate_sensor_event


class TestSensorEvents(unittest.TestCase):
    def test_frozen_contract_examples(self):
        samples = [
            {"type": "device.discovered", "device_id": "demo-device-beginner", "source": "bleak"},
            {"type": "device.lost", "source": "bleak"},
            {"type": "pose.tracking", "visible": True, "source": "mediapipe"},
            {"type": "pose.tracking", "visible": False, "source": "mediapipe"},
            {"type": "camera.status", "ready": False, "source": "mediapipe"},
            {"type": "gesture.recognized", "name": "swipe_right", "score": 0.8, "source": "dollarpy"},
            {"type": "gesture.recognized", "name": "circle", "source": "dollarpy"},
            {"type": "lighting.changed", "level": "low", "source": "camera"},
            {"type": "mode.selected", "mode": "gesture", "source": "ui_bridge"},
            {"type": "game.select", "object": "apple", "source": "gesture"},
            {"type": "game.restart", "source": "ui_bridge"},
        ]
        for sample in samples:
            with self.subTest(sample=sample):
                self.assertEqual(validate_sensor_event(sample), sample)

    def test_rejects_untruthful_bool_encodings(self):
        for value in ("false", "true", 0, 1, None, [], {}):
            for event_type, field in (("pose.tracking", "visible"), ("camera.status", "ready")):
                with self.subTest(value=value, type=event_type), self.assertRaises(InvalidSensorEvent):
                    validate_sensor_event({"type": event_type, field: value, "source": "mediapipe"})

    def test_rejects_bad_fields_and_types(self):
        samples = [
            None, [], {}, "foo", {"type": "unknown", "source": "simulator"},
            {"type": "device.discovered", "device_id": "x"},
            {"type": "device.discovered", "device_id": [], "source": "bleak"},
            {"type": "device.discovered", "device_id": "  ", "source": "bleak"},
            {"type": "device.lost", "source": "bleak", "user_id": "injected"},
            {"type": "gesture.recognized", "name": "", "source": "dollarpy"},
            {"type": "gesture.recognized", "name": "swipe", "score": True, "source": "dollarpy"},
            {"type": "gesture.recognized", "name": "swipe", "score": float("nan"), "source": "dollarpy"},
            {"type": "gesture.recognized", "name": "swipe", "score": float("inf"), "source": "dollarpy"},
            {"type": "lighting.changed", "level": "bright", "source": "camera"},
            {"type": "game.select", "object": {"name": "apple"}, "source": "gesture"},
            {"type": "game.select", "object": "apple", "source": "x\nmalicious"},
            {"type": "pose.tracking", "visible": True, "source": "mediapipe", "user_id": "injected"},
        ]
        for sample in samples:
            with self.subTest(sample=sample), self.assertRaises(InvalidSensorEvent):
                validate_sensor_event(sample)

    def test_input_is_not_mutated(self):
        original = {"type": "game.select", "object": "  apple  ", "source": "simulator"}
        result = validate_sensor_event(original)
        self.assertEqual(original["object"], "  apple  ")
        self.assertEqual(result["object"], "apple")
        self.assertIsNot(original, result)


if __name__ == "__main__":
    unittest.main()
