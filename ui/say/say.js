// Spoken search. Press to talk: hold and release, or click to start and click to stop.
// The audio goes to the server as recorded and is embedded directly; nothing is transcribed.
const $ = s => document.querySelector(s);
const el = { body: document.body, talk: $('#talk'), label: $('#talkLabel'), ring: $('#ring'), status: $('#status'),
  form: $('#typeForm'), typed: $('#typed'), results: $('#results'), best: $('#bestVideo'), heard: $('#heard'),
  heardLabel: $('#heardLabel'), bestCaption: $('#bestCaption'), bestScore: $('#bestScore'), replay: $('#replay'), tiles: $('#tiles') };

const MAX_SECONDS = 12;
const TAP_MS = 350;                 // a press shorter than this is a click: recording continues until the next click
let state = 'idle';                 // idle | arming | listening | searching
let stream = null, rec = null, chunks = [], ctx = null, analyser = null, buf = null, raf = 0;
let pressedAt = 0, releasedWhileArming = false, clickMode = false, stopTimer = 0, lastQueryUrl = null;

const setState = s => { state = s; el.body.dataset.state = s; };
const status = (t, err = false) => { el.status.textContent = t; el.status.className = `status${err ? ' error' : ''}`; };
addEventListener('error', e => status(`Page error: ${e.message}`, true));
addEventListener('unhandledrejection', e => status(`Page error: ${e.reason && e.reason.message || e.reason}`, true));

async function openMic() {
  if (stream) return true;
  try {
    stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } });
    ctx = ctx || new (window.AudioContext || window.webkitAudioContext)();
    analyser = ctx.createAnalyser(); analyser.fftSize = 512; buf = new Float32Array(analyser.fftSize);
    ctx.createMediaStreamSource(stream).connect(analyser);
    return true;
  } catch (e) {
    status(`The microphone is off (${e.name}). Allow it for this site in Safari settings, then reload.`, true);
    return false;
  }
}

function mime() {
  const c = ['audio/mp4', 'audio/webm;codecs=opus', 'audio/webm'];
  return c.find(t => window.MediaRecorder && MediaRecorder.isTypeSupported(t)) || '';
}

function meter() {
  if (!analyser) return;
  analyser.getFloatTimeDomainData(buf);
  let s = 0; for (let i = 0; i < buf.length; i++) s += buf[i] * buf[i];
  const lvl = Math.min(1, Math.sqrt(s / buf.length) * 6);
  el.ring.style.transform = `scale(${(1 + lvl * 0.45).toFixed(3)})`;
  raf = requestAnimationFrame(meter);
}

async function startTalk() {
  if (state !== 'idle') return;
  setState('arming'); el.label.textContent = 'Starting mic';
  if (ctx) ctx.resume();
  if (!(await openMic())) { setState('idle'); el.label.textContent = 'Hold to talk'; return; }
  if (state !== 'arming') return;
  chunks = [];
  const t = mime();
  rec = new MediaRecorder(stream, t ? { mimeType: t } : undefined);
  rec.ondataavailable = e => { if (e.data && e.data.size) chunks.push(e.data); };
  rec.onerror = e => status(`Recorder error: ${e.error && e.error.message || 'unknown'}`, true);
  rec.start();
  clickMode = releasedWhileArming;      // let go before the mic was ready: keep going until the next click
  setState('listening');
  el.label.textContent = clickMode ? 'Click to stop' : 'Listening';
  status(clickMode ? 'Listening. Click the mic again when you are done.' : 'Listening. Release when you are done.');
  raf = requestAnimationFrame(meter);
  stopTimer = setTimeout(stopTalk, MAX_SECONDS * 1000);
}

function stopTalk() {
  if (state !== 'listening' || !rec) return;
  clearTimeout(stopTimer);
  cancelAnimationFrame(raf); el.ring.style.transform = '';
  const r = rec; rec = null;
  setState('searching'); el.label.textContent = 'Searching';
  r.onstop = async () => {
    const blob = new Blob(chunks, { type: r.mimeType || 'audio/webm' });
    if (blob.size < 1500) { setState('idle'); el.label.textContent = 'Hold to talk'; status('Nothing was recorded. Hold the mic while you speak, or click it, speak, and click again.'); return; }
    await search(blob, null);
  };
  r.stop();
}

async function search(blob, text) {
  setState('searching'); el.label.textContent = 'Searching';
  status(text ? `Searching for "${text}"` : 'Embedding your voice and searching 1000 clips');
  try {
    const fd = new FormData();
    let r;
    if (blob) { fd.append('audio', blob, blob.type.includes('mp4') ? 'q.mp4' : 'q.webm'); fd.append('k', '9'); r = await fetch('/api/say', { method: 'POST', body: fd }); }
    else { fd.append('text', text); fd.append('k', '9'); r = await fetch('/api/ask', { method: 'POST', body: fd }); }
    if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
    render(await r.json());
  } catch (e) {
    status(`Search failed: ${e.message}`, true);
  } finally {
    setState('idle'); el.label.textContent = 'Hold to talk';
  }
}

function render(d) {
  const [top, ...rest] = d.results;
  el.results.hidden = false;
  el.best.src = top.url; el.best.poster = top.poster; el.best.play().catch(() => {});
  el.heardLabel.textContent = d.mode === 'speech' ? 'Closest caption to what you said' : 'Closest caption to what you typed';
  el.heard.textContent = d.heard;
  el.bestCaption.textContent = top.caption;
  el.bestScore.textContent = `similarity ${top.score.toFixed(3)}, ${top.z.toFixed(1)} standard deviations above the corpus mean, ${d.seconds} s`;
  lastQueryUrl = d.query_url || null;
  el.replay.hidden = !lastQueryUrl;
  el.tiles.innerHTML = '';
  rest.forEach((m, i) => {
    const li = document.createElement('li'); li.className = 'tile'; li.style.setProperty('--d', `${i * 50}ms`);
    li.innerHTML = `<button type="button"><span class="frame"><img alt=""><video muted loop playsinline preload="none"></video><span class="rank">${m.rank}</span></span><span class="cap"></span><span class="sc"></span></button>`;
    li.querySelector('img').src = m.poster; li.querySelector('video').src = m.url;
    li.querySelector('.cap').textContent = m.caption; li.querySelector('.sc').textContent = `${m.score.toFixed(3)}, z ${m.z.toFixed(1)}`;
    const v = li.querySelector('video');
    li.addEventListener('mouseenter', () => v.play().catch(() => {}));
    li.addEventListener('mouseleave', () => v.pause());
    li.querySelector('button').addEventListener('click', () => { el.best.src = m.url; el.best.poster = m.poster; el.best.play().catch(() => {}); el.bestCaption.textContent = m.caption; el.bestScore.textContent = `similarity ${m.score.toFixed(3)}, z ${m.z.toFixed(1)}`; });
    el.tiles.appendChild(li);
  });
  status(d.mode === 'speech' ? 'Say something else, or type it.' : 'Now say it out loud, in any language.');
}

// ---- press handling: hold-and-release, or click-and-click ----
function press() {
  pressedAt = performance.now(); releasedWhileArming = false;
  if (state === 'listening') { stopTalk(); return; }        // second click ends a click-mode recording
  if (state === 'idle') startTalk();
}
function release() {
  if (state === 'arming') { releasedWhileArming = true; return; }
  if (state !== 'listening') return;
  if (performance.now() - pressedAt < TAP_MS) {             // a tap: switch to click mode and keep listening
    clickMode = true; el.label.textContent = 'Click to stop'; status('Listening. Click the mic again when you are done.');
    return;
  }
  stopTalk();
}
el.talk.addEventListener('pointerdown', e => { e.preventDefault(); try { el.talk.setPointerCapture(e.pointerId); } catch {} press(); });
el.talk.addEventListener('pointerup', e => { e.preventDefault(); release(); });
el.talk.addEventListener('pointercancel', () => { if (state === 'listening' && !clickMode) stopTalk(); });
el.talk.addEventListener('click', e => e.preventDefault());
addEventListener('keydown', e => {
  if (e.code !== 'Space' || e.repeat || /INPUT|TEXTAREA/.test(e.target.tagName)) return;
  e.preventDefault(); press();
});
addEventListener('keyup', e => {
  if (e.code !== 'Space' || /INPUT|TEXTAREA/.test(e.target.tagName)) return;
  e.preventDefault(); release();
});
el.form.addEventListener('submit', e => { e.preventDefault(); const t = el.typed.value.trim(); if (t) search(null, t); });
el.replay.addEventListener('click', () => { if (lastQueryUrl) new Audio(lastQueryUrl).play(); });

const q0 = new URLSearchParams(location.search).get('q');
if (q0) { el.typed.value = q0; search(null, q0); }
fetch('/api/health').then(r => r.json()).then(h => { if (!h.ok) status('The model is still loading. Try again in a few seconds.', true); }).catch(() => status('Lost the line to the GPU box. Run ./ui.sh and try again.', true));
window.__say = { start: startTalk, stop: stopTalk, get state() { return state; } };
