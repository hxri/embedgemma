const $ = s => document.querySelector(s);
const el = { text: $('#text'), sugg: $('#sugg'), ops: $('#ops'), lang: $('#lang'), strength: $('#strength'), strengthOut: $('#strengthOut'), eq: $('#eq'),
  verdict: $('#verdict'), cols: $('#cols'), before: $('#before'), after: $('#after'), read: $('#read'), words: $('#words'), decode: $('#decode'), decoded: $('#decoded'), bankN: $('#bankN') };
const LABEL = { 'negation': 'not', 'past tense': 'past tense', 'question': 'question?', 'gender man>woman': 'man → woman', 'gender woman>man': 'woman → man', 'at night': 'at night', 'in slow motion': 'in slow motion' };
let meta = null, timer = null, seq = 0, last = null, lastResult = null, lastDecoded = null;
const ops = () => [...el.ops.querySelectorAll('button[aria-pressed="true"]')].map(b => b.dataset.op);
const status = (t, err = false) => { el.verdict.innerHTML = ''; const p = document.createElement('p'); p.className = `status${err ? ' error' : ''}`; p.textContent = t; el.verdict.appendChild(p); };

async function init() {
  meta = await (await fetch('/api/dir/ops')).json();
  el.bankN.textContent = meta.bank.toLocaleString();
  meta.ops.forEach(o => {
    const b = document.createElement('button'); b.type = 'button'; b.dataset.op = o.op; b.setAttribute('aria-pressed', 'false'); b.textContent = LABEL[o.op] || o.op; b.title = `fitted length ${o.alpha}`;
    b.addEventListener('click', () => { b.setAttribute('aria-pressed', b.getAttribute('aria-pressed') === 'true' ? 'false' : 'true'); schedule(0); });
    el.ops.appendChild(b);
  });
  meta.languages.forEach(l => { const o = document.createElement('option'); o.value = l.code; o.textContent = l.name; el.lang.appendChild(o); });
  meta.sentences.forEach(s => { const o = document.createElement('option'); o.value = s; el.sugg.appendChild(o); });
  const q = new URLSearchParams(location.search);
  if (q.has('text')) el.text.value = q.get('text');
  if (q.has('ops')) q.get('ops').split(',').forEach(op => { const b = el.ops.querySelector(`button[data-op="${op}"]`); b && b.setAttribute('aria-pressed', 'true'); });
  if (q.has('lang')) el.lang.value = q.get('lang');
  if (q.has('strength')) { el.strength.value = q.get('strength'); el.strengthOut.textContent = `${Number(el.strength.value).toFixed(1)}×`; }
  if (el.text.value) run();
}

function schedule(ms) { clearTimeout(timer); timer = setTimeout(run, ms); }
el.text.addEventListener('input', () => schedule(500));
el.text.addEventListener('keydown', e => { if (e.key === 'Enter') schedule(0); });
el.lang.addEventListener('change', () => schedule(0));
el.strength.addEventListener('input', () => { el.strengthOut.textContent = `${Number(el.strength.value).toFixed(1)}×`; schedule(150); });

function equation(d) {
  const parts = d.ops.map(o => `<b>${o.alpha >= 0 ? '+' : '−'} ${Math.abs(o.alpha).toFixed(1)} × ${LABEL[o.op] || o.op}</b>`);
  el.eq.innerHTML = `e(<q></q>) ${parts.join(' ') || '<b>+ nothing yet</b>'}`;
  el.eq.querySelector('q').textContent = d.text;
}

async function run() {
  const text = el.text.value.trim();
  if (!text) { status('Pick a sentence to start.'); el.cols.hidden = true; el.read.hidden = true; el.eq.textContent = ''; return; }
  const my = ++seq;
  const body = { text, ops: ops(), lang: el.lang.value || null, strength: Number(el.strength.value), k: 5 };
  try {
    const r = await fetch('/api/dir/move', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
    const d = await r.json();
    if (my !== seq) return;
    last = body; lastResult = d; lastDecoded = null; render(d);
  } catch (e) { if (my === seq) status(`Could not move the point: ${e.message}`, true); }
}

function render(d) {
  equation(d);
  el.verdict.innerHTML = '';
  const big = document.createElement('p'); big.className = 'big'; const why = document.createElement('p'); why.className = 'why';
  const n = d.bank.toLocaleString();
  if (!d.ops.length) {
    big.textContent = 'Nothing added yet.'; why.textContent = `The closest of ${n} sentences to an untouched sentence is the sentence itself. Press a button.`;
  } else if (d.expected === null) {
    big.textContent = 'No exact form to land on.'; why.textContent = (d.notes.join('. ') || 'No rule writes this form') + '. The right column shows what is closest anyway.';
  } else if (d.rank_after === 1) {
    big.className = 'big yes'; big.innerHTML = 'Landed. The closest sentence is now <q></q>'; big.querySelector('q').textContent = d.expected;
    why.textContent = `Cosine to that form ${d.cos_after} after the move, ${d.cos_before} before, when it was rank ${d.rank_before.toLocaleString()} of ${n}. The sentence itself is now ${d.after.find(x => x.typed && !x.expected) ? `rank ${d.after.findIndex(x => x.typed && !x.expected) + 1}` : 'below the top five'}.${d.notes.length ? ' ' + d.notes.join('. ') + '.' : ''} ${d.seconds} s.`;
  } else {
    big.className = 'big no'; big.innerHTML = `Not there: the changed form <q></q> is rank ${d.rank_after.toLocaleString()}.`; big.querySelector('q').textContent = d.expected;
    why.textContent = `Cosine to it ${d.cos_after} after the move, ${d.cos_before} before (rank ${d.rank_before.toLocaleString()}). Push further or less.${d.notes.length ? ' ' + d.notes.join('. ') + '.' : ''}`;
  }
  el.verdict.append(big, why);
  list(el.before, d.before); list(el.after, d.after); el.cols.hidden = false;
  el.words.innerHTML = ''; el.words.append('Read as words in any language: '); const b = document.createElement('b'); b.textContent = (d.words || []).join(' '); el.words.appendChild(b);
  el.decoded.textContent = ''; el.decode.disabled = false; el.read.hidden = false;
}

function list(ol, items) {
  ol.innerHTML = '';
  items.forEach(it => {
    const li = document.createElement('li'); if (it.typed) li.classList.add('typed'); if (it.expected) li.classList.add('expected');
    li.innerHTML = `<span class="t"><span class="k"></span></span><span class="c"></span>`;
    li.querySelector('.t').prepend(document.createTextNode(it.text));
    li.querySelector('.k').textContent = it.expected ? 'your sentence, changed by rule' : it.typed ? 'your sentence' : it.kind === 'caption' ? 'bank' : `bank, ${it.kind.replace('language en>', 'in ')}`;
    li.querySelector('.c').textContent = it.cos.toFixed(3);
    ol.appendChild(li);
  });
}

el.decode.addEventListener('click', async () => {
  if (!last) return;
  el.decode.disabled = true; el.decoded.textContent = 'Writing, about six seconds';
  try {
    const r = await fetch('/api/dir/decode', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(last) });
    if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
    const d = await r.json();
    el.decoded.innerHTML = ''; const b = document.createElement('b'); b.textContent = d.text; el.decoded.append(b, ` (${d.score}, ${d.seconds} s)`); lastDecoded = d.text;
  } catch (e) { el.decoded.textContent = `Could not write it: ${e.message}`; }
  el.decode.disabled = false;
});



// ================= How it works: the chart =================
const how = { el: $('#how'), chart: $('#chart'), stepN: $('#stepN'), title: $('#stepTitle'), text: $('#stepText'), back: $('#back'), next: $('#next'), play: $('#play') };
const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches || new URLSearchParams(location.search).has('shot');
const NODES = [
  { id: 'sentence', x: 20, y: 20, w: 270, h: 64, kind: 'txt', html: '<b>Your sentence</b><span id="c-sentence"></span>' },
  { id: 'eg1', x: 320, y: 20, w: 190, h: 64, kind: 'eg', html: '<b>EmbeddingGemma 2</b><span>reads it: 768 numbers</span>' },
  { id: 'e', x: 560, y: 52, r: 12, kind: 'pt', label: 'e', lx: 560, ly: 34, anchor: 'middle' },
  { id: 'dirs', x: 610, y: 20, w: 330, h: 64, kind: 'txt', html: '<b>Add the directions</b><span id="c-dirs"></span><i class="badge">each fitted once from 200 pairs, by EmbeddingGemma</i>' },
  { id: 'v', x: 560, y: 150, r: 14, kind: 'pt', label: 'v', lx: 541, ly: 178, anchor: 'end' },
  { id: 'expected', x: 20, y: 195, w: 260, h: 70, kind: 'nl', html: '<b>Expected form</b><span>written by rule, or by the translator</span><span id="c-expected"></span>' },
  { id: 'eg3', x: 300, y: 195, w: 160, h: 70, kind: 'eg', html: '<b>EmbeddingGemma 2</b><span>embeds it</span>' },
  { id: 'bank', x: 20, y: 300, w: 200, h: 60, kind: 'eg', html: '<b>26,939 bank vectors</b><span>embedded once by EmbeddingGemma</span>' },
  { id: 'search', x: 240, y: 300, w: 220, h: 60, kind: 'txt', html: '<b>Nearest to v</b><span>the bank plus the expected form</span>' },
  { id: 'verdict', x: 20, y: 390, w: 440, h: 60, kind: 'ok', html: '<b id="c-verdict"></b><span>the proof</span>' },
  { id: 'hints', x: 500, y: 200, w: 200, h: 60, kind: 'txt', html: '<b>5 hints</b><span>bank sentences nearest to v, never yours</span>' },
  { id: 'dg', x: 500, y: 300, w: 200, h: 70, kind: 'dg', html: '<b>DiffusionGemma 26B</b><span>one denoising step: token probabilities</span>' },
  { id: 'eg5', x: 740, y: 300, w: 200, h: 70, kind: 'eg', html: '<b>EmbeddingGemma 2 judges</b><span>soft tokens → vector c, cosine to v, gradient</span>' },
  { id: 'pick', x: 500, y: 420, w: 440, h: 60, kind: 'eg', html: '<b>Pick the closest of six</b><span>EmbeddingGemma scores the six finished sentences against v</span>' },
  { id: 'out', x: 500, y: 510, w: 440, h: 70, kind: 'txt', html: '<b>A reading, not the proof</b><span id="c-out"></span>' },
];
const EDGES = [
  { id: 'e1', d: 'M290,52 L320,52' }, { id: 'e2', d: 'M510,52 L548,52' }, { id: 'e3', d: 'M572,52 L610,52' },
  { id: 'e4', d: 'M560,64 L560,136' }, { id: 'e5', d: 'M775,84 L775,150 L574,150' },
  { id: 'e6', d: 'M150,84 L150,200', dashed: true, label: ['rule or NLLB', 158, 150] },
  { id: 'e7', d: 'M280,230 L300,230' }, { id: 'e8', d: 'M380,265 L380,300' }, { id: 'e9', d: 'M220,330 L240,330' }, { id: 'e10', d: 'M350,360 L350,390' },
  { id: 'e11', d: 'M546,150 L480,150 L480,330 L460,330' },
  { id: 'e12', d: 'M560,164 L560,200' }, { id: 'e13', d: 'M560,260 L560,300' },
  { id: 'e14', d: 'M700,335 L740,335' },
  { id: 'e15', d: 'M840,300 L840,282 L650,282 L650,300', label: ['nudge the probabilities, next step', 660, 276] },
  { id: 'e16', d: 'M560,370 L560,420' }, { id: 'e17', d: 'M720,480 L720,510' },
];
const STEPS = [
  { title: 'Your sentence becomes a point.', text: '<b>EmbeddingGemma 2</b> reads the sentence and returns 768 numbers. That point, e, is all the rest of the pipeline ever sees; the words are not used again.', nodes: ['sentence', 'eg1', 'e'], edges: ['e1', 'e2'], route: 'M290,52 L548,52' },
  { title: 'The directions were fitted once.', text: 'Each direction is the average difference between <b>EmbeddingGemma</b>’s embeddings of 200 sentences and their changed forms, written by rule: “a car is racing on road” against “a car is not racing on road”. Three pairs already give most of it. Nothing is trained.', nodes: ['dirs'], edges: [], route: null },
  { title: 'Add them. Nothing else changes.', text: 'The directions are added to e with their fitted lengths, three times the natural length for negation and tense because the model barely separates those on its own. The result is v. No word was edited.', nodes: ['e', 'dirs', 'v'], edges: ['e4', 'e5'], route: 'M560,64 L560,136' },
  { title: 'The proof writes the expected form.', text: 'From the text, not from v: a rule writes the negated, past, question or swapped form, and the <b>NLLB</b> translator writes the foreign one. <b>EmbeddingGemma</b> embeds it, so there is an exact point to land on.', nodes: ['sentence', 'expected', 'eg3'], edges: ['e6', 'e7', 'e8'], route: 'M150,84 L150,230 L380,230 L380,300' },
  { title: 'Nearest of 26,939.', text: 'v is compared with every bank vector, all of them embedded once by <b>EmbeddingGemma</b>, plus the expected form. If the expected form is rank 1, it landed. This is the evidence; nothing downstream can improve it.', nodes: ['v', 'bank', 'search', 'verdict'], edges: ['e11', 'e9', 'e10'], route: 'M546,150 L480,150 L480,330 L350,330 L350,390' },
  { title: 'The reading starts from hints.', text: 'The five bank sentences nearest to v become <b>DiffusionGemma</b>’s prompt. Your sentence and its expected form are never among them, so the reading cannot copy the answer.', nodes: ['v', 'hints', 'dg'], edges: ['e12', 'e13'], route: 'M560,164 L560,300' },
  { title: 'Inside every step, EmbeddingGemma judges.', text: '<b>DiffusionGemma</b> proposes token probabilities. They are turned into <b>EmbeddingGemma</b> input embeddings, possible because both models share one vocabulary of 262,144 tokens. EmbeddingGemma embeds the soft sentence, the cosine to v is measured, and its gradient nudges the probabilities. Twenty-four steps, six candidates in parallel.', nodes: ['dg', 'eg5'], edges: ['e14', 'e15'], route: 'M700,335 L740,335 L840,335 L840,282 L650,282 L650,335 L700,335', loop: true },
  { title: 'Pick the closest of six.', text: 'The six finished sentences are embedded for real by <b>EmbeddingGemma</b> and the one closest to v wins, with that cosine as its score. It follows the hints as much as the point, which is why it is a reading and the landing test is the proof.', nodes: ['dg', 'pick', 'out'], edges: ['e16', 'e17'], route: 'M560,370 L560,450 L720,450 L720,510' },
];
let step = 0, built = false, playTimer = null, loopTimer = null;
const svgNS = 'http://www.w3.org/2000/svg';
const mk = (tag, attrs = {}) => { const n = document.createElementNS(svgNS, tag); for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v); return n; };

function buildChart() {
  const svg = how.chart; svg.innerHTML = '';
  const defs = mk('defs');
  for (const [id, color] of [['arrow', '#111'], ['arrowOn', '#1f4fe0']]) {
    const m = mk('marker', { id, viewBox: '0 0 10 10', refX: 9, refY: 5, markerWidth: 7, markerHeight: 7, orient: 'auto-start-reverse' });
    m.appendChild(mk('path', { d: 'M0,0 L10,5 L0,10 z', fill: color })); defs.appendChild(m);
  }
  svg.appendChild(defs);
  EDGES.forEach((e, i) => {
    const p = mk('path', { d: e.d, class: `edge${e.dashed ? ' dashed' : ''}`, id: `edge-${e.id}` }); p.style.setProperty('--i', i); svg.appendChild(p);
    if (e.label) { const t = mk('text', { x: e.label[1], y: e.label[2], class: 'elabel' }); t.textContent = e.label[0]; svg.appendChild(t); }
  });
  NODES.forEach((n, i) => {
    if (n.kind === 'pt') {
      const g = mk('g', { class: 'pt', id: `node-${n.id}` }); g.style.setProperty('--i', i);
      g.appendChild(mk('circle', { cx: n.x, cy: n.y, r: n.r }));
      const t = mk('text', { x: n.lx, y: n.ly, 'text-anchor': n.anchor }); t.textContent = n.label; g.appendChild(t); svg.appendChild(g); return;
    }
    const g = mk('g', { class: `node ${n.kind}`, id: `node-${n.id}` }); g.style.setProperty('--i', i);
    g.appendChild(mk('rect', { x: n.x, y: n.y, width: n.w, height: n.h }));
    const fo = mk('foreignObject', { x: n.x, y: n.y, width: n.w, height: n.h });
    const div = document.createElementNS('http://www.w3.org/1999/xhtml', 'div'); div.className = 'lbl'; div.innerHTML = n.html; fo.appendChild(div); g.appendChild(fo); svg.appendChild(g);
  });
  const count = mk('text', { x: 720, y: 400, class: 'count', id: 'c-count', 'text-anchor': 'middle' }); count.textContent = ''; svg.appendChild(count);
  svg.appendChild(mk('path', { id: 'route', d: 'M0,0', fill: 'none', stroke: 'none' }));
  const dot = mk('circle', { class: 'dot', r: 7, id: 'dot', hidden: '' });
  const am = mk('animateMotion', { id: 'dotAnim', dur: '1.6s', fill: 'freeze', begin: 'indefinite' });
  const mp = mk('mpath'); mp.setAttributeNS('http://www.w3.org/1999/xlink', 'href', '#route'); am.appendChild(mp); dot.appendChild(am); svg.appendChild(dot);
  built = true;
}

function fillChart() {
  const d = lastResult; const n = (meta ? meta.bank : 26939).toLocaleString();
  const set = (id, t) => { const x = document.getElementById(id); if (x) x.textContent = t; };
  set('c-sentence', d ? `“${d.text}”` : '');
  set('c-dirs', d && d.ops.length ? d.ops.map(o => `${o.alpha >= 0 ? '+' : '−'} ${Math.abs(o.alpha).toFixed(1)} × ${LABEL[o.op] || o.op}`).join('  ') : 'nothing added yet');
  set('c-expected', d ? (d.expected ? `“${d.expected}”` : 'no rule writes this form for the sentence') : '');
  set('c-verdict', d ? (!d.ops.length ? 'nothing added yet' : d.expected === null ? 'no exact form to land on' : d.rank_after === 1 ? `rank 1 of ${n}: landed` : `rank ${d.rank_after.toLocaleString()} of ${n}: not there`) : '');
  set('c-out', lastDecoded ? `“${lastDecoded}”` : 'press “Write the sentence at this point” in Try it to get one');
}

function showStep(k, animate = true) {
  step = (k + STEPS.length) % STEPS.length; const s = STEPS[step];
  how.stepN.textContent = step + 1; how.title.textContent = s.title; how.text.innerHTML = s.text;
  how.chart.classList.add('focus');
  how.chart.querySelectorAll('.node, .pt').forEach(g => g.classList.toggle('on', s.nodes.includes(g.id.replace('node-', ''))));
  how.chart.querySelectorAll('.edge').forEach(p => p.classList.toggle('on', s.edges.includes(p.id.replace('edge-', ''))));
  clearInterval(loopTimer); loopTimer = null; const count = document.getElementById('c-count'); count.textContent = '';
  const dot = document.getElementById('dot'), anim = document.getElementById('dotAnim'), route = document.getElementById('route');
  if (s.route && animate && !reduced) {
    route.setAttribute('d', s.route); dot.removeAttribute('hidden');
    anim.setAttribute('dur', s.loop ? '1.4s' : '1.6s'); anim.setAttribute('repeatCount', s.loop ? 'indefinite' : '1'); anim.beginElement();
  } else dot.setAttribute('hidden', '');
  if (s.loop) { let k2 = 0; count.textContent = 'step 1 of 24'; loopTimer = setInterval(() => { k2 = (k2 % 24) + 1; count.textContent = `step ${k2} of 24`; }, reduced ? 1000 : 175); }
}

function setPlay(on) {
  clearInterval(playTimer); playTimer = null; how.play.setAttribute('aria-pressed', on ? 'true' : 'false'); how.play.textContent = on ? 'Pause' : 'Play';
  if (on) playTimer = setInterval(() => showStep(step + 1), 6000);
}

async function enterHow() {
  if (!built) buildChart();
  if (!lastResult && meta) {
    try { const r = await fetch('/api/dir/move', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text: meta.sentences[0], ops: ['negation', 'past tense'], lang: null, strength: 1, k: 5 }) }); lastResult = await r.json(); } catch (e) { /* chart still explains without labels */ }
  }
  fillChart();
  how.chart.classList.add('intro'); setTimeout(() => how.chart.classList.remove('intro'), 2200);
  showStep(0, false);
  setTimeout(() => showStep(0, true), reduced ? 0 : 1500);
}

function setView(v) {
  document.body.dataset.view = v; how.el.hidden = v !== 'how';
  document.querySelectorAll('.view button').forEach(b => b.setAttribute('aria-pressed', b.dataset.view === v ? 'true' : 'false'));
  if (v === 'how') { enterHow(); history.replaceState(null, '', '#how'); } else { setPlay(false); clearInterval(loopTimer); history.replaceState(null, '', location.pathname + location.search); }
}
document.querySelectorAll('.view button').forEach(b => b.addEventListener('click', () => setView(b.dataset.view)));
how.back.addEventListener('click', () => { setPlay(false); showStep(step - 1); });
how.next.addEventListener('click', () => { setPlay(false); showStep(step + 1); });
how.play.addEventListener('click', () => { const on = how.play.getAttribute('aria-pressed') !== 'true'; setPlay(on); if (on) showStep(step + 1); });
addEventListener('keydown', e => { if (how.el.hidden || e.target.tagName === 'INPUT') return; if (e.key === 'ArrowRight') { setPlay(false); showStep(step + 1); } if (e.key === 'ArrowLeft') { setPlay(false); showStep(step - 1); } });

init().then(() => { if (location.hash === '#how' || new URLSearchParams(location.search).get('view') === 'how') setView('how'); }).catch(() => status('The directions are not built on the server.', true));
