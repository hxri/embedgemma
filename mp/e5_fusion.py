# Phase 2: teach the model to read SEQUENCES of its own vectors. Adapter (+ optional LoRA on the layers).
# Objective: fused(any subset of a clip's items) ~ full-description vector of that clip (contrastive over clips) + singleton self-reconstruction.
import torch, sys, numpy as np, time, random, argparse; sys.path.insert(0, "mp")
from common import *
ap = argparse.ArgumentParser(); ap.add_argument("--lora", type=int, default=0); ap.add_argument("--steps", type=int, default=1500); ap.add_argument("--tag", default="")
args = ap.parse_args()
torch.manual_seed(0); random.seed(0)
eg = EG(); V, T, meta, caps, C = load_vindex()
for p in eg.am.parameters(): p.requires_grad_(False)
bank = torch.tensor(np.load("vindex/bank_aug.npz")["E"]).cuda()
audio = torch.tensor(np.load("index/index.npz")["audio"]).cuda()
single_pool = torch.cat([bank, C, audio])
cap2i = {c: i for i, c in enumerate(caps)}
groups = [C[[cap2i[c] for c in m["captions"] if c in cap2i]] for m in meta]
full_txt = [". ".join(m["captions"]) for m in meta]
FULL = torch.tensor(eg.st.encode(full_txt, prompt_name="SearchQuery", normalize_embeddings=True, batch_size=64)).cuda()
train_ids, test_ids = list(range(500)), list(range(500, 1000))
print("full-description vectors", FULL.shape, "train/test clips", len(train_ids), len(test_ids), flush=True)

# ---- LoRA on every *_proj Linear inside the layers ----
class LoRALinear(torch.nn.Module):
    on = True
    def __init__(self, base, r, alpha=16):
        super().__init__(); self.base = base
        self.A = torch.nn.Parameter(torch.randn(r, base.in_features, device=base.weight.device) * 0.01)
        self.B = torch.nn.Parameter(torch.zeros(base.out_features, r, device=base.weight.device))
        self.scale = alpha / r
    def forward(self, x):
        y = self.base(x)
        if LoRALinear.on: y = y + (x.to(self.A.dtype) @ self.A.T @ self.B.T * self.scale).to(y.dtype)
        return y
lora_params = []
if args.lora:
    for name, mod in list(eg.lm.layers.named_modules()):
        for cname, child in list(mod.named_children()):
            if isinstance(child, torch.nn.Linear) and cname.endswith("_proj"):
                w = LoRALinear(child, args.lora); setattr(mod, cname, w); lora_params += [w.A, w.B]
    print("lora linears:", len(lora_params)//2, flush=True)

class Adapter(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.lin = torch.nn.Linear(768, 512, bias=True)
        self.log_alpha = torch.nn.Parameter(torch.tensor(float(np.log(22.625))))
    def forward(self, e): return torch.nn.functional.normalize(self.lin(e), dim=-1) * self.log_alpha.exp()
ad = Adapter().cuda(); ad.load_state_dict(torch.load("mp/adapter.pt"))

def run_seqs(seqs):
    """seqs: list of (n_i,768) -> fused unit vectors, padded batch"""
    L = max(len(s) for s in seqs) + 2; b = len(seqs)
    x = torch.zeros(b, L, 512, device="cuda"); mask = torch.zeros(b, L, dtype=torch.long, device="cuda")
    for i, s in enumerate(seqs):
        z = torch.cat([eg.bos[None], ad(s), eg.eos[None]], 0); x[i, :len(z)] = z; mask[i, :len(z)] = 1
    h = eg.am(inputs_embeds=x.to(torch.bfloat16), attention_mask=mask).last_hidden_state.float()
    a = mask.unsqueeze(-1).float()
    return torch.nn.functional.normalize((h*a).sum(1)/a.sum(1), dim=-1)

@torch.no_grad()
def evaluate(tag):
    ad.eval(); te = test_ids
    Vt, Tt, FULLt = V[te], T[te], FULL[te]
    def batched(seqs): return torch.cat([run_seqs(seqs[s:s+128]) for s in range(0, len(seqs), 128)])
    f5 = batched([groups[i] for i in te]); m5 = torch.nn.functional.normalize(torch.stack([groups[i].mean(0) for i in te]), dim=-1)
    f2 = batched([groups[i][:2] for i in te]); m2 = torch.nn.functional.normalize(torch.stack([groups[i][:2].mean(0) for i in te]), dim=-1)
    fv1 = batched([torch.stack([V[i], groups[i][0]]) for i in te])   # video + 1 caption -> full description
    s1 = batched([T[i][None] for i in range(1000)])
    print(f"[{tag}] fuse5->vid {recall(Vt, f5)} (mean5 {recall(Vt, m5)['R@1']}, concat {recall(Vt, FULLt)['R@1']}) | fuse2->vid {recall(Vt, f2)} (mean2 {recall(Vt, m2)['R@1']}) "
          f"| cos(fuse5,FULL) {round((f5*FULLt).sum(-1).mean().item(),3)} | vid+cap1->FULL {recall(fv1, FULLt)} (vid alone {recall(Vt, FULLt)['R@1']}) "
          f"| selfpass cap->vid(all) {recall(s1, V)} | spread {spread(f5)}", flush=True)
    ad.train()

evaluate(f"phase1 adapter, lora={args.lora} untrained")
opt = torch.optim.AdamW([{"params": ad.parameters(), "lr": 5e-4}, {"params": lora_params, "lr": 3e-4}], weight_decay=0.0)
bs, tau, t0 = 128, 0.05, time.time()
for it in range(1, args.steps+1):
    clips = random.sample(train_ids, bs)
    seqs, tgt = [], []
    for c in clips:
        items = [g for g in groups[c]]
        if random.random() < 0.5: items.append(V[c])
        k = random.randint(1, len(items)); random.shuffle(items)
        seqs.append(torch.stack(items[:k])); tgt.append(FULL[c])
    f = run_seqs(seqs); tgt = torch.stack(tgt)
    loss_fuse = torch.nn.functional.cross_entropy((f @ tgt.T) / tau, torch.arange(bs, device="cuda")) + (1 - (f*tgt).sum(-1)).mean()
    e = single_pool[torch.randint(0, len(single_pool), (bs,), device="cuda")]
    g = run_seqs([v[None] for v in e])
    loss_self = torch.nn.functional.cross_entropy((g @ e.T) / tau, torch.arange(bs, device="cuda")) + (1 - (g*e).sum(-1)).mean()
    loss = loss_fuse + loss_self
    opt.zero_grad(); loss.backward(); opt.step()
    if it % 100 == 0: print(f"step {it} fuse {loss_fuse.item():.3f} self {loss_self.item():.3f} alpha {ad.log_alpha.exp().item():.1f} {time.time()-t0:.0f}s", flush=True)
    if it % 500 == 0: evaluate(f"step {it}")
torch.save({"adapter": ad.state_dict(), "lora": [p.detach().cpu() for p in lora_params], "rank": args.lora}, f"mp/fusion_lora{args.lora}{args.tag}.pt")
