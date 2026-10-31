"""Local TCP JSONL ingest + browser WebSocket bridge, from separate processes.
Install: pip install websockets>=14,<17
Run: python backend/server.py (from phase2 directory)
"""
import asyncio
import json
import logging
from engine import Engine

try:
    from websockets.asyncio.server import serve
except ImportError as exc:
    raise SystemExit("Install requirements: python -m pip install -r requirements-core.txt") from exc

HOST = "127.0.0.1"  # Never bind this classroom demo to public interfaces
engine = Engine()
subscribers = set()
lock = asyncio.Lock()

async def broadcast(state):
    message = json.dumps({"type": "state", "payload": state})
    dead = []
    for ws in list(subscribers):
        try:
            await ws.send(message)
        except Exception:
            dead.append(ws)
    for ws in dead:
        subscribers.discard(ws)

async def tcp_client(reader, writer):
    try:
        while (raw := await reader.readline()):
            if len(raw) > 8192:
                writer.write(b'{"ok":false,"error":"Message too large"}\n')
                await writer.drain()
                break
            try:
                event = json.loads(raw.decode('utf-8'))
                async with lock:
                    state = engine.handle(event)
                writer.write(b'{"ok":true}\n')
                await writer.drain()
                await broadcast(state)
            except (ValueError, UnicodeDecodeError) as exc:
                writer.write((json.dumps({"ok": False, "error": str(exc)}) + "\n").encode())
                await writer.drain()
    finally:
        writer.close()
        await writer.wait_closed()

async def ws_client(ws):
    subscribers.add(ws)
    try:
        await ws.send(json.dumps({"type": "state", "payload": engine.view()}))
        # Read-only frontend. Input/selection is sent via a sensor process on TCP.
        async for _ in ws:
            await ws.send(json.dumps({"type": "error", "message": "Read-only browser connection"}))
    finally:
        subscribers.discard(ws)

async def main():
    logging.basicConfig(level=logging.INFO)
    tcp = await asyncio.start_server(tcp_client, HOST, 8765, limit=16384)
    async with tcp, serve(ws_client, HOST, 8766):
        print("TCP event server: 127.0.0.1:8765")
        print("Browser WebSocket: ws://127.0.0.1:8766")
        await asyncio.Future()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Stopped")
