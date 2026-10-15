"""Curate demo images for the SFX finder: a few Wikimedia Commons photos per ESC-50 class, kept only if
EmbeddingGemma recognises them as that class (image vs class caption), so the demo has no out-of-distribution drops.
Then measure image->sound retrieval on the curated set: direct (image vs clip audio), bridged (image vs class
caption), and a z-blend."""
import io
import json
import os
import time
import urllib.parse
import urllib.request

import numpy as np
import torch
from PIL import Image
from sentence_transformers import SentenceTransformer

from captions import CAPTIONS

KEYWORDS = {
    "dog": "dog barking photo", "rooster": "rooster crowing", "pig": "pig farm", "cow": "cow pasture", "frog": "frog pond",
    "cat": "cat meowing", "hen": "hen chicken", "insects": "insects flying swarm", "sheep": "sheep flock", "crow": "crow bird",
    "rain": "rain falling street", "sea_waves": "ocean waves beach", "crackling_fire": "campfire flames", "crickets": "cricket insect grass",
    "chirping_birds": "songbird singing branch", "water_drops": "water drop splash", "wind": "wind blowing trees storm",
    "pouring_water": "pouring water glass", "toilet_flush": "toilet bathroom", "thunderstorm": "lightning thunderstorm",
    "crying_baby": "crying baby", "sneezing": "person sneezing", "clapping": "audience applause clapping", "breathing": "person breathing deeply",
    "coughing": "person coughing", "footsteps": "footsteps walking shoes pavement", "laughing": "people laughing", "brushing_teeth": "brushing teeth toothbrush",
    "snoring": "man snoring asleep bed", "drinking_sipping": "person drinking glass water", "door_wood_knock": "knocking wooden door hand",
    "mouse_click": "computer mouse hand click", "keyboard_typing": "typing keyboard hands", "door_wood_creaks": "old wooden door creaking",
    "can_opening": "opening soda can", "washing_machine": "washing machine laundry", "vacuum_cleaner": "vacuum cleaner carpet",
    "clock_alarm": "alarm clock ringing", "clock_tick": "wall clock pendulum", "glass_breaking": "broken shattered glass",
    "helicopter": "helicopter flying", "chainsaw": "chainsaw cutting wood", "siren": "ambulance siren lights", "car_horn": "car horn traffic jam",
    "engine": "car engine running", "train": "train railway", "church_bells": "church bell tower", "airplane": "airplane flying sky",
    "fireworks": "fireworks night sky", "hand_saw": "hand saw sawing wood",
}
OUT = "gallery"
os.makedirs(OUT, exist_ok=True)
UA = {"User-Agent": "embedgemma-sfx-demo/0.1 (research demo; contact: local)"}


def commons_search(q: str, n: int = 10):
    params = {"action": "query", "format": "json", "generator": "search", "gsrsearch": f"{q} filetype:bitmap", "gsrnamespace": "6",
              "gsrlimit": str(n), "prop": "imageinfo", "iiprop": "url|size|mime|extmetadata", "iiurlwidth": "720"}
    url = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
        d = json.load(r)
    out = []
    for p in (d.get("query", {}).get("pages", {}) or {}).values():
        ii = (p.get("imageinfo") or [{}])[0]
        if ii.get("mime") not in ("image/jpeg", "image/png") or (ii.get("width") or 0) < 500:
            continue
        em = ii.get("extmetadata", {}) or {}
        out.append({"title": p.get("title"), "thumb": ii.get("thumburl"), "page": ii.get("descriptionurl"),
                    "license": (em.get("LicenseShortName") or {}).get("value", ""), "artist": (em.get("Artist") or {}).get("value", "")})
    return out


def fetch(url: str):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
        return Image.open(io.BytesIO(r.read())).convert("RGB")


model = SentenceTransformer("google/embeddinggemma-2", device="cuda", model_kwargs={"torch_dtype": torch.bfloat16})
idx = np.load("index/index.npz", allow_pickle=True)
AUD, TXT, cats = idx["audio"].astype(np.float32), idx["text"].astype(np.float32), [str(c) for c in idx["cats"]]
meta = json.load(open("index/meta.json"))
clip_cat = np.array([cats.index(m["category"]) for m in meta])
photo_txt = np.asarray(model.encode([f"a photo of {CAPTIONS[c]}" for c in cats], prompt_name="Document", normalize_embeddings=True), dtype=np.float32)

gallery = []
for c in cats:
    try:
        cands = commons_search(KEYWORDS[c], 12)
    except Exception as e:
        print(f"{c}: search failed {e}", flush=True); cands = []
    imgs, keep = [], []
    for cand in cands[:12]:
        try:
            im = fetch(cand["thumb"]); im.thumbnail((720, 720)); imgs.append((cand, im))
        except Exception:
            continue
    if not imgs:
        print(f"{c}: no images", flush=True); continue
    E = np.asarray(model.encode([{"image": im} for _, im in imgs], batch_size=8, normalize_embeddings=True), dtype=np.float32)
    s_cls = E @ photo_txt.T                       # image vs every class's photo caption
    for k, (cand, im) in enumerate(imgs):
        rank = int((s_cls[k] > s_cls[k, cats.index(c)]).sum())   # 0 = this class is the image's best class
        keep.append((rank, -float(s_cls[k, cats.index(c)]), k))
    keep.sort()
    chosen = [k for r, _, k in keep if r == 0][:3] or [keep[0][2]]
    for j, k in enumerate(chosen):
        cand, im = imgs[k]
        fn = f"{OUT}/{c}_{j}.jpg"; im.save(fn, quality=88)
        gallery.append({"file": fn, "class": c, "caption": CAPTIONS[c], "title": cand["title"], "page": cand["page"], "license": cand["license"],
                        "class_rank": int([r for r, _, kk in keep if kk == k][0]), "emb": E[k].tolist()})
    print(f"{c:<18} candidates {len(imgs):>2}  kept {len(chosen)} (class ranks {[r for r,_,kk in keep if kk in chosen]})", flush=True)
    time.sleep(0.3)
json.dump(gallery, open(f"{OUT}/gallery.json", "w"))
print(f"gallery: {len(gallery)} images", flush=True)

# ---- evaluate image -> sound on the curated set ----
G = np.array([g["emb"] for g in gallery], dtype=np.float32); gt = np.array([cats.index(g["class"]) for g in gallery])
z = lambda x: (x - x.mean(1, keepdims=True)) / (x.std(1, keepdims=True) + 1e-8)
s_direct = G @ AUD.T                               # (n, 2000)
s_bridge_cls = G @ TXT.T                           # (n, 50) image vs class caption text (index captions)
s_photo_cls = G @ photo_txt.T                      # (n, 50) image vs "a photo of ..." captions
def class_scores_from_clips(S):                    # best clip per class
    out = np.full((S.shape[0], len(cats)), -9.0, dtype=np.float32)
    for c in range(len(cats)):
        out[:, c] = S[:, clip_cat == c].max(1)
    return out
methods = {"direct (image vs clip audio)": class_scores_from_clips(s_direct),
           "bridged (image vs caption)": s_bridge_cls,
           "bridged (image vs 'a photo of')": s_photo_cls,
           "blend z(direct)+z(photo caption)": z(class_scores_from_clips(s_direct)) + z(s_photo_cls)}
for name, S in methods.items():
    order = np.argsort(-S, axis=1)
    top1 = (order[:, 0] == gt).mean(); top3 = np.array([gt[i] in order[i, :3] for i in range(len(gt))]).mean()
    print(f"{name:<36} top-1 {100*top1:5.1f}%  top-3 {100*top3:5.1f}%", flush=True)
print("GALLERY_DONE", flush=True)
