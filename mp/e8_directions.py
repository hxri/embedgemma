# Are grammar and language linear directions in EmbeddingGemma 2's text space? Minimal pairs -> mean difference -> test on unseen sentences.
import torch, sys, json, re, random, numpy as np; sys.path.insert(0, "mp")
from common import *
random.seed(0); torch.manual_seed(0)
eg = EG()
caps = [str(c) for c in np.load("vindex/captions.npz")["caps"]]
def enc(texts): return torch.tensor(eg.st.encode(texts, prompt_name="SearchQuery", normalize_embeddings=True, batch_size=128)).cuda()

def pairs_regex(pattern, repl, exclude=None, limit=600):
    out = []
    for c in caps:
        if exclude and re.search(exclude, c): continue
        if re.search(pattern, c):
            v = re.sub(pattern, repl, c, count=1)
            if v != c: out.append((c, v))
    random.shuffle(out); return out[:limit]

attrs = {
    "negation": pairs_regex(r"\b(is|are) (\w+ing)\b", r"\1 not \2"),
    "past tense": pairs_regex(r"\b(is|are) (\w+ing)\b", lambda m: ("was" if m.group(1) == "is" else "were") + " " + m.group(2)),
    "question": pairs_regex(r"^(a|an|the|two|three|some|several) (.+?) (is|are) (.+)$", lambda m: f"{m.group(3)} {m.group(1)} {m.group(2)} {m.group(4)}?"),
    "gender man>woman": pairs_regex(r"\b(man|boy|guy)\b", lambda m: {"man": "woman", "boy": "girl", "guy": "girl"}[m.group(1)], exclude=r"\b(woman|girl|lady|women|girls)\b"),
    "at night": [(c, c + " at night") for c in random.sample(caps, 600)],
    "in slow motion": [(c, c + " in slow motion") for c in random.sample(caps, 600)],
}
tr = json.load(open("/tmp/xling/translations.json"))
langs = [l for l in next(iter(tr.values())).keys() if l != "en"]
for L in langs:
    attrs[f"language en>{L}"] = [(v["en"], v[L]) for v in tr.values() if L in v]

save = {}
for name, pr in attrs.items():
    n = len(pr); ntr = min(200, n // 2); tr_p, te_p = pr[:ntr], pr[ntr:ntr + 400]
    A = enc([p[0] for p in tr_p]); B = enc([p[1] for p in tr_p])
    diffs = B - A; d = diffs.mean(0)
    consistency = torch.nn.functional.cosine_similarity(diffs, d[None]).mean().item()
    At = enc([p[0] for p in te_p]); Bt = enc([p[1] for p in te_p]); N = len(te_p)
    pool = torch.cat([At, Bt])
    def evalq(Q):
        s = Q @ pool.T
        exact = (s.argmax(1) == torch.arange(N, device="cuda") + N).float().mean().item()
        sign = ((Q * Bt).sum(1) > (Q * At).sum(1)).float().mean().item()
        return exact, sign
    rows = [(a, *evalq(torch.nn.functional.normalize(At + a * d, dim=-1))) for a in (0.5, 1.0, 1.5, 2.0, 3.0)]
    rnd = torch.randn_like(d); rnd = rnd / rnd.norm() * d.norm()
    r_exact, _ = evalq(torch.nn.functional.normalize(At + rnd, dim=-1))
    best = max(rows, key=lambda r: r[1])
    cos_pair = (At * Bt).sum(1).mean().item()
    cos_pert = (torch.nn.functional.normalize(At + best[0] * d, dim=-1) * Bt).sum(1).mean().item()
    print(f"{name:18s} n={n:4d} | diffs agree {consistency:.2f} |d| {d.norm():.2f} | lands on own variant: α=1 {rows[1][1]*100:5.1f}%  best α={best[0]} {best[1]*100:5.1f}% (moved toward it {best[2]*100:5.1f}%) | random dir {r_exact*100:4.1f}% | cos(e,e') {cos_pair:.3f} -> cos(e+αd,e') {cos_pert:.3f} | e.g. {te_p[0][0]!r} -> {te_p[0][1]!r}", flush=True)
    save[name] = {"d": d.cpu().numpy(), "alpha": best[0], "exact": best[1], "example": te_p[0]}
np.save("mp/directions_text.npy", save, allow_pickle=True)

print("\n--- cross-lingual retrieval, 50 held-out captions: foreign query -> its English original, R@1 ---", flush=True)
en = enc([v["en"] for v in tr.values()])
for L in langs:
    X = enc([v[L] for v in tr.values()]); d = torch.tensor(save[f"language en>{L}"]["d"]).cuda()
    base = recall(X[50:], en[50:])["R@1"]
    moved = recall(torch.nn.functional.normalize(X[50:] - d, dim=-1), en[50:])["R@1"]
    both = recall(torch.nn.functional.normalize(X[50:] - d, dim=-1), torch.nn.functional.normalize(en[50:] + d, dim=-1))["R@1"]
    print(f"{L}: {base} -> subtract language direction from the query {moved} | meet halfway {both}", flush=True)
