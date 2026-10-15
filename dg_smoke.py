import time, torch
from transformers import DiffusionGemmaForBlockDiffusion, AutoProcessor
t = time.time()
MODEL_ID = "google/diffusiongemma-26B-A4B-it"
model = DiffusionGemmaForBlockDiffusion.from_pretrained(MODEL_ID, dtype=torch.bfloat16, device_map="cuda")
proc = AutoProcessor.from_pretrained(MODEL_ID)
print(f"loaded in {time.time()-t:.0f}s; mem {torch.cuda.max_memory_allocated()/1e9:.1f} GB", flush=True)
msg = [{"role": "user", "content": [{"type": "text", "text": "Write one sentence describing a short video of a dog running on a beach at night. Only the sentence."}]}]
ids = proc.apply_chat_template(msg, tokenize=True, add_generation_prompt=True, return_dict=True, return_tensors="pt").to(model.device)
for n in (32, 64):
    t = time.time()
    out = model.generate(**ids, max_new_tokens=n)
    dt = time.time() - t
    print(f"max_new_tokens={n}: {dt:.1f}s ->", repr(proc.decode(out[0][ids['input_ids'].shape[1]:], skip_special_tokens=True)), flush=True)
print("gen config:", {k: v for k, v in model.generation_config.to_dict().items() if v is not None and k not in ('_from_model_config',)}, flush=True)
print("DG_SMOKE_DONE", flush=True)
