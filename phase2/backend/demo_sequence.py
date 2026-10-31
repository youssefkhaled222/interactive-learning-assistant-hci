"""DEMO ONLY; generates synthetic events to test the plumbing, not graded hardware proof."""
import time
from send_event import send

sequence = [
 {"type": "device.discovered", "device_id": "demo-device-beginner", "source": "simulator"},
 {"type": "camera.status", "ready": True, "source": "simulator"},
 {"type": "pose.tracking", "visible": True, "source": "simulator"},
 {"type": "gesture.recognized", "name": "swipe_right", "source": "simulator"},
 {"type": "game.select", "object": "book", "source": "simulator"},
 {"type": "game.select", "object": "apple", "source": "simulator"},
 {"type": "device.discovered", "device_id": "demo-device-advanced", "source": "simulator"},
 {"type": "lighting.changed", "level": "low", "source": "simulator"},
]
for event in sequence:
    print(event, send(event))
    time.sleep(1.2)
