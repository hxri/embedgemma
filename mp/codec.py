# Vector -> words: greedy matching pursuit over the single-token codebook.
import torch, numpy as np, unicodedata, functools

class Codec:
    def __init__(self, eg):
        self.eg = eg; self.tok = eg.st.tokenizer
        CB = torch.tensor(np.load("mp/codebook.npy")).cuda().float()
        keep = torch.zeros(CB.shape[0], dtype=torch.bool)
        for i in range(CB.shape[0]):
            s = self.tok.decode([i]).strip()
            if len(s) >= 2 and not (s.startswith("<") and s.endswith(">")) and any(unicodedata.category(ch).startswith("L") for ch in s):
                keep[i] = True
        CB[~keep.cuda()] = 0; self.CB = CB

    @torch.no_grad()
    def embed_seqs(self, seqs):
        ids = torch.tensor(seqs, device="cuda")
        x = torch.cat([torch.full((len(ids), 1), 2, device="cuda"), ids, torch.full((len(ids), 1), 1, device="cuda")], 1)
        return torch.cat([self.eg.forward_ids(x[s:s+2048]) for s in range(0, len(x), 2048)])

    def words(self, seq): return " ".join(self.tok.decode([t]).strip() for t in seq)

    @torch.no_grad()
    def encode(self, E, k=8, C=32):
        """E (n,768) unit -> list of token id lists, re-embedded vectors (n,768), per-step mean cos"""
        n = len(E); seqs = [[] for _ in range(n)]; cur = torch.zeros_like(E)
        for step in range(k):
            resid = E if step == 0 else torch.nn.functional.normalize(E - (E*cur).sum(-1, keepdim=True)*cur, dim=-1)
            score = resid @ self.CB.T
            for i, s in enumerate(seqs):
                if s: score[i, s] = -9
            cand = score.topk(C, dim=-1).indices
            flat = [seqs[i] + [int(cand[i, j])] for i in range(n) for j in range(C)]
            emb = self.embed_seqs(flat).view(n, C, -1)
            cos = (emb * E[:, None]).sum(-1); best = cos.argmax(-1)
            for i in range(n): seqs[i].append(int(cand[i, best[i]]))
            cur = emb[torch.arange(n), best]
        return seqs, cur
