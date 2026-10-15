const $ = s => document.querySelector(s);
const el = { drop: $('#drop'), file: $('#file'), pick: $('#pick'), frame: $('#frame'), credit: $('#credit'), status: $('#status'), hits: $('#hits'), sees: $('#sees'), gallery: $('#gallery') };
let audio = null, playing = null, last = null;
const status = (t, err = false) => { el.status.textContent = t; el.status.className = `status${err ? ' error' : ''}`; };
const method = () => document.querySelector('input[name="method"]:checked').value;
const PLAY = '<svg class="p" viewBox="0 0 24 24" aria-hidden="true"><path d="M7 4.5v15l12-7.5z"/></svg><svg class="s" viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6h12v12H6z"/></svg>';

function stop() { if (audio) { audio.pause(); audio = null; } if (playing) { playing.dataset.on = 'false'; playing = null; } }
function play(url, btn) {
  if (playing === btn) { stop(); return; }
  stop(); audio = new Audio(url); audio.loop = true; audio.play().catch(() => {}); playing = btn; btn.dataset.on = 'true';
}

async function find(payload) {
  stop(); status('Embedding the frame and searching 2000 sounds'); el.hits.innerHTML = ''; el.sees.textContent = '';
  const fd = new FormData();
  if (payload.file) fd.append('file', payload.file, payload.file.name || 'frame.jpg'); else fd.append('gallery_id', String(payload.gallery_id));
  fd.append('method', method()); fd.append('k', '3');
  last = payload;
  try {
    const r = await fetch('/api/sfx', { method: 'POST', body: fd });
    if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
    render(await r.json());
  } catch (e) { status(`Could not search: ${e.message}`, true); }
}

function render(d) {
  el.frame.src = d.image_url; el.frame.hidden = false; el.drop.classList.add('has');
  el.credit.innerHTML = d.credit ? `Photo: Wikimedia Commons, ${d.credit.license || 'free licence'} <a href="${d.credit.page}" target="_blank" rel="noopener">source</a>` : '';
  el.hits.innerHTML = '';
  const max = Math.max(...d.results.map(r => r.score)), min = Math.min(...d.results.map(r => r.score));
  d.results.forEach((r, i) => {
    const li = document.createElement('li'); li.className = 'hit'; li.dataset.family = r.family; li.style.setProperty('--d', `${i * 70}ms`);
    const w = max > min ? 35 + 65 * (r.score - min) / (max - min) : 100;
    li.innerHTML = `<button class="play" type="button" aria-label="Play">${PLAY}</button><div><div class="name"><span class="dot"></span></div><div class="meta"></div><div class="bar"><i style="--w:${w.toFixed(0)}%"></i></div></div><div class="alt"></div>`;
    li.querySelector('.name').append(document.createTextNode(r.caption));
    li.querySelector('.meta').textContent = `${r.class.replaceAll('_', ' ')}, similarity ${r.score.toFixed(3)}, ${r.z.toFixed(1)} sd above the mean`;
    const btn = li.querySelector('.play'); btn.addEventListener('click', () => play(r.url, btn));
    const alt = li.querySelector('.alt');
    r.alternatives.slice(0, 2).forEach((a, j) => { const b = document.createElement('button'); b.type = 'button'; b.textContent = `take ${j + 2}`; b.addEventListener('click', () => play(a.url, btn)); alt.appendChild(b); });
    el.hits.appendChild(li);
    if (i === 0) setTimeout(() => play(r.url, btn), 150);
  });
  el.sees.textContent = `What the frame looks like to the model: ${d.sees.slice(0, 3).map(s => s.caption).join('; ')}. ${d.seconds} s.`;
  status('Top three sounds. The first one is playing.');
}

// ---- inputs ----
el.pick.addEventListener('click', () => el.file.click());
el.file.addEventListener('change', () => { if (el.file.files[0]) find({ file: el.file.files[0] }); });
['dragenter', 'dragover'].forEach(ev => el.drop.addEventListener(ev, e => { e.preventDefault(); el.drop.classList.add('over'); }));
['dragleave', 'drop'].forEach(ev => el.drop.addEventListener(ev, e => { e.preventDefault(); el.drop.classList.remove('over'); }));
el.drop.addEventListener('drop', e => { const f = e.dataTransfer.files && e.dataTransfer.files[0]; if (f) find({ file: f }); });
addEventListener('paste', e => { const it = [...(e.clipboardData?.items || [])].find(i => i.type.startsWith('image/')); if (it) find({ file: it.getAsFile() }); });
document.querySelectorAll('input[name="method"]').forEach(i => i.addEventListener('change', () => { if (last) find(last); }));

// ---- gallery ----
fetch('/api/sfx/gallery').then(r => r.json()).then(items => {
  items.forEach(it => {
    const li = document.createElement('li');
    li.innerHTML = `<button type="button" aria-pressed="false"><img loading="lazy" alt=""></button>`;
    li.querySelector('img').src = it.url;
    li.querySelector('button').addEventListener('click', () => {
      el.gallery.querySelectorAll('button').forEach(b => b.setAttribute('aria-pressed', 'false'));
      li.querySelector('button').setAttribute('aria-pressed', 'true');
      find({ gallery_id: it.id });
      scrollTo({ top: 0, behavior: 'smooth' });
    });
    el.gallery.appendChild(li);
  });
  const d = new URLSearchParams(location.search).get('demo');
  if (d !== null) { const b = el.gallery.querySelectorAll('button')[Number(d) || 0]; b && b.click(); }
}).catch(() => status('The gallery is not built yet.', true));
