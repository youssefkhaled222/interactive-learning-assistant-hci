"""Observe object detection metadata on the real local WebSocket bridge.

This is a developer diagnostic, not a game frontend or hardware proof.
Run from phase2/: python backend/monitor_objects.py
"""
import asyncio
import json
from websockets.asyncio.client import connect


async def main():
    print('Listening on ws://127.0.0.1:8766 — Ctrl+C to stop.', flush=True)
    previous = None
    async with connect('ws://127.0.0.1:8766') as ws:
        async for raw in ws:
            message = json.loads(raw)
            if message.get('type') != 'state':
                continue
            payload = message['payload']
            items = payload.get('detected_objects', [])
            active = payload.get('object_detection_active', False)
            current = (active, tuple((x['object'], x['target_id']) for x in items))
            if current != previous:
                summary = ', '.join(f"{x['object']} ({x['target_id']}, {x['confidence']:.2f})" for x in items)
                print(f"active={active} | detected={summary or 'none'}", flush=True)
                previous = current


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('Stopped')
