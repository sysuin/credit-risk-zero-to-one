# timeout: 600
# Two hundred thousand years of Fernhill's whole book: the one-year
# loss distribution, its tail, and the economic capital it implies.
import json

import fernhill
import numpy as np
from ballast import capital, portfolio as pf
from ballast.config import ROOT

con = fernhill.connect()
est = pf.load_json("correlations.json")
fac = pf.load_json("factors.json")
pools, names = pf.book(con, capital.load())
model = pf.model_from(est, fac, "rho", "central")
res = pf.simulate(pools, names, model)        # seeded from SEED
m = 1e8                                       # cents to $m
print(f"{len(res.total):,} years drawn")
print(f"expected loss: simulated ${res.el() / m:,.1f}m, "
      f"by formula ${pf.expected_loss(pools, names) / m:,.1f}m")
print(f"standard deviation ${res.total.std() / m:,.1f}m, "
      f"median year ${np.median(res.total) / m:,.1f}m")
for q in (0.99, 0.995, 0.999):
    print(f"  VaR {q:.1%}  ${res.var(q) / m:>8,.1f}m   "
          f"ES ${res.es(q) / m:>8,.1f}m")
lo, hi = res.var_interval()
print(f"  the simulation's own noise: 99.9% VaR between "
      f"${lo / m:,.1f}m and ${hi / m:,.1f}m")
print(f"economic capital, 99.9% VaR less EL: ${res.ec() / m:,.1f}m")
print(f"worst year of {len(res.total):,}: "
      f"${res.total.max() / m:,.1f}m")

t = res.tail()
print(f"\n{'segment':<14}{'EL $m':>8}{'alone 99.9%':>13}"
      f"{'in the tail':>13}")
for s in res.by_segment.columns:
    x = res.by_segment[s].to_numpy()
    print(f"{s:<14}{x.mean() / m:>8.2f}"
          f"{np.quantile(x, 0.999) / m:>13.1f}{x[t].mean() / m:>13.1f}")
total_alone = sum(np.quantile(res.by_segment[s], 0.999)
                  for s in res.by_segment.columns)
print(f"{'sum':<14}{res.el() / m:>8.2f}{total_alone / m:>13.1f}"
      f"{res.es() / m:>13.1f}")

bins = np.arange(0, 1_801, 10)
json.dump({"bins": bins.tolist(),
           "counts": np.histogram(res.total / m, bins)[0].tolist(),
           "el": res.el() / m, "var": res.var() / m,
           "es": res.es() / m, "var99": res.var(0.99) / m,
           "n": len(res.total)},
          open(ROOT / "code/22/09_simulate.json", "w"))
