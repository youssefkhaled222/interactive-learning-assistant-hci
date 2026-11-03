"""Pure, testable Phase II context-aware learning engine. No hardware or network dependencies."""
import math
import time
from copy import deepcopy

from content_packs import PACK_INFO, PACKS, SUPPORTED_OBJECTS, validate_packs

validate_packs()

# These are deliberately pseudonymous ENROLLED demo-device IDs, not identities
# inferred from a Bluetooth radio address or nearby stranger's device.
REGISTERED = {
    "demo-device-beginner": {"user_id": "learner_01", "level": "beginner"},
    "demo-device-advanced": {"user_id": "learner_02", "level": "advanced"},
}

EVENT_TYPES = (
    "device.discovered", "device.lost", "pose.tracking", "hand.tracking", "gaze.tracking", "camera.status",
    "lighting.changed", "mode.selected", "gesture.recognized",
    "game.select", "game.next", "game.restart",
)
LIGHTING_LEVELS = ("good", "low", "unknown")
MODES = ("gesture", "gaze")
DUPLICATE_SELECT_WINDOW_S = 1.5

MESSAGES = {
    "camera_not_ready": "Camera not ready - ask an adult to check the camera connection or permission.",
    "tracking_lost_gesture": "Tracking lost - show your hand to the camera. Your progress is saved.",
    "tracking_lost_gaze": "Tracking lost - look at the screen so the camera can see your eyes. Your progress is saved.",
    "low_light": "Low light - turn on a lamp or face a window so the camera can see better.",
    "gaze_not_ready": "Calibrate eye tracking with your face camera before playing.",
}


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


class Engine:
    def __init__(self, require_next=False, clock=time.monotonic, require_sensor_ready=False):
        # require_next=False keeps the starter's auto-advance contract.
        # require_next=True follows the Phase I "Next object" step (needs game.next).
        self.require_next = require_next
        # False is for legacy unit tests/simulator; the real socket server enables this.
        self.require_sensor_ready = require_sensor_ready
        self._clock = clock
        self._tracking_lost = False
        self._camera_problem = False
        self._last_device_ts = None
        self._last_select = None
        self.state = {
            "user_id": "guest", "level": "guest", "connected_device": None,
            "mode": "gesture", "tracking": False, "hand_tracking": False, "gaze_tracking":False, "gaze_calibrated":False, "camera_ready": False,
            "lighting": "unknown", "status": "Ready for setup", "last_gesture": None,
            "question_index": 0, "completed": False, "first_try_correct": 0,
            "wrong_attempts": 0, "attempts_this_question": 0,
            "questions_completed": 0, "awaiting_next": False,
            "event_source": "none", "demo_mode": False,
        }

    # ----- read model -------------------------------------------------
    def block_reason(self):
        # Genuine iris-based gaze is an independent camera/sensor pipeline.
        # The object-facing YOLO camera and hand tracker do not authorize gaze.
        if self.require_sensor_ready and self.state['mode'] == 'gaze':
            if not self.state['gaze_calibrated']:
                return 'gaze_not_ready'
            if not self.state['gaze_tracking']:
                return 'tracking_lost'
            return None
        if self._camera_problem or (self.require_sensor_ready and not self.state["camera_ready"]):
            return "camera_not_ready"
        # Pose does not implement calibrated gaze. Never certify gaze as ready.
        if self.require_sensor_ready and self.state["mode"] == "gaze":
            return "gaze_not_ready"
        # Gesture mode accepts either the original true Pose tracker OR
        # the genuine same-camera Hand Landmarker. Do not fake pose.tracking.
        real_tracking = (self.state["tracking"] or
                         (self.state["mode"] == 'gesture' and self.state["hand_tracking"]))
        if (self._tracking_lost and not real_tracking) or (self.require_sensor_ready and not real_tracking):
            return "tracking_lost"
        return None

    def _block_message(self, reason):
        if reason == "tracking_lost":
            return MESSAGES["tracking_lost_" + self.state["mode"]]
        return MESSAGES[reason]

    def notices(self):
        out = []
        reason = self.block_reason()
        if reason:
            out.append({"code": reason, "message": self._block_message(reason), "blocking": True})
        if self.state["lighting"] == "low":
            out.append({"code": "low_light", "message": MESSAGES["low_light"], "blocking": False})
        return out

    def view(self):
        s = deepcopy(self.state)
        # UI's existing generic tracking indicator includes real hand tracking
        # in gesture mode; preserve separate pose/hand facts for diagnostics.
        s['pose_tracking'] = s['tracking']
        if s['mode'] == 'gesture':
            s['tracking'] = s['tracking'] or s['hand_tracking']
        elif s['mode'] == 'gaze':
            s['tracking'] = s['gaze_tracking']
        level = s["level"]
        pack = PACKS[level]
        s["total_questions"] = len(pack)
        if s["completed"]:
            s["question"] = None
        else:
            s["question"] = deepcopy(pack[s["question_index"]])
            s["question"]["number"] = s["question_index"] + 1
        s["show_hint"] = (not s["completed"]) and s["attempts_this_question"] > 0
        s["pack_id"] = level
        s.update(PACK_INFO[level])
        reason = self.block_reason()
        s["input_blocked"] = reason is not None
        s["block_reason"] = reason
        if reason:
            s["status"] = self._block_message(reason)
        s["notices"] = self.notices()
        s["require_next"] = self.require_next
        return s

    # ----- session helpers ------------------------------------------------
    def reset_session(self):
        self.state.update(question_index=0, completed=False, first_try_correct=0,
                          wrong_attempts=0, attempts_this_question=0,
                          questions_completed=0, awaiting_next=False)
        self._last_select = None

    def _session_in_progress(self):
        s = self.state
        return (not s["completed"]) and (
            s["questions_completed"] > 0 or s["attempts_this_question"] > 0 or s["awaiting_next"])

    def _advance(self):
        # A selection on the previous question must never throttle the next one.
        self._last_select = None
        self.state["question_index"] += 1
        self.state["awaiting_next"] = False
        if self.state["question_index"] >= len(PACKS[self.state["level"]]):
            self.state["question_index"] = len(PACKS[self.state["level"]])
            self.state["completed"] = True
            self.state["status"] = "Great job! Session complete"
        else:
            self.state["status"] = "Correct! Next question"

    # ----- validation -----------------------------------------------------
    @staticmethod
    def validate(event):
        """Return the event type or raise ValueError. Never mutates engine state."""
        if not isinstance(event, dict) or not isinstance(event.get("type"), str):
            raise ValueError("Expected JSON object with string 'type'")
        t = event["type"]
        if t not in EVENT_TYPES:
            raise ValueError(f"Unknown event type: {t}")
        if "source" in event and not isinstance(event["source"], str):
            raise ValueError("'source' must be a string")
        if "ts" in event:
            if t not in ("device.discovered", "device.lost") or not _is_number(event["ts"]) or not math.isfinite(event["ts"]) or event["ts"] < 0:
                raise ValueError("'ts' must be a finite nonnegative device timestamp")
        if t == "device.discovered":
            device = event.get("device_id")
            if not isinstance(device, str) or not device.strip() or len(device) > 128:
                raise ValueError("device.discovered needs a non-empty 'device_id' string")
        elif t == "device.lost":
            device = event.get("device_id")
            if device is not None and (not isinstance(device, str) or not device.strip()):
                raise ValueError("'device_id' in device.lost must be a non-empty string")
        elif t in ("pose.tracking", "hand.tracking", "gaze.tracking"):
            if not isinstance(event.get("visible"), bool):
                raise ValueError(f"{t} needs boolean 'visible'")
            if t == 'gaze.tracking' and type(event.get('calibrated')) is not bool:
                raise ValueError('gaze.tracking needs calibrated boolean')
        elif t == "camera.status":
            if not isinstance(event.get("ready"), bool):
                raise ValueError("camera.status needs boolean 'ready'")
        elif t == "lighting.changed":
            if event.get("level") not in LIGHTING_LEVELS:
                raise ValueError("Invalid lighting level")
        elif t == "mode.selected":
            if event.get("mode") not in MODES:
                raise ValueError("Unsupported mode")
        elif t == "gesture.recognized":
            name = event.get("name")
            if not isinstance(name, str) or not name.strip():
                raise ValueError("gesture.recognized needs a non-empty 'name'")
            if "score" in event and not _is_number(event["score"]):
                raise ValueError("'score' must be a number")
        elif t == "game.select":
            obj = event.get("object")
            if not isinstance(obj, str) or not obj.strip():
                raise ValueError("Selection needs an 'object'")
        return t

    # ----- event handling -----------------------------------------------
    def handle(self, event):
        t = self.validate(event)
        source = event.get("source", "unspecified")
        # Provenance must come from the adapter; developer demo events are marked.
        self.state["event_source"] = source[:60]
        self.state["demo_mode"] = (source == "simulator")
        getattr(self, "_on_" + t.replace(".", "_"))(event)
        return self.view()

    def _is_stale_device_event(self, event):
        """Do not advance the clock until the event actually applies."""
        ts = event.get("ts")
        return ts is not None and self._last_device_ts is not None and ts < self._last_device_ts

    def _record_device_ts(self, event):
        if "ts" in event:
            self._last_device_ts = event["ts"]

    def _on_device_discovered(self, event):
        if self._is_stale_device_event(event):
            return
        device = event["device_id"].strip()
        self._record_device_ts(event)
        if device == self.state["connected_device"]:
            return  # repeated BLE advertisement: keep the running session untouched
        profile = REGISTERED.get(device)
        user_id = profile["user_id"] if profile else "guest"
        level = profile["level"] if profile else "guest"
        learner_changed = (user_id, level) != (self.state["user_id"], self.state["level"])
        self.state.update(connected_device=device, user_id=user_id, level=level)
        if learner_changed:
            self.reset_session()
        if profile:
            self.state["status"] = f"Registered profile loaded: {PACK_INFO[level]['pack_title']}"
        else:
            self.state["status"] = "Unknown device: guest content loaded"

    def _on_device_lost(self, event):
        if self._is_stale_device_event(event):
            return
        lost = event.get("device_id")
        current = self.state["connected_device"]
        if current is None:
            return  # nothing connected, nothing to undo
        if lost is not None and lost.strip() != current:
            return  # loss report for an older device must not remove the newer one
        self._record_device_ts(event)
        learner_changed = self.state["level"] != "guest"
        self.state.update(user_id="guest", level="guest", connected_device=None)
        if learner_changed:
            self.reset_session()
        self.state["status"] = "Device lost; guest content loaded"

    def _on_pose_tracking(self, event):
        visible = event["visible"]
        was_lost = self._tracking_lost
        self.state["tracking"] = visible
        self._tracking_lost = not visible
        if visible:
            if was_lost and not self.state["completed"]:
                n = self.state["question_index"] + 1
                self.state["status"] = f"Tracking is back - continue question {n}"
            else:
                self.state["status"] = "Body tracked"

    def _on_hand_tracking(self, event):  # HCI_REAL_PINCH_V4
        was_visible = self.state['hand_tracking']
        self.state['hand_tracking'] = event['visible']
        if event['visible'] and not was_visible:
            self.state['status'] = 'Hand tracked'

    def _on_gaze_tracking(self, event):  # HCI_GAZE_V6
        self.state['gaze_tracking'] = event['visible']
        self.state['gaze_calibrated'] = event['calibrated']

    def _on_camera_status(self, event):
        ready = event["ready"]
        self.state["camera_ready"] = ready
        self._camera_problem = not ready
        if ready:
            self.state["status"] = "Camera ready"

    def _on_lighting_changed(self, event):
        level = event["level"]
        self.state["lighting"] = level
        self.state["status"] = MESSAGES["low_light"] if level == "low" else "Lighting status updated"

    def _on_mode_selected(self, event):
        mode = event["mode"]
        if mode == self.state["mode"]:
            self.state["status"] = f"{mode.capitalize()} mode selected"
            return
        restart = self._session_in_progress()
        self.state["mode"] = mode
        if restart:
            self.reset_session()
            self.state["status"] = (f"{mode.capitalize()} mode selected - new session started "
                                    "with the same five questions")
        else:
            self.state["status"] = f"{mode.capitalize()} mode selected"

    def _on_gesture_recognized(self, event):
        self.state["last_gesture"] = event["name"].strip()[:60]
        self.state["status"] = f"Gesture recognized: {self.state['last_gesture']}"

    def _is_duplicate_select(self, obj):
        now = self._clock()
        last = self._last_select
        question_index = self.state["question_index"]
        self._last_select = (question_index, obj, now)
        return (last is not None and last[0] == question_index and last[1] == obj
                and 0 <= now - last[2] < DUPLICATE_SELECT_WINDOW_S)

    def _on_game_select(self, event):
        obj = event["object"].strip().lower()
        s = self.state
        if s["completed"]:
            s["status"] = "Session complete - replay to restart"
            return
        if self.block_reason():
            return  # unreliable input is ignored; view() shows the blocking message
        if s["awaiting_next"]:
            s["status"] = "Great job! Select Next object to continue"
            return
        question = PACKS[s["level"]][s["question_index"]]
        if obj not in question["choices"]:
            s["status"] = "Object not in current choices"
            return
        if self._is_duplicate_select(obj):
            return  # repeated detection within this question only
        if obj == question["answer"]:
            if s["attempts_this_question"] == 0:
                s["first_try_correct"] += 1
            s["attempts_this_question"] = 0
            s["questions_completed"] += 1
            last_question = s["question_index"] + 1 == len(PACKS[s["level"]])
            if self.require_next and not last_question:
                s["awaiting_next"] = True
                s["status"] = f"Great job! You found the {obj}! Select Next object"
            else:
                self._advance()
        else:
            s["wrong_attempts"] += 1
            s["attempts_this_question"] += 1
            s["status"] = "Good try! Try the same question again"

    def _on_game_next(self, event):
        s = self.state
        if s["completed"]:
            s["status"] = "Session complete - replay to restart"
        elif s["awaiting_next"]:
            self._advance()
        else:
            s["status"] = "Find the object first"

    def _on_game_restart(self, event):
        self.reset_session()
        self.state["status"] = "New session"
