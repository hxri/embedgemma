"""Vector -> words codec. Any EmbeddingGemma 2 vector is written back as k vocabulary words chosen so that the model,
reading those words, lands on (nearly) the same point. Greedy matching pursuit over a codebook of all 262k single-token
embeddings. No training anywhere."""
import os
import re
import unicodedata

import numpy as np
import torch

BOS, EOS = 2, 1


class WordsCodec:
    def __init__(self, model, codebook: str = "mp/codebook.npy", masks: str = "mp/codebook_masks.npz"):
        self.model = model
        self.am = model[0].auto_model.eval()
        self.tok = model.tokenizer
        self.CB = torch.tensor(np.load(codebook)).cuda().float()            # (262144, 768) unit vectors
        if os.path.exists(masks):
            z = np.load(masks)
            en, anyl = z["en"], z["any"]
        else:
            en, anyl = self._build_masks(self.CB.shape[0])
            np.savez(masks, en=en, any=anyl)
        self.masks = {"en": torch.tensor(en).cuda(), "any": torch.tensor(anyl).cuda()}
        self.counts = {k: int(v.sum()) for k, v in self.masks.items()}

    def _build_masks(self, n: int):
        en, anyl = np.zeros(n, bool), np.zeros(n, bool)
        english = set()
        if os.path.exists("mp/english.txt"):
            english = {w.strip().lower() for w in open("mp/english.txt", encoding="utf-8", errors="ignore") if len(w.strip()) >= 3}
        for i in range(n):
            s = self.tok.decode([i]).strip()
            if len(s) < 2 or len(s) > 20 or (s.startswith("<") and s.endswith(">")):
                continue
            if not any(unicodedata.category(ch).startswith("L") for ch in s):
                continue
            anyl[i] = True
            piece = self.tok.convert_ids_to_tokens(i) or ""
            if piece.startswith("▁") and re.fullmatch(r"[A-Za-z]{3,}", s) and (not english or s.lower() in english):
                en[i] = True                                                 # a whole word that is in the English dictionary
        return en, anyl

    @staticmethod
    def available(codebook: str = "mp/codebook.npy") -> bool:
        return os.path.exists(codebook)

    @torch.no_grad()
    def forward_ids(self, ids: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
        h = self.am(input_ids=ids, attention_mask=mask).last_hidden_state.float()
        a = mask.unsqueeze(-1).float()
        return torch.nn.functional.normalize((h * a).sum(1) / a.sum(1), dim=-1)

    @torch.no_grad()
    def embed_seqs(self, seqs: list[list[int]]) -> torch.Tensor:
        """[BOS] tokens [EOS], ragged sequences padded on the right and masked out of the mean."""
        L = max(len(s) for s in seqs) + 2
        ids = torch.zeros(len(seqs), L, dtype=torch.long, device="cuda")
        mask = torch.zeros(len(seqs), L, dtype=torch.long, device="cuda")
        for i, s in enumerate(seqs):
            row = [BOS] + list(s) + [EOS]
            ids[i, :len(row)] = torch.tensor(row, device="cuda"); mask[i, :len(row)] = 1
        return torch.cat([self.forward_ids(ids[s:s + 1024], mask[s:s + 1024]) for s in range(0, len(ids), 1024)])

    def word(self, i: int) -> str:
        return self.tok.decode([i]).strip()

    @torch.no_grad()
    def encode(self, vec: np.ndarray, k: int = 8, lang: str = "en", C: int = 48, hub: float = 0.0, tol: float = 0.005) -> dict:
        """Greedy forward selection: at each step try the C tokens closest to what is still missing and keep the one
        whose sequence reads back closest to the target. Then backward elimination: drop any word whose removal
        costs less than `tol`, so stepping-stone words do not survive. Returns the words in order with the
        read-back cosine after each prefix."""
        e = torch.tensor(vec, device="cuda").float()
        e = e / e.norm()
        mask = self.masks.get(lang, self.masks["en"])
        mu = self.CB[mask].mean(0) if hub else 0.0
        seq, cur = [], None
        for step in range(k):
            resid = e if cur is None else torch.nn.functional.normalize(e - (e @ cur) * cur, dim=-1)
            score = self.CB @ (resid - hub * mu)
            score[~mask] = -9
            if seq:
                score[seq] = -9
            cand = score.topk(C).indices.tolist()
            emb = self.embed_seqs([seq + [c] for c in cand])
            cos = emb @ e
            j = int(cos.argmax())
            seq.append(cand[j]); cur = emb[j]
        best = float(cur @ e)
        while len(seq) > 1:
            trials = [seq[:i] + seq[i + 1:] for i in range(len(seq))]
            cos = self.embed_seqs(trials) @ e
            i = int(cos.argmax())
            if float(cos[i]) < best - tol:
                break
            seq, best = trials[i], float(cos[i])
        pref = self.embed_seqs([seq[:i + 1] for i in range(len(seq))])
        cos = pref @ e
        steps = [{"id": t, "word": self.word(t), "cos": round(float(cos[i]), 3)} for i, t in enumerate(seq)]
        return {"words": [s["word"] for s in steps], "steps": steps, "cos": steps[-1]["cos"], "vec": pref[-1].cpu().numpy(),
                "stopped_early": len(seq) < k}

    @torch.no_grad()
    def read(self, text: str) -> np.ndarray:
        """Read words back exactly as the codec does: raw tokens between BOS and EOS, no task prompt."""
        ids = self.tok.encode(text, add_special_tokens=False)[:64] or [self.tok.encode("nothing", add_special_tokens=False)[0]]
        return self.embed_seqs([ids])[0].cpu().numpy()
