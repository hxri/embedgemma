# Load a fusion checkpoint (adapter + optional LoRA) onto an EG instance; expose fuse().
import torch
class LoRALinear(torch.nn.Module):
    on = True
    def __init__(self, base, A, B, r, alpha=16):
        super().__init__(); self.base = base; self.A = torch.nn.Parameter(A.cuda()); self.B = torch.nn.Parameter(B.cuda()); self.scale = alpha / r
    def forward(self, x):
        y = self.base(x)
        if LoRALinear.on: y = y + (x.to(self.A.dtype) @ self.A.T @ self.B.T * self.scale).to(y.dtype)
        return y
class Adapter(torch.nn.Module):
    def __init__(self):
        super().__init__(); self.lin = torch.nn.Linear(768, 512, bias=True); self.log_alpha = torch.nn.Parameter(torch.tensor(0.0))
    def forward(self, e): return torch.nn.functional.normalize(self.lin(e), dim=-1) * self.log_alpha.exp()
class Fusion:
    def __init__(self, eg, ckpt):
        self.eg = eg; ck = torch.load(ckpt)
        if ck["rank"]:
            it = iter(ck["lora"])
            for name, mod in list(eg.lm.layers.named_modules()):
                for cname, child in list(mod.named_children()):
                    if isinstance(child, torch.nn.Linear) and cname.endswith("_proj"):
                        setattr(mod, cname, LoRALinear(child, next(it), next(it), ck["rank"]))
        self.ad = Adapter().cuda(); self.ad.load_state_dict(ck["adapter"]); self.ad.eval()
    @torch.no_grad()
    def _run(self, seqs):
        L = max(len(s) for s in seqs) + 2; b = len(seqs); eg = self.eg
        x = torch.zeros(b, L, 512, device="cuda"); mask = torch.zeros(b, L, dtype=torch.long, device="cuda")
        for i, s in enumerate(seqs):
            z = torch.cat([eg.bos[None], self.ad(s), eg.eos[None]], 0); x[i, :len(z)] = z; mask[i, :len(z)] = 1
        return eg.forward_embeds(x, mask)
    def fuse(self, seqs):
        return torch.cat([self._run(seqs[s:s+128]) for s in range(0, len(seqs), 128)])
