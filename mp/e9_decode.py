# Decode perturbed text embeddings back into sentences with the DiffusionGemma guided decoder (steer service, port 8788).
import sys, numpy as np, httpx; sys.path.insert(0, "mp")
from common import *
eg = EG(); save = np.load("mp/directions_text.npy", allow_pickle=True).item()
def enc(t): return np.asarray(eg.st.encode(t, prompt_name="SearchQuery", normalize_embeddings=True), dtype=np.float32)
def decode(v, hints=True):
    return httpx.post("http://127.0.0.1:8788/decode", json={"target": [float(x) for x in v], "hints": hints, "particles": 6, "steps": 24}, timeout=180).json()
first = True
for s in ["a man is playing piano", "a woman is cooking in the kitchen", "two dogs are running on the beach", "a boy is riding a bike"]:
    e = enc(s); r = decode(e)
    if first:
        print("decode keys:", {k: (v if not isinstance(v, list) or len(v) < 6 else f"list[{len(v)}]") for k, v in r.items() if k != "text"}, flush=True); first = False
    print(f"\n[{s}]  decoded as is: {r.get('text')!r} ({r.get('score')})", flush=True)
    for name in ["negation", "past tense", "question", "gender man>woman", "at night", "in slow motion", "language en>hi", "language en>es", "language en>ja"]:
        if name not in save: continue
        d, a = save[name]["d"], save[name]["alpha"]
        v = e + a * d; v = v / np.linalg.norm(v)
        r = decode(v); r2 = decode(v, hints=False)
        print(f"   + {name:16s} α={a}: {r.get('text')!r} ({r.get('score')}) | no hints: {r2.get('text')!r} ({r2.get('score')})", flush=True)
