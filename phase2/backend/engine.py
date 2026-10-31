"""Pure, testable Phase II learning engine. No hardware or network dependencies."""
from copy import deepcopy

PACKS = {
    "guest": [
        {"prompt": "Find the apple", "answer": "apple", "choices": ["apple", "book", "cup"]},
        {"prompt": "Find the book", "answer": "book", "choices": ["cup", "book", "apple"]},
    ],
    "beginner": [
        {"prompt": "Find the red apple", "answer": "apple", "choices": ["apple", "cup", "book"]},
        {"prompt": "Find the cup", "answer": "cup", "choices": ["book", "cup", "apple"]},
        {"prompt": "Find the book", "answer": "book", "choices": ["apple", "book", "cup"]},
    ],
    "advanced": [
        {"prompt": "Choose the object used for reading", "answer": "book", "choices": ["book", "cup", "apple"]},
        {"prompt": "Choose the object used for drinking", "answer": "cup", "choices": ["apple", "book", "cup"]},
        {"prompt": "Choose the fruit", "answer": "apple", "choices": ["book", "apple", "cup"]},
    ],
}

# These are deliberately pseudonymous ENROLLED demo-device IDs, not identities
# inferred from a Bluetooth radio address or nearby stranger's device.
REGISTERED = {
    "demo-device-beginner": {"user_id": "learner_01", "level": "beginner"},
    "demo-device-advanced": {"user_id": "learner_02", "level": "advanced"},
}

class Engine:
    def __init__(self):
        self.state = {
            "user_id": "guest", "level": "guest", "connected_device": None,
            "mode": "gesture", "tracking": False, "camera_ready": False,
            "lighting": "unknown", "status": "Ready for setup", "last_gesture": None,
            "question_index": 0, "completed": False, "first_try_correct": 0,
            "wrong_attempts": 0, "attempts_this_question": 0,
            "event_source": "none", "demo_mode": False,
        }

    def view(self):
        s = deepcopy(self.state)
        pack = PACKS[s["level"]]
        s["total_questions"] = len(pack)
        s["question"] = None if s["completed"] else deepcopy(pack[s["question_index"]])
        return s

    def reset_session(self):
        self.state.update(question_index=0, completed=False, first_try_correct=0,
                          wrong_attempts=0, attempts_this_question=0)

    def handle(self, event):
        if not isinstance(event, dict) or not isinstance(event.get("type"), str):
            raise ValueError("Expected JSON object with string 'type'")
        t = event["type"]
        # Provenance must come from the adapter; developer demo events are marked.
        self.state["event_source"] = str(event.get("source", "unspecified"))[:60]
        self.state["demo_mode"] = (self.state["event_source"] == "simulator")
        if t == "device.discovered":
            device = str(event.get("device_id", ""))
            self.state["connected_device"] = device or None
            profile = REGISTERED.get(device)
            self.state["user_id"] = profile["user_id"] if profile else "guest"
            self.state["level"] = profile["level"] if profile else "guest"
            self.state["status"] = ("Registered profile loaded" if profile else
                                    "Unknown device: guest content loaded")
            self.reset_session()
        elif t == "device.lost":
            self.state.update(user_id="guest", level="guest", connected_device=None,
                              status="Device lost; guest content loaded")
            self.reset_session()
        elif t == "pose.tracking":
            self.state["tracking"] = bool(event.get("visible", False))
            self.state["status"] = ("Body tracked" if self.state["tracking"] else
                                    "Tracking lost — please return to camera")
        elif t == "camera.status":
            self.state["camera_ready"] = bool(event.get("ready", False))
            self.state["status"] = "Camera ready" if self.state["camera_ready"] else "Check camera"
        elif t == "lighting.changed":
            if event.get("level") not in ("good", "low", "unknown"):
                raise ValueError("Invalid lighting level")
            self.state["lighting"] = event["level"]
            self.state["status"] = ("Increase lighting to improve tracking" if event["level"] == "low" else
                                    "Lighting status updated")
        elif t == "mode.selected":
            if event.get("mode") not in ("gesture", "gaze"):
                raise ValueError("Unsupported mode")
            self.state["mode"] = event["mode"]
            self.state["status"] = f"{event['mode'].capitalize()} mode selected"
        elif t == "gesture.recognized":
            self.state["last_gesture"] = str(event.get("name", ""))[:60]
            self.state["status"] = f"Gesture recognized: {self.state['last_gesture']}"
        elif t == "game.select":
            obj = str(event.get("object", "")).lower().strip()
            if self.state["completed"]:
                self.state["status"] = "Session complete — replay to restart"
            elif not obj:
                raise ValueError("Selection needs an 'object'")
            elif obj not in PACKS[self.state["level"]][self.state["question_index"]]["choices"]:
                self.state["status"] = "Object not in current choices"
            elif obj == PACKS[self.state["level"]][self.state["question_index"]]["answer"]:
                if self.state["attempts_this_question"] == 0:
                    self.state["first_try_correct"] += 1
                self.state["question_index"] += 1
                self.state["attempts_this_question"] = 0
                if self.state["question_index"] == len(PACKS[self.state["level"]]):
                    self.state["completed"] = True
                    self.state["status"] = "Great job! Session complete"
                else:
                    self.state["status"] = "Correct! Next question"
            else:
                self.state["wrong_attempts"] += 1
                self.state["attempts_this_question"] += 1
                self.state["status"] = "Good try! Try the same question again"
        elif t == "game.restart":
            self.reset_session()
            self.state["status"] = "New session"
        else:
            raise ValueError(f"Unknown event type: {t}")
        return self.view()
