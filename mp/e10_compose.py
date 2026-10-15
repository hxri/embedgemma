# Do directions compose, transfer to other kinds of sentences, and how many pairs do they need?
import torch, sys, json, re, random, numpy as np; sys.path.insert(0, "mp")
from common import *
random.seed(1); torch.manual_seed(1)
eg = EG()
save = np.load("mp/directions_text.npy", allow_pickle=True).item()
D = {k: torch.tensor(v["d"]).cuda() for k, v in save.items()}
A = {k: v["alpha"] for k, v in save.items()}
def enc(texts): return torch.tensor(eg.st.encode(texts, prompt_name="SearchQuery", normalize_embeddings=True, batch_size=128)).cuda()
def nrm(x): return torch.nn.functional.normalize(x, dim=-1)
from variants import RULES
neg, past, ques, fem = RULES["negation"], RULES["past tense"], RULES["question"], RULES["gender man>woman"]

def exact(Q, variants, pool):
    """Q perturbed queries; variants: the true targets; pool: all candidates. fraction whose nearest in pool is its own target"""
    tgt = torch.tensor([pool_index[v] for v in variants], device="cuda")
    return (Q @ P.T).argmax(1).eq(tgt).float().mean().item() * 100

# 1. composition on 300 caption sentences with is/are X-ing and a man/boy
caps = [str(c) for c in np.load("vindex/captions.npz")["caps"]]
base = [c for c in caps if re.search(r"\b(is|are) \w+ing\b", c) and re.search(r"\b(man|boy|guy)\b", c) and not re.search(r"\b(woman|girl)\b", c)]
random.shuffle(base); base = base[-300:]   # tail: least likely to overlap the training pairs
combos = {"negation+past": (lambda c: past(neg(c)), ["negation", "past tense"]),
          "gender+negation": (lambda c: neg(fem(c)), ["gender man>woman", "negation"]),
          "gender+at night": (lambda c: fem(c) + " at night", ["gender man>woman", "at night"]),
          "negation+question": (lambda c: ques(neg(c)), ["negation", "question"]),
          "gender+past+night": (lambda c: past(fem(c)) + " at night", ["gender man>woman", "past tense", "at night"])}
singles = {"negation": neg, "past tense": past, "question": ques, "gender man>woman": fem, "at night": lambda c: c + " at night"}
texts = list(base)
for f in singles.values(): texts += [f(c) for c in base]
for f, _ in combos.values(): texts += [f(c) for c in base]
texts = list(dict.fromkeys(texts)); pool_index = {t: i for i, t in enumerate(texts)}; P = enc(texts); E = P[:len(base)]
print(f"pool of {len(texts)} sentences (300 bases x 1 + 5 singles + 5 combos)")
for name, (f, dirs) in combos.items():
    q = E.clone()
    for k in dirs: q = q + A[k] * D[k]
    acc = exact(nrm(q), [f(c) for c in base], P)
    q2 = E.clone()
    for k in dirs: q2 = q2 + 1.0 * D[k]
    print(f"compose {name:20s}: lands on the doubly-changed sentence {acc:5.1f}%  (with α=1 each {exact(nrm(q2), [f(c) for c in base], P):5.1f}%)", flush=True)
for name, f in singles.items():
    print(f"single  {name:20s}: {exact(nrm(E + A[name] * D[name]), [f(c) for c in base], P):5.1f}%  (α=1 {exact(nrm(E + D[name]), [f(c) for c in base], P):5.1f}%)", flush=True)

# 2. transfer to sentences that are nothing like video captions
other = ["the senate is debating the new tax bill", "my sister is learning to drive a truck", "the committee is reviewing the budget for next year",
         "a nurse is checking the patient's blood pressure", "the printer is jamming again", "our neighbors are building a fence",
         "the chef is tasting the soup before service", "the students are protesting outside the library", "the river is flooding the lower fields",
         "a lawyer is reading the contract aloud", "the band is tuning their instruments backstage", "the mayor is announcing the new bus routes",
         "my phone is charging on the kitchen counter", "the tomatoes are ripening early this summer", "the engineers are testing the bridge for cracks",
         "a monk is sweeping the temple steps", "the pilot is explaining the delay", "the kids are hiding under the table", "the bank is raising its fees",
         "the old dog is sleeping by the fire", "a man is fixing the roof before the storm", "the boy is counting coins on the floor",
         "the guy is arguing with the referee", "a man is proposing to his partner on the pier", "the boy is practising the violin"]
tex = list(other)
for f in singles.values(): tex += [f(c) for c in other]
tex = list(dict.fromkeys(tex)); pool_index = {t: i for i, t in enumerate(tex)}; P = enc(tex); E = P[:len(other)]
print(f"\ntransfer to {len(other)} unrelated sentences (pool {len(tex)}):")
for name, f in singles.items():
    idx = [i for i, c in enumerate(other) if f(c) != c]
    q = nrm(E[idx] + A[name] * D[name])
    tgt = torch.tensor([pool_index[f(other[i])] for i in idx], device="cuda")
    acc = (q @ P.T).argmax(1).eq(tgt).float().mean().item() * 100
    print(f"  {name:18s} on {len(idx):2d} sentences: lands on own variant {acc:5.1f}%", flush=True)

# 3. how many pairs are needed
print("\npairs needed (negation, exact % on 400 test sentences, α=3):")
prs = [(c, neg(c)) for c in random.sample([c for c in caps if re.search(r"\b(is|are) \w+ing\b", c)], 800)]
At = enc([p[0] for p in prs[400:]]); Bt = enc([p[1] for p in prs[400:]]); pool = torch.cat([At, Bt]); N = 400
for n in (1, 3, 10, 30, 100, 400):
    Atr = enc([p[0] for p in prs[:n]]); Btr = enc([p[1] for p in prs[:n]]); d = (Btr - Atr).mean(0)
    s = nrm(At + 3.0 * d) @ pool.T
    print(f"  {n:3d} pairs: {(s.argmax(1) == torch.arange(N, device='cuda') + N).float().mean().item()*100:5.1f}%", flush=True)
