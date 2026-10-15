"""Spoken search over a video corpus: a speech (or text) query embedded by EmbeddingGemma 2, matched against
video embeddings in the same space. No speech recognition anywhere."""
import json
import os

import numpy as np


class SpokenIndex:
    def __init__(self, model, d: str = "vindex"):
        idx = np.load(f"{d}/vindex.npz")
        self.V = idx["video"].astype(np.float32)
        self.T = idx["text"].astype(np.float32)   # the clips' captions, as SearchQuery text: a hint of what was understood
        with open(f"{d}/meta.json") as f:
            self.meta = json.load(f)
        self.model = model

    @staticmethod
    def available(d: str = "vindex") -> bool:
        return os.path.exists(f"{d}/vindex.npz")

    def embed_audio(self, wav: str) -> np.ndarray:
        return np.asarray(self.model.encode({"audio": wav}, normalize_embeddings=True), dtype=np.float32)

    def embed_text(self, text: str) -> np.ndarray:
        return np.asarray(self.model.encode(text, prompt_name="SearchQuery", normalize_embeddings=True), dtype=np.float32)

    def search(self, q: np.ndarray, k: int = 8) -> dict:
        s = self.V @ q
        z = (s - s.mean()) / (s.std() + 1e-8)
        order = np.argsort(-s)[:k]
        st = self.T @ q
        heard = int(np.argmax(st))
        results = []
        for r, i in enumerate(order):
            m = self.meta[i]
            results.append({"rank": r + 1, "video_id": m["video_id"], "caption": m["caption"], "captions": m["captions"],
                            "score": float(s[i]), "z": float(z[i]), "url": f"/clips/{m['video']}",
                            "poster": f"/posters/{m['video_id']}.jpg"})
        return {"results": results, "heard": self.meta[heard]["caption"], "heard_score": float(st[heard]),
                "corpus": len(self.meta)}
