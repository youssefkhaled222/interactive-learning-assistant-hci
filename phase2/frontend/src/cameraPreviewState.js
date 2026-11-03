/** The UI must not display a stale stream just because YOLO metadata exists. */
export function previewReady(health) {
  return health?.active === true && health?.has_frame === true;
}

/** Only monotonic, positive integer camera frame counters can refresh a snapshot. */
export function snapshotSequence(health) {
  const seq = health?.frame_sequence;
  return previewReady(health) && Number.isSafeInteger(seq) && seq > 0 ? seq : 0;
}
