"""Build the spoken-search video index: MSR-VTT test-1k clips embedded as video with EmbeddingGemma 2,
plus their captions as text (SearchQuery) so text->video retrieval can be measured before anyone speaks."""
import json
import os
import subprocess
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import torch
from huggingface_hub import hf_hub_download
from sentence_transformers import SentenceTransformer

OUT = "vindex"
os.makedirs(f"{OUT}/clips", exist_ok=True)
os.makedirs(f"{OUT}/posters", exist_ok=True)

test = json.load(open(hf_hub_download("friedrichor/MSR-VTT", "msrvtt_test_1k.json", repo_type="dataset")))
zp = hf_hub_download("friedrichor/MSR-VTT", "MSRVTT_Videos.zip", repo_type="dataset")
with zipfile.ZipFile(zp) as z:
    names = {os.path.basename(n): n for n in z.namelist() if n.endswith(".mp4")}
    for t in test:
        dst = f"{OUT}/clips/{t['video']}"
        if not os.path.exists(dst):
            with z.open(names[t["video"]]) as f, open(dst, "wb") as g:
                g.write(f.read())
print(f"clips: {len(test)}", flush=True)

data = json.load(open(hf_hub_download("friedrichor/MSR-VTT", "raw_data/MSRVTT_data.json", repo_type="dataset")))
caps = {}
for s in data["sentences"]:
    caps.setdefault(s["video_id"], []).append(s["caption"])


def poster(v):
    out = f"{OUT}/posters/{v[:-4]}.jpg"
    if not os.path.exists(out):
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", "1", "-i", f"{OUT}/clips/{v}", "-frames:v", "1",
                        "-vf", "scale=320:-2", "-q:v", "5", out])


with ThreadPoolExecutor(16) as pool:
    list(pool.map(poster, [t["video"] for t in test]))
print("posters done", flush=True)

model = SentenceTransformer("google/embeddinggemma-2", device="cuda", model_kwargs={"torch_dtype": torch.bfloat16})
vids = [t["video"] for t in test]
embs, t0 = [], time.time()
for i in range(0, len(vids), 8):
    batch = [{"video": f"{OUT}/clips/{v}"} for v in vids[i:i + 8]]
    embs.append(model.encode(batch, batch_size=8, normalize_embeddings=True,
                             processing_kwargs={"video": {"fps": 2.0, "max_frames": 24}}))
    if i % 80 == 0:
        print(f"embedded {i + len(batch)}/{len(vids)}  {time.time() - t0:.0f}s", flush=True)
V = np.concatenate(embs).astype(np.float32)
Q = np.asarray(model.encode([t["caption"] for t in test], prompt_name="SearchQuery", normalize_embeddings=True,
                            batch_size=64), dtype=np.float32)
S = Q @ V.T
diag = S[np.arange(len(test)), np.arange(len(test))]
ranks = (S > diag[:, None]).sum(1)
for k in (1, 5, 10):
    print(f"text->video R@{k}: {(ranks < k).mean() * 100:.1f}%")
print(f"text->video median rank: {np.median(ranks) + 1:.0f}")
meta = [{"video": t["video"], "video_id": t["video_id"], "caption": t["caption"],
         "captions": caps.get(t["video_id"], [])[:5], "category": t["category"]} for t in test]
np.savez(f"{OUT}/vindex.npz", video=V, text=Q)
json.dump(meta, open(f"{OUT}/meta.json", "w"))
print("VINDEX_DONE", flush=True)
