"""Decode service: DiffusionGemma writes a sentence for a point in EmbeddingGemma 2 space (guided.py).
Runs beside the main server; the main server proxies to it.  CUDA_VISIBLE_DEVICES=0 uvicorn steer_server:app --port 8788"""
import threading
import time
from contextlib import asynccontextmanager

import numpy as np
from fastapi import FastAPI
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

from guided import Steerer

state: dict = {}
lock = threading.Lock()


@asynccontextmanager
async def lifespan(app: FastAPI):
    state["s"] = await run_in_threadpool(Steerer)
    bank = np.load("vindex/bank_aug.npz", allow_pickle=True)
    state["caps"], state["E"] = [str(c) for c in bank["caps"]], bank["E"].astype(np.float32)
    yield


app = FastAPI(lifespan=lifespan)


class DecodeReq(BaseModel):
    target: list[float]
    hints: bool = True
    n_hints: int = 5
    particles: int = 6
    steps: int = 24
    lam_max: float = 6.0
    lam_min: float = 1.5
    hint_texts: list[str] | None = None   # caller-supplied hints override the bank lookup


@app.get("/health")
def health():
    s = state.get("s")
    return {"ok": s is not None, "load_s": round(s.load_s, 1) if s else None, "bank": len(state.get("caps", []))}


@app.post("/decode")
async def decode(req: DecodeReq):
    s = state["s"]
    t = np.asarray(req.target, dtype=np.float32)
    t = t / (np.linalg.norm(t) + 1e-8)
    if req.hint_texts:
        hints = req.hint_texts[: req.n_hints]
    else:
        hints = [state["caps"][i] for i in np.argsort(-(state["E"] @ t))[: req.n_hints]] if req.hints else None

    def run():
        with lock:
            return s.decode(t, hints=hints, particles=req.particles, steps=req.steps, lam_max=req.lam_max, lam_min=req.lam_min)

    t0 = time.time()
    r = await run_in_threadpool(run)
    r.update(hints=hints or [], seconds=round(time.time() - t0, 1))
    r["candidates"] = [{"text": a, "score": b} for a, b in r["candidates"]]
    return r
