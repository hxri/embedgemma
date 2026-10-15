# Embed every vocabulary token as a 3-token sequence [BOS, tok, EOS] -> 262144 x 768 codebook.
import torch, numpy as np, time
from sentence_transformers import SentenceTransformer
m = SentenceTransformer("google/embeddinggemma-2", device="cuda", model_kwargs={"torch_dtype": torch.bfloat16}, config_kwargs={"vision_config": None, "audio_config": None})
am = m[0].auto_model.eval()
V = am.get_input_embeddings().weight.shape[0]
B = 4096
out = np.zeros((V, 768), dtype=np.float16)
t0 = time.time()
with torch.no_grad():
    for s in range(0, V, B):
        ids = torch.arange(s, min(s+B, V), device="cuda")
        x = torch.stack([torch.full_like(ids, 2), ids, torch.full_like(ids, 1)], dim=1)
        h = am(input_ids=x, attention_mask=torch.ones_like(x)).last_hidden_state
        e = torch.nn.functional.normalize(h.float().mean(1), dim=-1)
        out[s:s+len(ids)] = e.cpu().numpy().astype(np.float16)
        if (s // B) % 8 == 0: print(s, f"{time.time()-t0:.0f}s", flush=True)
np.save("mp/codebook.npy", out)
print("done", out.shape, f"{time.time()-t0:.0f}s")
