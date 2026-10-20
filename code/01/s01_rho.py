# Exercises 1.2 and 1.3: the one-year-in-a-thousand loss as the loss
# given default and the shared share of borrowers' fortunes change.
import numpy as np
from scipy.stats import norm

from ballast.config import SEED

N_LOANS, PD, EAD, YEARS = 1_000, 0.04, 12_000, 100_000


def losses(lgd, rho, rng):
    economy = rng.standard_normal(YEARS)
    p = norm.cdf((norm.ppf(PD) - np.sqrt(rho) * economy)
                 / np.sqrt(1 - rho))
    return rng.binomial(N_LOANS, p) * lgd * EAD


print(f"{'LGD':>5}{'RHO':>6}{'expected':>11}{'1 in 1,000':>12}"
      f"{'ratio':>7}")
for lgd, rho in [(0.80, 0.10), (0.30, 0.10), (0.80, 0.02),
                 (0.80, 0.25)]:
    x = losses(lgd, rho, np.random.default_rng(SEED))
    q = np.quantile(x, 0.999)
    el = N_LOANS * PD * lgd * EAD
    print(f"{lgd:>5.2f}{rho:>6.2f}{el:>11,.0f}{q:>12,.0f}"
          f"{q / el:>7.1f}")
