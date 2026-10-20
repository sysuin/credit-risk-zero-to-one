# Merton's risk-neutral PD against what happened: listed clients at
# each March review, grouped by distance to default, and the defaults
# in the year that followed.
import numpy as np
import pandas as pd
from scipy.stats import poisson

import fernhill
from _listed import listed_panel, next_year

con = fernhill.connect()
s = next_year(listed_panel(con))
march = s[[m.month == 3 for m in s.month]].copy()
march["band"] = pd.cut(march.dd, [-np.inf, 1, 2, 3, np.inf],
                       labels=["below 1", "1 to 2", "2 to 3",
                               "3 and up"])
print(f"{'DD':<10}{'company-years':>14}{'defaults':>10}"
      f"{'rate':>8}{'mean PD':>9}{'expected':>10}")
for band, x in march.groupby("band", observed=True):
    print(f"{band:<10}{len(x):>14}{x.y.sum():>10}{x.y.mean():>8.1%}"
          f"{x.pd.mean():>9.1%}{x.pd.sum():>10.2f}")
exp, obs = march.pd.sum(), march.y.sum()
print(f"{'all':<10}{len(march):>14}{obs:>10}{obs / len(march):>8.1%}"
      f"{exp / len(march):>9.1%}{exp:>10.2f}")
lo, hi = poisson.ppf(0.05, exp), poisson.ppf(0.95, exp)
print("\nif the PDs were right, 90% of runs of these company-years")
print(f"  would see between {lo:.0f} and {hi:.0f} defaults; there "
      f"were {obs}")
