# timeout: 300
# How much can nine years say? Simulate 2,000 decades like Fernhill's
# at a known correlation, estimate it from each, and see the spread.
import fernhill
import numpy as np
from ballast import portfolio as pf
from ballast.config import SEED

con = fernhill.connect()
h = pf.default_history(con)
est = pf.load_json("correlations.json")
rng = np.random.default_rng(SEED)
print(f"{'segment':<10}{'true':>7}{'median':>8}{'90% of estimates':>18}"
      f"{'as low':>8}")
for seg in ("personal", "companies"):
    g, e = h[h.segment == seg], est[seg]
    n, p = g.at_risk.to_numpy(), g.rate.mean()
    for true in (e["rho"], e["rules"]):
        z = rng.standard_normal((2_000, len(n)))
        d = rng.binomial(n, pf.conditional_pd(p, true, z))
        found = np.array([pf.mom_rho(x / n, n) for x in d])
        lo, mid, hi = np.quantile(found, [0.05, 0.5, 0.95])
        print(f"{seg:<10}{true:>7.3f}{mid:>8.3f}{lo:>9.3f} to "
              f"{hi:.3f}{(found <= e['mom']).mean():>8.1%}")
    print(f"{'':<10}Fernhill's own, by moments: {e['mom']:.3f}")
