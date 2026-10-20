# Two arms with the same true bad rate, read every month: how often a
# test checked repeatedly declares a difference that is not there.
import numpy as np
from scipy.stats import norm

from ballast.config import SEED

rng = np.random.default_rng(SEED)
TESTS, MONTHS, PER_MONTH, BAD = 2000, 24, 144, 0.03
# Each month, each arm books PER_MONTH loans going bad at the same rate
# (outcomes treated as known at once, to isolate the peeking).
bads = rng.binomial(PER_MONTH, BAD, size=(TESTS, MONTHS, 2)).cumsum(1)
n = PER_MONTH * np.arange(1, MONTHS + 1)[None, :]
p1, p2 = bads[..., 0] / n, bads[..., 1] / n
pool = (bads[..., 0] + bads[..., 1]) / (2 * n)
z = (p1 - p2) / np.sqrt(pool * (1 - pool) * 2 / n)
alarm = np.abs(z) > norm.ppf(0.975)
print(f"{TESTS:,} tests, no real difference, {PER_MONTH} loans an arm"
      " a month")
print(f"  read once, at month {MONTHS}:"
      f"{alarm[:, -1].mean():>23.1%} declare a winner")
for k in (6, 12, 24):
    every = alarm[:, :k].any(axis=1).mean()
    print(f"  read every month, first {k:>2} months:"
          f"{every:>12.1%} declare a winner")
first = np.argmax(alarm, axis=1)[alarm.any(axis=1)] + 1
print(f"  of those, half had declared by month {int(np.median(first))}")
