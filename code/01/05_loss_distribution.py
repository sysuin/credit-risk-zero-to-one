# A thousand loans, a hundred thousand simulated years: the loss you
# expect, and the loss you have to survive.
import json

import numpy as np
from scipy.stats import norm

from ballast.config import ROOT, SEED

N_LOANS, PD, LGD, EAD = 1_000, 0.04, 0.80, 12_000
YEARS = 100_000
rng = np.random.default_rng(SEED)

expected = N_LOANS * PD * LGD * EAD
print(f"expected loss: {N_LOANS:,} x {PD:.0%} x {LGD:.0%} x "
      f"${EAD:,} = ${expected:,.0f}")

# Independent borrowers: each year, each loan defaults or not on
# its own coin.
independent = rng.binomial(N_LOANS, PD, YEARS) * LGD * EAD

# Borrowers who share an economy: in a bad year everyone's chance
# of default rises together. One common factor per year moves the
# default rate; on average it is still 4%.
RHO = 0.10
economy = rng.standard_normal(YEARS)
pd_this_year = norm.cdf((norm.ppf(PD) - np.sqrt(RHO) * economy)
                        / np.sqrt(1 - RHO))
shared = rng.binomial(N_LOANS, pd_this_year) * LGD * EAD

print()
print(f"{'':<22}{'independent':>14}{'shared economy':>17}")
print(f"{'average year':<22}{independent.mean():>14,.0f}"
      f"{shared.mean():>17,.0f}")

# A quantile is the loss that only a given share of years beat:
# 0.99 is the loss exceeded one year in a hundred.
for label, q in [("median year", 0.5), ("1 year in 100", 0.99),
                 ("1 year in 1,000", 0.999)]:
    a = np.quantile(independent, q)
    b = np.quantile(shared, q)
    print(f"{label:<22}{a:>14,.0f}{b:>17,.0f}")

# The figure is drawn from these counts, not from numbers typed by hand.
bins = np.arange(0, 3_000_001, 50_000)
json.dump({"bins": bins.tolist(),
           "independent": np.histogram(independent, bins)[0].tolist(),
           "shared": np.histogram(shared, bins)[0].tolist(),
           "expected": expected,
           "q999_shared": float(np.quantile(shared, 0.999))},
          open(ROOT / "code/01/05_loss_distribution.json", "w"))
