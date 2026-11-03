"""Software-only tests for shared-frame overlays. Not a webcam demonstration."""
import json
import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from camera_preview import FrameBuffer, start_preview
from hand_pointer_preview import boxes_at_point, fetch_frame, post_hand_state


CUP = {'object': 'cup', 'confidence': .75,
       'box': {'x_min': .2, 'y_min': .2, 'x_max': .6, 'y_max': .7}}


class FrameAndPointerTests(unittest.TestCase):
    def test_boxes_share_same_raw_frame(self):
        b = FrameBuffer()
        b.publish_raw(b'fake-image-bytes', detections=[CUP])
        jpeg, seq, detections = b.hand_frame()
        self.assertEqual(jpeg, b'fake-image-bytes')
        self.assertEqual(seq, 1)
        self.assertEqual(detections, [CUP])
        self.assertEqual(boxes_at_point(detections, (.3, .4)), ['cup'])
        self.assertEqual(boxes_at_point(detections, (.8, .4)), [])
        b.close()
        self.assertEqual(b.hand_frame(), (None, None, []))

    def test_pointer_fails_closed_on_bad_or_old_frame(self):
        b = FrameBuffer()
        b.publish_raw(b'f')
        self.assertFalse(b.update_hand({'frame_sequence': 1, 'pointer': [.2, math.nan], 'pinching': True}))
        self.assertFalse(b.update_hand({'frame_sequence': 1, 'pointer': [1.2, .5], 'pinching': True}))
        self.assertFalse(b.update_hand({'frame_sequence': 1, 'pointer': [.2, .5], 'pinching': 1}))
        self.assertFalse(b.update_hand({'frame_sequence': 1, 'pointer': None, 'pinching': True}))
        self.assertFalse(b.update_hand({'frame_sequence': 99, 'pointer': [.2, .5], 'pinching': True}))
        self.assertIsNone(b.recent_hand())
        self.assertTrue(b.update_hand({'frame_sequence': 1, 'pointer': [.2, .5], 'pinching': True}))
        self.assertEqual(b.recent_hand()['pointer'], [.2, .5])
        for _ in range(10):
            b.publish_raw(b'f')
        self.assertIsNone(b.recent_hand())
        b.close()

    def test_missing_hand_is_not_a_pinching_indicator(self):
        b = FrameBuffer()
        b.publish_raw(b'f')
        self.assertTrue(b.update_hand({'frame_sequence': 1, 'pointer': None, 'pinching': False}))
        self.assertIsNone(b.recent_hand()['pointer'])
        b.close()

    def test_loopback_contract_real_http_no_game_select(self):
        srv = start_preview(port=0)
        try:
            srv.buffer.publish_raw(b'jpeg-placeholder', detections=[CUP])
            base = f'http://127.0.0.1:{srv.server_address[1]}/hand-frame'
            body, seq, det = fetch_frame(base)
            self.assertEqual(body, b'jpeg-placeholder')
            self.assertEqual(seq, 1)
            self.assertEqual(det, [CUP])
            self.assertTrue(post_hand_state(base, seq, (.3, .4), True))
            self.assertEqual(srv.buffer.recent_hand()['pinching'], True)
            body2, seq2, det2 = fetch_frame(base, last_sequence=seq)
            self.assertIsNone(body2)
            self.assertEqual(seq2, seq)
            self.assertEqual(det2, [])
        finally:
            srv.close()


if __name__ == '__main__':
    unittest.main()
