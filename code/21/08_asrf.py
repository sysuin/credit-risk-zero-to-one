# The one-factor model behind the IRB formula: simulate many years of
# a large book's default rate, and compare its 1-in-1,000 year with
# the formula's.
import json

import numpy as np
from ballast import capital
from ballast.config import SEED
from scipy.stats import norm

PD, RHO, LGD, YEARS = 0.02, 0.15, 0.45, 1_000_000
rng = np.random.default_rng(SEED)
z = rng.standard_normal(YEARS)                 # the economy each year
# A very large book: the year's default rate is the conditional PD.
rate = norm.cdf((norm.ppf(PD) - np.sqrt(RHO) * z) / np.sqrt(1 - RHO))
print(f"PD {PD:.0%}, correlation {RHO}, {YEARS:,} simulated years")
print(f"average default rate      {rate.mean():.2%}")
print(f"median year               {np.median(rate):.2%}")
for q in (0.99, 0.999):
    name = f"1-in-{1 / (1 - q):,.0f} year"
    print(f"{name:<26}{np.quantile(rate, q):.2%}")
bad = norm.cdf((norm.ppf(PD) + np.sqrt(RHO) * norm.ppf(0.999))
               / np.sqrt(1 - RHO))
print(f"formula, 1-in-1,000 year  {bad:.2%} (confidence 99.9%)")
k = LGD * (bad - PD)
print(f"\nwith LGD {LGD:.0%}: expected loss {PD * LGD:.2%} of EAD, "
      f"loss in that year {LGD * bad:.2%}")
print(f"capital K = {k:.2%} of EAD; risk weight 12.5 x K = "
      f"{12.5 * k:.1%}")
print(f"capital_k(): {capital.capital_k(PD, LGD, 'mortgage'):.2%}")
hist, edges = np.histogram(rate, bins=100, range=(0, 0.20))
with open("code/21/08_asrf.json", "w") as f:
    json.dump({"pd": PD, "lgd": LGD, "edges": edges.tolist(),
               "share": (hist / YEARS).tolist(), "q999": bad}, f)
