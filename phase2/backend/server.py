"""Local TCP JSONL sensor ingest + browser WebSocket bridge.

Run from phase2/: python backend/server.py
Only the local React UI may send the allow-listed commands in ui_commands.py.
Hardware/device events continue to arrive through the existing TCP contract.
"""
import asyncio
import json
import logging
import os
import time  # HCI_PINCH_DIAGNOSTICS_V41

from engine import Engine
from ui_commands import InvalidUICommand, to_engine_event
from sensor_events import validate_sensor_event
from object_tracking import ObjectTracker
from hand_selection import HandSelectionGate  # HCI_REAL_PINCH_V4
from target_matching import resolve_target

try:
    from websockets.asyncio.server import serve
except ImportError as exc:
    raise SystemExit("Install: python -m pip install -r requirements-core.txt") from exc

HOST = "127.0.0.1"  # Deliberately loopback-only
TCP_PORT = 8765
WS_PORT = 8766
ALLOWED_WS_ORIGINS = (None, "http://127.0.0.1:5173", "http://localhost:5173")
WS_SEND_TIMEOUT_SECONDS = 1.0  # Avoid stalling sensor events behind a hung browser.
# The live server never accepts selections before real sensor readiness.
# Next-object UI is opt-in until Ahmed implements the corresponding screen.
engine = Engine(require_next=os.environ.get("HCI_REQUIRE_NEXT") == "1",
                require_sensor_ready=True)
subscribers = set()
lock = asyncio.Lock()
object_tracker = ObjectTracker()
hand_selection_gate = HandSelectionGate()
last_pinch_diagnostic_at = 0.0


async def broadcast(state):
    """Fan out state without letting one stalled browser block everyone else.

    Called under the state lock. Each browser gets the *same* snapshot;
    slow/failed subscribers are removed and may reconnect for fresh state.
    """
    message = json.dumps({"type": "state", "payload": state})

    async def deliver(ws):
        try:
            await asyncio.wait_for(ws.send(message), timeout=WS_SEND_TIMEOUT_SECONDS)
        except Exception as exc:
            subscribers.discard(ws)
            logging.warning("Dropped nonresponsive WebSocket subscriber: %s", type(exc).__name__)

    await asyncio.gather(*(deliver(ws) for ws in tuple(subscribers)))


def current_state():
    # Detector metadata is separate from Mohamed's mutable learning engine.
    return {**engine.view(), **object_tracker.state(),
            'hand_selection': hand_selection_gate.view()}  # HCI_PHASE2_READY_V5


async def expire_object_detections(now=None):
    """Broadcast a cleared detection state after a crashed/stalled detector."""
    async with lock:
        if object_tracker.expire(now=now):
            await broadcast(current_state())
            return True
    return False


async def detector_watchdog():
    while True:
        await asyncio.sleep(0.5)
        await expire_object_detections()
        async with lock:
            if hand_selection_gate.expired():
                engine.handle({'type':'hand.tracking','visible':False,
                               'source':'mediapipe-hand'})
                engine.handle({'type':'camera.status','ready':False,
                               'source':'mediapipe-hand'})
                await broadcast(current_state())


async def apply_event(event):
    """Serialize updates and broadcasts so consumers never receive stale state.

    Camera shutdown invalidates the last pose detection. Do this atomically
    before the public camera event, so React sees one consistent snapshot.
    The pose tracker currently sends camera.status=false when it exits but
    doesn't necessarily emit a final pose.tracking=false.
    """
    async with lock:
        if event['type'] == 'hand.pointer':
            # Hardware sensor ingress only: browser WS allow-list cannot send
            # this event. A loopback TCP source label is not authentication.
            if event['source'] != 'mediapipe-hand':
                raise ValueError('hand.pointer requires the local MediaPipe hand adapter')
            # A fresh local adapter observation is also a camera-liveness
            # signal. This recovers after the watchdog clears a stalled source.
            if not engine.state['camera_ready']:
                engine.handle({'type':'camera.status','ready':True,
                               'source':'mediapipe-hand'})
            visible = event['x'] is not None
            engine.handle({'type':'hand.tracking','visible':visible,
                           'source':'mediapipe-hand'})
            state = engine.view()
            # Read the previous arming state before the unchanged selection gate.
            # Diagnostic only: does not modify the sensor event or candidate.
            was_armed = hand_selection_gate.armed
            chosen = hand_selection_gate.observe(
                x=event['x'], y=event['y'], pinching=event['pinching'],
                tracker=object_tracker, ready=not state['input_blocked'],
                mode=state['mode'])
            # Log *rejected* pinches; v4 logged accepted selections only.
            # Throttle during a held pinch, and never log images or face data.
            global last_pinch_diagnostic_at
            now_diag = time.monotonic()
            if event['pinching'] and now_diag - last_pinch_diagnostic_at >= 0.6:
                last_pinch_diagnostic_at = now_diag
                target = resolve_target(
                    object_tracker, x=event['x'], y=event['y'],
                    coordinate_space='object_view',
                    target_id=hand_selection_gate.candidate_id, now=now_diag)
                held = (round(now_diag - hand_selection_gate.pinch_started, 2)
                        if hand_selection_gate.pinch_started is not None else None)
                logging.info(
                    'PINCH_DIAG mode=%s ready=%s block=%s '
                    'armed_before=%s armed_after=%s held_s=%s '
                    'candidate=%s target_reason=%s target=%s '
                    'detected=%s committed=%s',
                    state['mode'], not state['input_blocked'], state['block_reason'],
                    was_armed, hand_selection_gate.armed, held,
                    hand_selection_gate.candidate_id, target['reason'],
                    target.get('object'),
                    [(item['object'], round(item['confidence'], 2))
                     for item in object_tracker.objects], chosen)
            if chosen is not None:
                engine.handle({'type':'game.select','object':chosen,
                               'source':'mediapipe-hand'})
                logging.info('Real pinch proposed object=%s; engine status=%s',
                             chosen, engine.view()['status'])
            state = current_state()
            await broadcast(state)
            return state
        if event["type"] == "objects.detected":
            object_tracker.update(event)
            state = current_state()
            await broadcast(state)
            return state
        if event["type"] == "camera.status" and event["ready"] is False:
            engine.handle({
                "type": "pose.tracking", "visible": False,
                "source": event["source"],
            })
            if event['source'] == 'mediapipe-hand':
                hand_selection_gate.reset(forget_heartbeat=True)
                engine.handle({'type':'hand.tracking','visible':False,
                               'source':'mediapipe-hand'})
        engine.handle(event)
        state = current_state()
        await broadcast(state)
        return state


def _reject_nonfinite(value):
    raise ValueError("Non-finite JSON number is not allowed")


async def tcp_client(reader, writer):
    try:
        while True:
            try:
                raw = await reader.readline()
            except ValueError:
                writer.write(b'{"ok":false,"error":"Message too large"}\n')
                await writer.drain()
                break
            if not raw:
                break
            if len(raw) > 8192:
                writer.write(b'{"ok":false,"error":"Message too large"}\n')
                await writer.drain()
                break
            try:
                event = json.loads(raw.decode("utf-8"), parse_constant=_reject_nonfinite)
                await apply_event(validate_sensor_event(event))
                writer.write(b'{"ok":true}\n')
                await writer.drain()
            except (ValueError, UnicodeDecodeError) as exc:
                writer.write((json.dumps({"ok": False, "error": str(exc)[:200]}) + "\n").encode())
                await writer.drain()
    except (ConnectionResetError, BrokenPipeError):
        # A sensor process can terminate while sending or receiving its ack.
        # Do not let a dropped producer affect other connections.
        pass
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except (ConnectionResetError, BrokenPipeError):
            pass


async def ws_client(ws):
    try:
        # Subscribe and send the initial snapshot atomically with broadcasts.
        async with lock:
            subscribers.add(ws)
            await ws.send(json.dumps({"type": "state", "payload": current_state()}))

        async for raw in ws:
            try:
                if not isinstance(raw, str):
                    raise InvalidUICommand("Expected a JSON text command")
                command = json.loads(raw)
                event = to_engine_event(command)
                await apply_event(event)
            except (ValueError, json.JSONDecodeError) as exc:
                await ws.send(json.dumps({"type": "error", "message": str(exc)[:200]}))
    finally:
        subscribers.discard(ws)


async def main():
    logging.basicConfig(level=logging.INFO)
    tcp = await asyncio.start_server(tcp_client, HOST, TCP_PORT, limit=16384)
    async with tcp, serve(ws_client, HOST, WS_PORT,
                          origins=ALLOWED_WS_ORIGINS, max_size=8192):
        print(f"TCP event server: {HOST}:{TCP_PORT}")
        print(f"Browser WebSocket: ws://{HOST}:{WS_PORT}")
        watchdog = asyncio.create_task(detector_watchdog())
        try:
            await asyncio.Future()
        finally:
            watchdog.cancel()
            try:
                await watchdog
            except asyncio.CancelledError:
                pass


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Stopped")
