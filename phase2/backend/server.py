"""Local TCP JSONL sensor ingest + browser WebSocket bridge.

Run from phase2/: python backend/server.py
Only the local React UI may send the allow-listed commands in ui_commands.py.
Hardware/device events continue to arrive through the existing TCP contract.
"""
import asyncio
import json
import logging

from engine import Engine
from ui_commands import InvalidUICommand, to_engine_event
from sensor_events import validate_sensor_event

try:
    from websockets.asyncio.server import serve
except ImportError as exc:
    raise SystemExit("Install: python -m pip install -r requirements-core.txt") from exc

HOST = "127.0.0.1"  # Deliberately loopback-only
TCP_PORT = 8765
WS_PORT = 8766
ALLOWED_WS_ORIGINS = (None, "http://127.0.0.1:5173", "http://localhost:5173")
WS_SEND_TIMEOUT_SECONDS = 1.0  # Avoid stalling sensor events behind a hung browser.
engine = Engine()
subscribers = set()
lock = asyncio.Lock()


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


async def apply_event(event):
    """Serialize updates and broadcasts so consumers never receive stale state.

    Camera shutdown invalidates the last pose detection. Do this atomically
    before the public camera event, so React sees one consistent snapshot.
    The pose tracker currently sends camera.status=false when it exits but
    doesn't necessarily emit a final pose.tracking=false.
    """
    async with lock:
        if event["type"] == "camera.status" and event["ready"] is False:
            engine.handle({
                "type": "pose.tracking", "visible": False,
                "source": event["source"],
            })
        state = engine.handle(event)
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
            await ws.send(json.dumps({"type": "state", "payload": engine.view()}))

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
        await asyncio.Future()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Stopped")
