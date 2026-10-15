import { Capture } from '/core.js';
const $ = s => document.querySelector(s);
const el = { thumbs: $('#thumbs'), clipSearch: $('#clipSearch'), clipQuery: $('#clipQuery'), randomClip: $('#randomClip'),
  textForm: $('#textForm'), textBase: $('#textBase'), preview: $('#preview'), record: $('#record'), recStatus: $('#recStatus'),
  baseView: $('#baseView'), baseVideo: $('#baseVideo'), baseCaption: $('#baseCaption'), sliderList: $('#sliderList'), reset: $('#reset'),
  moved: $('#moved'), nearVideo: $('#nearVideo'), nearCaption: $('#nearCaption'), sounds: $('#sounds'), captions: $('#captions'),
  write: $('#write'), useHints: $('#useHints'), decodeStatus: $('#decodeStatus'), sentence: $('#sentence'), sentenceMeta: $('#sentenceMeta'), cands: $('#cands') };

let base = null, dirs = [], weights = {}, pointId = null, pointTimer = 0, capture = null, audio = null;
const post = async (url, body) => { const r = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }); if (!r.ok) throw new Error(`${r.status} ${await r.text()}`); return r.json(); };

// ---- tabs ----
document.querySelectorAll('.tabs [role="tab"]').forEach(b => b.addEventListener('click', () => {
  document.querySelectorAll('.tabs [role="tab"]').forEach(x => x.setAttribute('aria-selected', String(x === b)));
  document.querySelectorAll('.pane').forEach(p => { p.hidden = p.dataset.pane !== b.dataset.tab; });
  if (b.dataset.tab === 'camera') openCamera();
}));

// ---- base: clips ----
async function showClips(q) {
  const fd = new FormData(); fd.append('text', q); fd.append('k', '6');
  const r = await fetch('/api/ask', { method: 'POST', body: fd }); const d = await r.json();
  el.thumbs.innerHTML = '';
  d.results.forEach(m => {
    const li = document.createElement('li');
    li.innerHTML = `<button type="button" aria-pressed="false" title=""><img alt=""></button>`;
    li.querySelector('img').src = m.poster; li.querySelector('button').title = m.caption;
    li.querySelector('button').addEventListener('click', () => {
      el.thumbs.querySelectorAll('button').forEach(x => x.setAttribute('aria-pressed', 'false'));
      li.querySelector('button').setAttribute('aria-pressed', 'true');
      setBase({ kind: 'video', value: m.video_id }, { url: m.url, poster: m.poster, caption: m.caption, kind: 'video' });
    });
    el.thumbs.appendChild(li);
  });
}
const RANDOM = ['a man cooking', 'people dancing', 'a cat', 'a car race', 'children playing', 'a woman singing', 'a dog', 'a basketball game', 'a cartoon', 'someone talking to the camera', 'a beach', 'a concert'];
el.clipSearch.addEventListener('submit', e => { e.preventDefault(); if (el.clipQuery.value.trim()) showClips(el.clipQuery.value.trim()); });
el.randomClip.addEventListener('click', () => { const q = RANDOM[Math.floor(Math.random() * RANDOM.length)]; el.clipQuery.value = q; showClips(q); });

// ---- base: text ----
el.textForm.addEventListener('submit', e => { e.preventDefault(); const t = el.textBase.value.trim(); if (t) setBase({ kind: 'text', value: t }, { kind: 'text', caption: t }); });

// ---- base: camera ----
async function openCamera() {
  if (capture && capture.stream) return;
  try { capture = new Capture(el.preview); await capture.open(); el.recStatus.textContent = ''; }
  catch { el.recStatus.textContent = 'Camera is off. Allow it for this site, then reload.'; }
}
el.record.addEventListener('click', async () => {
  if (!capture || !capture.stream) { await openCamera(); if (!capture || !capture.stream) return; }
  el.record.disabled = true;
  const blob = await capture.record(6, (s, n) => { el.recStatus.textContent = `Recording ${s.toFixed(1)} of ${n} s`; });
  el.recStatus.textContent = 'Embedding the take';
  const fd = new FormData(); fd.append('video', blob, blob.type.includes('mp4') ? 'take.mp4' : 'take.webm');
  try {
    const r = await fetch('/api/steer/upload', { method: 'POST', body: fd }); const d = await r.json();
    el.recStatus.textContent = '';
    setBase({ kind: 'take', value: d.id }, { kind: 'take', url: d.url, poster: d.poster, caption: 'your take' });
  } catch (e) { el.recStatus.textContent = `Upload failed: ${e.message}`; }
  el.record.disabled = false;
});

function setBase(b, view) {
  base = b;
  el.baseView.hidden = false; el.baseView.dataset.kind = view.kind;
  if (view.url) { el.baseVideo.poster = view.poster || ''; el.baseVideo.src = view.url; el.baseVideo.play().catch(() => {}); } else { el.baseVideo.removeAttribute('src'); }
  el.baseCaption.textContent = view.caption || '';
  el.write.disabled = false;
  updatePoint();
}

// ---- sliders ----
async function loadDirs() {
  dirs = await (await fetch('/api/steer/dirs')).json();
  el.sliderList.innerHTML = '';
  dirs.forEach(d => {
    weights[d.name] = 0;
    const row = document.createElement('div'); row.className = 'axis'; row.dataset.name = d.name;
    row.innerHTML = `<span class="neg">${d.neg}</span><div><input type="range" min="-2" max="2" step="0.25" value="0" aria-label="${d.neg} to ${d.pos}"><div class="val">0</div></div><span class="pos">${d.pos}</span>`;
    const inp = row.querySelector('input');
    inp.addEventListener('input', () => {
      const w = Number(inp.value); weights[d.name] = w;
      row.querySelector('.val').textContent = w ? (w > 0 ? '+' : '') + w.toFixed(2) : '0';
      row.classList.toggle('on', w !== 0); row.dataset.sign = w > 0 ? 'pos' : 'neg';
      clearTimeout(pointTimer); pointTimer = setTimeout(updatePoint, 140);
    });
    el.sliderList.appendChild(row);
  });
}
el.reset.addEventListener('click', () => { el.sliderList.querySelectorAll('input').forEach(i => { i.value = 0; i.dispatchEvent(new Event('input')); }); });

// ---- the point and what is around it ----
async function updatePoint() {
  if (!base) return;
  try {
    const d = await post('/api/steer/point', { base, weights });
    pointId = d.point_id;
    el.moved.textContent = d.moved > 0.001 ? `moved ${(d.moved * 100).toFixed(0)}% of the way from the start` : 'at the starting point';
    if (d.clips && d.clips.length) {
      const c = d.clips[0];
      if (el.nearVideo.dataset.id !== c.video_id) { el.nearVideo.src = c.url; el.nearVideo.poster = c.poster; el.nearVideo.dataset.id = c.video_id; el.nearVideo.play().catch(() => {}); }
      el.nearCaption.textContent = `${c.caption} (${Math.min(1, c.score).toFixed(3)})`;
    }
    el.sounds.innerHTML = '';
    d.sounds.forEach(s => {
      const li = document.createElement('li');
      li.innerHTML = `<button type="button">Play</button><span></span><span class="muted"></span>`;
      li.querySelector('span').textContent = s.caption; li.querySelector('.muted').textContent = s.score.toFixed(3);
      li.querySelector('button').addEventListener('click', () => { if (audio) audio.pause(); audio = new Audio(s.url); audio.play(); });
      el.sounds.appendChild(li);
    });
    el.captions.innerHTML = '';
    (d.captions || []).forEach(c => { const li = document.createElement('li'); li.textContent = c.text; const sc = document.createElement('span'); sc.className = 'sc'; sc.textContent = c.score.toFixed(3); li.appendChild(sc); el.captions.appendChild(li); });
  } catch (e) { el.moved.textContent = `Could not move the point: ${e.message}`; }
}

// ---- decode ----
el.write.addEventListener('click', async () => {
  if (!pointId) return;
  el.write.disabled = true; el.sentence.textContent = ''; el.sentence.classList.add('writing'); el.sentenceMeta.textContent = ''; el.cands.innerHTML = '';
  el.decodeStatus.textContent = 'DiffusionGemma is writing (about 6 s)';
  try {
    const d = await post('/api/steer/decode', { point_id: pointId, hints: el.useHints.checked });
    // replay the denoising trajectory, then land on the final sentence
    const steps = d.trajectory.filter(t => t.best).map(t => t.best);
    for (let i = 0; i < steps.length; i += Math.max(1, Math.floor(steps.length / 10))) { el.sentence.textContent = steps[i]; await new Promise(r => setTimeout(r, 90)); }
    el.sentence.classList.remove('writing'); el.sentence.textContent = d.text;
    el.sentenceMeta.textContent = `similarity to the point ${d.score.toFixed(3)}, ${d.seconds} s${d.hints.length ? ', guided by the nearest captions' : ', gradient only'}`;
    d.candidates.slice(0, 5).forEach(c => { const li = document.createElement('li'); li.textContent = `${c.text} (${c.score.toFixed(3)})`; el.cands.appendChild(li); });
    if (d.hints.length) { const li = document.createElement('li'); li.textContent = `hints: ${d.hints.join(' | ')}`; el.cands.appendChild(li); }
    el.decodeStatus.textContent = '';
  } catch (e) { el.decodeStatus.textContent = `Could not write: ${e.message}`; el.sentence.classList.remove('writing'); }
  el.write.disabled = false;
});

// ---- boot ----
loadDirs().catch(() => { el.sliderList.textContent = 'Directions are not built yet.'; });
const demo = new URLSearchParams(location.search).get('demo');
if (demo) { el.clipQuery.value = demo; showClips(demo).then(() => { const b = el.thumbs.querySelector('button'); b && b.click(); }); } else { el.randomClip.click(); }
