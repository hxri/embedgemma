const $ = s => document.querySelector(s);
const el = { photos: $('#photos'), sounds: $('#sounds'), preview: $('#preview'), text: $('#text'), sentences: $('#sentences'), file: $('#file'), drop: $('#drop'), pick: $('#pick'),
  fname: $('#fname'), clear: $('#clear'), go: $('#go'), status: $('#status'), inputs: $('#inputs'), words: $('#words'), meter: $('#meter'), proof: $('#proof'),
  orig: $('#orig'), origSounds: $('#origSounds'), fromWords: $('#fromWords'), fromWordsSounds: $('#fromWordsSounds'), back: $('#back'), read: $('#read'), readout: $('#readout') };
const sel = { photo_id: null, sound_i: null, file: null };
let picks = null, result = null, audio = null, playingBtn = null;
const PLAY = '<svg class="p" viewBox="0 0 24 24" aria-hidden="true"><path d="M7 4.5v15l12-7.5z"/></svg><svg class="s" viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6h12v12H6z"/></svg>';
const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches || document.body.classList.contains('shot');
const status = (t, err = false) => { el.status.textContent = t; el.status.className = `status${err ? ' error' : ''}`; };
const k = () => Number(document.querySelector('.seg button[aria-pressed="true"]').dataset.k);
const lang = () => document.querySelector('input[name="lang"]:checked').value;

function stop() { if (audio) { audio.pause(); audio = null; } if (playingBtn) { playingBtn.dataset.on = 'false'; playingBtn = null; } }
function play(url, btn) {
  if (playingBtn === btn) { stop(); return; }
  stop(); audio = new Audio(url); audio.loop = true; audio.play().catch(() => {}); playingBtn = btn; btn.dataset.on = 'true';
}
function playButton(url) { const b = document.createElement('button'); b.type = 'button'; b.className = 'play'; b.setAttribute('aria-label', 'Play'); b.innerHTML = PLAY; b.addEventListener('click', () => play(url, b)); return b; }
function ready() { el.go.disabled = !(sel.photo_id !== null || sel.sound_i !== null || sel.file || el.text.value.trim()); }

// ---- picks ----
async function loadPicks() {
  picks = await (await fetch('/api/words/picks')).json();
  picks.photos.forEach(p => {
    const b = document.createElement('button'); b.type = 'button'; b.setAttribute('aria-pressed', 'false'); b.title = p.caption; b.dataset.id = p.id;
    b.innerHTML = `<img loading="lazy" alt="">`; b.querySelector('img').src = p.url;
    b.addEventListener('click', () => {
      const on = sel.photo_id === p.id;
      el.photos.querySelectorAll('button').forEach(x => x.setAttribute('aria-pressed', 'false'));
      sel.photo_id = on ? null : p.id; if (!on) b.setAttribute('aria-pressed', 'true'); ready();
    });
    el.photos.appendChild(b);
  });
  const groups = {};
  picks.sounds.forEach(s => { (groups[s.family] ||= []).push(s); });
  Object.entries(groups).forEach(([fam, items]) => {
    const g = document.createElement('optgroup'); g.label = fam;
    items.forEach(s => { const o = document.createElement('option'); o.value = s.i; o.textContent = s.caption; o.dataset.url = s.url; g.appendChild(o); });
    el.sounds.appendChild(g);
  });
  picks.sentences.forEach(s => { const o = document.createElement('option'); o.value = s; el.sentences.appendChild(o); });
  const q = new URLSearchParams(location.search);
  if (q.has('photo')) { const b = el.photos.querySelector(`button[data-id="${q.get('photo')}"]`); b && b.click(); }
  if (q.has('sound')) { el.sounds.value = q.get('sound'); el.sounds.dispatchEvent(new Event('change')); }
  if (q.has('text')) { el.text.value = q.get('text'); ready(); }
  if (q.has('photo') || q.has('sound') || q.has('text')) run();
}

el.sounds.addEventListener('change', () => { sel.sound_i = el.sounds.value ? Number(el.sounds.value) : null; stop(); ready(); });
el.preview.addEventListener('click', () => { const o = el.sounds.selectedOptions[0]; if (o && o.dataset.url) play(o.dataset.url, el.preview); });
el.text.addEventListener('input', ready);
el.text.addEventListener('keydown', e => { if (e.key === 'Enter' && !el.go.disabled) run(); });
el.pick.addEventListener('click', () => el.file.click());
el.file.addEventListener('change', () => setFile(el.file.files[0]));
['dragenter', 'dragover'].forEach(ev => el.drop.addEventListener(ev, e => { e.preventDefault(); el.drop.classList.add('over'); }));
['dragleave', 'drop'].forEach(ev => el.drop.addEventListener(ev, e => { e.preventDefault(); el.drop.classList.remove('over'); }));
el.drop.addEventListener('drop', e => { const f = e.dataTransfer.files && e.dataTransfer.files[0]; if (f) setFile(f); });
addEventListener('paste', e => { const it = [...(e.clipboardData?.items || [])].find(i => i.type.startsWith('image/')); if (it) setFile(it.getAsFile()); });
el.clear.addEventListener('click', () => setFile(null));
function setFile(f) { sel.file = f || null; el.drop.classList.toggle('has', !!f); el.fname.textContent = f ? (f.name || 'pasted image') : ''; el.clear.hidden = !f; ready(); }
el.go.addEventListener('click', run);
document.querySelectorAll('.ex').forEach(b => b.addEventListener('click', () => {
  if (!picks) return;
  el.photos.querySelectorAll('button').forEach(x => x.setAttribute('aria-pressed', 'false'));
  sel.photo_id = null; sel.sound_i = null; el.sounds.value = ''; el.text.value = b.dataset.text || ''; setFile(null);
  if (b.dataset.photo) { const p = picks.photos.find(x => x.class === b.dataset.photo); if (p) { sel.photo_id = p.id; const pb = el.photos.querySelector(`button[data-id="${p.id}"]`); pb && pb.setAttribute('aria-pressed', 'true'); pb && pb.scrollIntoView({ inline: 'center', block: 'nearest' }); } }
  if (b.dataset.sound) { const s = picks.sounds.find(x => x.class === b.dataset.sound); if (s) { sel.sound_i = s.i; el.sounds.value = String(s.i); } }
  ready(); run(); el.go.scrollIntoView({ block: 'center' });
}));
document.querySelectorAll('.seg button').forEach(b => b.addEventListener('click', () => { document.querySelectorAll('.seg button').forEach(x => x.setAttribute('aria-pressed', 'false')); b.setAttribute('aria-pressed', 'true'); if (result) run(); }));
document.querySelectorAll('input[name="lang"]').forEach(i => i.addEventListener('change', () => { if (result) run(); }));

// ---- encode ----
async function run() {
  if (el.go.disabled) return;
  stop(); status('Embedding the inputs, then hunting for the words'); el.words.innerHTML = ''; el.meter.textContent = ''; el.inputs.textContent = ''; el.proof.hidden = true; el.readout.textContent = '';
  const fd = new FormData();
  if (sel.photo_id !== null) fd.append('photo_id', String(sel.photo_id));
  if (sel.sound_i !== null) fd.append('sound_i', String(sel.sound_i));
  if (el.text.value.trim()) fd.append('text', el.text.value.trim());
  if (sel.file) fd.append('file', sel.file, sel.file.name || 'pasted.jpg');
  fd.append('k', String(k())); fd.append('lang', lang());
  try {
    const r = await fetch('/api/words', { method: 'POST', body: fd });
    if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
    render(await r.json());
  } catch (e) { status(`Could not write the words: ${e.message}`, true); }
}

function describe(inputs) {
  const parts = inputs.map(i => i.kind === 'photo' ? `a photo of ${i.label}` : i.kind === 'sound' ? `the sound of ${i.label}` : i.kind === 'video' ? `the video ${i.label}` : `the sentence “${i.label}”`);
  const list = parts.length > 1 ? parts.slice(0, -1).join(', ') + ' and ' + parts.at(-1) : parts[0];
  return `${parts.length > 1 ? 'Reading ' + list + ' as one point.' : 'Reading ' + list + '.'}`;
}

function render(d) {
  result = d;
  el.inputs.textContent = describe(d.inputs);
  el.status.scrollIntoView({ block: 'start', behavior: reduced ? 'auto' : 'smooth' });
  el.words.innerHTML = '';
  d.steps.forEach((s, i) => {
    const li = document.createElement('li');
    li.innerHTML = `<b></b><small></small>`;
    li.querySelector('b').textContent = s.word; li.querySelector('small').textContent = `reads back at ${s.cos.toFixed(2)}`;
    el.words.appendChild(li);
    setTimeout(() => li.classList.add('on'), reduced ? 0 : 120 + i * 380);
  });
  const done = reduced ? 0 : 120 + d.steps.length * 380;
  setTimeout(() => {
    el.meter.innerHTML = `After ${d.words.length} words the model reads back at <b>${d.cos.toFixed(2)}</b> of the original point. ${d.bits.words} bits in place of ${d.bits.vector.toLocaleString()}. ${d.seconds} s.`;
    status('Below: what the original point finds, next to what the words find.');
    renderProof(d.proof.original, el.orig, el.origSounds, d.proof.words);
    renderProof(d.proof.words, el.fromWords, el.fromWordsSounds, d.proof.original);
    el.proof.hidden = false; el.back.value = d.words.join(' ');
  }, done);
}

function renderProof(p, clipsEl, soundsEl, other) {
  clipsEl.innerHTML = ''; soundsEl.innerHTML = '';
  p.clips.forEach(c => {
    const li = document.createElement('li'); if (other.clips.some(o => o.video_id === c.video_id)) li.classList.add('same');
    li.innerHTML = `<img alt=""><div class="cap"><small></small></div>`;
    li.querySelector('img').src = c.poster; li.querySelector('.cap').prepend(document.createTextNode(c.caption)); li.querySelector('small').textContent = `similarity ${c.score.toFixed(3)}`;
    clipsEl.appendChild(li);
  });
  p.sounds.forEach(s => {
    const li = document.createElement('li'); li.dataset.family = s.family; if (other.sounds.some(o => o.class === s.class)) li.classList.add('same');
    li.appendChild(playButton(s.url));
    const cap = document.createElement('div'); cap.className = 'cap'; cap.innerHTML = `<span class="dot"></span><small></small>`;
    cap.insertBefore(document.createTextNode(s.caption), cap.querySelector('small')); cap.querySelector('small').textContent = `similarity ${s.score.toFixed(3)}`;
    li.appendChild(cap); soundsEl.appendChild(li);
  });
}

// ---- read back ----
el.read.addEventListener('click', async () => {
  if (!result) return;
  el.readout.textContent = 'Reading';
  const fd = new FormData(); fd.append('text', el.back.value); fd.append('id', result.id);
  try {
    const r = await fetch('/api/words/read', { method: 'POST', body: fd });
    if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
    const d = await r.json();
    renderProof(d, el.fromWords, el.fromWordsSounds, result.proof.original);
    el.readout.innerHTML = `Typed back, these words read at <b>${d.cos === null ? '?' : d.cos.toFixed(2)}</b> of the original point.`;
  } catch (e) { el.readout.textContent = `Could not read it back: ${e.message}`; }
});

if (new URLSearchParams(location.search).has('shot')) document.body.classList.add('shot');
loadPicks().catch(() => status('The codebook is not built on the server.', true));
