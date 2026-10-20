# Chapter 1's thousand loans again: the simulated bad years, the same
# years by Vasicek's formula, and what the size of the pool changes.
import numpy as np
from ballast import portfolio as pf
from ballast.config import SEED

N_LOANS, PD, LGD, EAD, RHO = 1_000, 0.04, 0.80, 12_000, 0.10
YEARS = 100_000
rng = np.random.default_rng(SEED)
rng.binomial(N_LOANS, PD, YEARS)          # Chapter 1's first column
economy = rng.standard_normal(YEARS)
p_year = pf.conditional_pd(PD, RHO, economy)
shared = rng.binomial(N_LOANS, p_year) * LGD * EAD

print(f"{'':<17}{'Chapter 1':>11}{'formula':>11}")
for label, q in [("1 year in 100", 0.99), ("1 year in 1,000", 0.999)]:
    formula = pf.vasicek_quantile(q, PD, RHO) * N_LOANS * LGD * EAD
    print(f"{label:<17}{np.quantile(shared, q):>11,.0f}"
          f"{formula:>11,.0f}")

# The same economies, pools of other sizes: the default rate in the
# one-in-a-thousand year, against the infinite pool of the formula.
print(f"\n{'loans':>10}{'99.9% default rate':>21}{'above formula':>15}")
limit = pf.vasicek_quantile(0.999, PD, RHO)
for n in (100, 1_000, 10_000, 100_000):
    rate = rng.binomial(n, p_year) / n
    q = np.quantile(rate, 0.999)
    print(f"{n:>10,}{q:>21.2%}{q / limit - 1:>+15.1%}")
print(f"{'infinite':>10}{limit:>21.2%}")
