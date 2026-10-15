"""Guided decoding: DiffusionGemma writes a sentence whose EmbeddingGemma 2 embedding lands on a target vector.

Classifier guidance, no training. Both models share one 262k-token vocabulary, and EmbeddingGemma accepts soft
token distributions through its input embeddings (verified: one-hot soft input reproduces encode() at cosine 0.999).
So at every denoising step the denoiser's logits are softmaxed, pushed through EmbeddingGemma as soft tokens, scored
against the target, and nudged along the gradient of that score before sampling. Particles add cheap diversity."""
import time

import numpy as np
import torch
from sentence_transformers import SentenceTransformer
from transformers import AutoProcessor, DiffusionGemmaForBlockDiffusion

DG_ID = "google/diffusiongemma-26B-A4B-it"
EG_ID = "google/embeddinggemma-2"


class GuidedDiffusionGemma(DiffusionGemmaForBlockDiffusion):
    guide = None

    # ---- differentiable score of the soft canvas under EmbeddingGemma ----
    def _soft_score_grad(self, logits: torch.Tensor, eos_pos: torch.Tensor) -> torch.Tensor:
        g = self.guide
        B, L, V = logits.shape
        with torch.enable_grad():
            lg = logits.detach().float().requires_grad_(True)
            p = torch.softmax(lg, dim=-1)
            soft = (p.to(g["W"].dtype) @ g["W"]) * g["scale"]                         # (B, L, 512) soft token embeddings
            pos = torch.arange(L, device=logits.device)[None, :]
            valid = (pos < eos_pos[:, None]).to(soft.dtype)                               # tokens after the sentence's end are ignored
            prefix = g["prefix"].expand(B, -1, -1)
            eos = g["eos_emb"].expand(B, 1, -1)
            x = torch.cat([prefix, soft * valid[..., None], eos], dim=1)
            att = torch.cat([torch.ones(B, prefix.shape[1], device=logits.device), valid, torch.ones(B, 1, device=logits.device)], dim=1).long()
            hid = g["eg"](inputs_embeds=x, attention_mask=att).last_hidden_state
            pooled = (hid.float() * att[..., None]).sum(1) / att.sum(1, keepdim=True)
            pooled = torch.nn.functional.normalize(pooled, dim=-1)
            score = pooled @ g["target_t"]                                                 # (B,)
            score.sum().backward()
            g["last_scores"] = score.detach().cpu().numpy()
            return lg.grad

    def _denoising_step(self, decoder_forward, current_canvas, argmax_canvas, input_ids, decoder_position_ids,
                        self_conditioning_logits, mask_mapping, past_key_values, finished_denoising, cur_step, sampler,
                        logits_processor, diffusion_stopping_criteria, **model_kwargs):
        # (the stock step, with guidance inserted after the logits processor)
        cur_step_t = torch.tensor(cur_step, device=current_canvas.device, dtype=torch.int32)
        torch.compiler.cudagraph_mark_step_begin()
        decoder_outputs = decoder_forward(decoder_input_ids=current_canvas, self_conditioning_logits=self_conditioning_logits,
                                          decoder_attention_mask=mask_mapping, past_key_values=past_key_values,
                                          decoder_position_ids=decoder_position_ids, **model_kwargs)
        processed_logits = logits_processor(input_ids, decoder_outputs.logits, cur_step=cur_step_t)
        g = self.guide
        if g is not None:
            Lg = g["Lg"]
            am = torch.argmax(processed_logits[:, :Lg], dim=-1)
            is_end = torch.isin(am, g["eos_ids"])
            eos_pos = torch.where(is_end.any(1), is_end.float().argmax(1), torch.full((am.shape[0],), Lg, device=am.device)).clamp(min=3)
            grad = self._soft_score_grad(processed_logits[:, :Lg], eos_pos)
            frac = (int(cur_step) - 1) / max(1, g["steps"] - 1)                           # 1 at the first (noisiest) step, 0 at the last
            lam = g["lam_min"] + (g["lam_max"] - g["lam_min"]) * frac
            step = lam * grad / (grad.abs().amax(-1, keepdim=True) + 1e-12)                # at most lam logits per position
            base = processed_logits[:, :Lg]
            topk = base.topk(g["topk"], dim=-1).indices                                      # only among tokens the model finds plausible
            allowed = torch.zeros_like(base, dtype=torch.bool).scatter_(-1, topk, True)
            allowed[..., g["protect"]] = False                                               # never push the sentence end around
            processed_logits = processed_logits.clone()
            processed_logits[:, :Lg] = base + torch.where(allowed, step.to(base.dtype), torch.zeros_like(base))
            g["trajectory"].append({"step": int(cur_step), "score": float(g["last_scores"].max()), "mean": float(g["last_scores"].mean()),
                                    "best": g["clean"](am[int(np.argmax(g["last_scores"]))])})
        probs = torch.softmax(processed_logits, dim=-1, dtype=torch.float32)
        vocab_size = self.config.text_config.vocab_size
        batch_size, canvas_length = current_canvas.shape
        denoiser_canvas = torch.multinomial(probs.view(-1, vocab_size), num_samples=1).squeeze(-1).view(batch_size, canvas_length)
        new_argmax_canvas = torch.argmax(processed_logits, dim=-1)
        accepted_canvas = sampler.accept_canvas(current_canvas, denoiser_canvas, processed_logits, cur_step_t).clone()
        new_current_canvas = sampler.renoise_canvas(accepted_canvas, cur_step_t).clone()
        if diffusion_stopping_criteria is not None:
            if finished_denoising.any():
                new_argmax_canvas = torch.where(finished_denoising[:, None], argmax_canvas, new_argmax_canvas)
                new_current_canvas = torch.where(finished_denoising[:, None], current_canvas, new_current_canvas)
                processed_logits = torch.where(finished_denoising[:, None, None], self_conditioning_logits, processed_logits)
            finished_denoising |= diffusion_stopping_criteria(new_argmax_canvas, processed_logits)
        self_conditioning_logits = processed_logits.to(self.model.decoder.embed_tokens.weight.dtype)
        return new_current_canvas, new_argmax_canvas, self_conditioning_logits, finished_denoising


class Steerer:
    def __init__(self, device="cuda"):
        t = time.time()
        self.model = GuidedDiffusionGemma.from_pretrained(DG_ID, dtype=torch.bfloat16, device_map=device)
        self.proc = AutoProcessor.from_pretrained(DG_ID)
        self.tok = self.proc.tokenizer
        self.st = SentenceTransformer(EG_ID, device=device, model_kwargs={"torch_dtype": torch.bfloat16},
                                      config_kwargs={"vision_config": None, "audio_config": None})
        self.eg = self.st[0].auto_model.eval()
        for p in self.eg.parameters():
            p.requires_grad_(False)
        emb = self.eg.get_input_embeddings()
        self.W, self.scale = emb.weight, emb.embed_scale.to(emb.weight.dtype)
        feat = self.st.tokenize([self.st.prompts["SearchQuery"]])
        pid = feat["input_ids"][0].tolist()
        if pid and pid[-1] == 1:
            pid = pid[:-1]                                                                 # drop the EOS the tokenizer appends
        self.prefix = (self.W[torch.tensor(pid, device=device)] * self.scale)[None]
        self.eos_emb = (self.W[torch.tensor([1], device=device)] * self.scale)[None]
        self.load_s = time.time() - t
        self.eos_ids = torch.tensor(self.model.generation_config.eos_token_id or [1, 106], device=device)
        self.eos = set(self.eos_ids.tolist())

    def clean(self, row) -> str:
        ids = row.tolist()
        cut = next((i for i, t in enumerate(ids) if t in self.eos or t == 0), len(ids))
        text = self.tok.decode(ids[:cut], skip_special_tokens=True).strip()
        if text.startswith("thought"):
            text = text[len("thought"):].strip()
        return text

    def decode(self, target, hints=None, particles=8, steps=32, max_new_tokens=40, guided=True, lam_max=6.0, lam_min=1.5,
               topk=100, t_min=0.7, t_max=1.1) -> dict:
        target = np.asarray(target, dtype=np.float32); target = target / (np.linalg.norm(target) + 1e-8)
        prompt = "Describe a short video clip in one plain sentence. Only the sentence."
        if hints:
            prompt = ("Here are captions of clips that are similar to the one you must describe:\n" + "\n".join(f"- {h}" for h in hints) +
                      "\nWrite one new plain sentence describing a clip like these. Only the sentence.")
        msg = [{"role": "user", "content": [{"type": "text", "text": prompt}]}]
        ids = self.proc.apply_chat_template(msg, tokenize=True, add_generation_prompt=True, return_dict=True,
                                            return_tensors="pt", enable_thinking=False).to(self.model.device)
        ids = {k: v.repeat(particles, *([1] * (v.dim() - 1))) for k, v in ids.items()}
        traj = []
        self.model.guide = {"W": self.W, "scale": self.scale, "prefix": self.prefix, "eos_emb": self.eos_emb, "eg": self.eg,
                            "target_t": torch.tensor(target, device=self.model.device), "Lg": max_new_tokens,
                            "lam_max": lam_max, "lam_min": lam_min, "steps": steps, "topk": topk,
                            "protect": torch.tensor(sorted(self.eos | {0}), device=self.model.device),
                            "eos_ids": self.eos_ids, "clean": self.clean, "trajectory": traj} if guided else None
        t = time.time()
        with torch.no_grad():
            out = self.model.generate(**ids, max_new_tokens=max_new_tokens, max_denoising_steps=steps, t_min=t_min, t_max=t_max,
                                      stability_threshold=10_000, confidence_threshold=1e-9)
        self.model.guide = None
        seq = out.sequences if hasattr(out, "sequences") else out
        n = ids["input_ids"].shape[1]
        texts = [self.clean(seq[i][n:]) for i in range(particles)]
        raw = self.tok.decode(seq[0][n:n + 12].tolist(), skip_special_tokens=False)
        E = self.st.encode(texts, prompt_name="SearchQuery", normalize_embeddings=True)
        scores = np.asarray(E, dtype=np.float32) @ target
        best = int(np.argmax(scores))
        cands = sorted(set(zip(texts, scores.tolist())), key=lambda x: -x[1])
        return {"text": texts[best], "score": float(scores[best]), "candidates": cands, "trajectory": traj,
                "seconds": round(time.time() - t, 1), "raw_head": raw}


if __name__ == "__main__":
    import json
    s = Steerer()
    print(f"loaded in {s.load_s:.0f}s", flush=True)
    full = SentenceTransformer(EG_ID, device="cuda", model_kwargs={"torch_dtype": torch.bfloat16})
    meta = json.load(open("vindex/meta.json")); V = np.load("vindex/vindex.npz")["video"]
    j = next((i for i, m in enumerate(meta) if "beach" in m["caption"] and "dog" in m["caption"]), 0)
    def txt(t): return np.asarray(full.encode(t, prompt_name="Document", normalize_embeddings=True), dtype=np.float32)
    # contextual directions: full sentences that differ in one attribute, averaged over a few carrier scenes
    carriers = ["a man and a woman are walking a dog on a beach", "two people walk down a city street", "a child plays in a park", "a car drives along a road"]
    attrs = {"night": "{} at night, in the dark", "snow": "{} in heavy snow", "crowd": "{} surrounded by a huge crowd of people", "underwater": "{} underwater, in the sea", "rain": "{} in pouring rain"}
    dirs = {k: np.mean([txt(tpl.format(c)) - txt(c) for c in carriers], axis=0) for k, tpl in attrs.items()}
    print("direction norms:", {k: round(float(np.linalg.norm(v)), 3) for k, v in dirs.items()}, flush=True)
    for name, base in (("TEXT 'a man and a woman are walking a dog on a beach'", txt(carriers[0])), (f"VIDEO {meta[j]['video_id']}", V[j])):
        print(f"\n##### {name}", flush=True)
        for d, vec in dirs.items():
            for w in (1.0, 2.0):
                r = s.decode(base + w * vec, guided=True)
                print(f"  +{w:.0f} x {d:<10}: {r['score']:.3f} -> {r['text']!r}", flush=True)
    print("GUIDED_DONE", flush=True)
