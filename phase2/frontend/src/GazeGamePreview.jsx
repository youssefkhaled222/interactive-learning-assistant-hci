import React, { useEffect, useRef, useState } from 'react';
import CameraPreview from './CameraPreview.jsx';
import { previewRectFromImage, sendGaze } from './gazeClient.js';

/** Only sends live preview DOM geometry, never game answers or gaze guesses. */
export default function GazeGamePreview({ gaze }) {
  const container = useRef(null);
  const [pixels, setPixels] = useState(null);

  useEffect(() => {
    let active = true;
    const poll = async () => {
      const root = container.current;
      const image = root?.querySelector('img');
      const measurement = previewRectFromImage(image, window.innerWidth, window.innerHeight);
      if (!measurement || !root || !active) {
        if (active) setPixels(null);
        return;
      }
      const parent = root.getBoundingClientRect();
      setPixels({
        left: measurement.pixels.left - parent.left,
        top: measurement.pixels.top - parent.top,
        width: measurement.pixels.width,
        height: measurement.pixels.height
      });
      try {
        await sendGaze('/geometry', {
          rect: measurement.rect,
          width: measurement.width,
          height: measurement.height
        });
      } catch { /* Backend remains blocked; UI displays status. */ }
    };
    poll();
    const timer = setInterval(poll, 650);
    return () => { active = false; clearInterval(timer); };
  }, []);

  const point = gaze?.point;
  const progress = Math.max(0, Math.min(100, (gaze?.progress || 0)*100));
  return (
    <div className="gaze-object-preview" ref={container}>
      <CameraPreview />
      {pixels && point && (
        <div className="gaze-aim-dot" aria-label="Estimated eye gaze position"
             style={{
               left: pixels.left + point.x * pixels.width,
               top: pixels.top + point.y * pixels.height
             }} />
      )}
      <div className="gaze-dwell-bar" aria-label="Gaze dwell progress">
        <span style={{ width: `${progress}%` }} />
      </div>
      <p className="gaze-small-status" role="status">
        {gaze?.calibrated ? 'Calibrated · ' : 'Calibration needed · '}
        {gaze?.phase || 'Waiting for gaze adapter'} · {Math.round(progress)}% / 1.5 s
      </p>
    </div>
  );
}
