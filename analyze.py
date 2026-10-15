"""Rescore recent takes against the running server and describe the chosen library clips."""
import json, subprocess, sys
import numpy as np, soundfile as sf

def density(name):
    x, sr = sf.read(f"index/wav/{name}", dtype="float32"); hop = int(sr * 0.02); n = len(x) // hop
    rms = np.sqrt((x[: n * hop].reshape(n, hop) ** 2).mean(1)); db = 20 * np.log10(rms + 1e-9)
    act = (db > max(np.percentile(db, 20) + 12, -42)).mean(); on = int(((db[1:] - db[:-1]) > 10).sum())
    return f"active {act * 100:.0f}%, ~{on} sharp onsets, {'dense' if act > 0.6 else 'sparse'}"

for f in sys.argv[1:]:
    out = subprocess.run(["curl", "-s", "-F", f"video=@{f}", "-F", "k=4", "http://127.0.0.1:8787/api/match"], capture_output=True, text=True).stdout
    d = json.loads(out); q = d["query"]
    print(f"--- {f}")
    print(f"query: {q['used']} | events kept {q.get('events_s')} of {q.get('audio_s')} s | embed {q['embed_s']} s")
    print("visual path:", [c["class"] for c in d["paths"]["text"][:4]])
    print("audio  path:", [c["class"] for c in d["paths"]["audio"][:5]])
    for c in d["classes"][:4]:
        print(f"   band: {c['class']:<18} z {c['z']:5.2f}  {c['clip']}  [{density(c['clip'])}]")
