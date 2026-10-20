# timeout: 600
# Ten thousand simulated lives of the pool with correlated defaults:
# the pool's loss distribution and each class's share of it.
import json

import numpy as np

import fernhill
from ballast import securitisation as sec
from ballast.config import ROOT, SEED

RHO, SIMS = 0.10, 10_000
con = fernhill.connect()
deal = sec.inputs(con)
total = float(deal.loans["balance_cents"].sum())
cf = sec.simulate(deal, SIMS, RHO, SEED)
loss = sec.pool_loss(cf, total)
w = sec.waterfall(cf, sec.notes(deal))
det = sec.project(deal, "long_run")
expect = (det.defaulted - det.recovered).sum() / total

print(f"{SIMS:,} lives of the pool, asset correlation {RHO:.2f}")
print(f"pool net loss, % of the pool at closing: mean {loss.mean():.2%}"
      f"\n  (the projection says {expect:.2%})")
qs = [("median", 0.5), ("1 in 10", 0.9), ("1 in 100", 0.99),
      ("1 in 1,000", 0.999)]
print("  " + "; ".join(f"{a} {np.quantile(loss, q):.2%}"
                       for a, q in qs[:3]) + ";")
print(f"  {qs[3][0]} {np.quantile(loss, qs[3][1]):.2%}; "
      f"worst {loss.max():.2%}")

att = sec.attachment()
print(f"\n{'':<20}{'losses alone':>18}{'after the waterfall':>24}")
print(f"{'class':<6}{'attach':>7}{'detach':>7}{'P(loss)':>10}"
      f"{'EL':>8}{'P(loss)':>12}{'worst $':>12}")
for n in ("C", "B", "A"):
    a, d = att[n]
    alone = sec.tranche_loss(loss, a, d)
    print(f"{n:<6}{a:>7.0%}{d:>7.0%}{(alone > 0).mean():>10.2%}"
          f"{alone.mean():>8.2%}{(w['loss'][n] > 100).mean():>12.2%}"
          f"{w['loss'][n].max() / 100:>12,.0f}")
released = w["residual"].sum(-1) / total
low = np.quantile(released, 0.01)
print(f"\nreleased to class C over the deal: mean {released.mean():.2%}"
      f" of the pool,\n1 in 100 below {low:.2%}")

bins = np.arange(0, 0.0501, 0.001)
json.dump({"bins": bins.tolist(),
           "counts": np.histogram(loss, bins)[0].tolist(),
           "mean": float(loss.mean()),
           "q999": float(np.quantile(loss, 0.999)),
           "attach": {n: list(v) for n, v in att.items()}},
          open(ROOT / "code/28/06_monte_carlo.json", "w"))
