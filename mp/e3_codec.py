# Vector -> k vocabulary tokens -> re-embed. Top-k bag and greedy matching pursuit.
import torch, sys, json, numpy as np, unicodedata; sys.path.insert(0, "mp")
from common import *
eg = EG(); V, T, meta, caps, C = load_vindex()
tok = eg.st.tokenizer
CB = torch.tensor(np.load("mp/codebook.npy")).cuda().float()
keep = torch.zeros(CB.shape[0], dtype=torch.bool)
for i in range(CB.shape[0]):
    s = tok.decode([i]).strip()
    if len(s) >= 2 and not (s.startswith("<") and s.endswith(">")) and any(unicodedata.category(ch).startswith("L") for ch in s):
        keep[i] = True
print("wordy tokens:", int(keep.sum()))
CBk = CB.clone(); CBk[~keep.cuda()] = 0

def embed_seqs(seqs):
    ids = torch.tensor(seqs, device="cuda")
    x = torch.cat([torch.full((len(ids), 1), 2, device="cuda"), ids, torch.full((len(ids), 1), 1, device="cuda")], 1)
    return torch.cat([eg.forward_ids(x[s:s+2048]) for s in range(0, len(x), 2048)])

def words(seq): return " ".join(tok.decode([t]).strip() for t in seq)

def topk_bag(E, k):
    ids = (E @ CBk.T).topk(k, dim=-1).indices
    return ids.tolist(), embed_seqs(ids.tolist())

def greedy(E, k=12, C=32):
    n = len(E); seqs = [[] for _ in range(n)]; cur = torch.zeros_like(E); hist = []
    for step in range(k):
        resid = E if step == 0 else torch.nn.functional.normalize(E - (E*cur).sum(-1, keepdim=True)*cur, dim=-1)
        score = resid @ CBk.T
        for i, s in enumerate(seqs):
            if s: score[i, s] = -9
        cand = score.topk(C, dim=-1).indices
        flat = [seqs[i] + [int(cand[i, j])] for i in range(n) for j in range(C)]
        emb = embed_seqs(flat).view(n, C, -1)
        cos = (emb * E[:, None]).sum(-1)
        best = cos.argmax(-1)
        for i in range(n): seqs[i].append(int(cand[i, best[i]]))
        cur = emb[torch.arange(n), best]
        hist.append((step+1, round(cos.max(-1).values.mean().item(), 3), cur.clone()))
    return seqs, hist

for name, E, lib_eval in (("video", V, lambda L: recall(T, L)), ("caption", T, lambda L: recall(L, V))):
    print(f"==== {name} vectors ====  baseline", lib_eval(E), flush=True)
    for k in (1, 4, 16):
        ids, R = topk_bag(E, k)
        print(f"topk-bag k={k}: cos {round((R*E).sum(-1).mean().item(), 3)} | {lib_eval(R)}", flush=True)
    seqs, hist = greedy(E, k=12)
    for k, cos, R in hist:
        if k in (1, 2, 4, 6, 8, 12): print(f"greedy k={k}: cos {cos} | {lib_eval(R)}", flush=True)
    for i in [0, 1, 2, 3, 4, 100, 200, 300, 400, 500]:
        print(f"  [{meta[i]['caption']}]  ->  {words(seqs[i][:8])}")
    json.dump({"seqs": seqs, "words": [words(s) for s in seqs]}, open(f"mp/codec_{name}.json", "w"))
