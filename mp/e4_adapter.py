# Learn a 768->512 adapter so that the frozen model re-embeds its own vectors faithfully.
import torch, sys, numpy as np, time; sys.path.insert(0, "mp")
from common import *
eg = EG(); V, T, meta, caps, C = load_vindex()
for p in eg.am.parameters(): p.requires_grad_(False)
bank = torch.tensor(np.load("vindex/bank_aug.npz")["E"]).cuda()
audio = torch.tensor(np.load("index/index.npz")["audio"]).cuda()
train = torch.cat([bank, C, audio]); print("train vectors", train.shape, flush=True)
cap2i = {c: i for i, c in enumerate(caps)}
groups = [C[[cap2i[c] for c in m["captions"] if c in cap2i]] for m in meta]
mean5 = torch.nn.functional.normalize(torch.stack([g.mean(0) for g in groups]), dim=-1)

class Adapter(torch.nn.Module):
    def __init__(self, init):
        super().__init__()
        self.lin = torch.nn.Linear(768, 512, bias=True)
        with torch.no_grad(): self.lin.weight.copy_(init); self.lin.bias.zero_()
        self.log_alpha = torch.nn.Parameter(torch.tensor(float(np.log(22.625))))
    def forward(self, e):
        return torch.nn.functional.normalize(self.lin(e), dim=-1) * self.log_alpha.exp()

def run(ad, E):
    z = ad(E); b = len(z)
    x = torch.stack([eg.bos.expand(b, -1), z, eg.eos.expand(b, -1)], 1)
    h = eg.am(inputs_embeds=x.to(torch.bfloat16), attention_mask=torch.ones(b, 3, device="cuda", dtype=torch.long)).last_hidden_state.float()
    return torch.nn.functional.normalize(h.mean(1), dim=-1)

@torch.no_grad()
def fuse(ad, gs):
    out = []
    for g in gs:
        z = torch.cat([eg.bos[None], ad(g), eg.eos[None]], 0)
        out.append(eg.forward_embeds(z[None])[0])
    return torch.stack(out)

@torch.no_grad()
def evaluate(ad, tag):
    V2 = torch.cat([run(ad, V[s:s+256]) for s in range(0, 1000, 256)])
    T2 = torch.cat([run(ad, T[s:s+256]) for s in range(0, 1000, 256)])
    F = fuse(ad, groups)
    print(f"[{tag}] both-sides cap->vid {recall(T2, V2)} | query-only {recall(T2, V)} | cos(e,f(e)) V {round((V*V2).sum(-1).mean().item(), 3)} "
          f"| spread {spread(V2)} | fuse5 vid->text {recall(V, F)} (mean5 {recall(V, mean5)['R@1']}) | cos(F,mean5) {round((F*mean5).sum(-1).mean().item(), 3)}", flush=True)

ad = Adapter(eg.Pinv).cuda()
evaluate(ad, "init=pinv, untrained")
opt = torch.optim.AdamW(ad.parameters(), lr=1e-3, weight_decay=0.0)
steps, bs, tau = 2000, 256, 0.05
t0 = time.time()
for it in range(1, steps+1):
    e = train[torch.randint(0, len(train), (bs,), device="cuda")]
    f = run(ad, e)
    logits = (f @ e.T) / tau
    loss = torch.nn.functional.cross_entropy(logits, torch.arange(bs, device="cuda")) + (1 - (f*e).sum(-1)).mean()
    opt.zero_grad(); loss.backward(); opt.step()
    if it % 100 == 0: print(f"step {it} loss {loss.item():.3f} alpha {ad.log_alpha.exp().item():.1f} {time.time()-t0:.0f}s", flush=True)
    if it % 500 == 0: evaluate(ad, f"step {it}")
torch.save(ad.state_dict(), "mp/adapter.pt")
