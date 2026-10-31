import React, {useEffect, useState} from 'react';
import {createRoot} from 'react-dom/client';
import './style.css';

const icons = {apple:'🍎',book:'📘',cup:'🥤'};
function useGameSocket(){
 const [state,setState] = useState(null);
 const [connected,setConnected] = useState(false);
 useEffect(()=>{
  let ws, active = true, retry;
  const connect = () => {
   ws = new WebSocket('ws://127.0.0.1:8766');
   ws.onopen = () => active && setConnected(true);
   ws.onmessage = e => {try {const data=JSON.parse(e.data); if(data.type==='state' && active) setState(data.payload);}catch{}};
   ws.onclose = () => {if(active){setConnected(false);retry=setTimeout(connect,1500);}};
   ws.onerror = () => ws.close();
  };
  connect();
  return ()=>{active=false;clearTimeout(retry);ws?.close();};
 },[]);
 return [state,connected];
}
function App(){
 const [state,connected] = useGameSocket();
 const total = state?.total_questions ?? 0;
 const completedCount=state?.completed?total:(state?.question_index??0);
 return <main className="shell">
  <header className="nav"><span className="logo">✦ Find the Object</span><span className={'signal '+(connected?'online':'offline')}>{connected?'● Live socket connected':'○ Waiting for Python server'}</span></header>
  <section className="hero"><div><p className="eyebrow">HCI • Phase II integration test</p><h1>Learn with your eyes & hands! ✨</h1><p>Real-time events from the Python context engine appear here.</p></div><div className="sun">🌈 🧸 🍎</div></section>
  <div className="notice"><strong>Integration preview — not the final Figma implementation.</strong> The colored object cards below are sample content, not actual camera-detected objects. This interface cannot select with gaze or a hand yet; Ahmed will integrate the real views.</div>
  <section className="stats">
   <div><small>Learner profile</small><strong>{state?.user_id??'—'}</strong><span>{state?.level??'No state'}</span></div>
   <div><small>Input mode</small><strong>{state?.mode??'—'}</strong><span>Gaze/gesture planned</span></div>
   <div><small>Session progress</small><strong>{completedCount}/{total}</strong><span>Questions completed</span></div>
   <div><small>MediaPipe tracking</small><strong>{state?.tracking?'Detected':'Not detected'}</strong><span>{state?.last_gesture?`Last gesture: ${state.last_gesture}`:'No gesture recognized'}</span></div>
  </section>
  <div className="columns">
   <section className="game"><div className="tag">{state?.level?.toUpperCase()??'START THE SERVER'} LEARNING PACK</div>
    <h2>{state?.completed?'🎉 Great job!':state?.question?.prompt??'Waiting for questions…'}</h2>
    <p>These choice cards change when a registered demonstration device is detected.</p>
    <div className="choices">{(state?.question?.choices??[]).map((c,i)=><article key={i} className="choice"><span>{icons[c]??'🔎'}</span><strong>{c}</strong></article>)}</div>
    {state?.completed&&<div className="end">First-try correct: {state.first_try_correct}/{total} · Wrong attempts: {state.wrong_attempts}</div>}
   </section>
   <section className="side"><h3>Live context status</h3><div className="pill">🔵 {state?.status??'Run backend/server.py'}</div><dl><dt>Connected device</dt><dd>{state?.connected_device??'None'}</dd><dt>Lighting</dt><dd>{state?.lighting??'Unknown'}</dd><dt>Event origin</dt><dd>{state?.event_source??'None'}</dd><dt>Last source simulated?</dt><dd>{state?.demo_mode?'Yes — SIMULATION':'No (still verify hardware)'}</dd></dl><p className="small">Actual camera tracking, Bluetooth ID enrollment and gesture recognition must be demonstrated independently. Simulator events do not satisfy those marks.</p></section>
  </div>
  <footer>Phase II integration scaffold • All camera data should stay on the local computer</footer>
 </main>;
}
createRoot(document.getElementById('root')).render(<App/>);
