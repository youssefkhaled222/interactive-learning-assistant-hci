"""SIMULATOR ONLY: walks the context engine through each context so the
question pack change can be watched in the React preview. Every event is sent
with source="simulator"; this checks the software pipeline, not hardware.

Run from the phase2 folder while backend/server.py is running:
    .\\.venv\\Scripts\\python.exe backend\\context_demo.py
"""
import argparse
import time

from content_packs import PACKS
from send_event import send

STEPS = [
    ("Start: no device, guest pack", {"type": "device.lost"}, PACKS["guest"][0]["prompt"]),
    ("Fresh session", {"type": "game.restart"}, PACKS["guest"][0]["prompt"]),
    ("Beginner device detected", {"type": "device.discovered", "device_id": "demo-device-beginner"},
     PACKS["beginner"][0]["prompt"]),
    ("Simulation: camera ready", {"type": "camera.status", "ready": True}, PACKS["beginner"][0]["prompt"]),
    ("Simulation: pose visible", {"type": "pose.tracking", "visible": True}, PACKS["beginner"][0]["prompt"]),
    ("Beginner answers question 1", {"type": "game.select", "object": "apple"},
     "Auto mode: Q2; Next mode: Q1 until game.next"),
    ("Explicit Next object (safe in auto mode)", {"type": "game.next"}, PACKS["beginner"][1]["prompt"]),
    ("Same beginner device seen again (no reset)", {"type": "device.discovered", "device_id": "demo-device-beginner"},
     PACKS["beginner"][1]["prompt"]),
    ("Tracking lost (input paused)", {"type": "pose.tracking", "visible": False}, PACKS["beginner"][1]["prompt"]),
    ("Selection while paused is ignored", {"type": "game.select", "object": "cup"}, PACKS["beginner"][1]["prompt"]),
    ("Tracking back", {"type": "pose.tracking", "visible": True}, PACKS["beginner"][1]["prompt"]),
    ("Low light warning", {"type": "lighting.changed", "level": "low"}, PACKS["beginner"][1]["prompt"]),
    ("Lighting good again", {"type": "lighting.changed", "level": "good"}, PACKS["beginner"][1]["prompt"]),
    ("Advanced device detected (new learner, reset)", {"type": "device.discovered", "device_id": "demo-device-advanced"},
     PACKS["advanced"][0]["prompt"]),
    ("Advanced device lost (guest fallback)", {"type": "device.lost", "device_id": "demo-device-advanced"},
     PACKS["guest"][0]["prompt"]),
]

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--delay", type=float, default=3.0, help="seconds between steps")
    args = parser.parse_args()
    for i, (label, event, expected_prompt) in enumerate(STEPS, start=1):
        event = dict(event, source="simulator")
        reply = send(event)
        print(f"{i:2}. {label}")
        print(f"    sent: {event}")
        print(f"    broker: {reply}")
        print(f"    expected question on screen: {expected_prompt}")
        time.sleep(args.delay)
