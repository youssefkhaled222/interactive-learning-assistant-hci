"""Local HTTP JPEG snapshot refresh and shutdown; no physical camera or fake game score."""
import json
import sys
import time
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from camera_preview import FrameBuffer, start_preview

REF = 'http://127.0.0.1:5173/'


class TestSnapshotRefresh(unittest.TestCase):
    def setUp(self):
        self.srv = start_preview(port=0)
        self.base = f'http://127.0.0.1:{self.srv.server_address[1]}'

    def tearDown(self):
        self.srv.close()

    def req(self, path, referer=None):
        return urlopen(Request(self.base + path, headers=({'Referer': referer} if referer else {})),timeout=2)

    def test_new_frame_updates_serial_and_bytes_without_mjpeg(self):
        self.srv.buffer.publish(b'first-jpeg')
        with self.req('/health') as r:
            state = json.load(r)
        self.assertTrue(state['has_frame'])
        self.assertEqual(state['frame_sequence'], 1)
        with self.req('/snapshot?frame=1', REF) as r:
            self.assertEqual(r.read(), b'first-jpeg')
            self.assertEqual(r.headers['Content-Type'], 'image/jpeg')
            self.assertEqual(r.headers['Cache-Control'], 'no-store')
        self.srv.buffer.publish(b'second-jpeg')
        with self.req('/health') as r:
            self.assertEqual(json.load(r)['frame_sequence'], 2)
        with self.req('/snapshot?frame=2', REF) as r:
            self.assertEqual(r.read(), b'second-jpeg')

    def test_snapshot_not_embeddable_by_other_sites(self):
        self.srv.buffer.publish(b'image')
        for referer in (None, 'https://untrusted.example/'):
            with self.assertRaises(HTTPError) as err:
                self.req('/snapshot?frame=1', referer)
            self.assertEqual(err.exception.code, 403)

    def test_stale_frame_not_reported_as_live(self):
        self.srv.buffer.publish(b'image')
        self.srv.buffer._last_jpeg_at -= 3.0
        with self.req('/health') as r:
            state = json.load(r)
        self.assertFalse(state['has_frame'])
        self.assertEqual(state['frame_sequence'], 0)
        with self.assertRaises(HTTPError) as err:
            self.req('/snapshot?frame=1', REF)
        self.assertEqual(err.exception.code, 503)

    def test_invalid_query_rejected(self):
        self.srv.buffer.publish(b'image')
        with self.assertRaises(HTTPError) as err:
            self.req('/snapshot?frame=1&anything=2', REF)
        self.assertEqual(err.exception.code, 400)


if __name__ == '__main__':
    unittest.main()
