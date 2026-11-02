"""Camera preview tests use dummy JPEG bytes, never a webcam or an AI model."""
import json
import os
import sys
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))
from camera_preview import FrameBuffer, approved_origin, start_preview


class TestOriginRules(unittest.TestCase):
    def test_allowed_local_development_referrers(self):
        for url in ('http://127.0.0.1:5173/', 'http://localhost:5173/screen',
                    'http://127.0.0.1:5174/'):
            self.assertTrue(approved_origin(url), url)

    def test_remote_or_malformed_referrers_are_rejected(self):
        for url in ('', None, 'https://evil.example', 'http://localhost.evil.org:5173',
                    'http://127.0.0.1:5173.evil.com', 'http://127.0.0.1:8767',
                    'http://127.0.0.1:5173@evil.org', 'file:///demo.html'):
            self.assertFalse(approved_origin(url), url)

    def test_stale_frame_not_retained_after_close(self):
        buffer = FrameBuffer()
        buffer.publish(b'jpeg')
        first, frame, active = buffer.next_frame(0, timeout=0.01)
        self.assertEqual((first, frame, active), (1, b'jpeg', True))
        buffer.close()
        _, frame, active = buffer.next_frame(first, timeout=0.01)
        self.assertIsNone(frame)
        self.assertFalse(active)
        buffer.publish(b'new')
        self.assertIsNone(buffer.frame)


class TestHTTPPreview(unittest.TestCase):
    def setUp(self):
        self.server = start_preview(port=0)
        self.base = 'http://127.0.0.1:' + str(self.server.server_port)

    def tearDown(self):
        self.server.close()

    def request(self, path, headers=None):
        return Request(self.base + path, headers=headers or {})

    def test_health_is_local_and_reports_real_frames_only(self):
        with urlopen(self.request('/health', {'Origin': 'http://127.0.0.1:5173'}), timeout=3) as response:
            self.assertEqual(response.headers.get('Access-Control-Allow-Origin'), 'http://127.0.0.1:5173')
            self.assertEqual(json.load(response), {'active': True, 'has_frame': False})
        self.server.buffer.publish(b'fake-jpeg-test')
        with urlopen(self.request('/health'), timeout=3) as response:
            self.assertEqual(json.load(response), {'active': True, 'has_frame': True})

    def test_remote_origin_cannot_read_health(self):
        with self.assertRaises(HTTPError) as cm:
            urlopen(self.request('/health', {'Origin': 'https://external.site'}), timeout=3)
        self.assertEqual(cm.exception.code, 403)

    def test_video_requires_frontend_referrer(self):
        self.server.buffer.publish(b'not-personal-video-data')
        for headers in ({}, {'Referer': 'https://external.site/'}):
            with self.assertRaises(HTTPError) as cm:
                urlopen(self.request('/video', headers), timeout=3)
            self.assertEqual(cm.exception.code, 403)

    def test_browser_receives_multipart_stream(self):
        self.server.buffer.publish(b'fake-jpeg-test')
        with urlopen(self.request('/video', {'Referer': 'http://127.0.0.1:5173/'}), timeout=3) as response:
            self.assertIn('multipart/x-mixed-replace', response.headers['Content-Type'])
            body = response.read(len(b'--frame\r\nContent-Type: image/jpeg\r\nContent-Length: 14\r\n\r\nfake-jpeg-test\r\n'))
            self.assertIn(b'fake-jpeg-test', body)


if __name__ == '__main__':
    unittest.main()
