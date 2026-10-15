# Multimodal fusion test on ESC-50 gallery: image + audio -> class caption. Adapter(+LoRA) fusion vs averaging.
import torch, sys, json, numpy as np, random, argparse; sys.path.insert(0, "mp")
from common import *
from codec import Codec
ap = argparse.ArgumentParser(); ap.add_argument("--ckpt", default="mp/fusion_lora0.pt"); args = ap.parse_args()
random.seed(0); torch.manual_seed(0)
eg = EG()
ck = torch.load(args.ckpt)
class LoRALinear(torch.nn.Module):
    on = True
    def __init__(self, base, A, B, r, alpha=16):
        super().__init__(); self.base = base; self.A = torch.nn.Parameter(A.cuda()); self.B = torch.nn.Parameter(B.cuda()); self.scale = alpha / r
    def forward(self, x):
        y = self.base(x)
        if LoRALinear.on: y = y + (x.to(self.A.dtype) @ self.A.T @ self.B.T * self.scale).to(y.dtype)
        return y
if ck["rank"]:
    it = iter(ck["lora"])
    for name, mod in list(eg.lm.layers.named_modules()):
        for cname, child in list(mod.named_children()):
            if isinstance(child, torch.nn.Linear) and cname.endswith("_proj"):
                setattr(mod, cname, LoRALinear(child, next(it), next(it), ck["rank"]))
class Adapter(torch.nn.Module):
    def __init__(self):
        super().__init__(); self.lin = torch.nn.Linear(768, 512, bias=True); self.log_alpha = torch.nn.Parameter(torch.tensor(0.0))
    def forward(self, e): return torch.nn.functional.normalize(self.lin(e), dim=-1) * self.log_alpha.exp()
ad = Adapter().cuda(); ad.load_state_dict(ck["adapter"]); ad.eval()

@torch.no_grad()
def run_seqs(seqs):
    L = max(len(s) for s in seqs) + 2; b = len(seqs)
    x = torch.zeros(b, L, 512, device="cuda"); mask = torch.zeros(b, L, dtype=torch.long, device="cuda")
    for i, s in enumerate(seqs):
        z = torch.cat([eg.bos[None], ad(s), eg.eos[None]], 0); x[i, :len(z)] = z; mask[i, :len(z)] = 1
    return eg.forward_embeds(x, mask)
def fuse(seqs): return torch.cat([run_seqs(seqs[s:s+128]) for s in range(0, len(seqs), 128)])
def nrm(x): return torch.nn.functional.normalize(x, dim=-1)

gal = json.load(open("gallery/gallery.json")); idx = np.load("index/index.npz"); meta = json.load(open("index/meta.json"))
cats = list(idx["cats"]); cat2i = {c: i for i, c in enumerate(cats)}
TXT = torch.tensor(idx["text"]).cuda(); AUD = torch.tensor(idx["audio"]).cuda()
IMG = torch.tensor([g["emb"] for g in gal]).cuda().float(); IMG = nrm(IMG); img_cls = torch.tensor([cat2i[g["class"]] for g in gal]).cuda()
aud_cls = torch.tensor([cat2i[m["category"]] for m in meta]).cuda()
by_cls = {c: [i for i in range(2000) if aud_cls[i] == c] for c in range(50)}
pairs = [(i, random.choice(by_cls[int(img_cls[i])])) for i in range(130) for _ in range(5)]   # matched image+audio
I = IMG[[p[0] for p in pairs]]; A = AUD[[p[1] for p in pairs]]; y = img_cls[[p[0] for p in pairs]]
def acc(Q, L=TXT, target=y):
    S = Q @ L.T; r = (S > S[torch.arange(len(Q)), target][:, None]).sum(1)
    return f"top1 {100*(r<1).float().mean():.1f} top3 {100*(r<3).float().mean():.1f}"
print("matched pairs", len(pairs))
print("image alone      ->class", acc(I))
print("audio alone      ->class", acc(A))
print("mean(img,aud)    ->class", acc(nrm(I + A)))
print("selfpass(img)    ->class", acc(fuse([v[None] for v in I])))
print("selfpass(aud)    ->class", acc(fuse([v[None] for v in A])))
F = fuse([torch.stack([i, a]) for i, a in zip(I, A)])
print("fused [img,aud]  ->class", acc(F))
TXT2 = fuse([v[None] for v in TXT])
print("fused [img,aud]  ->selfpass(class)", acc(F, TXT2))
print("fused [aud,img]  ->class", acc(fuse([torch.stack([a, i]) for i, a in zip(I, A)])))
# conflicting pairs: image of class a, audio of class b != a
conf = [(i, random.choice(by_cls[b])) for i in range(130) for b in random.sample([c for c in range(50) if c != int(img_cls[i])], 4)]
Ic = IMG[[p[0] for p in conf]]; Ac = AUD[[p[1] for p in conf]]; ya = img_cls[[p[0] for p in conf]]; yb = aud_cls[[p[1] for p in conf]]
def split(Q):
    top = (Q @ TXT.T).argmax(-1)
    return f"image-class {100*(top==ya).float().mean():.1f}%  audio-class {100*(top==yb).float().mean():.1f}%  other {100*((top!=ya)&(top!=yb)).float().mean():.1f}%"
print("conflicting pairs", len(conf))
print("mean(img,aud)   picks:", split(nrm(Ic + Ac)))
print("fused [img,aud] picks:", split(fuse([torch.stack([i, a]) for i, a in zip(Ic, Ac)])))
print("fused [aud,img] picks:", split(fuse([torch.stack([a, i]) for i, a in zip(Ic, Ac)])))
# words for a few fused examples
cd = Codec(eg)
ex = [(i, random.choice(by_cls[int(img_cls[i])])) for i in range(0, 130, 13)] + [(i, random.choice(by_cls[(int(img_cls[i]) + 7) % 50])) for i in range(0, 130, 26)]
Fe = fuse([torch.stack([IMG[i], AUD[a]]) for i, a in ex]); seqs, R = cd.encode(Fe, k=8)
for (i, a), s, r in zip(ex, seqs, R):
    print(f"  image:{gal[i]['class']:>14} + audio:{cats[int(aud_cls[a])]:<14} -> {cd.words(s)}   (re-embed cos {(r*Fe[ex.index((i,a))]).sum():.2f}, top class {cats[int((r@TXT.T).argmax())]})")
