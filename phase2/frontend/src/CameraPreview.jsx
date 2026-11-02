import React, { useEffect, useState } from 'react';
import { previewReady } from './cameraPreviewState.js';

const PREVIEW_URL = 'http://127.0.0.1:8767';

/** Real MJPEG frames from the local YOLO process; no synthetic selections. */
export default function CameraPreview({ compact = false }) {
  const [available, setAvailable] = useState(false);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let mounted = true;
    const check = async () => {
      try {
        const response = await fetch(`${PREVIEW_URL}/health`, { cache: 'no-store' });
        if (!response.ok) throw new Error(`Preview HTTP ${response.status}`);
        const data = await response.json();
        if (mounted) {
          const ready = previewReady(data);
          setAvailable(ready);
          if (!ready) setFailed(false);
        }
      } catch {
        if (mounted) {
          setAvailable(false);
          setFailed(false);
        }
      }
    };
    check();
    const interval = setInterval(check, 1800);
    return () => { mounted = false; clearInterval(interval); };
  }, []);

  const live = available && !failed;
  return (
    <section className={`local-camera-preview ${compact ? 'compact' : ''}`} aria-label="Local object camera preview">
      {live && (
        <img
          src={`${PREVIEW_URL}/video`}
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
