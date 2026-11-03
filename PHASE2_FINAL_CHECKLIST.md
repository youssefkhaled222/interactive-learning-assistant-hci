# HCI Phase II — final readiness checklist

**Snapshot: 3 November 2026 | V6 branch: `feature/real-eye-tracking` | Commit: `a927371` (before documentation updates)**

This checklist separates **demonstrated**, **automated-tested**, **individually reported**, and **not yet verified**. A passing unit suite is not evidence of physical eye-tracking accuracy or a completed HCI user study.

## Completed / recorded

- [x] Phase I written/Figma deliverables previously submitted; historical details in project README.
- [x] Python broker (TCP `8765`), browser state bridge (WebSocket `8766`), React/Vite learning game and three learner packs integrated.
- [x] YOLO11s on real camera detects supported apple, book, cup with box metadata; local preview at HTTP `8767`.
- [x] MediaPipe Hands sees a real index point/pinch; backend target matching requires current, sufficiently stable object detection.
- [x] **Physical hand-mode game completed: 5/5 questions, 5/5 first attempt, 0 wrong attempts**, screenshot captured by student.
- [x] Stable gesture milestone committed and pushed: `f3602a7` on `feature/real-hand-object-selection`.
- [x] Malak reports real BLE enrolled-device demonstration working separately; code integrated.
- [x] Pose/DollarPy tracker code present and previously component-tested; integrated event pipeline has automated coverage.
- [x] V6 face-camera calibration and 1.5-second gaze dwell code committed/pushed: `a927371` on `feature/real-eye-tracking`.
- [x] On original V6 installation: **198 Python tests**, **22 React tests**, and frontend production build all passed.
- [x] Official Face Landmarker model downloaded on original development laptop; **model is not committed to GitHub**.

## Finish before asking the teammate to perform the LAST physical gaze test

- [ ] Replace outdated README, demonstration and checklist text with current implementation description and evidence.
- [ ] Audit `.gitignore` and untracked files; ensure no `.venv`, `node_modules`, model bundles, child videos, ZIP payloads, installers, backups or secrets are committed accidentally.
- [ ] Re-run `Run-HCI-Tests.cmd` after any subsequent edits; keep terminal output and `git diff --check` result.
- [ ] Review Malak's BLE setup and capture her hardware proof or short screen recording; run one combined profile-change test if a shared machine/device is available.
- [ ] Review Mostafa's approved camera/model/template setup; capture real horizontal/vertical classification output separately to avoid camera collision.
- [ ] Preserve the existing successful 5/5 gesture result and test a negative case (hand loss / no live detection) without unexpectedly scoring.
- [ ] Prepare architecture explanation, roles, screenshots, discussion questions and actual TA rubric requirements; don't invent child-user study results.
- [ ] Have teammates review the V6 branch / proposed PR and agree on hardware test owner, model setup and evidence format. **Keep V6 unmerged until accepted.**

## LAST: physical gaze validation by teammate with TWO camera sources

- [ ] Fresh clone/checkout of `feature/real-eye-tracking` and reproducible environment + model setup.
- [ ] Separate object-facing YOLO camera and player-facing Face Landmarker camera both produce valid live observations.
- [ ] Genuine nine-point calibration succeeds on teammate's hardware (including held-out center check).
- [ ] Estimated gaze point tracks where participant actually looks in the large on-screen preview.
- [ ] At least one 1.5-second gaze dwell selects the **correct fresh YOLO detection**, confirmed by backend log and React state.
- [ ] Full five-question gaze session reaches results screen using only real gaze selections and Next Object.
- [ ] Looking away, too-short dwell, wrong object, lost face, stale/ambiguous object boxes and calibration failure do not falsely score.
- [ ] Re-run gesture test after V6 integration on that machine (or separately demonstrate it remains functional).
- [ ] Record device model, camera indices, software versions, calibration result, test date, screenshots, successes and failures, and the exact commit tested.
- [ ] If acceptance succeeds, team reviews final PR and merges; if it fails, document it accurately and fix only demonstrated problems before another acceptance attempt.

## Delivery / academic controls

- [ ] Confirm current HCI **course code**, submission platform, deadline, rubric, minimum evidence, test-participant/consent requirements, and whether two-camera gaze is mandatory. These are **not established** by the repository alone.
- [ ] Submit only required files/links; avoid sharing personal BLE keys, face imagery without consent, child recordings, bulky model weights and secrets.
- [ ] If the assignment demands quantitative usability evaluation, schedule and report **real** participants and measured results; no measured study is claimed as of this snapshot.

**Completion criterion:** Only mark fully complete after the course rubric is satisfied, all required demonstrations—including hardware gaze if mandatory—are evidenced, and the final branch is reviewed and merged or otherwise submitted as instructed.
