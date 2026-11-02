"""Unit tests for strict browser command validation."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
from ui_commands import InvalidUICommand, to_engine_event


class TestUICommands(unittest.TestCase):
    def test_mode_gesture(self):
        self.assertEqual(to_engine_event({"type":"command","action":"mode.selected","payload":{"mode":"gesture"}}),
                         {"type":"mode.selected","mode":"gesture","source":"ui_bridge"})

    def test_mode_gaze(self):
        event = to_engine_event({"type":"command","action":"mode.selected","payload":{"mode":"gaze"}})
        self.assertEqual(event["mode"], "gaze")

    def test_restart(self):
        self.assertEqual(to_engine_event({"type":"command","action":"game.restart","payload":{}}),
                         {"type":"game.restart","source":"ui_bridge"})

    def test_rejects_sensor_impersonation(self):
        messages = [
            {"type":"command","action":"game.select","payload":{"object":"apple"}},
            {"type":"command","action":"device.discovered","payload":{"device_id":"fake"}},
            {"type":"command","action":"mode.selected","payload":{"mode":"gaze"},"source":"simulator"},
            {"type":"command","action":"mode.selected","payload":{"mode":"gaze","source":"mediapipe"}},
        ]
        for m in messages:
            with self.subTest(message=m), self.assertRaises(InvalidUICommand):
                to_engine_event(m)

    def test_next_object_command(self):
        self.assertEqual(to_engine_event({"type":"command","action":"game.next","payload":{}}),
                         {"type":"game.next","source":"ui_bridge"})

    def test_bad_shapes(self):
        messages = [None, 3, [], {},
                    {"type":"event","action":"game.restart","payload":{}},
                    {"type":"command","action":"mode.selected","payload":{"mode":"other"}},
                    {"type":"command","action":"game.restart","payload":{"x":1}},
                    {"type":"command","action":"game.next","payload":{"object":"book"}},
                    {"type":"command","action":"mode.selected","payload":None}]
        for m in messages:
            with self.subTest(message=m), self.assertRaises(InvalidUICommand):
                to_engine_event(m)


if __name__ == '__main__':
    unittest.main()
