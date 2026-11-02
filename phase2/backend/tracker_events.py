"""Nonblocking camera-side sender using the existing send(event) TCP contract."""
import json
import threading
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path


class EventPublisher:
    def __init__(self, sender, log_path=None, retry_seconds=2, heartbeat_seconds=10):
        self.sender = sender
        self.log_path = Path(log_path) if log_path else None
        self.retry_seconds = retry_seconds
        self.heartbeat_seconds = heartbeat_seconds
        self.desired = {}
        self.acked = {}
        self.gestures = deque(maxlen=8)
        self.cv = threading.Condition()
        self.stopping = False
        self.retry_at = 0
        self.heartbeat_at = time.monotonic() + heartbeat_seconds
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def status(self, kind, value):
        field = {'camera.status': 'ready', 'pose.tracking': 'visible'}[kind]
        event = {'type': kind, field: bool(value), 'source': 'mediapipe'}
        with self.cv:
            if self.desired.get(kind) != event:
                self.desired[kind] = event
                self.cv.notify()

    def gesture(self, prediction):
        if not prediction['accepted']:
            return
        with self.cv:
            self.gestures.append((time.monotonic(), dict(type='gesture.recognized',
                name=prediction['predicted'], score=prediction['score'], source='dollarpy')))
            self.cv.notify()

    def _log(self, event, ack=None, error=None):
        row = dict(time=datetime.now(timezone.utc).isoformat(), event=event, ack=ack, error=error)
        print(json.dumps(row), flush=True)
        if self.log_path:
            try:
                self.log_path.parent.mkdir(parents=True, exist_ok=True)
                with self.log_path.open('a', encoding='utf-8') as out:
                    out.write(json.dumps(row) + '\n')
            except OSError as exc:
                print(f'Cannot write event log: {exc}', flush=True)
                self.log_path = None

    def _run(self):
        while True:
            with self.cv:
                now = time.monotonic()
                if self.stopping and (now < self.retry_at or self.desired == self.acked):
                    return
                if now >= self.heartbeat_at:
                    self.acked.clear()
                    self.heartbeat_at = now + self.heartbeat_seconds
                event = None
                if now >= self.retry_at:
                    event = next((dict(e) for k, e in self.desired.items() if self.acked.get(k) != e), None)
                    while event is None and self.gestures and not self.stopping:
                        recorded, candidate = self.gestures.popleft()
                        if now - recorded <= 2:
                            event = candidate
                if event is None:
                    self.cv.wait(.1)
                    continue
            try:
                ack = self.sender(event)
                if not isinstance(ack, dict) or ack.get('ok') is not True:
                    raise ValueError(f'Broker rejected event: {ack}')
                self._log(event, ack=ack)
                with self.cv:
                    if event['type'] in self.desired:
                        self.acked[event['type']] = event
            except (OSError, ValueError, TypeError) as exc:
                self._log(event, error=str(exc))
                with self.cv:
                    self.acked.clear()
                    self.gestures.clear()  # Never replay stale movements after an outage.
                    self.retry_at = time.monotonic() + self.retry_seconds

    def close(self):
        with self.cv:
            self.stopping = True
            self.gestures.clear()
            self.cv.notify()
        self.thread.join(timeout=9)
        if self.thread.is_alive():
            print('Sender shutdown timed out; final broker state is unconfirmed', flush=True)
