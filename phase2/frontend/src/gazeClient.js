/** Gaze service is localhost only; no browser-supplied game.select. */
export const GAZE_API = 'http://127.0.0.1:8770';
export const TARGETS = Object.freeze([
  [0.12, 0.12], [0.5, 0.12], [0.88, 0.12],
  [0.12, 0.5], [0.88, 0.5],
  [0.12, 0.88], [0.5, 0.88], [0.88, 0.88],
  [0.5, 0.5] // held-out validation point, MUST be last
]);

export async function getGazeHealth() {
  const response = await fetch(`${GAZE_API}/health`, { cache: 'no-store' });
  if (!response.ok) throw new Error(`Gaze camera HTTP ${response.status}`);
  return response.json();
}

export async function sendGaze(path, payload = {}) {
  const response = await fetch(`${GAZE_API}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
    cache: 'no-store'
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || `Gaze HTTP ${response.status}`);
  return result;
}

/** Browser target rect after object-fit: contain. Correctly handles letterboxing. */
export function previewRectFromImage(image, viewportWidth, viewportHeight) {
  if (!image || !viewportWidth || !viewportHeight ||
      image.naturalWidth <= 0 || image.naturalHeight <= 0) return null;
  const rect = image.getBoundingClientRect();
  if (rect.width < 100 || rect.height < 80) return null;
  const scale = Math.min(rect.width / image.naturalWidth, rect.height / image.naturalHeight);
  const paintedWidth = image.naturalWidth * scale;
  const paintedHeight = image.naturalHeight * scale;
  const left = rect.left + (rect.width - paintedWidth) / 2;
  const top = rect.top + (rect.height - paintedHeight) / 2;
  const points = [left / viewportWidth, top / viewportHeight,
    (left + paintedWidth) / viewportWidth, (top + paintedHeight) / viewportHeight];
  if (!points.every(n => Number.isFinite(n) && n >= 0 && n <= 1)) return null;
  return { rect: points, width: viewportWidth, height: viewportHeight,
    pixels: { left, top, width: paintedWidth, height: paintedHeight } };
}
