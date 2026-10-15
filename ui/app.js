// Rythmo: the band is time. Everything that happens, happens at the bar.
import { Api, Capture, Player } from '/core.js';

const $ = s => document.querySelector(s);
const el = {
  body: document.body, picture: $('#picture'), preview: $('#preview'), take: $('#take'), pictureNote: $('#pictureNote'),
  picToggle: $('#picToggle'), band: $('#band'), strip: $('#strip'), bar: $('#bar'), bandNote: $('#bandNote'),
  mic: $('#mic'), micLabel: $('#micLabel'), transport: $('#transport'), loopLabel: $('#loopLabel'), tc: $('#tc'),
  sheet: $('#sheet'), sheetTab: $('#sheetTab'), sheetClose: $('#sheetClose'), sheetLoop: $('#sheetLoop'),
  queryLine: $('#queryLine'), opts: $('#opts'), alpha: $('#alpha'), alphaOut: $('#alphaOut'), keepAudio: $('#keepAudio'),
  redetect: $('#redetect'), download: $('#download'), classRows: $('#classRows'), timings: $('#timings'),
};

const REC_SECONDS = 10;
const CLIP_SECONDS = 5;       // every ESC-50 clip is 5 s; it loops over the take
const GAP_SECONDS = 2.6;      // strip space between takes
const PREROLL = 1.2;          // seconds the winner travels toward the bar before the sound starts
const LINES = 4;              // the playing cue plus three runners-up
const VISIBLE_SECONDS = 8.5;  // how much of the strip the band shows
const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
const params = new URLSearchParams(location.search);
if (params.has('shot')) el.body.classList.add('shot');
window.__errors = [];
addEventListener('error', e => window.__errors.push(String(e.message || e)));
addEventListener('unhandledrejection', e => window.__errors.push(String(e.reason && e.reason.message || e.reason)));

let PPS = 170;      // pixels per second on the strip
let bandT = 0;      // strip seconds under the bar
let state = 'boot';
let takes = [];
let current = null;
let capture = null;
let player = null;
let busy = false;

const setState = s => { state = s; el.body.dataset.state = s; if (params.has('shot')) document.title = `Rythmo ${s}`; };
const wait = ms => new Promise(r => setTimeout(r, ms));
const linear = x => x;
const easeOutExpo = x => (x >= 1 ? 1 : 1 - Math.pow(2, -10 * x));
const label = c => c.replaceAll('_', ' ');
const fmtTc = t => { t = Math.max(0, t || 0); const m = Math.floor(t / 60), s = Math.floor(t % 60), d = Math.floor((t * 10) % 10); return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}.${d}`; };

function tween(from, to, ms, ease, onUpdate) {
  return new Promise(res => {
    const t0 = performance.now();
    const step = now => {
      const x = Math.min(1, (now - t0) / ms);
      onUpdate(from + (to - from) * ease(x));
      if (x < 1) requestAnimationFrame(step); else res();
    };
    requestAnimationFrame(step);
  });
}

function note(text, kind = '') {
  el.bandNote.textContent = text || '';
  el.bandNote.hidden = !text;
  el.bandNote.className = `band-note ${kind}`;
}
function flashBar() { el.bar.classList.remove('flash'); void el.bar.offsetWidth; el.bar.classList.add('flash'); }

// ---------- strip layout ----------
function layout() {
  PPS = Math.max(90, el.band.clientWidth / VISIBLE_SECONDS);
  for (const t of takes) {
    t.el.style.left = `${t.originT * PPS}px`;
    t.el.style.width = `${t.D * PPS}px`;
    t.el.querySelectorAll('.count').forEach(c => { c.style.left = `${c.dataset.t * PPS}px`; });
    drawTrace(t);
    t.el.querySelectorAll('.line').forEach(b => { b.style.width = `${t.D * PPS}px`; });
    t.el.querySelectorAll('.cue').forEach(c => { c.style.left = `${c.dataset.j * CLIP_SECONDS * PPS}px`; c.style.width = `${CLIP_SECONDS * PPS - 18}px`; });
    fitCues(t);
  }
}
addEventListener('resize', layout);

function frame() {
  if (state === 'playing' && current && !el.take.paused) bandT = current.originT + el.take.currentTime;
  el.strip.style.transform = `translate3d(${(-bandT * PPS).toFixed(2)}px,0,0)`;
  if (state === 'playing' && current) el.tc.textContent = fmtTc(el.take.currentTime);
  requestAnimationFrame(frame);
}

function newTake() {
  const n = takes.length + 1;
  const last = takes[takes.length - 1];
  const originT = last ? last.originT + last.D + GAP_SECONDS : 0;
  const div = document.createElement('div');
  div.className = 'take';
  div.innerHTML = `<div class="take-mark"><span>Loop ${n}</span></div><svg class="trace" preserveAspectRatio="none"><polygon points=""></polygon></svg><div class="cues"></div>`;
  el.strip.appendChild(div);
  const t = { n, originT, D: REC_SECONDS, el: div, trace: [], lines: [], lineEls: [], blob: null, result: null };
  takes.forEach(p => p.el.classList.add('past'));
  takes.push(t);
  div.addEventListener('click', e => { if (t !== current && !e.target.closest('.line')) showTake(t); });
  layout();
  return t;
}

function addCountdown(t) {
  [-3, -2, -1].forEach(k => {
    const c = document.createElement('div');
    c.className = 'count'; c.dataset.t = k; c.textContent = String(-k);
    c.style.left = `${k * PPS}px`;
    t.el.appendChild(c);
  });
}

function drawTrace(t) {
  const svg = t.el.querySelector('.trace');
  const w = t.D * PPS, h = el.band.clientHeight;
  svg.setAttribute('viewBox', `0 0 ${w} ${h}`); svg.style.width = `${w}px`;
  const mid = h * 0.5, amp = h * 0.16;                       // a quiet pen trace under the lettering, never over it
  const lvl = v => Math.sqrt(Math.min(1, v * 4));             // compress: a clap and a word both read, neither dominates
  const top = t.trace.map(([s, v]) => `${(s * PPS).toFixed(1)},${(mid - lvl(v) * amp).toFixed(1)}`);
  const bot = t.trace.map(([s, v]) => `${(s * PPS).toFixed(1)},${(mid + lvl(v) * amp).toFixed(1)}`).reverse();
  svg.querySelector('polygon').setAttribute('points', top.concat(bot).join(' '));
}

// ---------- cues ----------
function renderLines(t) {
  const cues = t.el.querySelector('.cues');
  cues.innerHTML = '';
  t.lineEls = t.lines.map((c, i) => {
    const b = document.createElement('button');
    b.type = 'button';
    b.className = `line l${i}`;
    b.dataset.family = c.family;
    b.style.width = `${t.D * PPS}px`;
    const reps = Math.ceil(t.D / CLIP_SECONDS);
    for (let j = 0; j < reps; j++) {
      const s = document.createElement('span');
      s.className = 'cue'; s.dataset.j = j;
      s.style.left = `${j * CLIP_SECONDS * PPS}px`; s.style.width = `${CLIP_SECONDS * PPS - 18}px`;
      s.style.setProperty('--delay', `${i * 90 + j * 140}ms`);
      s.innerHTML = `<span class="cue-text"></span>`;
      s.firstElementChild.textContent = label(c.class);
      b.appendChild(s);
    }
    b.addEventListener('click', () => promote(t, b));
    cues.appendChild(b);
    return b;
  });
  updateLineLabels(t);
  requestAnimationFrame(() => fitCues(t));
}

function fitCues(t) {
  t.el.querySelectorAll('.cue').forEach(cue => {
    const txt = cue.firstElementChild;
    txt.style.letterSpacing = '';
    const W = cue.clientWidth - 10, nat = Math.max(1, txt.offsetWidth);
    const fs = parseFloat(getComputedStyle(txt).fontSize) || 16;
    const need = W / nat;
    const k = Math.min(2.4, Math.max(1, need));              // marker letters elongated to the duration, up to a limit
    let ls = 0;
    if (need > k) {                                           // a little tracking, never more than 0.12em
      const n = Math.max(1, txt.textContent.length - 1);
      ls = Math.min(0.12 * fs, (W / k - nat) / n);
      txt.style.letterSpacing = `${ls.toFixed(2)}px`;
    }
    txt.style.transform = `scaleX(${k.toFixed(3)})`;
    const end = Math.min(W, (nat + ls * Math.max(0, txt.textContent.length - 1)) * k);
    cue.style.setProperty('--text-end', `${(end + 10).toFixed(0)}px`);   // the rest of the cue is held as a rule
  });
}

function updateLineLabels(t) {
  t.lineEls.forEach((b, i) => {
    const c = t.lines[i];
    b.setAttribute('aria-label', `${c.caption}, rank ${c.rank}, z ${c.z.toFixed(1)}${i === 0 ? ', playing' : ', press to play'}`);
    b.setAttribute('aria-pressed', i === 0 ? 'true' : 'false');
  });
}

async function promote(t, btn) {
  const i = t.lineEls.indexOf(btn);
  if (i <= 0 || t !== current) return;
  [t.lines[0], t.lines[i]] = [t.lines[i], t.lines[0]];
  [t.lineEls[0], t.lineEls[i]] = [t.lineEls[i], t.lineEls[0]];
  t.lineEls.forEach((b, k) => { b.className = `line l${k}`; });
  updateLineLabels(t);
  setTimeout(() => fitCues(t), 480);
  await player.play(t.lines[0].url);
  flashBar();
  renderSheet(t);
}

// Pull any of the 50 classes onto the band as the playing sound (from the sheet).
async function pull(t, cls) {
  if (t !== current) return;
  const idx = t.lines.findIndex(l => l.class === cls.class);
  if (idx === 0) return;
  if (idx > 0) return promote(t, t.lineEls[idx]);
  t.lines = [cls, ...t.lines.slice(0, LINES - 1)];
  renderLines(t);
  requestAnimationFrame(() => t.el.querySelectorAll('.cue').forEach(c => c.classList.add('written')));
  await player.preload([cls.url]);
  await player.play(cls.url);
  flashBar();
  renderSheet(t);
}

// ---------- camera ----------
async function openCamera() {
  if (capture && capture.stream) return true;
  try {
    capture = new Capture(el.preview, player.ctx);
    await capture.open();
    el.pictureNote.hidden = true;
    return true;
  } catch (e) {
    setState('nocam');
    el.pictureNote.textContent = 'The camera is off. In Safari settings for this site, allow Camera and Microphone, then reload.';
    el.pictureNote.hidden = false;
    note('');
    return false;
  }
}

function currentOpts() {
  const f = new FormData(el.opts);
  return { query: f.get('query') || 'both', mode: f.get('mode') || 'both', alpha: Number(el.alpha.value), k: 8 };
}

// ---------- the take ----------
function unlockMedia() {
  // Safari only unlocks the audio context and media elements inside a user gesture; play() here, even on an
  // empty element, lets the later programmatic play() of the take go through.
  player.ctx.resume();
  for (const v of [el.take, el.preview]) {
    const p = v.play();
    if (p && p.catch) p.catch(() => {});
  }
}

async function runTake() {
  if (busy) return;
  unlockMedia();
  if (!(await openCamera())) return;
  busy = true;
  el.mic.disabled = true;
  try {
    if (current && state === 'playing') { el.take.pause(); player.stop(); }
    const t = newTake();
    current = t;
    el.loopLabel.textContent = `Loop ${t.n}`;
    el.transport.disabled = true; el.transport.dataset.playing = 'false';
    note('');
    setState('countdown');
    el.micLabel.textContent = 'Ready';
    addCountdown(t);
    bandT = t.originT - 3.6;
    await tween(bandT, t.originT, 3600, linear, v => { bandT = v; });

    setState('recording');
    el.micLabel.textContent = 'Recording';
    const blob = await capture.record(REC_SECONDS, (s) => {
      bandT = t.originT + s;
      el.tc.textContent = fmtTc(s);
      el.micLabel.textContent = `Recording ${fmtTc(s)}`;
      t.trace.push([s, capture.level()]);
      if (t.trace.length % 2 === 0) drawTrace(t);
    });
    t.blob = blob;
    el.micLabel.textContent = 'Record again';
    await detect(t, true);
  } catch (e) {
    console.error(e);
    setState('error');
    const msg = e && e.name === 'NotAllowedError'
      ? 'Safari blocked the camera, microphone or playback. In Safari settings for this site, allow Camera and Microphone and set Auto-Play to Allow All, then reload.'
      : (e.message && e.message.includes('fetch') ? 'Lost the line to the GPU box. Run ./ui.sh and try again.' : `Something broke: ${e.message || e}`);
    note(msg, 'error');
  } finally {
    busy = false;
    el.mic.disabled = false;
  }
}

async function detect(t, firstTime) {
  setState('detecting');
  el.loopLabel.textContent = `Loop ${t.n}, detecting`;
  note('detecting');
  const req = Api.match(t.blob, currentOpts());
  if (!reduced && firstTime) {
    el.strip.classList.add('whip');
    await tween(bandT, t.originT - PREROLL, 750, easeOutExpo, v => { bandT = v; });
    el.strip.classList.remove('whip');
  } else {
    bandT = t.originT - PREROLL;
  }
  const res = await req;
  note('');
  applyResult(t, res);
  await loadTakeVideo(t);
  setState('writing');
  await player.preload(t.lines.map(l => l.url));
  await wait(reduced ? 0 : 650);
  if (!reduced) await tween(t.originT - PREROLL, t.originT, PREROLL * 1000, linear, v => { bandT = v; });
  await player.play(t.lines[0].url);
  el.take.currentTime = 0;
  setState('playing');
  el.loopLabel.textContent = `Loop ${t.n}`;
  el.transport.disabled = false;
  el.picToggle.hidden = false;
  el.redetect.disabled = false; el.download.disabled = false;
  try {
    await el.take.play();
  } catch (e) {
    if (e && e.name === 'NotAllowedError') {        // Safari refused to roll without a tap: ask for one
      el.transport.dataset.playing = 'false';
      note('press play to roll the take');
      return;
    }
    throw e;
  }
  el.take.muted = !el.keepAudio.checked;
  el.transport.dataset.playing = 'true';
  flashBar();
}

function applyResult(t, res) {
  t.result = res;
  t.lines = res.classes.slice(0, LINES).map(c => ({ ...c }));
  renderLines(t);
  requestAnimationFrame(() => t.el.querySelectorAll('.cue').forEach(c => c.classList.add('written')));
  const q = res.query;
  if (q.requested !== q.used) {
    const why = q.has_audio ? 'silent take, matched on frames only' : 'no audio in the take, matched on frames only';
    note(why);
    setTimeout(() => { if (state === 'playing') note(''); }, 4000);
  }
  renderSheet(t);
}

function loadTakeVideo(t) {
  return new Promise((res, rej) => {
    const v = el.take;
    v.muted = !el.keepAudio.checked;
    v.muted = true;                                   // always start muted (autoplay rules); unmute after it rolls
    const done = () => { v.removeEventListener('canplay', done); v.currentTime = 0; res(); };
    v.addEventListener('canplay', done);
    v.addEventListener('error', () => rej(new Error('the take could not be loaded')), { once: true });
    v.poster = t.result.poster_url || '';
    v.src = t.result.video_url;
    v.load();
  });
}

function showTake(t) {
  if (!t.result) return;
  if (current) { el.take.pause(); player.stop(); current.el.classList.add('past'); }
  current = t;
  t.el.classList.remove('past');
  el.loopLabel.textContent = `Loop ${t.n}`;
  loadTakeVideo(t).then(async () => {
    await player.play(t.lines[0].url);
    await el.take.play();
    setState('playing');
    el.transport.dataset.playing = 'true';
    renderSheet(t);
  });
}

// ---------- sheet ----------
function renderSheet(t) {
  const r = t.result; if (!r) return;
  el.sheetLoop.textContent = `loop ${t.n}`;
  const q = r.query;
  const how = { both: 'frames and audio', video: 'frames only', audio: 'audio only' }[q.used];
  const against = { both: `blend, ${Math.round(r.alpha * 100)}% audio`, audio: 'library audio', text: 'captions' }[r.mode];
  let line = `Detected from ${how}, scored against ${against}.`;
  if (q.used !== 'video' && q.events_s != null && q.audio_s != null && q.events_s < q.audio_s) line += ` Of ${q.audio_s.toFixed(0)} s of audio, the ${q.events_s.toFixed(1)} s with sound in them were embedded.`;
  if (q.requested !== q.used) {
    const lv = q.mean_db == null ? '' : ` averaged ${q.mean_db.toFixed(0)} dB${q.peak_db == null ? '' : ` with a peak of ${q.peak_db.toFixed(0)} dB`},`;
    line += q.has_audio ? ` The take's audio${lv} which is room tone, so it was left out.` : ' The take had no audio track.';
  }
  el.queryLine.textContent = line;
  const onBand = new Set(t.lines.map(l => l.class));
  el.classRows.innerHTML = '';
  r.classes.forEach(c => {
    const tr = document.createElement('tr');
    tr.dataset.family = c.family;
    if (c.class === t.lines[0].class) tr.classList.add('on');
    if (onBand.has(c.class)) tr.classList.add('top');
    tr.innerHTML = `<td>${c.rank}</td><td><span class="dot"></span>${label(c.class)}</td><td>${c.z.toFixed(2)}</td><td>${c.text.toFixed(3)}</td><td>${c.audio.toFixed(3)}</td>`;
    tr.title = c.caption;
    tr.addEventListener('click', () => pull(t, c));
    el.classRows.appendChild(tr);
  });
  const tm = r.timings;
  el.timings.textContent = tm ? `Transcode ${tm.transcode_s} s, embed ${tm.embed_s} s, ${tm.total_s} s in all. Paths: visual ${r.paths.text.slice(0, 3).map(d => label(d.class)).join(', ')}; audio ${r.paths.audio.slice(0, 3).map(d => label(d.class)).join(', ')}.` : '';
}

function toggleSheet(open) {
  const o = open ?? !el.sheet.classList.contains('open');
  el.sheet.hidden = false;
  requestAnimationFrame(() => el.sheet.classList.toggle('open', o));
  el.sheetTab.setAttribute('aria-expanded', String(o));
  if (o) el.sheetClose.focus(); else el.sheetTab.focus();
}

// ---------- transport ----------
function togglePlay() {
  if (state !== 'playing' || !current) return;
  if (el.take.paused) {
    el.take.play().then(() => { el.take.muted = !el.keepAudio.checked; flashBar(); if (el.bandNote.textContent.startsWith('press play')) note(''); }).catch(() => {});
    el.transport.dataset.playing = 'true'; el.transport.setAttribute('aria-label', 'Pause'); el.picToggle.setAttribute('aria-label', 'Pause the take');
  }
  else { el.take.pause(); el.transport.dataset.playing = 'false'; el.transport.setAttribute('aria-label', 'Play'); el.picToggle.setAttribute('aria-label', 'Play the take'); }
}

// ---------- wiring ----------
el.mic.addEventListener('click', runTake);
el.transport.addEventListener('click', togglePlay);
el.picToggle.addEventListener('click', togglePlay);
el.sheetTab.addEventListener('click', () => toggleSheet());
el.sheetClose.addEventListener('click', () => toggleSheet(false));
el.alpha.addEventListener('input', () => { el.alphaOut.textContent = `${Math.round(el.alpha.value * 100)}% audio`; });
el.keepAudio.addEventListener('change', () => { el.take.muted = !el.keepAudio.checked; });
el.redetect.addEventListener('click', async () => {
  if (!current || !current.blob || busy) return;
  busy = true; el.redetect.disabled = true;
  try { el.take.pause(); player.stop(); await detect(current, false); }
  catch (e) { setState('error'); note(`Detection failed: ${e.message || e}`, 'error'); }
  finally { busy = false; el.redetect.disabled = false; }
});
el.download.addEventListener('click', async () => {
  if (!current || !current.result) return;
  el.download.disabled = true; el.download.textContent = 'Rendering';
  try {
    const url = await Api.mux(current.result.id, current.lines[0].clip, el.keepAudio.checked);
    const a = document.createElement('a'); a.href = url; a.download = `rythmo-loop${current.n}-${current.lines[0].class}.mp4`; document.body.appendChild(a); a.click(); a.remove();
  } catch (e) { note(`Could not render the dub: ${e.message || e}`, 'error'); }
  finally { el.download.disabled = false; el.download.textContent = 'Download the dub'; }
});
addEventListener('keydown', e => {
  if (e.target.matches('input, textarea, select')) return;
  if (e.key === ' ') { e.preventDefault(); if (state === 'playing') togglePlay(); else if (state === 'idle' || state === 'error') runTake(); }
  else if (e.key === 'r' || e.key === 'R') runTake();
  else if (e.key === 's' || e.key === 'S') toggleSheet();
  else if (e.key === 'Escape') toggleSheet(false);
  else if (/^[1-4]$/.test(e.key) && current) { const b = current.lineEls[Number(e.key) - 1]; b && promote(current, b); }
});

// ---------- boot ----------
async function boot() {
  player = new Player(el.take);
  window.__rythmo = { get takes() { return takes; }, get current() { return current; }, get player() { return player; }, get state() { return state; } };
  layout();
  requestAnimationFrame(frame);
  document.fonts && document.fonts.ready.then(layout);

  if (params.get('shot') === 'result') {         // screenshot fixture: a real earlier result, no camera needed
    const res = await (await fetch('/fixture.json')).json();
    const t = newTake(); current = t; t.blob = null;
    for (let s = 0; s < REC_SECONDS; s += 1 / 30) t.trace.push([s, 0.03 + 0.12 * Math.abs(Math.sin(s * 3.1)) * (s > 4 && s < 6 ? 2.5 : 1)]);
    drawTrace(t);
    applyResult(t, res);
    note('');
    setState('playing');
    el.take.muted = true; el.take.poster = res.poster_url || ''; el.take.src = res.video_url;
    el.loopLabel.textContent = `Loop ${t.n}`; el.tc.textContent = fmtTc(2.4);
    el.transport.disabled = false; el.transport.dataset.playing = 'false';
    el.redetect.disabled = false; el.download.disabled = false;
    el.picToggle.hidden = false;
    if (params.get('sheet') === '1') toggleSheet(true);
    el.take.play().catch(() => {});
    await wait(500);
    el.take.pause();
    el.take.currentTime = 2.4; bandT = t.originT + 2.4; el.tc.textContent = fmtTc(2.4);
    return;
  }
  try {
    const h = await Api.health();
    if (!h.ok) throw new Error('model loading');
  } catch (e) {
    setState('error');
    note('Lost the line to the GPU box. Run ./ui.sh and try again.', 'error');
    return;
  }
  setState('idle');
  note(innerWidth < 720 ? 'press the mic' : 'step up and press the mic');
  await openCamera();
  if (params.get('autorun') === '1' && state === 'idle') runTake();   // headless end-to-end test hook
}
boot();
