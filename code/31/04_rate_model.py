# A model of the charge-off rate: dollars charged off per dollar at
# risk, by age, by cohort, and by unemployment some months before.
import numpy as np

import fernhill
from _chargeoffs import (AGES, COHORTS, REF_AGE, REFERENCE,
                         account_months, cells, fit, long_run_u,
                         unemployment)
from ballast.parameters import pd as pdm

con = fernhill.connect()
m = account_months(con)
lr = long_run_u(con)

print("unemployment taken this many months before the charge-off")
LAGS = (0, 3, 6, 9, 12)
print(f"{'lag, months':<28}" + "".join(f"{k:>8}" for k in LAGS))
dev = [fit(cells(m, unemployment(con, k)), lr).deviance for k in LAGS]
print(f"{'deviance, $m (lower fits)':<28}"
      + "".join(f"{d / 1e6:>8.2f}" for d in dev))

res = fit(cells(m, unemployment(con, 6)), lr)
b, se = res.params, res.bse
print(f"\nlag 6: {int(res.nobs):,} cells, 2017-2025; "
      f"long-run unemployment {lr:.2f}%")
print(f"{'':<28}{'rate x':>8}{'90% interval':>16}")


def row(label, k):
    lo, hi = np.exp(b[k] - 1.645 * se[k]), np.exp(b[k] + 1.645 * se[k])
    print(f"{label:<28}{np.exp(b[k]):>8.2f}{lo:>9.2f} to {hi:.2f}")


for lo, hi in AGES:
    a = f"{lo}-{hi}" if hi < 999 else f"{lo}+"
    if a == REF_AGE:
        print(f"{'age ' + a + ' months':<28}{1:>8.2f}  (yardstick)")
    else:
        row(f"age {a} months", f"age {a}")
for name, _ in COHORTS:
    if name == REFERENCE:
        print(f"{'booked ' + name:<28}{1:>8.2f}  (yardstick)")
    else:
        row(f"booked {name}", name)
row("unemployment, a point", "u")
k18 = pdm.load_pd_model().params["u_ahead"]
print(f"{'Chapter 18, 12-month PD':<28}{np.exp(k18):>8.2f}")
print(f"dispersion {res.scale:,.0f}: the variance of a cell's dollars")
print("is that many times its expected dollars")
