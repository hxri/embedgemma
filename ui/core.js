// Direction-independent plumbing: camera capture, API calls, and synced looping playback.
// No DOM assumptions beyond the elements handed in.

export const Api = {
  async health() { return (await fetch('/api/health')).json(); },
  async classes() { return (await fetch('/api/classes')).json(); },
  async match(blob, opts = {}) {
    const fd = new FormData();
    fd.append('video', blob, blob.type.includes('mp4') ? 'clip.mp4' : 'clip.webm');
    for (const [k, v] of Object.entries(opts)) fd.append(k, String(v));
    const r = await fetch('/api/match', { method: 'POST', body: fd });
    if (!r.ok) throw new Error(`match failed (${r.status}): ${await r.text()}`);
    return r.json();
  },
  async mux(id, clip, mix = false) {
    const fd = new FormData();
    fd.append('id', id); fd.append('clip', clip); fd.append('mix', mix ? 'true' : 'false');
    const r = await fetch('/api/mux', { method: 'POST', body: fd });
    if (!r.ok) throw new Error(`mux failed (${r.status})`);
    return (await r.json()).url;
  },
};

export class Capture {
  constructor(previewEl, ctx) { this.previewEl = previewEl; this.stream = null; this.ctx = ctx || null; this.analyser = null; }

  async open() {
    this.stream = await navigator.mediaDevices.getUserMedia({
      video: { width: { ideal: 1280 }, height: { ideal: 720 }, facingMode: 'user' },
      audio: { echoCancellation: false, noiseSuppression: false, autoGainControl: false },
    });
    this.previewEl.srcObject = this.stream;
    this.previewEl.muted = true;
    await this.previewEl.play();
    return this.stream;
  }

  // Live microphone level, 0..1 (RMS), for meters while recording.
  level() {
    if (!this.analyser) {
      this.ctx = this.ctx || new (window.AudioContext || window.webkitAudioContext)();
      const src = this.ctx.createMediaStreamSource(this.stream);
      this.analyser = this.ctx.createAnalyser();
      this.analyser.fftSize = 1024;
      src.connect(this.analyser);
      this._buf = new Float32Array(this.analyser.fftSize);
    }
    this.analyser.getFloatTimeDomainData(this._buf);
    let s = 0; for (let i = 0; i < this._buf.length; i++) s += this._buf[i] * this._buf[i];
    return Math.sqrt(s / this._buf.length);
  }

  mimeType() {
    const c = ['video/mp4;codecs=avc1,mp4a.40.2', 'video/mp4', 'video/webm;codecs=vp9,opus', 'video/webm;codecs=vp8,opus', 'video/webm'];
    return c.find(t => window.MediaRecorder && MediaRecorder.isTypeSupported(t)) || '';
  }

  // Records `seconds` from the open stream. onTick(elapsed, total) fires every frame.
  record(seconds, onTick) {
    return new Promise((resolve, reject) => {
      const type = this.mimeType();
      const rec = new MediaRecorder(this.stream, type ? { mimeType: type, videoBitsPerSecond: 2_500_000 } : undefined);
      const chunks = [];
      rec.ondataavailable = e => { if (e.data && e.data.size) chunks.push(e.data); };
      rec.onerror = e => reject(e.error || new Error('recorder error'));
      rec.onstop = () => resolve(new Blob(chunks, { type: rec.mimeType || type || 'video/webm' }));
      rec.start(250);
      const t0 = performance.now();
      const tick = () => {
        const el = (performance.now() - t0) / 1000;
        if (el >= seconds) { rec.stop(); return; }
        onTick && onTick(el, seconds);
        requestAnimationFrame(tick);
      };
      requestAnimationFrame(tick);
    });
  }

  close() { this.stream && this.stream.getTracks().forEach(t => t.stop()); this.stream = null; }
}

// Plays a looping sound over a looping <video>, phase-locked to video.currentTime, with instant switching.
export class Player {
  constructor(videoEl) {
    this.video = videoEl;
    this.ctx = new (window.AudioContext || window.webkitAudioContext)();
    this.gain = this.ctx.createGain();
    this.out = this.ctx.createAnalyser(); this.out.fftSize = 512;
    this.gain.connect(this.out); this.out.connect(this.ctx.destination);
    this.buffers = new Map();
    this.src = null; this.current = null;
    this.video.addEventListener('play', () => this._restart());
    this.video.addEventListener('pause', () => this._stop());
    this.video.addEventListener('seeked', () => { if (!this.video.paused) this._restart(); });
    let last = 0;  // when a looping video wraps, re-phase the sound
    this.video.addEventListener('timeupdate', () => { if (this.video.currentTime < last - 0.5 && !this.video.paused) this._restart(); last = this.video.currentTime; });
  }

  async preload(urls) {
    await Promise.all(urls.map(async u => {
      if (this.buffers.has(u)) return;
      const ab = await (await fetch(u)).arrayBuffer();
      this.buffers.set(u, await this.ctx.decodeAudioData(ab));
    }));
  }

  // Switches the playing sound; starts at the phase matching the video's loop position.
  async play(url) {
    await this.ctx.resume();
    if (!this.buffers.has(url)) await this.preload([url]);
    this.current = url;
    if (!this.video.paused) this._restart();
  }

  // Playing sound's output level 0..1, for visualisers.
  level() {
    if (!this._lvl) this._lvl = new Float32Array(this.out.fftSize);
    this.out.getFloatTimeDomainData(this._lvl);
    let s = 0; for (let i = 0; i < this._lvl.length; i++) s += this._lvl[i] * this._lvl[i];
    return Math.sqrt(s / this._lvl.length);
  }

  _restart() {
    this._stop();
    const buf = this.current && this.buffers.get(this.current);
    if (!buf) return;
    const s = this.ctx.createBufferSource();
    s.buffer = buf; s.loop = true;
    const g = this.ctx.createGain();
    g.gain.setValueAtTime(0, this.ctx.currentTime);
    g.gain.linearRampToValueAtTime(1, this.ctx.currentTime + 0.01);  // de-click
    s.connect(g); g.connect(this.gain);
    s.start(0, this.video.currentTime % buf.duration);
    this.src = s; this._g = g;
  }

  _stop() {
    if (!this.src) return;
    try { this._g.gain.setTargetAtTime(0, this.ctx.currentTime, 0.005); this.src.stop(this.ctx.currentTime + 0.03); } catch {}
    this.src = null;
  }

  stop() { this.current = null; this._stop(); }
}
