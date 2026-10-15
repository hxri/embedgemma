import torch, numpy as np, time, json
from sentence_transformers import SentenceTransformer
from words import WordsCodec
m = SentenceTransformer("google/embeddinggemma-2", device="cuda", model_kwargs={"torch_dtype": torch.bfloat16}, config_kwargs={"vision_config": None, "audio_config": None})
t = time.time(); wc = WordsCodec(m); print("codec ready", wc.counts, f"{time.time()-t:.0f}s")
def show(name, v):
    v = v / np.linalg.norm(v)
    out = []
    t0 = time.time(); r = wc.encode(v, k=8, lang="en"); out.append(f"en : {' '.join(r['words'])} ({r['cos']}, {[x['cos'] for x in r['steps']]}, {time.time()-t0:.2f}s)")
    r = wc.encode(v, k=8, lang="any"); out.append(f"any: {' '.join(r['words'])} ({r['cos']})")
    print(f"[{name}]\n   " + "\n   ".join(out))
for s in ["a man is playing piano", "a woman creating a fondant baby and flower", "a dog barking at the mailman", "rain falling on a tin roof at night", "children laughing in a playground", "a cat getting a bath in a little tub"]:
    show(s, m.encode(s, prompt_name="SearchQuery", normalize_embeddings=True))
g = json.load(open("gallery/gallery.json")); idx = np.load("index/index.npz"); meta = json.load(open("index/meta.json"))
cats = list(idx["cats"]); A = idx["audio"]; T = idx["text"]
def best_audio(cls):
    c = cats.index(cls); members = [i for i, mm in enumerate(meta) if mm["category"] == cls]
    return members[int(np.argmax(A[members] @ T[c]))]
def photo(cls): return next(x for x in g if x["class"] == cls)
for pc, sc in [("cow", "cow"), ("airplane", "chirping_birds"), ("cat", "rain"), ("dog", "dog"), ("sea_waves", "sea_waves"), ("keyboard_typing", "keyboard_typing"), ("train", "train"), ("rooster", "rooster")]:
    try:
        p = np.asarray(photo(pc)["emb"], dtype=np.float32); a = A[best_audio(sc)]
        show(f"photo {pc}", p); show(f"sound {sc}", a); show(f"photo {pc} + sound {sc}", p + a)
    except StopIteration:
        print("no photo for", pc)
