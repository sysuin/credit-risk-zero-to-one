# Exercise 31.2: is today's lending different from the yardstick?
# The cohort since July 2022 split at January 2024, refitted.
import numpy as np

import _chargeoffs as co
import fernhill

co.COHORTS = co.COHORTS + [("since Jan 2024", "2024-01")]
con = fernhill.connect()
m = co.account_months(con)
lr = co.long_run_u(con)
c = co.cells(m, co.unemployment(con))
res = co.fit(c, lr)
b, se = res.params["since Jan 2024"], res.bse["since Jan 2024"]
print("loans booked since Jan 2024 against Jul 2022-Dec 2023:")
print(f"  rate x {np.exp(b):.2f} (90% {np.exp(b - 1.645 * se):.2f} to "
      f"{np.exp(b + 1.645 * se):.2f})")
t = co.by_year(co.components(c, res.params, lr))
print("chance in 2025 with the split: "
      f"{t.loc[2025, 'chance']:+,.0f} dollars")
