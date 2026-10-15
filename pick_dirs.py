"""Pick the five steering directions the decoder responds to, and build an attribute-augmented caption bank.

A direction is the mean difference between sentence pairs that differ in one attribute, over carrier scenes.
For each candidate we decode base +2 d and base -2 d (guided, with hints) and measure how far apart the two
decoded sentences are along d. The five with the largest, most consistent effect win."""
import json
import numpy as np
import torch
from sentence_transformers import SentenceTransformer
from guided import Steerer, EG_ID

CANDIDATES = {  # name: (positive template, negative template, positive pole label, negative pole label)
    "night": ("{} at night, in the dark", "{} in bright daylight", "night", "day"),
    "snow": ("{} in heavy snow", "{} in warm summer sun", "snow", "summer"),
    "water": ("{} in the water with waves splashing", "{} on dry land", "water", "land"),
    "city": ("{} on a busy city street with traffic", "{} in the quiet countryside", "city", "countryside"),
    "crowd": ("{} surrounded by a cheering crowd", "{} alone with nobody around", "crowd", "alone"),
    "music": ("{} while a band plays loud music and people dance", "{} in complete silence", "music", "silence"),
    "cartoon": ("a cartoon animation of {}", "a realistic live video of {}", "cartoon", "real"),
    "children": ("{} with small children playing", "{} with only adults", "children", "adults"),
    "fast": ("{} moving very fast and frantic", "{} moving very slowly and calmly", "frantic", "calm"),
    "indoor": ("{} indoors in a living room", "{} outdoors under the open sky", "indoors", "outdoors"),
    "vintage": ("an old black-and-white film of {}", "a modern high-definition video of {}", "old film", "modern"),
    "animals": ("{} with dogs and cats running around", "{} with no animals anywhere", "animals", "no animals"),
    "food": ("{} while cooking and eating a big meal", "{} with no food in sight", "food", "no food"),
}
CARRIERS = ["a man and a woman are walking a dog on a beach", "two people walk down a street", "a child plays in a park",
            "a car drives along a road", "a woman is talking to the camera", "a group of friends sit at a table"]

full = SentenceTransformer(EG_ID, device="cuda", model_kwargs={"torch_dtype": torch.bfloat16})
txt = lambda t: np.asarray(full.encode(t, prompt_name="Document", normalize_embeddings=True, batch_size=64), dtype=np.float32)
dirs = {}
for k, (pos, neg, _, _) in CANDIDATES.items():
    P, N = txt([pos.format(c) for c in CARRIERS]), txt([neg.format(c) for c in CARRIERS])
    dirs[k] = (P - N).mean(0)
print("direction norms:", {k: round(float(np.linalg.norm(v)), 2) for k, v in dirs.items()}, flush=True)

# augmented bank: the 1000 test captions, each rewritten with every pole of every candidate attribute
meta = json.load(open("vindex/meta.json"))
base_caps = [m["caption"] for m in meta]
texts, tags = list(base_caps), [("", "")] * len(base_caps)
for k, (pos, neg, _, _) in CANDIDATES.items():
    for c in base_caps:
        texts.append(pos.format(c)); tags.append((k, "+"))
        texts.append(neg.format(c)); tags.append((k, "-"))
E = txt(texts)
np.savez("vindex/bank_aug.npz", caps=np.array(texts), tags=np.array(tags), E=E)
print(f"augmented bank: {len(texts)} captions", flush=True)

def hints_for(t, n=5):
    t = t / (np.linalg.norm(t) + 1e-8)
    return [texts[i] for i in np.argsort(-(E @ t))[:n]]

s = Steerer()
V = np.load("vindex/vindex.npz")["video"]
j = next((i for i, m in enumerate(meta) if "beach" in m["caption"] and "dog" in m["caption"]), 0)
k2 = next((i for i, m in enumerate(meta) if "cook" in m["caption"]), 1)
bases = [("text: a man and a woman are walking a dog on a beach", txt(CARRIERS[0])), (f"video {meta[j]['video_id']}", V[j]), (f"video {meta[k2]['video_id']} ({meta[k2]['caption']})", V[k2])]
results = {}
for k, d in dirs.items():
    dn = d / np.linalg.norm(d)
    effects = []
    for bname, b in bases:
        out = {}
        for w in (2.0, -2.0):
            t = b + w * d
            r = s.decode(t, hints=hints_for(t), guided=True, particles=6, steps=24)
            out[w] = r["text"]
        ep, en = txt([out[2.0], out[-2.0]])
        eff = float((ep - en) @ dn)
        effects.append(eff)
        print(f"  [{k:<9}] {bname[:38]:<38} eff {eff:+.3f} | + {out[2.0][:70]!r} | - {out[-2.0][:70]!r}", flush=True)
    results[k] = {"effect_mean": float(np.mean(effects)), "effect_min": float(np.min(effects))}
    print(f"{k:<9} mean effect {results[k]['effect_mean']:+.3f}  min {results[k]['effect_min']:+.3f}", flush=True)
ranked = sorted(results, key=lambda k: -(results[k]["effect_mean"] + results[k]["effect_min"]))
chosen = ranked[:5]
print("RANKED:", [(k, round(results[k]["effect_mean"], 3)) for k in ranked], flush=True)
json.dump({"chosen": chosen, "directions": {k: {"vec": dirs[k].tolist(), "pos": CANDIDATES[k][2], "neg": CANDIDATES[k][3],
           "effect": results[k]} for k in dirs}}, open("vindex/directions.json", "w"))
print("PICK_DONE", flush=True)
