import React, { useEffect, useRef, useState } from 'react';
import { previewReady, snapshotSequence } from './cameraPreviewState.js';

const PREVIEW_URL = 'http://127.0.0.1:8767';

/** Real MJPEG frames from the local YOLO process; no synthetic selections. */
export default function CameraPreview({ compact = false }) {
  const [available, setAvailable] = useState(false);
  const [failed, setFailed] = useState(false);
  const [sequence, setSequence] = useState(0); // HCI_SNAPSHOT_RECOVERY_V3
  const currentSequence = useRef(0);

  useEffect(() => {
    let mounted = true;
    const check = async () => {
      try {
        const response = await fetch(`${PREVIEW_URL}/health`, { cache: 'no-store' });
        if (!response.ok) throw new Error(`Preview HTTP ${response.status}`);
        const data = await response.json();
        if (mounted) {
          const next = snapshotSequence(data);
          const ready = previewReady(data) && next > 0;
          setAvailable(ready);
          if (ready && next !== currentSequence.current) {
            currentSequence.current = next;
            setSequence(next);
            setFailed(false); // Retry automatically once a new genuine JPEG exists.
          } else if (!ready) {
            currentSequence.current = 0;
            setSequence(0);
            setFailed(false);
          }
        }
      } catch {
        if (mounted) {
          setAvailable(false);
          currentSequence.current = 0;
          setSequence(0);
          setFailed(false);
        }
      }
    };
    check();
    const interval = setInterval(check, 400);
    return () => { mounted = false; clearInterval(interval); };
  }, []);

  const live = available && !failed;
  return (
    <section className={`local-camera-preview ${compact ? 'compact' : ''}`} aria-label="Local object camera preview">
      {live && (
        <img
          src={`${PREVIEW_URL}/snapshot?frame=${sequence}`}
          alt="Live camera with labeled YOLO object detection boxes"
          referrerPolicy="strict-origin-when-cross-origin"
          onError={() => setFailed(true)}
        />
      )}
      {!live && (
        <div className="preview-fallback" role="status">
          <span aria-hidden="true">📷</span>
          <strong>Live camera preview not available</strong>
          <small>Start the local YOLO detector with --stream --publish. No video is sent through WebSocket.</small>
          {available && failed && (
            <button type="button" className="secondary-btn" onClick={() => setFailed(false)}>
              Retry preview
            </button>
          )}
        </div>
      )}
      <p className="preview-caption">
        {live ? 'Live local YOLO object camera · detection only' : 'Camera preview offline · game data can still connect'}
      </p>
    </section>
  );
}
