import torch, sys; sys.path.insert(0, "mp")
from common import *
eg = EG(); V, T, meta, caps, C = load_vindex()
print("baseline cap->vid", recall(T, V), "vid->cap", recall(V, T), "spread V", spread(V), "T", spread(T))
for d in (256, 128):
    f = lambda X: torch.nn.functional.normalize(X[:, :d], dim=-1)
    print(f"MRL {d} cap->vid", recall(f(T), f(V)))
for wrap in (True, False):
    for alpha in (10.0, 22.625, 50.0, 100.0):
        V2, T2 = eg.selfpass(V, alpha, wrap), eg.selfpass(T, alpha, wrap)
        print(f"selfpass wrap={wrap} alpha={alpha}: both-sides cap->vid", recall(T2, V2), "| query-only", recall(T2, V),
              "| cos(e,f(e)) V", round((V*V2).sum(-1).mean().item(),3), "T", round((T*T2).sum(-1).mean().item(),3), "| spread V2", spread(V2), "T2", spread(T2))
# two passes
V3, T3 = eg.selfpass(eg.selfpass(V), ), eg.selfpass(eg.selfpass(T))
print("double pass both-sides", recall(T3, V3), "spread", spread(V3))
