"""Sentence arithmetic: add fitted directions to a sentence's embedding and prove where it lands."""
import os
import time

import numpy as np
import torch

from variants import DIRECTION_OF, LANGS, expected

SUGGESTIONS = ["a man is fixing the roof before the storm", "the chef is tasting the soup before service", "my sister is learning to drive a truck",
               "a boy is feeding the ducks at the pond", "the senate is debating the new tax bill", "a woman is painting the fence white",
               "two dogs are chasing a ball on the beach", "the pilot is explaining the delay"]


class Directions:
    def __init__(self, model, dirs: str = "mp/directions_text.npy", bank: str = "vindex/variant_bank.npz"):
        self.model = model
        d = np.load(dirs, allow_pickle=True).item()
        self.dirs = {k: (np.asarray(v["d"], dtype=np.float32), float(v["alpha"])) for k, v in d.items()}
        z = np.load(bank, allow_pickle=True)
        self.texts, self.kind, self.E = [str(t) for t in z["texts"]], [str(k) for k in z["kind"]], z["E"].astype(np.float32)
        self.nllb = None
        self.nllb_tried = False

    @staticmethod
    def available() -> bool:
        return os.path.exists("mp/directions_text.npy") and os.path.exists("vindex/variant_bank.npz")

    def ops(self) -> dict:
        rule_ops = [{"op": op, "alpha": self.dirs[DIRECTION_OF[op][0]][1]} for op in DIRECTION_OF if DIRECTION_OF[op][0] in self.dirs]
        langs = [{"code": c, "name": n, "alpha": self.dirs[f"language en>{c}"][1]} for c, (n, _) in LANGS.items() if f"language en>{c}" in self.dirs]
        return {"ops": rule_ops, "languages": langs, "bank": len(self.texts), "sentences": SUGGESTIONS, "translator": self._translator() is not None}

    def embed(self, texts: list[str]) -> np.ndarray:
        return np.asarray(self.model.encode(texts, prompt_name="SearchQuery", normalize_embeddings=True, batch_size=64), dtype=np.float32)

    # ---- translation of the expected form, so a typed sentence has its own foreign variant to land on ----
    def _translator(self):
        if self.nllb is None and not self.nllb_tried:
            self.nllb_tried = True
            try:
                from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
                name = "facebook/nllb-200-distilled-600M"
                tok = AutoTokenizer.from_pretrained(name, src_lang="eng_Latn", local_files_only=True)
                mdl = AutoModelForSeq2SeqLM.from_pretrained(name, torch_dtype=torch.float16, local_files_only=True).cuda().eval()
                self.nllb = (tok, mdl)
            except Exception as e:  # not downloaded yet: the language proof falls back to the bank
                print("translator unavailable:", str(e)[:120])
                self.nllb = None
        return self.nllb

    @torch.no_grad()
    def translate(self, text: str, code: str) -> str | None:
        t = self._translator()
        if t is None:
            return None
        tok, mdl = t
        inputs = tok([text], return_tensors="pt").to("cuda")
        out = mdl.generate(**inputs, forced_bos_token_id=tok.convert_tokens_to_ids(LANGS[code][1]), max_new_tokens=96, num_beams=3)
        return tok.batch_decode(out, skip_special_tokens=True)[0].strip()

    def vector(self, e: np.ndarray, ops: list[str], lang: str | None, strength: float) -> tuple[np.ndarray, list[dict]]:
        v, applied = e.copy(), []
        for op in ops:
            if op not in DIRECTION_OF or DIRECTION_OF[op][0] not in self.dirs:
                continue
            name, sign = DIRECTION_OF[op]
            d, a = self.dirs[name]
            v = v + sign * a * strength * d
            applied.append({"op": op, "alpha": round(sign * a * strength, 2)})
        if lang and f"language en>{lang}" in self.dirs:
            d, a = self.dirs[f"language en>{lang}"]
            v = v + a * strength * d
            applied.append({"op": f"to {LANGS[lang][0]}", "alpha": round(a * strength, 2)})
        return v / (np.linalg.norm(v) + 1e-8), applied

    def move(self, text: str, ops: list[str], lang: str | None = None, strength: float = 1.0, k: int = 5) -> dict:
        t0 = time.time()
        e = self.embed([text])[0]
        v, applied = self.vector(e, ops, lang, strength)
        exp, missing = expected(text, ops)
        notes = [f"no rule writes “{op}” for this sentence" for op in missing]
        if lang:
            tr = self.translate(exp, lang)
            if tr:
                exp = tr
            else:
                notes.append(f"{LANGS[lang][0]} form not written: translator not loaded, so only bank sentences can be hit")
                exp = None
        if exp == text:
            exp = None
        family = [text] + ([exp] if exp else [])
        F = self.embed(family)
        P = np.concatenate([self.E, F]); names = self.texts + family; kinds = self.kind + ["typed"] * len(family)
        s_after, s_before = P @ v, P @ e

        def top(s):
            order = np.argsort(-s)[:k]
            return [{"text": names[i], "cos": round(float(s[i]), 3), "typed": bool(i >= len(self.texts)),
                     "expected": bool(exp is not None and names[i] == exp), "kind": kinds[i]} for i in order.tolist()]

        out = {"text": text, "ops": applied, "strength": strength, "expected": exp, "notes": notes, "after": top(s_after), "before": top(s_before),
               "bank": len(self.texts), "seconds": round(time.time() - t0, 2)}
        if exp is not None:
            j = names.index(exp)
            out["rank_after"] = int((s_after > s_after[j]).sum()) + 1
            out["rank_before"] = int((s_before > s_before[j]).sum()) + 1
            out["cos_after"] = round(float(s_after[j]), 3)
            out["cos_before"] = round(float(s_before[j]), 3)
            out["cos_text_expected"] = round(float(e @ F[-1]), 3)
        return out

    def hints(self, v: np.ndarray, n: int = 5) -> list[str]:
        return [self.texts[i] for i in np.argsort(-(self.E @ v))[:n]]
