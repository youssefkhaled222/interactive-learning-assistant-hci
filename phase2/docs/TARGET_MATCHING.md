# Candidate target matching — safety-first backend preparation

This feature improves the **temporary YOLO target IDs across brief missed
inference frames** and adds a **pure candidate-matching gate**. It does **NOT**
implement hand gesture selection, gaze selection, camera preview, or change the
learning engine. In particular, it never generates `game.select` from detections.

## Why the previous monitor output flickered

YOLO sometimes emitted `cup`, then an empty frame, then `cup` again. The prior
tracker forgot the ID on an empty frame and assigned `obj-1`, `obj-2`, ...
This version remembers *identity history only* for up to 0.85 seconds.
**Missing objects remain absent from `detected_objects` and cannot be selected.**
The ID history is cleared on detector shutdown and on the 2.5-second watchdog.

This is a short-time IoU heuristic, not robust object tracking across occlusion,
camera movements or similar objects. It doesn't prove that a returning target
is the identical physical object. We require proof in the discussion demo.

## Candidate-matching helper

`backend/target_matching.py` exports `resolve_target(tracker, *, x, y,
coordinate_space, target_id=None, now=None)`.

* Coordinates must be **normalized in the object-facing camera preview**.
  Hand-camera landmarks or raw screen coordinates are **not** equivalent.
  Use `coordinate_space='object_view'` only after actual geometric mapping.
* The point must lie inside **exactly one** currently visible box.
* The detection must be **fresh** (under 0.8 seconds), repeated at least twice,
  and have confidence at least 0.35.
* Requested `target_id`, when present, must match the selected visible box.
* Rejection is returned as `{'accepted': False, 'reason': '...'}`.
* Success returns `{'accepted': True, 'reason': 'candidate-only', 'object': ...,
  'target_id': ..., 'confidence': ...}` — **not** an answer selection.

## Integration still required

1. Show actual object-facing video with aligned bounding boxes in React; boxes
   alone, without the camera image, are not usable target regions.
2. Acquire real hand pointer and deliberate pinch or calibrated gaze + dwell.
3. Map the interaction into **the same object-preview coordinate frame**.
4. Debounce gesture input (release required), reject tracking loss/ambiguous
   targets, and check the current question before calling `game.select`.
5. Implement approved five-question feedback -> Next Object behavior with
   Mohamed's engine and Ahmed's interface, without editing their files blindly.
6. Verify two camera streams or demonstrate modules separately with the one
   verified laptop webcam. Never imply simultaneous hand + object tracking works
   using a single camera if it has not been tested.

The current loopback TCP `source` field is diagnostic, **not** authenticated
hardware provenance. An actual camera test is needed. The code never processes
identifiable child faces or stores videos, and does not upload images.

Tests from repository root:

```powershell
.\phase2\.venv\Scripts\python.exe -m unittest discover -s phase2\tests -v
```

The new tests use synthetic boxes to exercise safety logic, **not real model
accuracy**. The real YOLO-to-WebSocket bridge was separately demonstrated on
Windows, with cup detection; an apple remains untested.
