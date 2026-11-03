# HCI Phase II — discussion and explanation guide

Use this to prepare the TA conversation; it is **not a fabricated evaluation report**. Verify the actual course rubric and ask team members to explain the components they personally built.

## Short opening (about one minute)

> Our project, Little Explorers, is an interactive Find the Object learning activity for young children. It uses YOLO11s to detect a real apple, book or cup, then lets the child choose an object without using a mouse. Hand mode uses a real index-finger hover followed by a pinch; we completed a five-question session with that mode. We also built camera-based gaze calibration and 1.5-second dwell selection, which has passed software tests but still needs the final two-camera hardware test. The backend controls learner profiles, question rules, tracking readiness and feedback.

## Questions the TA may ask — grounded answers

**Why is this HCI, not just computer vision?**

The work concerns input techniques for young learners: discoverability, clear instructions, multimodal interaction, timely feedback, error prevention, confidence/reassurance, visibility of current state, and accessibility choices. Object detection and eye/hand landmarks are enabling technologies, not the complete interaction design.

**Why two input modes?**

The original interaction concept offers alternatives with different strengths and constraints. Hand gestures need visible, deliberate movement and the open-hover-before-pinch sequence. Eye gaze can potentially reduce hand movement, but low-cost webcam gaze is sensitive to calibration, gaze drift, lighting, and fatigue. We have not yet measured which is more usable for children.

**How does the system know an answer is correct?**

YOLO supplies actual object labels and boxes. The corresponding sensor gate must validate a current stable target, then the engine compares its label with the active question's answer. Scores, attempts, stars and progression are issued by the engine, not by mouse clicks in the UI.

**How does context awareness work?**

A registered BLE device may load Beginner/Advanced content; otherwise Guest content is shown. The engine uses mode, camera readiness, tracking visibility, lighting notices and progress to guide or block interaction. The BLE demo identifier is pseudonymous; it is not a secure user account.

**Why is calibration necessary?**

The face camera reports pupil/iris features relative to facial landmarks, not exact on-screen pixels. A session-specific mapping from multiple target points estimates screen gaze. A separate held-out point checks whether the fit is plausible; failed calibration must not unlock scoring. The real accuracy still has to be measured.

**How do you avoid accidental selections?**

Gesture mode first requires the open finger to hover on a detected object, then a valid pinch/hold/release. Gaze mode requires 1.5 seconds on one stable detection, fresh sensor input and rearming on looking away. Missing cameras, lost tracking, stale boxes and failed calibration should block selection. These properties have automated coverage; final physical negative testing is pending.

**What is already proven, and what is not?**

As of 3 November 2026, **198 Python tests** and **22 frontend tests** passed, along with a production build. A physical **5/5 gesture** session succeeded. The real BLE test was reported by Malak independently. Gaze physical validation and full combined demonstration remain open; no child-participant study or statistical comparison has yet been evidenced.

**What if gaze calibration fails in front of the TA?**

Do not bypass checks or simulate success. Explain that the system intentionally blocks a low-quality calibration, document the device/camera placement, and demonstrate the verified gesture pathway. Show the gaze code/tests clearly labeled as implementation with a pending hardware limitation.

## What to show in order

1. The age/PACT context and the problem being addressed.
2. UI choice of Hand or Gaze, plus the guided tutorial/calibration.
3. Architecture diagram and distinct responsibilities of YOLO, MediaPipe, the broker, and the engine.
4. Real gesture demo with apple/book/cup, Next Object, feedback and results.
5. Real BLE profile switch with Malak's registered phone (if available); separate Pose/DollarPy run with Mostafa's camera setup.
6. Latest automated test summary and source-control branch history.
7. Gaze implementation architecture, current validation status and final assigned teammate hardware-test plan.
8. Limitations and proposed usability-study methodology, without inventing measured findings.

## HCI evaluation plan (proposal, not completed study)

With required guardian consent and course approval, compare gesture and gaze in a controlled setting. For each session record task success, unintended activations, number of retries, time per question, calibration failures, tracking interruptions, and simple age-appropriate feedback. Counterbalance mode order; track different lighting/camera conditions; avoid collecting identifiable recordings unless explicitly needed and consented. Report sample size and actual observations before drawing conclusions.

## Final-submission checkpoint

Confirm the assignment's course code, discussion timing, slide/report requirements, team photos if required, and grading criteria using the current course instructions. Do **not** present this outline as confirmation of those requirements.
