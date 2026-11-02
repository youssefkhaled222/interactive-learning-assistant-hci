import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
from content_packs import PACKS, QUESTIONS_PER_PACK, SUPPORTED_OBJECTS, validate_packs
from engine import DUPLICATE_SELECT_WINDOW_S, REGISTERED, Engine

BEGINNER = "demo-device-beginner"
ADVANCED = "demo-device-advanced"


class FakeClock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t

    def tick(self, seconds=DUPLICATE_SELECT_WINDOW_S + 0.5):
        self.t += seconds


class EngineTestCase(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.e = Engine(clock=self.clock)

    def emit(self, **event):
        event.setdefault("source", "unit_test")
        state = self.e.handle(event)
        self.clock.tick()  # keep separate selections outside the duplicate window
        return state

    def answer_current(self):
        return self.emit(type="game.select", object=self.e.view()["question"]["answer"])

    def wrong_current(self):
        q = self.e.view()["question"]
        wrong = next(c for c in q["choices"] if c != q["answer"])
        return self.emit(type="game.select", object=wrong)


class TestContentPacks(EngineTestCase):
    def test_every_pack_has_exactly_five_questions(self):
        self.assertEqual(set(PACKS), {"guest", "beginner", "advanced"})
        for pack_id, questions in PACKS.items():
            self.assertEqual(len(questions), QUESTIONS_PER_PACK, pack_id)

    def test_answer_configuration_is_valid(self):
        self.assertTrue(validate_packs())
        for pack_id, questions in PACKS.items():
            answers = [q["answer"] for q in questions]
            self.assertEqual(set(answers), set(SUPPORTED_OBJECTS), pack_id)
            for a, b in zip(answers, answers[1:]):
                self.assertNotEqual(a, b, f"{pack_id} repeats {a} twice in a row")
            for q in questions:
                self.assertEqual(sorted(q["choices"]), sorted(SUPPORTED_OBJECTS))
                self.assertEqual(q["choices"].count(q["answer"]), 1)

    def test_validator_rejects_broken_packs(self):
        broken = copy.deepcopy(PACKS)
        broken["guest"][0]["answer"] = "banana"
        with self.assertRaises(ValueError):
            validate_packs(broken)
        short = copy.deepcopy(PACKS)
        short["beginner"].pop()
        with self.assertRaises(ValueError):
            validate_packs(short)
        repeated = copy.deepcopy(PACKS)
        repeated["advanced"][1] = copy.deepcopy(repeated["advanced"][0])
        repeated["advanced"][1]["prompt"] = "A different prompt"
        with self.assertRaises(ValueError):
            validate_packs(repeated)

    def test_three_packs_have_distinct_prompts(self):
        prompts = {pid: [q["prompt"] for q in qs] for pid, qs in PACKS.items()}
        all_prompts = sum(prompts.values(), [])
        self.assertEqual(len(all_prompts), len(set(all_prompts)))

    def test_advanced_prompts_describe_instead_of_naming(self):
        for q in PACKS["advanced"]:
            self.assertNotIn(q["answer"], q["prompt"].lower())
        for q in PACKS["beginner"]:
            self.assertIn(q["answer"], q["prompt"].lower())


class TestDeviceContext(EngineTestCase):
    def test_initial_state_is_guest_pack(self):
        v = self.e.view()
        self.assertEqual((v["level"], v["pack_id"], v["user_id"]), ("guest", "guest", "guest"))
        self.assertEqual(v["question"]["prompt"], PACKS["guest"][0]["prompt"])
        self.assertEqual(v["total_questions"], 5)

    def test_registered_devices_change_the_actual_questions(self):
        b = self.emit(type="device.discovered", device_id=BEGINNER)
        self.assertEqual(b["level"], "beginner")
        self.assertEqual(b["user_id"], REGISTERED[BEGINNER]["user_id"])
        self.assertEqual(b["question"]["prompt"], PACKS["beginner"][0]["prompt"])
        a = self.emit(type="device.discovered", device_id=ADVANCED)
        self.assertEqual(a["level"], "advanced")
        self.assertEqual(a["question"]["prompt"], PACKS["advanced"][0]["prompt"])
        self.assertEqual(a["question"]["answer"], "book")
        self.assertEqual(a["age_range"], "8-10")

    def test_unknown_device_loads_guest_pack(self):
        self.emit(type="device.discovered", device_id=BEGINNER)
        x = self.emit(type="device.discovered", device_id="unregistered-device-123")
        self.assertEqual(x["level"], "guest")
        self.assertEqual(x["question"]["prompt"], PACKS["guest"][0]["prompt"])
        self.assertIn("guest", x["status"].lower())

    def test_device_lost_falls_back_to_guest(self):
        self.emit(type="device.discovered", device_id=ADVANCED)
        self.answer_current()
        x = self.emit(type="device.lost", device_id=ADVANCED)
        self.assertEqual(x["level"], "guest")
        self.assertIsNone(x["connected_device"])
        self.assertEqual(x["question_index"], 0)
        self.assertEqual(x["question"]["prompt"], PACKS["guest"][0]["prompt"])

    def test_duplicate_discovery_does_not_reset_session(self):
        self.emit(type="device.discovered", device_id=BEGINNER)
        self.answer_current()
        self.wrong_current()
        before = self.e.view()
        x = self.emit(type="device.discovered", device_id=BEGINNER)
        self.assertEqual(x["question_index"], 1)
        self.assertEqual(x["questions_completed"], before["questions_completed"])
        self.assertEqual(x["attempts_this_question"], 1)
        self.assertEqual(x["status"], before["status"])

    def test_switching_learner_resets_session(self):
        self.emit(type="device.discovered", device_id=BEGINNER)
        self.answer_current()
        self.answer_current()
        x = self.emit(type="device.discovered", device_id=ADVANCED)
        self.assertEqual(x["question_index"], 0)
        self.assertEqual(x["questions_completed"], 0)
        self.assertEqual(x["first_try_correct"], 0)
        self.assertEqual(x["user_id"], "learner_02")

    def test_lost_event_for_older_device_is_ignored(self):
        self.emit(type="device.discovered", device_id=BEGINNER)
        self.emit(type="device.discovered", device_id=ADVANCED)
        x = self.emit(type="device.lost", device_id=BEGINNER)
        self.assertEqual(x["level"], "advanced")
        self.assertEqual(x["connected_device"], ADVANCED)

    def test_older_timestamped_event_cannot_overwrite_newer_profile(self):
        self.emit(type="device.discovered", device_id=ADVANCED, ts=20.0)
        x = self.emit(type="device.discovered", device_id=BEGINNER, ts=10.0)
        self.assertEqual(x["level"], "advanced")
        x = self.emit(type="device.lost", ts=15.0)
        self.assertEqual(x["level"], "advanced")
        x = self.emit(type="device.lost", ts=25.0)
        self.assertEqual(x["level"], "guest")

    def test_lost_without_connected_device_keeps_guest_progress(self):
        self.answer_current()
        x = self.emit(type="device.lost")
        self.assertEqual(x["question_index"], 1)


class TestPhysicalContext(EngineTestCase):
    def test_low_light_shows_actionable_guidance(self):
        x = self.emit(type="lighting.changed", level="low", source="camera")
        self.assertEqual(x["lighting"], "low")
        self.assertIn("lamp", x["status"])
        self.assertIn("low_light", [n["code"] for n in x["notices"]])
        self.assertFalse(x["input_blocked"])
        x = self.emit(type="lighting.changed", level="good", source="camera")
        self.assertNotIn("low_light", [n["code"] for n in x["notices"]])

    def test_tracking_loss_blocks_input_and_keeps_progress(self):
        self.emit(type="device.discovered", device_id=BEGINNER)
        self.answer_current()
        x = self.emit(type="pose.tracking", visible=False)
        self.assertTrue(x["input_blocked"])
        self.assertEqual(x["block_reason"], "tracking_lost")
        x = self.emit(type="game.select", object=x["question"]["answer"])
        self.assertEqual(x["question_index"], 1)
        self.assertEqual(x["questions_completed"], 1)
        self.assertEqual(x["wrong_attempts"], 0)
        self.assertIn("lost", x["status"].lower())

    def test_tracking_recovery_resumes_same_question(self):
        self.emit(type="device.discovered", device_id=BEGINNER)
        self.answer_current()
        self.emit(type="pose.tracking", visible=False)
        x = self.emit(type="pose.tracking", visible=True)
        self.assertFalse(x["input_blocked"])
        self.assertIn("question 2", x["status"])
        x = self.answer_current()
        self.assertEqual(x["question_index"], 2)

    def test_tracking_message_matches_mode(self):
        x = self.emit(type="pose.tracking", visible=False)
        self.assertIn("hand", x["status"])
        x = self.emit(type="mode.selected", mode="gaze")
        self.assertIn("eyes", x["status"])

    def test_camera_not_ready_blocks_input(self):
        x = self.emit(type="camera.status", ready=False)
        self.assertEqual(x["block_reason"], "camera_not_ready")
        x = self.answer_current()
        self.assertEqual(x["question_index"], 0)
        x = self.emit(type="camera.status", ready=True)
        self.assertFalse(x["input_blocked"])
        x = self.answer_current()
        self.assertEqual(x["question_index"], 1)

    def test_legacy_simulated_engine_can_select_before_sensor_report(self):
        self.assertFalse(self.e.require_sensor_ready)
        x = self.answer_current()
        self.assertEqual(x["question_index"], 1)


class TestGameplay(EngineTestCase):
    def test_wrong_answers_allow_unlimited_retries(self):
        self.emit(type="device.discovered", device_id=ADVANCED)
        for _ in range(7):
            x = self.wrong_current()
        self.assertEqual(x["question_index"], 0)
        self.assertEqual(x["wrong_attempts"], 7)
        self.assertTrue(x["show_hint"])
        x = self.answer_current()
        self.assertEqual(x["question_index"], 1)
        self.assertEqual(x["first_try_correct"], 0)
        self.assertEqual(x["questions_completed"], 1)
        self.assertFalse(x["show_hint"])

    def test_completion_and_first_try_counted_separately(self):
        self.emit(type="device.discovered", device_id=BEGINNER)
        for i in range(5):
            if i in (1, 3):
                self.wrong_current()
            x = self.answer_current()
        self.assertTrue(x["completed"])
        self.assertIsNone(x["question"])
        self.assertEqual(x["questions_completed"], 5)
        self.assertEqual(x["first_try_correct"], 3)
        self.assertEqual(x["wrong_attempts"], 2)

    def test_finished_session_ignores_further_selections(self):
        for _ in range(5):
            x = self.answer_current()
        self.assertTrue(x["completed"])
        x = self.emit(type="game.select", object="apple")
        self.assertTrue(x["completed"])
        self.assertEqual(x["questions_completed"], 5)
        self.assertIn("complete", x["status"].lower())

    def test_restart_resets_progress_but_keeps_learner(self):
        self.emit(type="device.discovered", device_id=ADVANCED)
        self.answer_current()
        self.wrong_current()
        x = self.emit(type="game.restart")
        self.assertEqual((x["question_index"], x["questions_completed"], x["wrong_attempts"]), (0, 0, 0))
        self.assertEqual(x["level"], "advanced")

    def test_repeated_detection_is_scoped_to_the_question(self):
        self.emit(type="device.discovered", device_id=BEGINNER)
        self.e.handle({"type": "game.select", "object": "apple", "source": "unit_test"})
        # Same object is a legitimate WRONG attempt on the NEXT question.
        x = self.e.handle({"type": "game.select", "object": "apple", "source": "unit_test"})
        self.assertEqual(x["question_index"], 1)
        self.assertEqual(x["wrong_attempts"], 1)
        # A repeated wrong sensor event on the SAME question is de-duplicated.
        x = self.e.handle({"type": "game.select", "object": "apple", "source": "unit_test"})
        self.assertEqual(x["wrong_attempts"], 1)
        x = self.e.handle({"type": "game.select", "object": "cup", "source": "unit_test"})
        self.assertEqual(x["question_index"], 2)

    def test_object_outside_choices_is_not_a_wrong_attempt(self):
        x = self.emit(type="game.select", object="banana")
        self.assertEqual(x["wrong_attempts"], 0)
        self.assertIn("not in current choices", x["status"])

    def test_mode_parity_same_questions_in_gaze_and_gesture(self):
        for device in (None, BEGINNER, ADVANCED):
            gesture, gaze = Engine(clock=FakeClock()), Engine(clock=FakeClock())
            gaze.handle({"type": "mode.selected", "mode": "gaze"})
            if device:
                gesture.handle({"type": "device.discovered", "device_id": device})
                gaze.handle({"type": "device.discovered", "device_id": device})
            for _ in range(5):
                a, b = gesture.view(), gaze.view()
                self.assertEqual(a["question"], b["question"])
                ans = a["question"]["answer"]
                gesture.handle({"type": "game.select", "object": ans})
                gaze.handle({"type": "game.select", "object": ans})
                gesture._clock.tick()
                gaze._clock.tick()
            self.assertTrue(gesture.view()["completed"] and gaze.view()["completed"])

    def test_mode_switch_mid_session_restarts_same_pack(self):
        self.emit(type="device.discovered", device_id=BEGINNER)
        self.answer_current()
        x = self.emit(type="mode.selected", mode="gaze")
        self.assertEqual(x["mode"], "gaze")
        self.assertEqual(x["question_index"], 0)
        self.assertEqual(x["level"], "beginner")

    def test_next_object_flow_when_enabled(self):
        e = Engine(require_next=True, clock=FakeClock())
        x = e.handle({"type": "game.select", "object": "apple"})
        self.assertTrue(x["awaiting_next"])
        self.assertEqual(x["question_index"], 0)
        self.assertEqual(x["questions_completed"], 1)
        x = e.handle({"type": "game.select", "object": "book"})
        self.assertEqual(x["wrong_attempts"], 0)
        x = e.handle({"type": "game.next"})
        self.assertFalse(x["awaiting_next"])
        self.assertEqual(x["question"]["answer"], "book")

    def test_game_next_is_harmless_in_auto_advance_mode(self):
        x = self.emit(type="game.next")
        self.assertEqual(x["question_index"], 0)


class TestValidation(EngineTestCase):
    def test_garbage_values_are_rejected_without_changing_state(self):
        before = self.e.view()
        bad_events = [
            {"type": "pose.tracking", "visible": "no"},
            {"type": "camera.status", "ready": 1},
            {"type": "device.discovered", "device_id": ""},
            {"type": "device.discovered"},
            {"type": "device.lost", "device_id": 42},
            {"type": "lighting.changed", "level": "dark"},
            {"type": "mode.selected", "mode": "voice"},
            {"type": "game.select", "object": "   "},
            {"type": "game.select", "object": 3},
            {"type": "gesture.recognized", "name": ""},
            {"type": "game.select", "object": "apple", "source": 5},
            {"type": "device.discovered", "device_id": BEGINNER, "ts": "yesterday"},
            {"type": "made.up"},
            ["not", "a", "dict"],
        ]
        for bad in bad_events:
            with self.assertRaises(ValueError, msg=str(bad)):
                self.e.handle(bad)
        self.assertEqual(self.e.view(), before)

    def test_simulator_events_are_labelled(self):
        x = self.emit(type="device.discovered", device_id=BEGINNER, source="simulator")
        self.assertTrue(x["demo_mode"])
        x = self.emit(type="pose.tracking", visible=True, source="mediapipe")
        self.assertFalse(x["demo_mode"])
        self.assertEqual(x["event_source"], "mediapipe")


if __name__ == "__main__":
    unittest.main()
