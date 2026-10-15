"""Proof bank for /directions/: every caption, every rule-written variant of it, and the translated captions."""
import json
import numpy as np
import torch
from sentence_transformers import SentenceTransformer
from variants import RULES

caps = [str(c) for c in np.load("vindex/captions.npz")["caps"]]
texts, kind = [], []
for c in caps:
    texts.append(c); kind.append("caption")
for name, f in RULES.items():
    for c in caps:
        v = f(c)
        if v != c:
            texts.append(v); kind.append(name)
for v in json.load(open("vindex/translations.json")).values():
    for L, t in v.items():
        if L != "en":
            texts.append(t); kind.append(f"language en>{L}")
seen, T, K = set(), [], []
for t, k in zip(texts, kind):
    if t not in seen:
        seen.add(t); T.append(t); K.append(k)
m = SentenceTransformer("google/embeddinggemma-2", device="cuda", model_kwargs={"torch_dtype": torch.bfloat16},
                        config_kwargs={"vision_config": None, "audio_config": None})
E = m.encode(T, prompt_name="SearchQuery", normalize_embeddings=True, batch_size=256, show_progress_bar=False)
np.savez("vindex/variant_bank.npz", texts=np.array(T), kind=np.array(K), E=np.asarray(E, dtype=np.float16))
print("bank:", len(T), {k: K.count(k) for k in dict.fromkeys(K)})
