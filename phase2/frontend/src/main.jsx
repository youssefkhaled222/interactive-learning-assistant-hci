
import React, { useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './style.css';
import { feedbackChange, feedbackNextAction, visibleDetections } from './gameUiState.js';

const icons = {
  apple: '🍎',
  book: '📘',
  cup: '🥤'
};

const screenNames = {
  welcome: 'Welcome',
  mode: 'Choose a Mode',
  hand: 'Hand Gesture Tutorial',
  eye: 'Eye Tracking Calibration',
  camera: 'Camera & Object Setup',
  game: 'Find the Object',
  feedback: 'Feedback',
  results: 'Session Results'
};

// --------------------------------------------------
// WebSocket Connection
// --------------------------------------------------

function useGameSocket() {
  const [state, setState] = useState(null);
  const [connected, setConnected] = useState(false);
  const [socket, setSocket] = useState(null);
  const [socketError, setSocketError] = useState('');

  useEffect(() => {
    let ws;
    let active = true;
    let retry;

    const connect = () => {
      ws = new WebSocket('ws://127.0.0.1:8766');

      ws.onopen = () => {
        if (active) {
          setConnected(true);
          setSocket(ws);
          setSocketError('');
        }
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);

          if (data.type === 'state' && active) {
            setState(data.payload);
            setSocketError('');
          } else if (data.type === 'error' && active) {
            setSocketError(data.message || 'Backend rejected the command.');
          }
        } catch (error) {
          console.error('WebSocket message error:', error);
        }
      };

      ws.onclose = () => {
        if (active) {
          setConnected(false);
          setSocket(null);
          retry = setTimeout(connect, 1500);
        }
      };

      ws.onerror = () => {
        if (active) {
          setSocketError('Unable to connect to backend.');
          ws.close();
        }
      };
    };

    connect();

    return () => {
      active = false;
      clearTimeout(retry);
      ws?.close();
    };
  }, []);

  const sendCommand = (action, payload = {}) => {
    if (!socket || socket.readyState !== WebSocket.OPEN) {
      setSocketError('Backend is not connected');
      return false;
    }

    socket.send(JSON.stringify({
      type: 'command',
      action,
      payload
    }));

    return true;
  };

  return {
    state,
    connected,
    sendCommand,
    socketError
  };
}

// --------------------------------------------------
// Main Application
// --------------------------------------------------

function App() {
  const {
    state: backend,
    connected,
    sendCommand,
    socketError
  } = useGameSocket();

  const [screen, setScreen] = useState('welcome');
  const [mode, setMode] = useState('gesture');
  const [localSelection, setLocalSelection] = useState('');
  const [feedbackType, setFeedbackType] = useState('');

  const previous = useRef(null);
  const nextPending = useRef(false);

  useEffect(() => {
    // Never strand the Next Object button after a rejected command or disconnect.
    if (!connected || socketError) nextPending.current = false;
  }, [connected, socketError]);

  // ------------------------------------------------
  // Monitor validated backend state; never infer success from a local click.
  // ------------------------------------------------

  useEffect(() => {
    if (!backend) return;
    const old = previous.current;
    previous.current = backend;
    if (!old || screen !== 'game') return;

    const feedback = feedbackChange(old, backend);
    if (feedback) {
      setFeedbackType(feedback);
      setLocalSelection('');
      setScreen('feedback');
      return;
    }
    // Recover from reconnecting directly to an already completed session.
    if (backend.completed && !old.completed) {
      setScreen('results');
    }
  }, [backend]);

  // ------------------------------------------------
  // Backend Data
  // ------------------------------------------------

  const question = backend?.question || null;
  const choices = question?.choices || [];

  const total = backend?.total_questions || 0;

  const questionNo = backend?.completed
    ? total
    : Math.min(
        (backend?.question_index || 0) + 1,
        total
      );

  const engineMode =
    backend?.mode || (mode === 'eye' ? 'gaze' : 'gesture');

  const isDemo =
    backend?.demo_mode === true ||
    backend?.event_source === 'simulator';

  const status =
    backend?.status || 'Waiting for backend state';

  const detections = visibleDetections(backend);
  const notices = Array.isArray(backend?.notices) ? backend.notices : [];
  const questionDone = backend?.questions_completed ?? backend?.question_index ?? 0;

  // ------------------------------------------------
  // Navigation Functions
  // ------------------------------------------------

  function chooseMode(next) {
    setMode(next);

    sendCommand('mode.selected', {
      mode: next === 'hand' ? 'gesture' : 'gaze'
    });

    setScreen(next === 'hand' ? 'hand' : 'eye');
  }

  function restart() {
    const sent = sendCommand('game.restart', {});

    if (!sent) return;

    previous.current = null; // a new session is not a new selection
    setLocalSelection('');
    setFeedbackType('');
    setScreen('game');
  }

  function continueAfterFeedback() {
    const next = feedbackNextAction(backend, feedbackType);
    if (next === 'results') {
      setFeedbackType('');
      setScreen('results');
      return;
    }
    if (next === 'game.next') {
      if (!connected || nextPending.current) return;
      nextPending.current = true;
      if (!sendCommand('game.next', {})) {
        nextPending.current = false;
        return;
      }
      // Do not move ahead until the server confirms a changed question.
      return;
    }
    setFeedbackType('');
    setScreen('game');
  }

  useEffect(() => {
    if (!nextPending.current || !backend) return;
    if (!backend.awaiting_next || backend.completed) {
      nextPending.current = false;
      setFeedbackType('');
      setScreen(backend.completed ? 'results' : 'game');
    }
  }, [backend]);

  function mousePreview(choice) {
    // Local UI preview only.
    // Browser selection is not sent to the backend.
    setLocalSelection(choice);
  }

  function home() {
    setScreen('welcome');
    setLocalSelection('');
    setFeedbackType('');
    nextPending.current = false;
  }

  // ------------------------------------------------
  // UI
  // ------------------------------------------------

  return (
    <main className="app-shell">

      {/* Header */}

      <header className="topbar">
        <button
          className="brand"
          onClick={home}
          aria-label="Back to home"
        >
          <span className="brand-mark">✦</span>
          <span>Little Explorers</span>
        </button>

        <div className="topbar-right">
          <span className={`connection ${
            connected ? 'is-online' : 'is-offline'
          }`}>
            <i />
            {connected ? 'Connected' : 'Backend not connected'}
          </span>

          <span className="screen-label">
            {screenNames[screen]}
          </span>
        </div>
      </header>

      <div className="page-content">

        {/* Welcome Screen */}

        {screen === 'welcome' && (
          <section className="welcome-card">

            <div className="welcome-copy">
              <span className="eyebrow">
                A little game for curious minds
              </span>

              <h1>
                Let’s Learn<br />
                <span>and Play!</span>
              </h1>

              <p>
                Look, explore, and find familiar objects
                in a fun learning adventure.
              </p>

              <button
                className="primary-btn"
                onClick={() => setScreen('mode')}
              >
                Start Learning <span>→</span>
              </button>

              <p className="helper-text">
                A grown-up can help you get ready.
              </p>

              <div className="backend-mini">
                Backend profile: <b>{backend?.user_id || 'Waiting…'}</b>
                {' · '}Pack: <b>{backend?.pack_title || 'Guest'}</b>
              </div>
            </div>

            <div className="welcome-art">
              <div className="art-sun">☀️</div>
              <div className="art-cloud cloud-one">☁️</div>
              <div className="art-cloud cloud-two">☁️</div>
              <div className="art-kid">🧒🏻</div>
              <div className="art-block block-a">A</div>
              <div className="art-block block-b">B</div>
              <div className="art-block block-c">C</div>
              <div className="art-toy">🧸</div>
              <div className="art-star">⭐</div>
            </div>

          </section>
        )}

        {/* Mode Selection */}

        {screen === 'mode' && (
          <section className="standard-panel">

            <div className="section-heading">
              <span className="eyebrow">
                Choose how you want to play
              </span>

              <h1>How would you like to play?</h1>

              <p>
                Both ways let you play the same finding game.
              </p>
            </div>

            <div className="mode-grid">

              <button
                className="mode-card"
                onClick={() => chooseMode('hand')}
              >
                <span className="mode-icon">👆</span>
                <h2>Hand Gestures</h2>
                <p>
                  Use your hand to point and choose an object.
                </p>
                <span className="card-action">
                  Choose this way →
                </span>
              </button>

              <button
                className="mode-card"
                onClick={() => chooseMode('eye')}
              >
                <span className="mode-icon">👀</span>
                <h2>Eye Tracking</h2>
                <p>
                  Look at an object and hold your look to choose.
                </p>
                <span className="card-action">
                  Choose this way →
                </span>
              </button>

            </div>

            {socketError && (
              <p className="error-note">{socketError}</p>
            )}

            <button className="text-btn" onClick={home}>
              ← Back
            </button>

          </section>
        )}

        {/* Hand Gesture Tutorial */}

        {screen === 'hand' && (
          <section className="standard-panel">

            <div className="section-heading">
              <span className="eyebrow">Let’s get ready</span>
              <h1>Let’s learn the hand gesture!</h1>
              <p>Follow these three simple steps.</p>
            </div>

            <div className="steps-grid">

              <article className="step-card">
                <span>🖐️</span>
                <b>1. Show your hand</b>
                <p>
                  Keep your hand where the camera can see it.
                </p>
              </article>

              <article className="step-card">
                <span>👆</span>
                <b>2. Move your hand</b>
                <p>
                  Point towards the object you want to choose.
                </p>
              </article>

              <article className="step-card">
                <span>🤏</span>
                <b>3. Pinch to choose</b>
                <p>
                  Bring your finger and thumb together to select.
                </p>
              </article>

            </div>

            <div className="info-banner">
              Tracking:
              <b>{backend?.tracking ? 'Detected' : 'Not detected'}</b>
              {' · '}
              Last gesture:
              <b>{backend?.last_gesture || 'None yet'}</b>
            </div>

            <div className="button-row">
              <button
                className="text-btn"
                onClick={() => setScreen('mode')}
              >
                Back
              </button>

              <button
                className="primary-btn"
                onClick={() => setScreen('camera')}
              >
                Continue →
              </button>
            </div>

          </section>
        )}

        {/* Eye Tracking Calibration */}

        {screen === 'eye' && (
          <section className="standard-panel">

            <div className="section-heading">
              <span className="eyebrow">Let’s get ready</span>
              <h1>Look at the targets</h1>
              <p>Visual layout preview only. Real gaze calibration is not yet implemented.</p>
            </div>

            <div className="calibration-box">

              {['one', 'two', 'three', 'four'].map(n => (
                <span key={n} className={`target target-${n}`} aria-hidden="true" />
              ))}

              <div className="calibration-center">👁️</div>

              <span className="calibration-hint">
                UI preview only — gaze calibration is not connected
              </span>

            </div>

            <p className="warning-note" role="status">
              Eye tracking and gaze dwell are not available in this build.
              Clicking a dot would not calibrate a camera.
            </p>
            <div className="button-row centered">
              <button className="secondary-btn" onClick={() => setScreen('mode')}>
                Back to mode selection
              </button>
            </div>

          </section>
        )}

        {/* Camera and Object Setup */}

        {screen === 'camera' && (
          <section className="standard-panel">

            <div className="section-heading">
              <span className="eyebrow">Almost ready</span>
              <h1>Let’s get things ready!</h1>
              <p>Make sure the objects are easy to see.</p>
            </div>

            <div className="setup-grid">

              <div className="camera-placeholder">
                <span>📷</span>
                <b>Camera preview area</b>
                <small>
                  No video is transmitted over WebSocket. The object detector
                  sends class names and box metadata only.
                </small>
              </div>

              <div className="setup-side">

                <h2>Object area</h2>

                <div className="object-row">
                  <span>🍎</span>
                  <span>📘</span>
                  <span>🥤</span>
                </div>

                <div className="readiness">
                  <b>
                    Camera: {backend?.camera_ready ? 'Ready' : 'Not ready'}
                  </b>
                  <p>{status}</p>
                </div>

                <div className={`readiness ${
                  backend?.lighting === 'low' ? 'warning' : ''
                }`}>
                  <b>Lighting: {backend?.lighting || 'unknown'}</b>
                  <p>
                    {backend?.lighting === 'low'
                      ? 'Increase lighting to improve tracking.'
                      : 'Lighting status from backend.'}
                  </p>
                </div>

                <div className="readiness">
                  <b>Object detector: {backend?.object_detection_active ? 'Active' : 'Inactive'}</b>
                  <p>{detections.length ? `${detections.length} object(s) detected` : 'No verified objects in the current frame'}</p>
                </div>

                <div className="readiness">
                  <b>Device</b>
                  <p>
                    {backend?.connected_device ||
                      'No registered device detected'}
                  </p>
                </div>

              </div>
            </div>

            <div className="button-row">

              <button
                className="text-btn"
                onClick={() =>
                  setScreen(mode === 'hand' ? 'hand' : 'eye')
                }
              >
                Back
              </button>

              <button
                className="primary-btn"
                disabled={!connected || !backend}
                onClick={() => {
                  setLocalSelection('');
                  setScreen('game');
                }}
              >
                Open game →
              </button>

            </div>

          </section>
        )}

        {/* Game Screen */}

        {screen === 'game' && (
          <section className="game-layout">

            <div className="game-main">

              <div className="game-topline">

                <span className="tag">
                  {engineMode === 'gaze'
                    ? '👀 EYE TRACKING'
                    : '👆 HAND GESTURES'}
                </span>

                <span className="question-count">
                  {total
                    ? `Question ${questionNo} of ${total}`
                    : 'Waiting for question'}
                </span>

              </div>

              <div className="progress-track">
                <span style={{
                  width: `${
                    total
                      ? (questionDone / total) * 100
                      : 0
                  }%`
                }} />
              </div>

              <h1>
                {question?.prompt ||
                  'Waiting for the backend question…'}
              </h1>

              <p className="game-instruction">
                Choose the object that matches the question.
              </p>

              <div className="object-stage">

                <span className="big-object" aria-hidden="true">🔎</span>

                <span className="stage-caption">
                  Find the object! The answer is not shown here.
                </span>
                <span className="detection-note">
                  {detections.length
                    ? `${detections.length} real object detection(s) received`
                    : 'Waiting for real object detections'}
                </span>

              </div>

              {backend?.show_hint && question?.hint && (
                <p className="hint-note">💡 Hint: {question.hint}</p>
              )}
              {notices.map(notice => (
                <p key={notice.code} className={notice.blocking ? 'warning-note' : 'hint-note'} role="status">
                  {notice.message}
                </p>
              ))}
              {backend?.input_blocked && (
                <p className="warning-note">Selections are blocked until sensors are ready.</p>
              )}

              {choices.length ? (

                <div className="choices-grid">

                  {choices.map(choice => (

                    <button
                      className={`answer-card ${
                        localSelection === choice ? 'selected' : ''
                      }`}
                      key={choice}
                      onClick={() => mousePreview(choice)}
                      title="Local preview only; does not submit an answer"
                    >

                      <span>{icons[choice] || '❔'}</span>
                      <b>{choice}</b>

                    </button>

                  ))}

                </div>

              ) : (

                <p className="info-banner">
                  No active backend question is available yet.
                </p>

              )}

              <p className="dev-note">
                Mouse selection is a local UI preview only;
                it is not sent to the backend. Sensor selections
                are processed by the backend.
              </p>

              {localSelection && (
                <p className="preview-note">
                  Local preview selection:
                  <b>{localSelection}</b>
                  {' — not sent to backend.'}
                </p>
              )}

            </div>

            <aside className="game-aside">

              <h3>Your progress</h3>

              <div className="progress-number">
                  {questionDone}
                <small> / {total || '—'}</small>
              </div>

              <p>{status}</p>

              <div className="mini-stars">
                ⭐ ⭐ ⭐ ⭐ ⭐
              </div>

              <div className="sensor-note">

                <b>Sensor connection</b>

                <span>
                  {connected
                    ? 'Backend connected'
                    : 'Waiting for backend'}
                </span>

                <span>
                  Object detector: {backend?.object_detection_active ? 'Active' : 'Inactive'}
                </span>

                <span>
                  Visible objects: {detections.map(d => `${d.object} (${d.target_id})`).join(', ') || 'none'}
                </span>

                <span>
                  Tracking: {backend?.tracking
                    ? 'Detected'
                    : 'Not detected'}
                </span>

                <span>
                  Camera: {backend?.camera_ready
                    ? 'Ready'
                    : 'Not ready'}
                </span>

                <span>
                  Gesture: {backend?.last_gesture || '—'}
                </span>

                <span>
                  Lighting: {backend?.lighting || 'unknown'}
                </span>

                <span>
                  Device: {backend?.connected_device || '—'}
                </span>

              </div>

            </aside>

          </section>
        )}

        {/* Feedback Screen */}

        {screen === 'feedback' && (
          <section className="standard-panel feedback-panel">

            <div className={`feedback-icon ${feedbackType}`}>
              {feedbackType === 'correct' ? '🎉' : '💛'}
            </div>

            <span className="eyebrow">
              Backend game update
            </span>

            <h1>
              {feedbackType === 'correct'
                ? 'Great job!'
                : 'Almost there!'}
            </h1>

            <p>
              {feedbackType === 'correct'
                ? 'The backend confirmed a correct selection.'
                : 'The backend recorded an incorrect selection. Try the same question again.'}
            </p>

            <p className="backend-status-line">
              Backend status: {status}
            </p>

            <button
              className="primary-btn"
              onClick={continueAfterFeedback}
              disabled={nextPending.current}
            >
              {feedbackType === 'correct'
                ? (backend?.completed ? 'View results →' : backend?.awaiting_next ? 'Next Object →' : 'Continue →')
                : 'Try again →'}
            </button>

          </section>
        )}

        {/* Results Screen */}

        {screen === 'results' && (
          <section className="standard-panel results-panel">

            <div className="results-art">
              🏆 ⭐ 🎈
            </div>

            <span className="eyebrow">
              You did it!
            </span>

            <h1>
              Great job completing the activity!
            </h1>

            <div className="results-stats">

              <div>
                <strong>
                  {questionDone}
                  /{total}
                </strong>

                <span>Questions completed</span>
              </div>

              <div>
                <strong>
                  {backend?.first_try_correct || 0}/{total}
                </strong>

                <span>Correct on first try</span>
              </div>

            </div>

            <p>
              Wrong attempts: {backend?.wrong_attempts || 0}
            </p>

            <div className="button-row centered">

              <button
                className="primary-btn"
                onClick={restart}
              >
                ↻ Play again
              </button>

              <button
                className="secondary-btn"
                onClick={home}
              >
                ⌂ Back to home
              </button>

            </div>

          </section>
        )}

      </div>

      {/* Footer */}

      <footer className="footer">

        <span>
          Little Explorers · HCI Phase II
        </span>

        <span className="footer-status">
          Backend: {connected ? 'Connected' : 'Not connected'}
          {' · '}
          {backend?.event_source || 'No event source'}
          {isDemo ? ' · DEMO DATA' : ''}
        </span>

      </footer>

      {socketError && (
        <div className="socket-error" role="status">
          {socketError}
        </div>
      )}

    </main>
  );
}

createRoot(document.getElementById('root')).render(<App />);
