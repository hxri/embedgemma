import torch, sys; sys.path.insert(0, "mp")
from common import *
eg = EG(); V, T, meta, caps, C = load_vindex()
# per clip: 5 captions -> fuse. Build groups from captions.npz (caps aligned to meta order by matching text)
cap2i = {c: i for i, c in enumerate(caps)}
groups, concat = [], []
for m in meta:
    idx = [cap2i[c] for c in m["captions"] if c in cap2i]
    groups.append(C[idx]); concat.append(". ".join(m["captions"]))
print("n groups", len(groups), "mean size", sum(len(g) for g in groups)/len(groups))
mean = torch.nn.functional.normalize(torch.stack([g.mean(0) for g in groups]), dim=-1)
first = torch.stack([g[0] for g in groups])
print("video->text  first caption", recall(V, first), "| mean of 5", recall(V, mean))
concat_e = torch.tensor(eg.st.encode(concat, prompt_name="SearchQuery", normalize_embeddings=True, batch_size=64)).cuda()
print("video->text  concatenated 5 captions (real text)", recall(V, concat_e))
for alpha in (22.625, 50.0):
    fused = eg.fuse(groups, alpha)
    print(f"video->text  pseudo-token fusion alpha={alpha}", recall(V, fused), "| cos(fused, mean)", round((fused*mean).sum(-1).mean().item(),3))
    # both sides through the pass: fuse video too (single token) for fairness
    V2 = eg.selfpass(V, alpha)
    print(f"   both sides through pass: selfpass(video)->fused", recall(V2, fused))
