# The one-factor model by formula and by simulation, with its noise.
import numpy as np

from ballast import portfolio as pf
from ballast.config import SEED

P, RHO, Q = 0.02, 0.10, 0.999
var = pf.vasicek_variance(P, RHO)
print(f"PD {P:.0%}, asset correlation {RHO:.2f}, q = {Q}")
print(f"default correlation {var / (P * (1 - P)):.4f}; "
      f"sd of the yearly rate {np.sqrt(var):.4f}")
worst = float(pf.vasicek_quantile(Q, P, RHO))
print(f"99.9% year by formula {worst:.4f}, "
      f"expected shortfall {pf.vasicek_es(Q, P, RHO):.4f}")

print(f"\n{'years':>9}{'mean':>8}{'+/- 2 se':>10}{'99.9%':>8}"
      f"{'ES':>8}{'q-band':>16}")
for n in (1_000, 10_000, 100_000, 1_000_000):
    rng = np.random.default_rng(SEED)
    x = np.sort(pf.conditional_pd(P, RHO, rng.standard_normal(n)))
    k = int(np.ceil(Q * n))                 # the VaR's order statistic
    half = 1.96 * np.sqrt(n * Q * (1 - Q))
    lo = x[max(int(k - half) - 1, 0)]
    hi = x[min(int(k + half) - 1, n - 1)]
    se = x.std() / np.sqrt(n)
    print(f"{n:>9,}{x.mean():>8.4f}{2 * se:>10.5f}{x[k - 1]:>8.4f}"
          f"{x[k - 1:].mean():>8.4f}{f'{lo:.4f}-{hi:.4f}':>16}")

# A finite book: 2,000 loans, so private luck adds to the economy's.
rng = np.random.default_rng(SEED)
z = rng.standard_normal(100_000)
rate = rng.binomial(2_000, pf.conditional_pd(P, RHO, z)) / 2_000
print(f"\n2,000 loans, 100,000 years: 99.9% year "
      f"{np.quantile(rate, Q):.4f}, sd {rate.std():.4f}")
