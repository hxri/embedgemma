# Is the learned pass more faithful than averaging to "what the model says about the concatenated text"? Plus recursion.
import torch, sys, numpy as np; sys.path.insert(0, "mp")
from common import *; from fusion_model import Fusion, LoRALinear; from codec import Codec
eg = EG(); V, T, meta, caps, C = load_vindex()
cap2i = {c: i for i, c in enumerate(caps)}
groups = [C[[cap2i[c] for c in m["captions"] if c in cap2i]] for m in meta]
te = list(range(500, 1000)); Vt = V[te]
def nrm(x): return torch.nn.functional.normalize(x, dim=-1)
def enc(texts): return torch.tensor(eg.st.encode(texts, prompt_name="SearchQuery", normalize_embeddings=True, batch_size=64)).cuda()
LoRALinear.on = False
concat = {k: enc([". ".join(meta[i]["captions"][:k]) for i in te]) for k in (2, 3, 5)}   # real-text references, original weights
fu = Fusion(eg, "mp/fusion_lora8.pt"); LoRALinear.on = True
for k in (2, 3, 5):
    f = fu.fuse([groups[i][:k] for i in te]); m = nrm(torch.stack([groups[i][:k].mean(0) for i in te])); ref = concat[k]
    print(f"k={k}: cos(fused,concat) {(f*ref).sum(-1).mean():.3f} vs cos(mean,concat) {(m*ref).sum(-1).mean():.3f} | which-concat R@1: fused {recall(f, ref)['R@1']} mean {recall(m, ref)['R@1']} | vid->: fused {recall(Vt, f)['R@1']} mean {recall(Vt, m)['R@1']} concat {recall(Vt, ref)['R@1']}", flush=True)
# recursion: two-level pass
lvl1 = [torch.stack([fu.fuse([g[:2]])[0], fu.fuse([g[2:5]])[0]]) for g in (groups[i] for i in te)]
h2 = fu.fuse(lvl1); ref = concat[5]
print(f"two-level fuse(fuse(c1,c2), fuse(c3,c4,c5)): cos to concat5 {(h2*ref).sum(-1).mean():.3f} | vid-> {recall(Vt, h2)} ", flush=True)
# singletons re-read: fuse([selfpass(c_i)]) 
sp = [fu.fuse([v[None] for v in groups[i]]) for i in te]
h3 = fu.fuse(sp)
print(f"fuse of 5 self-passed vectors: cos to concat5 {(h3*ref).sum(-1).mean():.3f} | vid-> {recall(Vt, h3)}", flush=True)
# three passes on a single vector
x = T[te]
for p in range(1, 4):
    x = fu.fuse([v[None] for v in x]); print(f"pass {p}: cos to original {(x*T[te]).sum(-1).mean():.3f} | cap->vid {recall(x, Vt)}", flush=True)
# words of fused-5 vectors (original weights for the codec re-embedding)
f5 = fu.fuse([groups[i] for i in te]); LoRALinear.on = False; cd = Codec(eg)
seqs, R = cd.encode(f5[:6], k=8)
for j, (s, r) in enumerate(zip(seqs, R)):
    i = te[j]; print(f"  {meta[i]['captions']}\n     -> {cd.words(s)}   (re-embed cos {(r*f5[j]).sum():.2f})")
