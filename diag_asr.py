"""Diagnostic only: transcribe the user's spoken queries with whisper-tiny to see content, language and truncation."""
import glob, os, sys, numpy as np, soundfile as sf, torch
from transformers import pipeline
asr = pipeline("automatic-speech-recognition", model="openai/whisper-tiny", device=0, torch_dtype=torch.float16)
files = sorted(glob.glob("media/say_*_q16k.wav"), key=os.path.getmtime)
for f in files:
    x, sr = sf.read(f, dtype="float32")
    if x.ndim > 1: x = x.mean(1)
    dur = len(x) / sr
    # where does speech start? first 20 ms frame above -35 dBFS
    hop = int(sr * 0.02); n = len(x) // hop
    db = 20 * np.log10(np.sqrt((x[:n * hop].reshape(n, hop) ** 2).mean(1)) + 1e-9)
    on = np.flatnonzero(db > -35); onset = on[0] * 0.02 if on.size else None
    out = asr({"raw": x, "sampling_rate": sr}, return_language=True, generate_kwargs={"task": "transcribe"})
    lang = out.get("chunks", [{}])[0].get("language") if out.get("chunks") else None
    print(f"{os.path.basename(f):<28} {dur:4.1f}s  speech from {('none' if onset is None else f'{onset:.2f}s'):>6}  lang={lang}  text={out['text']!r}", flush=True)
