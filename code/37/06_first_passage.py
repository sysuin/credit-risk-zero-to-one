# Why companies default more often than their true one-year PD says.
import numpy as np
from scipy.stats import norm

from ballast.config import SEED

rng = np.random.default_rng(SEED)
N, MONTHS, dt = 200_000, 12, 1 / 12
sigma, beta = 0.25, 1.0                    # a typical company
mu = 0.035 + 0.5 * sigma ** 2              # quality q = 0
print("one company, 200,000 simulated years from the same start")
print(f"{'truth pd_1y':>12}{'ends below':>12}{'ever below':>12}"
      f"{'as generated':>14}")
for pd_1y in (0.005, 0.02, 0.05, 0.10):
    # the start that gives this pd_1y on the truth's own formula
    dd = -norm.ppf(pd_1y)
    log_v_dp = dd * sigma - (mu - 0.5 * sigma ** 2)
    z = rng.normal(0, 1, (N, MONTHS))
    step = (mu - 0.5 * sigma ** 2) * dt + sigma * np.sqrt(dt) * z
    path = log_v_dp + np.cumsum(step, axis=1)
    ends = (path[:, -1] < 0).mean()
    ever = (path < 0).any(axis=1).mean()
    # as corporate.py moves it: the economy-wide factor's share
    # (its own draw for each year) and its average month, and debt
    # that grows about 0.2% a month
    f = 0.6 * rng.normal(0, 1, (N, MONTHS)) - 0.08
    eps = (beta / 1.2 * 0.55 * f
           + np.sqrt(1 - 0.55 ** 2) * rng.normal(0, 1, (N, MONTHS)))
    debt = np.cumsum(0.002 + rng.normal(0, 0.004, (N, MONTHS)), axis=1)
    gen = log_v_dp + np.cumsum((mu - 0.5 * sigma ** 2) * dt
                               + sigma * np.sqrt(dt) * eps, axis=1)
    hit = ((gen - debt) < 0).any(axis=1).mean()
    print(f"{pd_1y:>12.1%}{ends:>12.2%}{ever:>12.2%}{hit:>14.2%}")
