import torch, numpy as np, json
from sentence_transformers import SentenceTransformer

class EG:
    def __init__(self):
        self.st = SentenceTransformer("google/embeddinggemma-2", device="cuda", model_kwargs={"torch_dtype": torch.bfloat16}, config_kwargs={"vision_config": None, "audio_config": None})
        self.am = self.st[0].auto_model.eval()
        self.lm = self.am.language_model
        self.E = self.am.get_input_embeddings()          # scaled word embedding (x22.625)
        self.P = self.lm.embedding_projection.weight.float()   # 768x512
        self.Pinv = torch.linalg.pinv(self.P)             # 512x768
        self.bos = self.E(torch.tensor([2], device="cuda"))[0].float().detach()
        self.eos = self.E(torch.tensor([1], device="cuda"))[0].float().detach()

    @torch.no_grad()
    def forward_embeds(self, x, mask=None):
        """x: (B,T,512) float -> pooled unit 768 vectors"""
        if mask is None: mask = torch.ones(x.shape[:2], device=x.device, dtype=torch.long)
        h = self.am(inputs_embeds=x.to(torch.bfloat16), attention_mask=mask).last_hidden_state.float()
        a = mask.unsqueeze(-1).float()
        return torch.nn.functional.normalize((h*a).sum(1)/a.sum(1), dim=-1)

    @torch.no_grad()
    def forward_ids(self, ids, mask=None):
        if mask is None: mask = torch.ones_like(ids)
        h = self.am(input_ids=ids, attention_mask=mask).last_hidden_state.float()
        a = mask.unsqueeze(-1).float()
        return torch.nn.functional.normalize((h*a).sum(1)/a.sum(1), dim=-1)

    def to_input(self, e, alpha=22.625):
        """unit 768 output vectors (N,768) -> 512 pseudo-token inputs with norm alpha"""
        z = e @ self.Pinv.T
        return torch.nn.functional.normalize(z, dim=-1) * alpha

    @torch.no_grad()
    def selfpass(self, e, alpha=22.625, wrap=True, bs=512):
        out = []
        for s in range(0, len(e), bs):
            z = self.to_input(e[s:s+bs], alpha)              # (b,512)
            if wrap:
                b = z.shape[0]
                x = torch.stack([self.bos.expand(b,-1), z, self.eos.expand(b,-1)], 1)
            else:
                x = z.unsqueeze(1)
            out.append(self.forward_embeds(x))
        return torch.cat(out)

    @torch.no_grad()
    def fuse(self, groups, alpha=22.625, wrap=True):
        """groups: list of (n_i,768) tensors -> (len,768) fused via pseudo-token sequences"""
        out = []
        for g in groups:
            z = self.to_input(g, alpha)
            if wrap: z = torch.cat([self.bos[None], z, self.eos[None]], 0)
            out.append(self.forward_embeds(z[None])[0])
        return torch.stack(out)

def recall(Q, L, k=(1,5,10), target=None):
    """Q (n,d) queries, L (m,d) library, target[i] = correct index (default i)"""
    S = Q @ L.T
    if target is None: target = torch.arange(len(Q), device=Q.device)
    rank = (S > S[torch.arange(len(Q)), target][:,None]).sum(1)
    return {f"R@{kk}": round(100*(rank < kk).float().mean().item(), 1) for kk in k}

def spread(X, n=1000):
    X = X[:n]; S = X @ X.T; m = ~torch.eye(len(X), dtype=bool, device=X.device)
    return round(S[m].mean().item(), 3)

def load_vindex():
    z = np.load("vindex/vindex.npz"); meta = json.load(open("vindex/meta.json"))
    c = np.load("vindex/captions.npz")
    return (torch.tensor(z["video"]).cuda(), torch.tensor(z["text"]).cuda(), meta, list(c["caps"]), torch.tensor(c["C"]).cuda())
