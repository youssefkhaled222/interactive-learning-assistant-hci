"""Independent tests: no torch, model downloads, camera or YOLO needed."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from object_detector import (SUPPORTED_OBJECTS, normalize_box, parse_detections,
                             preview_record, supported_class_indices)


def result_with(*items):
    names = {0: "person", 41: "cup", 47: "apple", 73: "book"}
    boxes = [SimpleNamespace(cls=[cls], conf=[conf], xyxy=[box]) for cls, conf, box in items]
    return SimpleNamespace(names=names, boxes=boxes)


class TestObjectDetector(unittest.TestCase):
    def test_supported_classes(self):
        self.assertEqual(set(supported_class_indices({41: "cup", 47: "apple", 73: "book"})),
                         {41, 47, 73})
        self.assertEqual(SUPPORTED_OBJECTS, {"apple", "cup", "book"})

    def test_missing_model_class_rejected(self):
        with self.assertRaises(ValueError):
            supported_class_indices({41: "cup", 47: "apple"})

    def test_normalizes_pixel_box(self):
        self.assertEqual(normalize_box((32, 48, 320, 240), 640, 480),
                         dict(x_min=.05, y_min=.1, x_max=.5, y_max=.5))

    def test_clamps_box_to_frame(self):
        self.assertEqual(normalize_box((-20, -20, 660, 500), 640, 480),
                         dict(x_min=0.0, y_min=0.0, x_max=1.0, y_max=1.0))
        self.assertIsNone(normalize_box((650, 10, 680, 30), 640, 480))

    def test_invalid_coordinates_rejected(self):
        for coords in ((10, 10, 10, 30), (20, 20, 1, 30), (0, 0, float('nan'), 20)):
            with self.subTest(coords=coords), self.assertRaises(ValueError):
                normalize_box(coords, 640, 480)

    def test_only_real_supported_detections(self):
        result = result_with(
            (47, .82, (10, 20, 100, 150)), (0, .99, (20, 40, 100, 100)),
            (41, .2, (2, 2, 30, 30)), (73, .65, (50, 80, 200, 400)))
        detections = parse_detections(result, 640, 480)
        self.assertEqual([d['object'] for d in detections], ['apple', 'book'])
        self.assertEqual([d['confidence'] for d in detections], [.82, .65])

    def test_empty_result_does_not_invent_objects(self):
        self.assertEqual(parse_detections(result_with(), 640, 480), [])
        self.assertEqual(preview_record([], 640, 480)['detections'], [])

    def test_confidence_bounds_and_nonfinite_skipped(self):
        result = result_with((47, .3, (0, 0, 20, 20)), (41, float('nan'), (0, 0, 20, 20)),
                             (73, .85, (5, 5, 200, 200)))
        self.assertEqual([d['object'] for d in parse_detections(result, 640, 480, .5)], ['book'])
        for bad in (0, -1, 1.5):
            with self.assertRaises(ValueError):
                parse_detections(result, 640, 480, bad)


if __name__ == "__main__":
    unittest.main()
