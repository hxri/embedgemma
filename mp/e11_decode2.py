# Decode perturbed points with hints drawn from a bank that contains grammatical variants and translations, on sentences not in any bank.
import sys, re, json, numpy as np, httpx, torch; sys.path.insert(0, "mp")
from common import *
from words import WordsCodec
eg = EG(); save = np.load("mp/directions_text.npy", allow_pickle=True).item()
caps = [str(c) for c in np.load("vindex/captions.npz")["caps"]]
neg = lambda c: re.sub(r"\b(is|are) (\w+ing)\b", r"\1 not \2", c, count=1)
past = lambda c: re.sub(r"\b(is|are) (\w+ing)\b", lambda m: ("was" if m.group(1) == "is" else "were") + " " + m.group(2), c, count=1)
ques = lambda c: re.sub(r"^(a|an|the|two|three|some|several) (.+?) (is|are) (.+)$", lambda m: f"{m.group(3)} {m.group(1)} {m.group(2)} {m.group(4)}?", c, count=1)
fem = lambda c: re.sub(r"\b(man|boy|guy)\b", lambda m: {"man": "woman", "boy": "girl", "guy": "girl"}[m.group(1)], c, count=1)
bank = list(caps)
for f in (neg, past, ques, fem, lambda c: c + " at night", lambda c: c + " in slow motion"): bank += [f(c) for c in caps]
tr = json.load(open("/tmp/xling/translations.json"))
bank += [v[L] for v in tr.values() for L in v if L != "en"]
bank = list(dict.fromkeys(bank)); print("hint bank:", len(bank), flush=True)
B = torch.tensor(eg.st.encode(bank, prompt_name="SearchQuery", normalize_embeddings=True, batch_size=256)).cuda()
def enc(t): return np.asarray(eg.st.encode(t, prompt_name="SearchQuery", normalize_embeddings=True), dtype=np.float32)
def hints(v, n=5): return [bank[i] for i in (B @ torch.tensor(v).cuda()).topk(n).indices.tolist()]
def decode(v):
    h = hints(v)
    r = httpx.post("http://127.0.0.1:8788/decode", json={"target": [float(x) for x in v], "hint_texts": h, "particles": 6, "steps": 24}, timeout=180).json()
    return r.get("text"), round(r.get("score", 0), 2), h[0]
cd = WordsCodec(eg.st)
sents = ["my sister is learning to drive a truck", "a man is fixing the roof before the storm", "the chef is tasting the soup before service"]
dirs = ["negation", "past tense", "question", "gender man>woman", "at night", "language en>hi", "language en>ta", "language en>es", "language en>ja"]
for s in sents:
    e = enc(s); t, sc, h = decode(e)
    print(f"\n[{s}]  decoded as is: {t!r} ({sc})  nearest hint: {h!r}", flush=True)
    for name in dirs:
        d, a = save[name]["d"], save[name]["alpha"]
        v = e + a * d; v = v / np.linalg.norm(v)
        t, sc, h = decode(v)
        extra = ""
        if name.startswith("language"):
            w = cd.encode(v, k=6, lang="any"); extra = f" | words(any): {' '.join(w['words'])}"
        print(f"   + {name:16s} α={a}: {t!r} ({sc})  nearest hint: {h!r}{extra}", flush=True)
# two directions at once
for s in ["a man is fixing the roof before the storm", "the chef is tasting the soup before service"]:
    e = enc(s)
    for combo in (["negation", "past tense"], ["gender man>woman", "at night"], ["gender man>woman", "language en>hi"]):
        v = e.copy()
        for name in combo: v = v + save[name]["alpha"] * save[name]["d"]
        v = v / np.linalg.norm(v); t, sc, h = decode(v)
        print(f"[{s}] + {' + '.join(combo)}: {t!r} ({sc})  nearest hint: {h!r}", flush=True)
