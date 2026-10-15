import time, torch
from sentence_transformers import SentenceTransformer
t=time.time()
m = SentenceTransformer("google/embeddinggemma-2", device="cuda", model_kwargs={"torch_dtype": torch.bfloat16})
print(f"loaded in {time.time()-t:.1f}s device={m.device} dtype={m.dtype}")
print(m)
t=time.time(); e = m.encode(["the sound of clapping"], prompt_name="Document", normalize_embeddings=True); print("text", e.shape, f"{time.time()-t:.2f}s")
t=time.time(); v = m.encode({"video": "in/camtest.mp4"}, normalize_embeddings=True); print("video", v.shape, f"{time.time()-t:.2f}s")
cands = ["a person sitting at a desk looking at a laptop", "a dog running in a park", "a car driving on a highway", "the sound of keyboard typing", "the sound of a rooster"]
print(m.similarity(v, m.encode(cands, prompt_name="Document", normalize_embeddings=True)))
print("mem GB", torch.cuda.max_memory_allocated()/1e9)
