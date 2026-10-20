# Exercise 31.1: the decomposition of 2023-2024 and 2024-2025 with
# unemployment taken three, six and nine months before the charge-off.
import fernhill
from _chargeoffs import (account_months, by_year, cells, components,
                         fit, long_run_u, unemployment)

con = fernhill.connect()
m = account_months(con)
lr = long_run_u(con)
print(f"{'$000':<10}{'lag':>4}{'book':>8}{'economy':>9}{'quality':>9}"
      f"{'chance':>8}{'u coef':>8}")
for lag in (3, 6, 9):
    c = cells(m, unemployment(con, lag))
    res = fit(c, lr)
    t = by_year(components(c, res.params, lr))
    for a, z in ((2023, 2024), (2024, 2025)):
        d = t.loc[z] - t.loc[a]
        print(f"{a}-{z % 100:<5}{lag:>4}{d.book / 1e3:>+8.0f}"
              f"{d.economy / 1e3:>+9.0f}{d.quality / 1e3:>+9.0f}"
              f"{d.chance / 1e3:>+8.0f}{res.params['u']:>8.3f}")
