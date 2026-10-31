"""Developer-only smoke test of the actual WebSocket command path.

Run while the server and preview are open: python backend/demo_ui_commands.py
This tests UI control plumbing, NOT real gaze or gesture sensing.
"""
import asyncio
import json

from websockets.asyncio.client import connect


async def main():
    async with connect("ws://127.0.0.1:8766") as ws:
        initial = json.loads(await ws.recv())
        print("Initial mode:", initial["payload"]["mode"])
        for action, payload in (
            ("mode.selected", {"mode": "gaze"}),
            ("game.restart", {}),
        ):
            await ws.send(json.dumps({"type": "command", "action": action, "payload": payload}))
            reply = json.loads(await ws.recv())
            if reply["type"] == "error":
                raise RuntimeError(reply["message"])
            print(f"{action}: mode={reply['payload']['mode']}, "
                  f"question_index={reply['payload']['question_index']}, "
                  f"source={reply['payload']['event_source']}")


if __name__ == "__main__":
    asyncio.run(main())
