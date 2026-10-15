"""Persistent demo server on big-machine: keeps EmbeddingGemma 2 loaded, serves the UI, the API, and media.

  CUDA_VISIBLE_DEVICES=0 uvicorn server:app --host 127.0.0.1 --port 8787
"""
import json
import os
import threading
import time
import uuid
from contextlib import asynccontextmanager

import httpx
import numpy as np
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from fastapi.concurrency import run_in_threadpool
from fastapi.staticfiles import StaticFiles

from captions import CAPTIONS
from engine import Engine, extract_audio, mux, poster, transcode
from spoken import SpokenIndex
from words import WordsCodec
from directions import Directions

MEDIA = "media"
os.makedirs(MEDIA, exist_ok=True)
state: dict = {}
lock = threading.Lock()  # one GPU, one inference at a time


@asynccontextmanager
async def lifespan(app: FastAPI):
    state["engine"] = await run_in_threadpool(Engine)
    if SpokenIndex.available():
        state["spoken"] = SpokenIndex(state["engine"].model)
    if os.path.exists("vindex/directions.json"):
        d = json.load(open("vindex/directions.json"))
        state["dirs"] = {k: {"vec": np.asarray(v["vec"], dtype=np.float32), "pos": v["pos"], "neg": v["neg"]}
                         for k, v in d["directions"].items() if k in d["chosen"]}
        state["dir_order"] = d["chosen"]
    if os.path.exists("vindex/bank_aug.npz"):
        bank = np.load("vindex/bank_aug.npz", allow_pickle=True)
        state["bank_caps"], state["bank_E"] = [str(c) for c in bank["caps"]], bank["E"].astype(np.float32)
    state["points"] = {}
    state["takes"] = {}
    if WordsCodec.available():
        state["words"] = await run_in_threadpool(WordsCodec, state["engine"].model)
        state["words_vecs"] = {}
    if Directions.available():
        state["dirs_text"] = await run_in_threadpool(Directions, state["engine"].model)
    if os.path.exists("gallery/gallery.json"):
        g = json.load(open("gallery/gallery.json"))
        state["gallery"] = g
        state["gallery_E"] = np.asarray([x["emb"] for x in g], dtype=np.float32)
        e = state["engine"]
        state["photo_txt"] = np.asarray(e.model.encode([f"a photo of {CAPTIONS[c]}" for c in e.cats], prompt_name="Document",
                                                       normalize_embeddings=True), dtype=np.float32)
    yield


app = FastAPI(lifespan=lifespan)


@app.get("/api/health")
def health():
    e = state.get("engine")
    return {"ok": e is not None, "model": "google/embeddinggemma-2", "clips": len(e.meta) if e else 0,
            "classes": len(e.cats) if e else 0, "load_s": round(e.load_s, 1) if e else None}


@app.get("/api/classes")
def classes():
    e = state["engine"]
    first = {}
    for m in e.meta:
        first.setdefault(m["category"], m)
    return [{"class": c, "caption": CAPTIONS[c], "family": first[c]["family"], "clip": first[c]["name"],
             "url": f"/sfx/{first[c]['name']}"} for c in e.cats]


@app.post("/api/match")
async def match(video: UploadFile = File(...), query: str = Form("both"), mode: str = Form("both"),
                alpha: float = Form(0.5), k: int = Form(8), fps: float = Form(3.0), max_frames: int = Form(32),
                gate_db: float = Form(-42.0), peak_db: float = Form(-28.0), events: bool = Form(True)):
    e = state.get("engine")
    if e is None:
        raise HTTPException(503, "model still loading")
    vid = uuid.uuid4().hex[:10]
    ext = (video.filename or "clip.webm").rsplit(".", 1)[-1].lower() or "webm"
    raw = f"{MEDIA}/{vid}_raw.{ext}"
    mp4 = f"{MEDIA}/{vid}.mp4"
    with open(raw, "wb") as f:
        f.write(await video.read())
    t0 = time.time()
    await run_in_threadpool(transcode, raw, mp4)
    await run_in_threadpool(poster, mp4, f"{MEDIA}/{vid}.jpg")
    t1 = time.time()

    def run():
        with lock:
            return e.match(mp4, query=query, mode=mode, alpha=alpha, k=k, fps=fps, max_frames=max_frames, gate_db=gate_db, peak_db=peak_db, events=events)

    out = await run_in_threadpool(run)
    out.update(id=vid, video_url=f"/media/{vid}.mp4", poster_url=f"/media/{vid}.jpg",
               timings={"transcode_s": round(t1 - t0, 2), "embed_s": out["query"]["embed_s"], "total_s": round(time.time() - t0, 2)})
    return out


@app.post("/api/say")
async def say(audio: UploadFile = File(...), k: int = Form(8)):
    sp = state.get("spoken")
    if sp is None:
        raise HTTPException(503, "video index not built")
    sid = uuid.uuid4().hex[:10]
    ext = (audio.filename or "q.webm").rsplit(".", 1)[-1].lower() or "webm"
    raw = f"{MEDIA}/say_{sid}.{ext}"
    with open(raw, "wb") as f:
        f.write(await audio.read())
    t0 = time.time()
    wav = await run_in_threadpool(extract_audio, raw)

    def run():
        with lock:
            return sp.search(sp.embed_audio(wav), k)

    out = await run_in_threadpool(run)
    out.update(id=sid, query_url=f"/media/say_{sid}_q16k.wav", seconds=round(time.time() - t0, 2), mode="speech")
    return out


@app.post("/api/ask")
async def ask(text: str = Form(...), k: int = Form(8)):
    sp = state.get("spoken")
    if sp is None:
        raise HTTPException(503, "video index not built")
    t0 = time.time()

    def run():
        with lock:
            return sp.search(sp.embed_text(text), k)

    out = await run_in_threadpool(run)
    out.update(seconds=round(time.time() - t0, 2), mode="text", text=text)
    return out


# ---------------- steering: move a point in the space, look around it, decode it ----------------
STEER_URL = "http://127.0.0.1:8788"


class SteerPoint(BaseModel):
    base: dict            # {"kind": "text"|"video"|"take", "value": sentence | video_id | take id}
    weights: dict[str, float] = {}


@app.get("/api/steer/dirs")
def steer_dirs():
    if "dirs" not in state:
        raise HTTPException(503, "directions not built yet")
    return [{"name": k, "pos": state["dirs"][k]["pos"], "neg": state["dirs"][k]["neg"]} for k in state["dir_order"]]


def _base_vector(base: dict) -> tuple[np.ndarray, dict]:
    e, sp = state["engine"], state.get("spoken")
    kind, value = base.get("kind"), base.get("value")
    if kind == "text":
        v = np.asarray(e.model.encode(str(value), prompt_name="Document", normalize_embeddings=True), dtype=np.float32)
        return v, {"kind": "text", "text": str(value)}
    if kind == "video":
        if sp is None:
            raise HTTPException(503, "video index not built")
        i = next((i for i, m in enumerate(sp.meta) if m["video_id"] == value), None)
        if i is None:
            raise HTTPException(404, "unknown video")
        m = sp.meta[i]
        return sp.V[i], {"kind": "video", "video_id": value, "caption": m["caption"], "url": f"/clips/{m['video']}", "poster": f"/posters/{value}.jpg"}
    if kind == "take":
        t = state["takes"].get(value)
        if t is None:
            raise HTTPException(404, "unknown take")
        return t["vec"], {"kind": "take", "id": value, "url": t["url"], "poster": t["poster"]}
    raise HTTPException(400, "base.kind must be text, video or take")


@app.post("/api/steer/point")
def steer_point(req: SteerPoint):
    if "dirs" not in state:
        raise HTTPException(503, "directions not built yet")
    with lock:
        base, info = _base_vector(req.base)
    t = base.copy()
    for k, w in req.weights.items():
        if k in state["dirs"] and w:
            t = t + float(w) * state["dirs"][k]["vec"]
    t = t / (np.linalg.norm(t) + 1e-8)
    pid = uuid.uuid4().hex[:10]
    state["points"][pid] = t
    if len(state["points"]) > 200:
        state["points"].pop(next(iter(state["points"])))
    out = {"point_id": pid, "base": info, "weights": req.weights, "moved": float(1 - base @ t)}
    sp, e = state.get("spoken"), state["engine"]
    if sp is not None:
        s = sp.V @ t
        out["clips"] = [{"video_id": sp.meta[i]["video_id"], "caption": sp.meta[i]["caption"], "score": float(s[i]),
                         "url": f"/clips/{sp.meta[i]['video']}", "poster": f"/posters/{sp.meta[i]['video_id']}.jpg"} for i in np.argsort(-s)[:4]]
    sa = e.audio @ t
    sounds, seen = [], set()
    for i in np.argsort(-sa):
        m = e.meta[i]
        if m["category"] in seen:
            continue
        seen.add(m["category"])
        sounds.append({"class": m["category"], "caption": CAPTIONS[m["category"]], "family": m["family"], "score": float(sa[i]), "url": f"/sfx/{m['name']}"})
        if len(sounds) == 3:
            break
    out["sounds"] = sounds
    if "bank_E" in state:
        sb = state["bank_E"] @ t
        out["captions"] = [{"text": state["bank_caps"][i], "score": float(sb[i])} for i in np.argsort(-sb)[:5]]
    return out


class SteerDecode(BaseModel):
    point_id: str
    hints: bool = True
    particles: int = 6
    steps: int = 24


@app.post("/api/steer/decode")
async def steer_decode(req: SteerDecode):
    t = state["points"].get(req.point_id)
    if t is None:
        raise HTTPException(404, "unknown point; move a slider first")
    async with httpx.AsyncClient(timeout=180) as c:
        try:
            r = await c.post(f"{STEER_URL}/decode", json={"target": t.tolist(), "hints": req.hints, "particles": req.particles, "steps": req.steps})
        except httpx.HTTPError as ex:
            raise HTTPException(503, f"decoder not running: {ex}")
    if r.status_code != 200:
        raise HTTPException(r.status_code, r.text)
    return r.json()


@app.post("/api/steer/upload")
async def steer_upload(video: UploadFile = File(...)):
    e = state["engine"]
    tid = uuid.uuid4().hex[:10]
    ext = (video.filename or "clip.webm").rsplit(".", 1)[-1].lower() or "webm"
    raw, mp4, jpg = f"{MEDIA}/take_{tid}_raw.{ext}", f"{MEDIA}/take_{tid}.mp4", f"{MEDIA}/take_{tid}.jpg"
    with open(raw, "wb") as f:
        f.write(await video.read())
    await run_in_threadpool(transcode, raw, mp4)
    await run_in_threadpool(poster, mp4, jpg)

    def run():
        with lock:
            v = e.model.encode({"video": mp4}, normalize_embeddings=True, processing_kwargs={"video": {"fps": 3.0, "max_frames": 32}})
            return np.asarray(v, dtype=np.float32)

    vec = await run_in_threadpool(run)
    state["takes"][tid] = {"vec": vec, "url": f"/media/take_{tid}.mp4", "poster": f"/media/take_{tid}.jpg"}
    return {"id": tid, "url": f"/media/take_{tid}.mp4", "poster": f"/media/take_{tid}.jpg"}


# ---------------- SFX finder: a still frame in, the three closest sound effects out ----------------
@app.get("/api/sfx/gallery")
def sfx_gallery():
    g = state.get("gallery")
    if not g:
        raise HTTPException(503, "gallery not built")
    import random
    items = [{"id": i, "url": f"/{x['file']}", "caption": x["caption"], "license": x["license"], "page": x["page"]} for i, x in enumerate(g)]
    random.Random(7).shuffle(items)
    return items


def _frame_from_upload(raw: str, ext: str) -> str:
    """Images are used as-is; videos give their frame at 1 s."""
    if ext in ("mp4", "mov", "webm", "m4v", "mkv"):
        jpg = raw.rsplit(".", 1)[0] + ".jpg"
        poster(raw, jpg, at=1.0)
        return jpg
    return raw


@app.post("/api/sfx")
async def sfx(file: UploadFile | None = File(None), gallery_id: int | None = Form(None), method: str = Form("bridged"), k: int = Form(3)):
    e = state["engine"]
    if "photo_txt" not in state:
        raise HTTPException(503, "gallery not built")
    t0 = time.time()
    if gallery_id is not None:
        g = state["gallery"][gallery_id]
        emb, image_url, credit = state["gallery_E"][gallery_id], f"/{g['file']}", {"license": g["license"], "page": g["page"], "title": g["title"]}
    elif file is not None:
        sid = uuid.uuid4().hex[:10]
        ext = (file.filename or "frame.jpg").rsplit(".", 1)[-1].lower() or "jpg"
        raw = f"{MEDIA}/sfx_{sid}.{ext}"
        with open(raw, "wb") as f:
            f.write(await file.read())
        frame = await run_in_threadpool(_frame_from_upload, raw, ext)
        from PIL import Image
        img = Image.open(frame).convert("RGB"); img.thumbnail((1024, 1024))

        def run():
            with lock:
                return np.asarray(e.model.encode({"image": img}, normalize_embeddings=True), dtype=np.float32)

        emb = await run_in_threadpool(run)
        image_url, credit = f"/{frame}", None
    else:
        raise HTTPException(400, "send a file or a gallery_id")

    s_photo = state["photo_txt"] @ emb                      # (50) what the frame looks like, by class caption
    s_direct = e.audio @ emb                                 # (2000) frame vs every clip's audio, the weak path
    cls_direct = np.array([s_direct[e.clip_cat == c].max() for c in range(len(e.cats))])
    z = lambda x: (x - x.mean()) / (x.std() + 1e-8)
    cls = {"bridged": s_photo, "direct": cls_direct, "blend": z(s_photo) + z(cls_direct)}.get(method, s_photo)
    order = np.argsort(-cls)
    results = []
    for c in order[:k]:
        members = np.flatnonzero(e.clip_cat == c)
        best = int(members[np.argmax(s_direct[members])])
        m = e.meta[best]
        results.append({"class": e.cats[c], "caption": CAPTIONS[e.cats[c]], "family": m["family"], "score": float(cls[c]),
                        "z": float(z(cls)[c]), "clip": m["name"], "url": f"/sfx/{m['name']}",
                        "alternatives": [{"clip": e.meta[int(i)]["name"], "url": f"/sfx/{e.meta[int(i)]['name']}"} for i in members[np.argsort(-s_direct[members])[1:4]]]})
    return {"image_url": image_url, "credit": credit, "method": method, "results": results,
            "sees": [{"class": e.cats[c], "caption": CAPTIONS[e.cats[c]], "score": float(s_photo[c])} for c in np.argsort(-s_photo)[:5]],
            "seconds": round(time.time() - t0, 2)}


# ---------------- words codec: any point in the space, written back as k words the model reads the same way ----------------
SENTENCES = ["a man is playing piano", "a dog barking at the mailman", "rain falling on a tin roof at night",
             "children laughing in a playground", "a woman decorating a cake with flowers", "a train pulling into a busy station"]


def _nearest(vec: np.ndarray, k: int = 3) -> dict:
    e, sp = state["engine"], state.get("spoken")
    s = e.audio @ vec
    sounds, seen = [], set()
    for i in np.argsort(-s):
        c = e.meta[i]["category"]
        if c in seen:
            continue
        seen.add(c)
        sounds.append({"class": c, "caption": CAPTIONS[c], "family": e.meta[i]["family"], "url": f"/sfx/{e.meta[i]['name']}",
                       "score": round(float(s[i]), 3)})
        if len(sounds) == k:
            break
    clips = []
    if sp is not None:
        clips = [{"video_id": r["video_id"], "caption": r["caption"], "url": r["url"], "poster": r["poster"], "score": round(r["score"], 3)}
                 for r in sp.search(vec, k)["results"]]
    return {"sounds": sounds, "clips": clips}


@app.get("/api/words/picks")
def words_picks():
    wc = state.get("words")
    if wc is None:
        raise HTTPException(503, "codebook not built")
    e = state["engine"]
    import random
    photos = [{"id": i, "url": f"/{x['file']}", "caption": x["caption"], "class": x["class"]} for i, x in enumerate(state.get("gallery", []))]
    random.Random(7).shuffle(photos)
    sounds = []
    for c, name in enumerate(e.cats):
        members = np.flatnonzero(e.clip_cat == c)
        best = int(members[np.argmax(e.audio[members] @ e.text[c])])
        m = e.meta[best]
        sounds.append({"i": best, "class": name, "caption": CAPTIONS[name], "family": m["family"], "url": f"/sfx/{m['name']}"})
    sounds.sort(key=lambda d: (d["family"], d["class"]))
    return {"photos": photos, "sounds": sounds, "sentences": SENTENCES, "vocab": wc.counts}


@app.post("/api/words")
async def words_encode(file: UploadFile | None = File(None), photo_id: int | None = Form(None), sound_i: int | None = Form(None),
                       text: str = Form(""), k: int = Form(8), lang: str = Form("en")):
    wc = state.get("words")
    if wc is None:
        raise HTTPException(503, "codebook not built")
    e = state["engine"]
    t0 = time.time()
    inputs, vecs = [], []
    if photo_id is not None and "gallery" in state:
        g = state["gallery"][photo_id]
        vecs.append(state["gallery_E"][photo_id])
        inputs.append({"kind": "photo", "label": g["caption"], "url": f"/{g['file']}"})
    if sound_i is not None:
        m = e.meta[sound_i]
        vecs.append(e.audio[sound_i])
        inputs.append({"kind": "sound", "label": CAPTIONS[m["category"]], "url": f"/sfx/{m['name']}", "family": m["family"]})
    text = text.strip()
    if text:
        def run_text():
            with lock:
                return np.asarray(e.model.encode(text, prompt_name="SearchQuery", normalize_embeddings=True), dtype=np.float32)
        vecs.append(await run_in_threadpool(run_text))
        inputs.append({"kind": "text", "label": text})
    if file is not None:
        sid = uuid.uuid4().hex[:10]
        ext = (file.filename or "upload.bin").rsplit(".", 1)[-1].lower() or "bin"
        raw = f"{MEDIA}/words_{sid}.{ext}"
        with open(raw, "wb") as f:
            f.write(await file.read())
        kind = ("video" if ext in ("mp4", "mov", "webm", "m4v", "mkv") else
                "sound" if ext in ("wav", "mp3", "m4a", "aac", "ogg", "flac", "aiff", "aif", "caf") else "photo")

        def run_file():
            with lock:
                if kind == "photo":
                    from PIL import Image
                    img = Image.open(raw).convert("RGB")
                    img.thumbnail((1024, 1024))
                    return np.asarray(e.model.encode({"image": img}, normalize_embeddings=True), dtype=np.float32)
                if kind == "sound":
                    return np.asarray(e.model.encode({"audio": extract_audio(raw)}, normalize_embeddings=True), dtype=np.float32)
                return np.asarray(e.model.encode({"video": raw}, normalize_embeddings=True,
                                                 processing_kwargs={"video": {"fps": 2.0, "max_frames": 24}}), dtype=np.float32)

        vecs.append(await run_in_threadpool(run_file))
        item = {"kind": kind, "label": file.filename or kind, "url": f"/{raw}"}
        if kind == "video":
            jpg = raw.rsplit(".", 1)[0] + ".jpg"
            await run_in_threadpool(poster, raw, jpg, 1.0)
            item["poster"] = f"/{jpg}"
        inputs.append(item)
    if not vecs:
        raise HTTPException(400, "give it a photo, a sound, a sentence or a file")
    v = np.sum(vecs, axis=0)
    v = (v / np.linalg.norm(v)).astype(np.float32)

    def run_codec():
        with lock:
            return wc.encode(v, k=max(1, min(int(k), 16)), lang=lang if lang in ("en", "any") else "en")

    r = await run_in_threadpool(run_codec)
    wid = uuid.uuid4().hex[:8]
    state["words_vecs"][wid] = v
    return {"id": wid, "inputs": inputs, "words": r["words"], "steps": [{"word": s["word"], "cos": s["cos"]} for s in r["steps"]],
            "cos": r["cos"], "proof": {"original": _nearest(v), "words": _nearest(r["vec"].astype(np.float32))},
            "bits": {"vector": 768 * 16, "words": len(r["words"]) * 18}, "lang": lang, "seconds": round(time.time() - t0, 2)}


@app.post("/api/words/read")
async def words_read(text: str = Form(...), id: str = Form("")):
    wc = state.get("words")
    if wc is None:
        raise HTTPException(503, "codebook not built")
    t0 = time.time()

    def run():
        with lock:
            return wc.read(text)

    v = (await run_in_threadpool(run)).astype(np.float32)
    ref = state["words_vecs"].get(id)
    out = _nearest(v)
    out.update(text=text, cos=round(float(v @ ref), 3) if ref is not None else None, seconds=round(time.time() - t0, 2))
    return out


# ---------------- sentence arithmetic: fitted directions added to a sentence's embedding, proved by where it lands ----------------
class MoveReq(BaseModel):
    text: str
    ops: list[str] = []
    lang: str | None = None
    strength: float = 1.0
    k: int = 5


@app.get("/api/dir/ops")
def dir_ops():
    dt = state.get("dirs_text")
    if dt is None:
        raise HTTPException(503, "directions or variant bank not built")
    return dt.ops()


@app.post("/api/dir/move")
async def dir_move(req: MoveReq):
    dt = state.get("dirs_text")
    if dt is None:
        raise HTTPException(503, "directions or variant bank not built")
    text = req.text.strip()
    if not text:
        raise HTTPException(400, "type a sentence")

    def run():
        with lock:
            out = dt.move(text, req.ops, req.lang or None, max(0.0, min(req.strength, 3.0)), max(1, min(req.k, 10)))
            wc = state.get("words")
            if wc is not None:
                v, _ = dt.vector(dt.embed([text])[0], req.ops, req.lang or None, out["strength"])
                out["words"] = wc.encode(v, k=6, lang="any")["words"]
            return out

    return await run_in_threadpool(run)


@app.post("/api/dir/decode")
async def dir_decode(req: MoveReq):
    dt = state.get("dirs_text")
    if dt is None:
        raise HTTPException(503, "directions or variant bank not built")
    text = req.text.strip()

    def prep():
        with lock:
            v, _ = dt.vector(dt.embed([text])[0], req.ops, req.lang or None, max(0.0, min(req.strength, 3.0)))
            return v, dt.hints(v)

    v, hints = await run_in_threadpool(prep)
    t0 = time.time()
    try:
        async with httpx.AsyncClient(timeout=180) as client:
            r = await client.post(f"{STEER_URL}/decode", json={"target": [float(x) for x in v], "hint_texts": hints, "particles": 6, "steps": 24})
            r.raise_for_status()
            d = r.json()
    except Exception as e:
        raise HTTPException(503, f"decode service unavailable: {e}")
    return {"text": d.get("text"), "score": round(float(d.get("score", 0)), 3), "hints": hints, "seconds": round(time.time() - t0, 1)}


@app.post("/api/mux")
async def mux_endpoint(id: str = Form(...), clip: str = Form(...), mix: bool = Form(False)):
    e = state["engine"]
    src = f"{MEDIA}/{id}.mp4"
    sfx = e.clip_path(clip)
    if not os.path.exists(src) or sfx is None:
        raise HTTPException(404, "unknown clip or video id")
    out = f"{MEDIA}/{id}_{clip.rsplit('.', 1)[0]}{'_mix' if mix else ''}.mp4"
    await run_in_threadpool(mux, src, sfx, out, mix)
    return {"url": f"/{out}"}


app.mount("/sfx", StaticFiles(directory="index/wav"), name="sfx")
app.mount("/media", StaticFiles(directory=MEDIA), name="media")
app.mount("/clips", StaticFiles(directory="vindex/clips", check_dir=False), name="clips")
app.mount("/gallery", StaticFiles(directory="gallery", check_dir=False), name="gallery")
app.mount("/posters", StaticFiles(directory="vindex/posters", check_dir=False), name="posters")
app.mount("/", StaticFiles(directory="ui", html=True), name="ui")
