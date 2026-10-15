"""Core retrieval logic shared by the CLI (match.py) and the web server (server.py).

Everything is EmbeddingGemma 2: the query clip (frames, its audio, or both interleaved),
the ESC-50 clips (audio) and the class captions (text) all live in one 768-d space.
"""
import json
import os
import re
import subprocess
import time

import numpy as np
import soundfile as sf
import torch
from sentence_transformers import SentenceTransformer

from captions import CAPTIONS

MODEL_ID = "google/embeddinggemma-2"
FAMILIES = ["animals", "nature", "human", "home", "city"]  # ESC-50 target // 10


def has_audio(path: str) -> bool:
    p = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=codec_type", "-of", "csv=p=0", path],
        capture_output=True, text=True,
    )
    return "audio" in p.stdout


def levels_db(path: str) -> tuple[float, float]:
    """(mean, peak) level of the clip's audio in dBFS, ignoring 0.3 s at each end (start/stop clicks).
    A quiet room averages around -50; talking or clapping -25 to -40; a single snap or knock peaks above -20."""
    p = subprocess.run(["ffmpeg", "-hide_banner", "-i", path, "-vn",
                        "-af", "atrim=start=0.3,areverse,atrim=start=0.3,areverse,volumedetect", "-f", "null", "-"],
                       capture_output=True, text=True)
    m = re.search(r"mean_volume:\s*(-?[\d.]+) dB", p.stderr)
    pk = re.search(r"max_volume:\s*(-?[\d.]+) dB", p.stderr)
    return (float(m.group(1)) if m else -99.0, float(pk.group(1)) if pk else -99.0)


def mean_db(path: str) -> float:
    return levels_db(path)[0]


def extract_audio(path: str) -> str:
    wav = path.rsplit(".", 1)[0] + "_q16k.wav"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", path, "-vn", "-ac", "1", "-ar", "16000",
                    "-c:a", "pcm_s16le", wav], check=True)
    return wav


def events_only(wav: str, pad_s: float = 0.18, min_events_s: float = 0.25) -> tuple[str, float, float]:
    """Keep only the loud moments of a take (a clap, a knock, a word), padded, concatenated.
    A ten-second take with three claps is mostly room tone, and room tone embeds as 'train' or 'crickets';
    the events are what the sound actually is. Returns (path, seconds kept, seconds total); falls back to the
    whole take when there is nothing sharp enough to gate on."""
    x, sr = sf.read(wav, dtype="float32")
    if x.ndim > 1:
        x = x.mean(axis=1)
    hop = int(sr * 0.02)
    n = len(x) // hop
    rms = np.sqrt(np.maximum(1e-12, (x[: n * hop].reshape(n, hop) ** 2).mean(axis=1)))
    db = 20 * np.log10(rms + 1e-9)
    floor = np.percentile(db, 20)
    thr = max(floor + 12.0, -42.0)
    active = db > thr
    pad = int(pad_s / 0.02)
    idx = np.flatnonzero(active)
    if idx.size == 0:
        return wav, 0.0, len(x) / sr
    keep = np.zeros(n, dtype=bool)
    for i in idx:
        keep[max(0, i - pad): min(n, i + pad + 1)] = True
    kept_s = keep.sum() * 0.02
    if kept_s < min_events_s or keep.all():
        return wav, kept_s, len(x) / sr
    out = np.concatenate([x[i * hop:(i + 1) * hop] for i in np.flatnonzero(keep)])
    ev = wav.replace("_q16k.wav", "_q16k_events.wav")
    sf.write(ev, out, sr)
    return ev, float(kept_s), len(x) / sr


def transcode(src: str, dst: str) -> None:
    """Normalise any upload (webm from Chrome, mp4 from Safari/ffmpeg) to h264 + aac mp4."""
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-c:v", "libx264", "-preset", "veryfast",
                    "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-c:a", "aac", "-ar", "48000", dst], check=True)


def poster(video: str, out: str, at: float = 1.0) -> None:
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", str(at), "-i", video, "-frames:v", "1", "-q:v", "4", out], check=True)


def mux(video: str, sfx: str, out: str, mix: bool) -> None:
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", video, "-stream_loop", "-1", "-i", sfx]
    if mix and has_audio(video):
        cmd += ["-filter_complex", "[0:a][1:a]amix=inputs=2:duration=first:dropout_transition=0[a]",
                "-map", "0:v:0", "-map", "[a]"]
    else:
        cmd += ["-map", "0:v:0", "-map", "1:a:0", "-shortest"]
    subprocess.run(cmd + ["-c:v", "copy", "-c:a", "aac", "-movflags", "+faststart", out], check=True)


def family_of(file: str) -> str:
    target = int(os.path.basename(file).rsplit("-", 1)[1].split(".")[0])  # ESC-50 name: fold-src-take-target.wav
    return FAMILIES[target // 10]


class Engine:
    def __init__(self, index_dir: str = "index", device: str = "cuda"):
        idx = np.load(f"{index_dir}/index.npz", allow_pickle=True)
        with open(f"{index_dir}/meta.json") as f:
            self.meta = json.load(f)
        self.audio = idx["audio"].astype(np.float32)
        self.text = idx["text"].astype(np.float32)
        self.cats = [str(c) for c in idx["cats"]]
        self.cat_pos = {c: i for i, c in enumerate(self.cats)}
        self.clip_cat = np.array([self.cat_pos[m["category"]] for m in self.meta])
        for m in self.meta:
            m["name"] = os.path.basename(m["file"])
            m["family"] = family_of(m["file"])
        t = time.time()
        self.model = SentenceTransformer(MODEL_ID, device=device, model_kwargs={"torch_dtype": torch.bfloat16})
        self.load_s = time.time() - t

    # ---- query ---------------------------------------------------------------------------------
    def embed_query(self, video: str, query: str = "both", fps: float = 3.0, max_frames: int = 32,
                    gate_db: float = -42.0, peak_db: float = -28.0, events: bool = True) -> tuple[np.ndarray | None, np.ndarray | None, dict]:
        """Two separate embeddings: frames (v) and the clip's audio (a). Interleaving them into one vector lets
        thousands of frame tokens drown a few hundred audio tokens in the mean pool; scoring them apart keeps
        a clap a clap."""
        info = {"requested": query, "has_audio": has_audio(video), "mean_db": None, "peak_db": None}
        use_audio = query in ("audio", "both") and info["has_audio"]
        if use_audio and query == "both":
            info["mean_db"], info["peak_db"] = levels_db(video)
            # room tone only: quiet on average AND nothing sharp (a snap, a knock) anywhere in the take
            if info["mean_db"] < gate_db and info["peak_db"] < peak_db:
                use_audio = False
        used = "audio" if (use_audio and query == "audio") else ("both" if use_audio else "video")
        t = time.time()
        v = a = None
        if used in ("video", "both"):
            v = self.model.encode({"video": video}, normalize_embeddings=True,
                                  processing_kwargs={"video": {"fps": fps, "max_frames": max_frames}})
            v = np.asarray(v, dtype=np.float32)
        if used in ("audio", "both"):
            wav = extract_audio(video)
            if events:
                wav, kept, total = events_only(wav)
                info.update(events_s=round(kept, 2), audio_s=round(total, 2))
            a = np.asarray(self.model.encode({"audio": wav}, normalize_embeddings=True), dtype=np.float32)
        info.update(used=used, embed_s=round(time.time() - t, 3))
        return v, a, info

    # ---- scoring -------------------------------------------------------------------------------
    def score(self, v: np.ndarray | None, a: np.ndarray | None, mode: str = "both", alpha: float = 0.5,
              k: int = 8) -> dict:
        """visual path: frames vs class captions (the benchmarked video<->text pairing);
        audio path: the take's audio vs every library clip's audio. Each path is z-scored over the library
        before blending, so a path with a wider dynamic range cannot swamp the other."""
        s_cat = self.text @ (v if v is not None else a)          # per class
        s_text = s_cat[self.clip_cat]                             # per clip
        s_audio = self.audio @ (a if a is not None else v)        # per clip
        z = lambda x: (x - x.mean()) / (x.std() + 1e-8)
        za, zt = z(s_audio), z(s_text)
        score = {"audio": za, "text": zt, "both": alpha * za + (1 - alpha) * zt}[mode]

        def clip(i: int, rank: int | None = None) -> dict:
            m = self.meta[i]
            return {"rank": rank, "clip": m["name"], "class": m["category"], "caption": CAPTIONS[m["category"]],
                    "family": m["family"], "score": float(score[i]), "z": float(score[i]),
                    "audio": float(s_audio[i]), "text": float(s_text[i]), "url": f"/sfx/{m['name']}"}

        order = np.argsort(-score)
        results = [clip(int(i), r + 1) for r, i in enumerate(order[:k])]

        # per-class view: the best clip of each class under the active scoring
        best = {}
        for i in order:
            c = int(self.clip_cat[i])
            if c not in best:
                best[c] = int(i)
        cls_score = np.array([score[best[c]] for c in range(len(self.cats))])
        classes = []
        for c, name in enumerate(self.cats):
            m = self.meta[best[c]]
            classes.append({"class": name, "caption": CAPTIONS[name], "family": m["family"],
                            "score": float(cls_score[c]), "z": float(cls_score[c]),
                            "audio": float(s_audio[best[c]]), "text": float(s_cat[c]),
                            "clip": m["name"], "url": f"/sfx/{m['name']}"})
        classes.sort(key=lambda d: -d["score"])
        for r, d in enumerate(classes, 1):
            d["rank"] = r

        text_top = [{"class": self.cats[i], "score": float(s_cat[i])} for i in np.argsort(-s_cat)[:5]]
        audio_top, seen = [], set()
        for i in np.argsort(-s_audio):
            c = self.meta[i]["category"]
            if c not in seen:
                seen.add(c)
                audio_top.append({"class": c, "score": float(s_audio[i])})
            if len(audio_top) == 5:
                break
        return {"mode": mode, "alpha": alpha, "results": results, "classes": classes,
                "paths": {"text": text_top, "audio": audio_top}}

    def match(self, video: str, query: str = "both", mode: str = "both", alpha: float = 0.5, k: int = 8,
              fps: float = 3.0, max_frames: int = 32, gate_db: float = -42.0, peak_db: float = -28.0,
              events: bool = True) -> dict:
        v, a, info = self.embed_query(video, query, fps, max_frames, gate_db, peak_db, events)
        out = self.score(v, a, mode, alpha, k)
        out["query"] = info
        return out

    def clip_path(self, name: str) -> str | None:
        for m in self.meta:
            if m["name"] == name:
                return m["file"]
        return None
