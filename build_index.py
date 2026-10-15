#!/usr/bin/env python
"""Build the sound-effect index on the GPU box.

Downloads ESC-50 (2000 x 5 s environmental sound clips, 50 classes), writes each clip
as 16 kHz mono wav, embeds every clip as AUDIO with EmbeddingGemma 2, and embeds each
class label as a TEXT document. Both live in the same 768-d space as a video embedding.
"""
import argparse
import json
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import torch
from datasets import Audio, load_dataset
from sentence_transformers import SentenceTransformer

from captions import CAPTIONS

MODEL_ID = "google/embeddinggemma-2"


def to_16k_mono(src: str, dst: str) -> None:
    if os.path.exists(dst):
        return
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", dst],
        check=True,
    )


def embed_labels(model: SentenceTransformer, cats: list[str]) -> np.ndarray:
    missing = [c for c in cats if c not in CAPTIONS]
    assert not missing, f"no caption for: {missing}"
    embs = model.encode([CAPTIONS[c] for c in cats], prompt_name="Document", normalize_embeddings=True)
    return np.asarray(embs, dtype=np.float32)


def save_index(out: str, audio: np.ndarray, text: np.ndarray, cats: list[str]) -> None:
    tmp = f"{out}/index.npz.tmp.npz"
    np.savez(tmp, audio=audio, text=text, cats=np.array(cats))
    os.replace(tmp, f"{out}/index.npz")  # atomic: a concurrent match.py sees old or new, never a torn file


def relabel(out: str) -> None:
    idx = np.load(f"{out}/index.npz", allow_pickle=True)
    cats = [str(c) for c in idx["cats"]]
    model = SentenceTransformer(MODEL_ID, device="cuda", model_kwargs={"torch_dtype": torch.bfloat16})
    save_index(out, idx["audio"], embed_labels(model, cats), cats)
    print(f"relabelled {len(cats)} classes -> {out}/index.npz")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="index")
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--limit", type=int, default=0, help="only first N clips (smoke test)")
    ap.add_argument("--relabel", action="store_true", help="recompute only the text-label embeddings of an existing index")
    args = ap.parse_args()

    if args.relabel:
        return relabel(args.out)

    raw_dir, wav_dir = f"{args.out}/raw", f"{args.out}/wav"
    os.makedirs(raw_dir, exist_ok=True)
    os.makedirs(wav_dir, exist_ok=True)

    ds = load_dataset("ashraq/esc50", split="train")
    if args.limit:
        ds = ds.select(range(args.limit))
    ds = ds.cast_column("audio", Audio(decode=False))  # keep raw bytes; we resample with ffmpeg

    meta, jobs = [], []
    for i, ex in enumerate(ds):
        stem = os.path.splitext(ex["filename"])[0]
        raw, wav = f"{raw_dir}/{stem}.wav", f"{wav_dir}/{stem}.wav"
        if not os.path.exists(raw):
            with open(raw, "wb") as f:
                f.write(ex["audio"]["bytes"])
        jobs.append((raw, wav))
        meta.append({"i": i, "file": wav, "category": ex["category"], "fold": ex["fold"], "esc10": bool(ex["esc10"])})
    with ThreadPoolExecutor(16) as pool:
        list(pool.map(lambda j: to_16k_mono(*j), jobs))
    print(f"prepared {len(meta)} clips")

    model = SentenceTransformer(MODEL_ID, device="cuda", model_kwargs={"torch_dtype": torch.bfloat16})
    audio_embs = model.encode(
        [{"audio": m["file"]} for m in meta], batch_size=args.batch, normalize_embeddings=True, show_progress_bar=True
    )
    cats = sorted({m["category"] for m in meta})
    text_embs = embed_labels(model, cats)
    save_index(args.out, np.asarray(audio_embs, dtype=np.float32), text_embs, cats)
    with open(f"{args.out}/meta.json", "w") as f:
        json.dump(meta, f)
    print(f"index: {len(meta)} audio embs, {len(cats)} label embs -> {args.out}/index.npz")


if __name__ == "__main__":
    main()
