/** The UI must not display a stale stream just because YOLO metadata exists. */
export function previewReady(health) {
  return health?.active === true && health?.has_frame === true;
}
