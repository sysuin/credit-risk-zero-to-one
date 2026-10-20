# Merton's model for every listed client at every month end: how many
# estimates, and how far from default Fernhill's listed clients stood
# at each year end.
import numpy as np

import fernhill
from ballast import market as mk

con = fernhill.connect()
p = mk.merton_panel(con)
print(f"estimates: {len(p):,} company-months, "
      f"{p.company_id.nunique()} companies, "
      f"{p.month.min():%b %Y} to {p.month.max():%b %Y}")
print(f"  solver converged: {p.converged.sum():,}")
print(f"  median equity vol {p.sigma_e.median():.1%}, "
      f"asset vol {p.sigma_a.median():.1%}")

print(f"\n{'month end':<11}{'firms':>6}{'median DD':>11}{'p10 DD':>8}"
      f"{'DD < 1':>8}{'DD < 2':>8}")
months = sorted(m for m in p.month.unique() if m.month == 12)
months.insert(3, next(m for m in p.month.unique()
                      if m.year == 2020 and m.month == 3))
for m in months:
    x = p[p.month == m].dd
    print(f"{m:%b %Y}{len(x):>9}{x.median():>11.2f}"
          f"{np.percentile(x, 10):>8.2f}{(x < 1).mean():>8.0%}"
          f"{(x < 2).mean():>8.0%}")
