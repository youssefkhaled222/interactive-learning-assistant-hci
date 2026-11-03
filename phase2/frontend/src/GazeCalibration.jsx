import React, { useEffect, useRef, useState } from 'react';
import { getGazeHealth, sendGaze, TARGETS } from './gazeClient.js';

/** A parent/teacher clicks Capture; only actual detected iris features are saved. */
export default function GazeCalibration({ onContinue, onBack }) {
  const [health, setHealth] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [online, setOnline] = useState(false);
  const box = useRef(null);

  useEffect(() => {
    let active = true;
    const poll = async () => {
      try {
        const next = await getGazeHealth();
        if (active) { setHealth(next); setOnline(true); }
      } catch {
        if (active) { setHealth(null); setOnline(false); }
      }
    };
    poll();
    const timer = setInterval(poll, 650);
    return () => { active = false; clearInterval(timer); };
  }, []);

  const index = health?.calibration_count ?? 0;
  const point = TARGETS[index] || null;
  const ready = Boolean(online && health?.face_visible);

  async function capture() {
    if (!point || !ready || !box.current || busy) return;
    const rect = box.current.getBoundingClientRect();
    const width = window.innerWidth;
    const height = window.innerHeight;
    setBusy(true);
    setError('');
    try {
      const result = await sendGaze('/capture', {
        index,
        x: (rect.left + point[0] * rect.width) / width,
        y: (rect.top + point[1] * rect.height) / height,
        width, height
      });
      setHealth(result);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function reset() {
    setBusy(true);
    try {
      setHealth(await sendGaze('/reset'));
      setError('');
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="standard-panel gaze-calibration-panel">
      <div className="section-heading">
        <span className="eyebrow">Real webcam eye tracking</span>
        <h1>Look at each glowing dot</h1>
        <p>Use a second camera facing your eyes. Keep your head still. Look at the dot for one second, then ask an adult to press Capture. Repeat nine times.</p>
      </div>
      <div className="gaze-calibration-board" ref={box}>
        {point && <span className="gaze-calibration-target"
                        style={{ left: `${point[0]*100}%`, top: `${point[1]*100}%` }}
                        aria-label={`Look here: target ${index+1}`} />}
        {health?.calibrated && <div className="gaze-calibration-done">✅ Calibration passed</div>}
      </div>
      <p className="gaze-small-status" role="status">
        Face camera: <strong>{!online ? 'Offline' : health.face_visible ? 'Eyes detected' : 'Face not visible'}</strong>
        {' · '}Targets: <strong>{index} / 9</strong>
        {health?.calibration_quality && ` · Error: ${health.calibration_quality.held_out}`}
      </p>
      {!online && <p className="warning-note">Start the Gaze launcher and make sure a SECOND player-facing webcam is connected. The object camera is already used by YOLO.</p>}
      {error && <p className="warning-note" role="alert">{error}</p>}
      {health?.calibrated ? (
        <p className="hint-note">Calibration is accepted. Keep the same browser size and seating position. Look at the object in the large camera preview for 1.5 seconds to select it.</p>
      ) : (
        <p className="hint-note">{point ? `Target ${index+1}/9: focus on the dot; adult presses Capture after one second.` : 'Reset calibration to retry.'}</p>
      )}
      <div className="button-row centered">
        <button className="secondary-btn" onClick={onBack}>Back</button>
        <button className="secondary-btn" onClick={reset} disabled={!online || busy}>Reset calibration</button>
        {!health?.calibrated ? (
          <button className="primary-btn" disabled={!ready || busy || !point} onClick={capture}>
            {busy ? 'Capturing…' : `Capture point ${index+1} →`}
          </button>
        ) : (
          <button className="primary-btn" onClick={onContinue}>Continue to objects →</button>
        )}
      </div>
    </section>
  );
}
